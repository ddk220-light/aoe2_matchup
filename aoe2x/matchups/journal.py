"""Crash-safe record files for matchup runs: JSONL journals, atomic JSON, the runner lock.

Same write discipline as the 2026 runners (``append()``/``json()`` in RB
``aoe2x/js_simulation/node/civ-matchups/forecast-validation-lib.mjs``; RB =
``origin/simulations/civ-forecast-recovery-2026-11-10``):

* a journal line is appended and ``fsync``ed before any state that depends on
  it is written;
* ``state.json`` and other derived files are written to a temp file, fsynced
  and renamed over the old one;
* the runner lock holds the owner's PID (as ``.runner.lock`` did); a lock whose
  process is gone is stale. Additions: the lock also records the process start
  time (``/proc/<pid>/stat`` field 22) so a recycled PID is not mistaken for a
  live runner, and a torn trailing journal line (a kill in the middle of a
  write) is repaired instead of aborting the resume.
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path


class IntegrityError(RuntimeError):
    """A record file is inconsistent in a way that must not be repaired automatically."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_json_atomic(path: Path, value, *, indent: int | None = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json.dumps(value, indent=indent) + "\n").encode()
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def read_json(path: Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


# --------------------------------------------------------------------- journal

def repair_journal(path: Path) -> dict:
    """Drop a torn trailing line (no newline, or unparsable last line). Returns a repair report.

    A line in the middle that does not parse is never repaired: that is an
    integrity error (the file was edited or the disk is corrupt).
    """
    path = Path(path)
    if not path.exists():
        return {"repaired": False, "lines": 0}
    data = path.read_bytes()
    if not data:
        return {"repaired": False, "lines": 0}
    cut = len(data)
    reason = None
    if not data.endswith(b"\n"):
        cut = data.rfind(b"\n") + 1  # 0 when the only line is torn
        reason = "torn trailing line (no newline)"
    else:
        start = data.rfind(b"\n", 0, len(data) - 1) + 1
        last = data[start:len(data) - 1]
        try:
            json.loads(last)
        except ValueError:
            cut = start
            reason = "unparsable trailing line"
    report = {"repaired": False, "lines": data[:cut].count(b"\n")}
    if reason:
        with open(path, "r+b") as f:
            f.truncate(cut)
            f.flush()
            os.fsync(f.fileno())
        report.update(repaired=True, reason=reason, droppedBytes=len(data) - cut,
                      dropped=data[cut:].decode("utf-8", "replace")[:200])
    return report


def read_journal(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with open(path, "rb") as f:
        for number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as error:
                raise IntegrityError(f"{path}:{number}: unparsable journal line ({error}); "
                                     "only a torn trailing line is repaired automatically") from error
    return rows


class Journal:
    """Append-only JSONL file; every append is flushed and fsynced before it returns."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "ab")

    def append(self, row: dict) -> None:
        self._f.write((json.dumps(row, separators=(",", ":")) + "\n").encode())
        self._f.flush()
        os.fsync(self._f.fileno())

    def close(self) -> None:
        self._f.close()


# ------------------------------------------------------------------------ lock

def process_start_time(pid: int) -> str | None:
    """Kernel start time of a process (clock ticks since boot), or None if it is not running."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # comm (field 2) may contain spaces; fields after the closing parenthesis are fixed.
    fields = text[text.rindex(")") + 2:].split()
    if fields[0] == "Z":  # zombie: dead, not yet reaped
        return None
    return fields[19]


def pid_alive(pid: int, start_time: str | None = None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    started = process_start_time(pid)
    if started is None:
        # No /proc (not Linux): fall back to the signal check alone.
        return not Path("/proc").is_dir()
    return start_time is None or started == start_time


class LockBusy(RuntimeError):
    def __init__(self, path: Path, owner: dict):
        super().__init__(f"{path} is held by live process {owner.get('pid')} (started {owner.get('startedAt')}, "
                         f"host {owner.get('host')}); stop it first")
        self.owner = owner


class RunnerLock:
    """``<records>/.runner.lock``: at most one runner per records directory."""

    def __init__(self, path: Path, info: dict | None = None):
        self.path = Path(path)
        self.info = info or {}
        self.held = False
        self.cleared = None

    def read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return None
        except ValueError:
            return {"pid": None, "unreadable": True}

    def owner_alive(self, owner: dict | None) -> bool:
        if not owner:
            return False
        if owner.get("host") not in (None, socket.gethostname()):
            # Another machine sharing the directory: never treat it as stale automatically.
            return True
        return pid_alive(owner.get("pid"), owner.get("startTime"))

    def acquire(self) -> "RunnerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            body = {"pid": os.getpid(), "startTime": process_start_time(os.getpid()), "host": socket.gethostname(),
                    "startedAt": now(), **self.info}
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            except FileExistsError:
                owner = self.read()
                if self.owner_alive(owner):
                    raise LockBusy(self.path, owner)
                # Stale: the owner is dead (or its PID was recycled). Clear it, as the 2026 runners did.
                self.cleared = owner
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(body) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self.held = True
            return self
        raise LockBusy(self.path, self.read() or {})

    def release(self) -> None:
        if not self.held:
            return
        owner = self.read()
        if owner and owner.get("pid") == os.getpid():
            self.path.unlink(missing_ok=True)
        self.held = False

    def clear_stale(self) -> dict:
        """Remove the lock if its owner is dead; refuse while it is alive."""
        owner = self.read()
        if owner is None:
            return {"cleared": False, "reason": "no lock"}
        if self.owner_alive(owner):
            raise LockBusy(self.path, owner)
        self.path.unlink(missing_ok=True)
        return {"cleared": True, "owner": owner}

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
