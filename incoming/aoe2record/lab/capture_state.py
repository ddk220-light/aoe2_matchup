"""Resilient FULL capture of the CadeRemote frame stream to disk.

Saves length-delimited FrameSequence protobufs (state patches + commands +
events) to frames_raw.bin. Auto-reconnects so it survives the replay being
stopped/restarted -- so you can replay from the start at fast speed and it grabs
the whole game. Analyze offline afterwards (decode entity state over time).

Records start `INFO\n<gameVersion>\n` markers and, each (re)connection, the
first full-state patch separately (first_patch_seg<N>.bin).
"""
import struct
import sys
import time

import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 3600.0   # 60 min wall cap
SIZE_CAP = 4000 * 1024 * 1024                                # full-vision => bigger
OUTFILE = "GAME_fogoff_raw.bin"


def chan():
    ca = open("certificate-authority.pem", "rb").read()
    cert = open("cade-client.pem", "rb").read()
    key = open("cade-client.key", "rb").read()
    creds = grpc.ssl_channel_credentials(ca, key, cert)
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
                               options=[("grpc.ssl_target_name_override", "ca-game-api"),
                                        ("grpc.max_receive_message_length", 512 * 1024 * 1024)])


def main():
    out = open(OUTFILE, "wb")
    written = total_frames = total_seqs = 0
    seg = 0
    t0 = time.time()
    last_wait = 0.0
    print(f"FULL capture armed (FOG OFF): up to {DUR:.0f}s / {SIZE_CAP//1024//1024}MB -> {OUTFILE}. "
          f"Waiting for the replay on :4341 ... (start your replay now)", flush=True)

    while time.time() - t0 < DUR and written < SIZE_CAP:
        try:
            ch = chan()
            grpc.channel_ready_future(ch).result(timeout=5)
            stub = pbg.CadeRemoteStub(ch)
            info = stub.Info(pb.InfoRequest(), timeout=5)
            seg += 1
            saved_first = False
            print(f"[seg {seg}] connected gameVersion={info.gameVersion} at "
                  f"{time.time()-t0:.0f}s", flush=True)
            # CRITICAL: disable fog so BOTH players' units appear as real entities
            # (not fog-shadow DoppleEntities). Without this the capture is limited to
            # the default perspective's vision and the enemy's units are undercounted.
            try:
                stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5)
                # CRITICAL: perspective 0 = ALL-PLAYER / observer view. The entity
                # stream is perspective-bound (default p1), so without this only
                # player 1's units stream in full. 0 gives every player's entities.
                stub.SetPerspective(pb.SetPerspectiveRequest(playerId=0), timeout=5)
                print(f"[seg {seg}] fog OFF + perspective=ALL (both players' entities)", flush=True)
            except Exception as e:  # noqa
                print(f"[seg {seg}] SetFogOfWar/SetPerspective failed: {e}", flush=True)
            last_time = None
            for sq in stub.Frames(pb.FramesRequest(disableParticles=True, disableParticleCulling=True),
                                  timeout=DUR + 10):
                b = sq.SerializeToString()
                out.write(struct.pack("<I", len(b)))
                out.write(b)
                written += 4 + len(b)
                total_seqs += 1
                for fr in sq.frame:
                    total_frames += 1
                    last_time = fr.time
                    if not saved_first and fr.patch:
                        with open(f"first_patch_seg{seg}.bin", "wb") as fp:
                            fp.write(fr.patch)
                        saved_first = True
                        print(f"[seg {seg}] first patch {len(fr.patch)} bytes, gametime={fr.time}ms",
                              flush=True)
                if total_seqs % 500 == 0:
                    out.flush()
                    print(f"  {total_seqs} seqs / {total_frames} frames / gametime={last_time}ms / "
                          f"{written//1024//1024}MB", flush=True)
                if time.time() - t0 > DUR or written > SIZE_CAP:
                    break
        except (grpc.FutureTimeoutError, grpc.RpcError):
            now = time.time()
            if now - last_wait > 15:
                print(f"  ...waiting for the game/replay on :4341 ({now-t0:.0f}s elapsed)", flush=True)
                last_wait = now
            time.sleep(2.0)
        except Exception as e:  # noqa
            print("err:", type(e).__name__, repr(e)[:160], flush=True)
            time.sleep(2.0)

    out.close()
    print(f"\nDONE. segments={seg} seqs={total_seqs} frames={total_frames} "
          f"file=frames_raw.bin {written//1024//1024}MB", flush=True)


if __name__ == "__main__":
    main()
