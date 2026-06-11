"""ARMED gRPC ground-truth capture -- catch the FULL details of every new game.

Runs forever, waiting on the CadeRemote engine (:4341). The moment a game/replay
streams frames it captures the complete FrameSequence stream (state patches +
commands + events) with FOG OFF and perspective = ALL players, so every player's
real entities are recorded (not fog shadows / undercounted enemy units).

Each distinct game is written to its OWN timestamped file -- a new file is rolled
whenever the engine's gametime resets toward 0 (a new game or a replay restarted
from the beginning). A sidecar .json manifest per game records gameVersion, frame
counts, gametime span and size. Survives the replay being stopped / restarted /
reconnected (auto-reconnect).

Usage:
  python arm_capture.py                 # arm forever (leave it running)
  python arm_capture.py 7200            # arm with a 2-hour wall cap
Output: C:/dev/aoe2/aoe2record/lab/captures/capture_<YYYYmmdd-HHMMSS>.bin (+ .json)
"""
import json
import os
import socket
import struct
import sys
import time

import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg

# Single-instance guard: bind a fixed local port as a cross-process mutex. If another
# arm_capture is already recording, this process exits immediately -- so multiple
# accidental launches can NEVER compete for the engine's single Frames stream (the
# bug that silently broke capture). The holder keeps _LOCK alive for its lifetime.
_LOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _LOCK.bind(("127.0.0.1", 48417))
    _LOCK.listen(1)
except OSError:
    print("arm_capture: another instance already holds the recorder lock; exiting.", flush=True)
    sys.exit(0)

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 1e12      # run forever by default
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
SIZE_CAP = 4000 * 1024 * 1024                                # per-game cap
RESET_BACK_MS = 30_000                                       # gametime jump back => new game
PER_GAME_IDLE_ROLL = 90                                      # s disconnected => next stream is a new game


def chan():
    ca = open("certificate-authority.pem", "rb").read()
    cert = open("cade-client.pem", "rb").read()
    key = open("cade-client.key", "rb").read()
    creds = grpc.ssl_channel_credentials(ca, key, cert)
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
                               options=[("grpc.ssl_target_name_override", "ca-game-api"),
                                        ("grpc.max_receive_message_length", 512 * 1024 * 1024)])


class Game:
    """One captured game = one output file + manifest."""
    def __init__(self, game_version):
        os.makedirs(OUT_DIR, exist_ok=True)
        self.stamp = time.strftime("%Y%m%d-%H%M%S")
        self.path = os.path.join(OUT_DIR, f"capture_{self.stamp}.bin")
        self.out = open(self.path, "wb")
        self.game_version = game_version
        self.bytes = self.seqs = self.frames = 0
        self.first_gt = None
        self.last_gt = None
        self.t0 = time.time()
        print(f"\n=== NEW GAME -> {os.path.basename(self.path)} (gameVersion={game_version}) ===", flush=True)

    def write(self, sq):
        b = sq.SerializeToString()
        self.out.write(struct.pack("<I", len(b)))
        self.out.write(b)
        self.bytes += 4 + len(b)
        self.seqs += 1
        for fr in sq.frame:
            self.frames += 1
            if fr.time:
                if self.first_gt is None:
                    self.first_gt = fr.time
                self.last_gt = fr.time

    def close(self):
        try:
            self.out.flush()
            self.out.close()
        except Exception:
            pass
        man = {
            "file": os.path.basename(self.path),
            "captured_at": self.stamp,
            "game_version": self.game_version,
            "seqs": self.seqs, "frames": self.frames,
            "first_gametime_ms": self.first_gt, "last_gametime_ms": self.last_gt,
            "minutes": round((self.last_gt or 0) / 60000.0, 1),
            "size_mb": round(self.bytes / 1024 / 1024, 1),
        }
        json.dump(man, open(self.path[:-4] + ".json", "w"), indent=2)
        print(f"=== GAME DONE: {man['file']}  {man['frames']} frames  "
              f"{man['minutes']}min  {man['size_mb']}MB ===", flush=True)


def configure(stub, seg):
    """Fog OFF + perspective ALL -- the two settings that make the capture complete."""
    try:
        stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5)
        stub.SetPerspective(pb.SetPerspectiveRequest(playerId=0), timeout=5)
        print(f"[conn {seg}] fog OFF + perspective=ALL", flush=True)
    except Exception as e:  # noqa
        print(f"[conn {seg}] SetFogOfWar/SetPerspective failed: {e}", flush=True)


def main():
    print(f"gRPC capture ARMED (fog off, all players). Forever={DUR>=1e12}. "
          f"Output dir: {OUT_DIR}\nWaiting for a game/replay on :4341 ...", flush=True)
    t_start = time.time()
    game = None
    seg = 0
    last_frame_wall = 0.0
    last_wait_log = 0.0

    while time.time() - t_start < DUR:
        try:
            ch = chan()
            grpc.channel_ready_future(ch).result(timeout=5)
            stub = pbg.CadeRemoteStub(ch)
            info = stub.Info(pb.InfoRequest(), timeout=5)
            seg += 1
            print(f"[conn {seg}] connected gameVersion={info.gameVersion}", flush=True)
            configure(stub, seg)

            # if we were disconnected a long time, the next stream is a new game
            if game is not None and time.time() - last_frame_wall > PER_GAME_IDLE_ROLL:
                game.close()
                game = None

            # NO deadline on the stream: a huge finite timeout (DUR=forever=1e12)
            # overflows the gRPC deadline and makes Frames fail instantly -- which
            # silently broke capture. None = stream until the game/connection ends.
            for sq in stub.Frames(pb.FramesRequest(disableParticles=True,
                                                   disableParticleCulling=True), timeout=None):
                # detect game boundary by gametime reset toward 0
                gt = next((fr.time for fr in sq.frame if fr.time), None)
                if game is not None and gt is not None and game.last_gt is not None \
                        and gt + RESET_BACK_MS < game.last_gt:
                    game.close()
                    game = None
                if game is None:
                    game = Game(info.gameVersion)
                game.write(sq)
                last_frame_wall = time.time()
                if game.seqs % 500 == 0:
                    game.out.flush()
                    print(f"  {game.seqs} seqs / {game.frames} frames / "
                          f"gametime={game.last_gt}ms / {game.bytes//1024//1024}MB", flush=True)
                if game.bytes > SIZE_CAP:
                    print("  per-game size cap hit, rolling.", flush=True)
                    game.close()
                    game = None
        except (grpc.FutureTimeoutError, grpc.RpcError):
            now = time.time()
            if now - last_wait_log > 20:
                print(f"  ...armed, waiting for a game on :4341 ({now-t_start:.0f}s)", flush=True)
                last_wait_log = now
            time.sleep(2.0)
        except KeyboardInterrupt:
            break
        except Exception as e:  # noqa
            print("err:", type(e).__name__, repr(e)[:160], flush=True)
            time.sleep(2.0)

    if game is not None:
        game.close()
    print("capture disarmed.", flush=True)


if __name__ == "__main__":
    main()
