"""Minimal live probe of the AoE2:DE CadeRemote gRPC API (non-intrusive).
Calls Info(), then briefly reads Frames() to see if state streams in the current mode."""
import sys, time
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg

D = r"C:\dev\aoe2\aoe2record\lab"
def rd(n): return open(D + "\\" + n, "rb").read()

creds = grpc.ssl_channel_credentials(rd("certificate-authority.pem"),
                                     rd("cade-client.key"), rd("cade-client.pem"))
ch = grpc.secure_channel("ipv6:[::1]:4341", creds,
                         options=[("grpc.ssl_target_name_override", "ca-game-api"),
                                  ("grpc.max_receive_message_length", 512 * 1024 * 1024)])
grpc.channel_ready_future(ch).result(timeout=6)
stub = pbg.CadeRemoteStub(ch)
info = stub.Info(pb.InfoRequest(), timeout=6)
print(f"INFO  gameVersion={info.gameVersion}  apiVersion={info.apiVersion}  baseDir={info.baseDirectory!r}")

try:
    n = patches = maxp = 0
    t0 = time.time()
    for sq in stub.Frames(pb.FramesRequest(disableParticles=True), timeout=5):
        for fr in sq.frame:
            n += 1
            if fr.patch:
                patches += 1
                maxp = max(maxp, len(fr.patch))
        if n >= 10 or time.time() - t0 > 4:
            break
    print(f"FRAMES  streamed={n}  patches={patches}  max_patch_bytes={maxp}")
except grpc.RpcError as e:
    print("FRAMES  rpc:", e.code(), str(e.details())[:90])
except Exception as e:
    print("FRAMES  err:", type(e).__name__, str(e)[:90])
