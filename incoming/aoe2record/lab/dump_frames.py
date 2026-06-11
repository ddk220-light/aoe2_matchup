"""Stream a few seconds of CadeRemote.Frames() from a running replay and report
what we get (frames, patches, commands, events). Saves the first state patch and
a raw sample for offline decoding.
"""
import time
from collections import Counter

import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg

PORT = 4341
SECONDS = 6.0


def channel():
    ca = open("certificate-authority.pem", "rb").read()
    cert = open("cade-client.pem", "rb").read()
    key = open("cade-client.key", "rb").read()
    creds = grpc.ssl_channel_credentials(root_certificates=ca, private_key=key, certificate_chain=cert)
    return grpc.secure_channel(f"ipv6:[::1]:{PORT}", creds,
                               options=[("grpc.ssl_target_name_override", "ca-game-api"),
                                        ("grpc.max_receive_message_length", 256 * 1024 * 1024)])


def main():
    ch = channel()
    grpc.channel_ready_future(ch).result(timeout=6)
    stub = pbg.CadeRemoteStub(ch)
    req = pb.FramesRequest(disableParticles=True, disableParticleCulling=True)

    sequences = frames = events = commands = patch_bytes = 0
    cmd_types, event_types = Counter(), Counter()
    first_patch = None
    t0 = time.time()
    raw = open("frames_sample.bin", "wb")
    try:
        for seq in stub.Frames(req, timeout=SECONDS + 4):
            sequences += 1
            for fr in seq.frame:
                frames += 1
                patch_bytes += len(fr.patch)
                events += len(fr.event)
                commands += len(fr.command)
                if first_patch is None and fr.patch:
                    first_patch = fr.patch
                    with open("first_patch.bin", "wb") as f:
                        f.write(fr.patch)
                for c in fr.command:
                    cmd_types[c.WhichOneof("command")] += 1
                for e in fr.event:
                    event_types[e.WhichOneof("event")] += 1
            raw.write(seq.SerializeToString())
            if time.time() - t0 > SECONDS:
                break
    except grpc.RpcError as e:
        if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
            print(f"[rpc error] {e.code()} {e.details()}")
    raw.close()

    print(f"captured in ~{SECONDS:.0f}s of wall time:")
    print(f"  sequences={sequences}  frames={frames}  commands={commands}  events={events}")
    print(f"  total patch bytes={patch_bytes}  first_patch={len(first_patch) if first_patch else 0} bytes")
    if first_patch:
        print(f"  first_patch head (hex): {first_patch[:48].hex()}")
    if cmd_types:
        print(f"  command types seen: {dict(cmd_types.most_common())}")
    if event_types:
        print(f"  event types seen:   {dict(event_types.most_common())}")
    if frames == 0:
        print("  (0 frames -> the replay is probably PAUSED. Press play in-game and re-run.)")


if __name__ == "__main__":
    main()
