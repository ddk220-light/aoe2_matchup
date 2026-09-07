"""Start the artifact viewer and optionally publish it through Tailscale Serve."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request

from .config import LabConfig
from .errors import PublicationError
from .io import utc_now, write_json


def _command(config: LabConfig, host: str, port: int) -> list[str]:
    return [
        config.node,
        str(config.project_root / "aoe2x/js_simulation/server.mjs"),
        "--host", host,
        "--port", str(port),
        "--lab-root", str(config.artifacts_root),
    ]


def _probe_host(host: str) -> str:
    return "127.0.0.1" if host in ("0.0.0.0", "::") else host


def _assert_port_available(host: str, port: int) -> None:
    if port < 1:
        raise PublicationError("viewer port must be between 1 and 65535")
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            if os.name == "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind((host, port))
    except OSError as error:
        raise PublicationError(
            f"viewer port {host}:{port} is unavailable: {error}",
            hint="stop the prior viewer or choose --port with a free port",
        ) from error


def _viewer_url(base_url: str, catalogue: dict) -> str:
    if catalogue.get("jobs"):
        selected_job = catalogue["jobs"][0]
        selected_seed = selected_job.get("viewerSeed", selected_job["seeds"][0])
        return f"{base_url}?mode=lab&job={selected_job['jobId']}&seed={selected_seed}"
    return base_url


def _wait_ready(
    host: str,
    port: int,
    *,
    process: subprocess.Popen | None = None,
    timeout: float = 20.0,
) -> dict:
    deadline = time.time() + timeout
    base = f"http://{_probe_host(host)}:{port}/"
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            raise PublicationError(
                f"viewer process exited with code {process.returncode} before readiness",
                hint="inspect the viewer server log; another process may already own the port",
            )
        try:
            with urllib.request.urlopen(base, timeout=2) as page:
                if page.status != 200 or b"Battle Simulation" not in page.read():
                    raise OSError("viewer shell did not match")
            with urllib.request.urlopen(f"{base}api/lab/jobs", timeout=2) as response:
                if response.status == 200:
                    return json.loads(response.read())
        except OSError:
            pass
        time.sleep(0.25)
    raise PublicationError(f"viewer did not become ready at {base}")


def _tailnet_url(config: LabConfig) -> str:
    completed = subprocess.run(
        [config.tailscale, "status", "--json"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise PublicationError(
            f"could not read Tailscale status: {(completed.stderr or completed.stdout).strip()}",
            hint="run the command from a terminal allowed to access the Tailscale service",
        )
    value = json.loads(completed.stdout)
    dns = value.get("Self", {}).get("DNSName", "").rstrip(".")
    if not dns:
        raise PublicationError("Tailscale status did not provide this device's DNS name")
    return f"https://{dns}{config.viewer_route}/"


def publish_tailnet(config: LabConfig, *, host: str, port: int) -> str:
    target = f"http://{host}:{port}"
    command = [
        config.tailscale,
        "serve",
        "--bg",
        "--yes",
        "--https=443",
        f"--set-path={config.viewer_route}",
        target,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise PublicationError(
            f"Tailscale Serve failed: {(completed.stderr or completed.stdout).strip()}",
            hint="verify Tailscale is running and this terminal may update Serve configuration",
        )
    url = _tailnet_url(config)
    jobs_url = f"{url}api/lab/jobs"
    try:
        with urllib.request.urlopen(jobs_url, timeout=15) as response:
            if response.status != 200:
                raise PublicationError(f"Tailnet verification returned HTTP {response.status}")
            catalogue = json.loads(response.read())
        with urllib.request.urlopen(url, timeout=15) as response:
            if response.status != 200 or b"Battle Simulation" not in response.read():
                raise PublicationError("Tailnet viewer shell verification failed")
        if catalogue.get("jobs"):
            job = catalogue["jobs"][0]
            seed = job.get("viewerSeed", job["seeds"][0])
            artifact_url = f"{url}api/lab/result?job={job['jobId']}&seed={seed}"
            with urllib.request.urlopen(artifact_url, timeout=30) as response:
                playback = json.loads(response.read())
                if playback.get("mode") != "aoe2-lab":
                    raise PublicationError("Tailnet playback provenance verification failed")
    except (OSError, ValueError) as error:
        raise PublicationError(f"Tailnet route was configured but verification failed: {error}") from error
    if catalogue.get("jobs"):
        job = catalogue["jobs"][0]
        seed = job.get("viewerSeed", job["seeds"][0])
        return f"{url}?mode=lab&job={job['jobId']}&seed={seed}"
    return url


def serve(
    config: LabConfig,
    *,
    foreground: bool,
    tailnet: bool,
    host: str | None = None,
    port: int | None = None,
) -> dict:
    selected_host = host or config.viewer_host
    selected_port = config.viewer_port if port is None else port
    command = _command(config, selected_host, selected_port)
    if foreground:
        if tailnet:
            raise PublicationError("--tailnet requires background viewer mode")
        _assert_port_available(selected_host, selected_port)
        return {"foreground": True, "command": command}
    runtime = config.artifacts_root / "viewer"
    runtime.mkdir(parents=True, exist_ok=True)
    log_path = runtime / "server.log"
    local_base_url = f"http://{_probe_host(selected_host)}:{selected_port}/"
    try:
        _assert_port_available(selected_host, selected_port)
    except PublicationError as collision:
        try:
            catalogue = _wait_ready(selected_host, selected_port, timeout=2.0)
        except Exception:
            raise collision
        tailnet_url = (
            publish_tailnet(config, host=selected_host, port=selected_port)
            if tailnet else None
        )
        state = {
            "schemaVersion": 1,
            "startedAt": utc_now(),
            "pid": None,
            "reused": True,
            "localBaseUrl": local_base_url,
            "localUrl": _viewer_url(local_base_url, catalogue),
            "tailnetUrl": tailnet_url,
            "route": config.viewer_route,
            "jobCount": len(catalogue.get("jobs", [])),
            "log": str(log_path),
        }
        write_json(runtime / "state.json", state)
        return state
    log = log_path.open("a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=config.project_root,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    log.close()
    try:
        catalogue = _wait_ready(selected_host, selected_port, process=process)
        if process.poll() is not None:
            raise PublicationError(
                f"viewer process exited with code {process.returncode} after readiness probe"
            )
    except Exception:
        if process.poll() is None:
            process.terminate()
        raise
    local_url = _viewer_url(local_base_url, catalogue)
    tailnet_url = publish_tailnet(config, host=selected_host, port=selected_port) if tailnet else None
    state = {
        "schemaVersion": 1,
        "startedAt": utc_now(),
        "pid": process.pid,
        "reused": False,
        "localBaseUrl": local_base_url,
        "localUrl": local_url,
        "tailnetUrl": tailnet_url,
        "route": config.viewer_route,
        "jobCount": len(catalogue.get("jobs", [])),
        "log": str(log_path),
    }
    write_json(runtime / "state.json", state)
    return state
