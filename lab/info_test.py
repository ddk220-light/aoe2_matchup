"""Connectivity test for AoE2:DE's CadeRemote gRPC endpoint.

Run AoE2:DE, load a replay, then run this. It does an mTLS Info() call to
[::1]:4341 using CaptureAge's client cert. Success proves we can read the
game-state stream directly (no CaptureAge app needed).
"""
import socket
import sys

import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg

HOST = "::1"
PORT = 4341
TARGET = f"ipv6:[{HOST}]:{PORT}"


def port_open():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((HOST, PORT))
        s.close()
        return True
    except OSError:
        # try IPv4 loopback too, in case the endpoint binds there
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=2)
            s.close()
            return "ipv4"
        except OSError:
            return False


def main():
    op = port_open()
    if not op:
        print(f"[x] Nothing listening on {PORT} (IPv6 or IPv4 loopback).")
        print("    -> Launch AoE2:DE and load/play a replay first. If it's playing and")
        print("       this still fails, the CA:DE remote endpoint may need CaptureAge")
        print("       running (or a launch flag) to be enabled. Re-run then.")
        return 1
    print(f"[ok] Port {PORT} is listening ({op}). Attempting mTLS gRPC Info()...")

    ca = open("certificate-authority.pem", "rb").read()
    cert = open("cade-client.pem", "rb").read()
    key = open("cade-client.key", "rb").read()
    creds = grpc.ssl_channel_credentials(root_certificates=ca, private_key=key, certificate_chain=cert)

    target = "ipv4:127.0.0.1:%d" % PORT if op == "ipv4" else TARGET
    # the server cert (aoe.pem) CN is 'ca-game-api'; override the name we verify
    options = [("grpc.ssl_target_name_override", "ca-game-api")]
    try:
        channel = grpc.secure_channel(target, creds, options=options)
        grpc.channel_ready_future(channel).result(timeout=6)
        stub = pbg.CadeRemoteStub(channel)
        resp = stub.Info(pb.InfoRequest(), timeout=6)
        print("\n[SUCCESS] CadeRemote.Info() responded:")
        print(f"   gameVersion : {resp.gameVersion}")
        print(f"   apiVersion  : {resp.apiVersion}")
        print(f"   baseDir     : {resp.baseDirectory}")
        print(f"   mods        : {list(resp.enabledModDirectories)}")
        print("\n--> We can read the live game-state stream. Next: stream Frames().")
        return 0
    except grpc.FutureTimeoutError:
        print("[x] TLS/HTTP2 handshake timed out — endpoint is up but rejected the")
        print("    connection (likely cert mismatch: CaptureAge may have rotated certs,")
        print("    or the override name is wrong). We'd need current certs.")
        return 2
    except grpc.RpcError as e:
        print(f"[x] gRPC error: {e.code()} - {e.details()}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
