"""Sustained capture of the CadeRemote Frames stream while a replay plays.
Logs production-relevant commands (Make/Create/Queue/Build/...) with full fields
to test whether they link a unit TYPE to the produced unit's id (ground truth),
and saves the first full-state patch for the state-decode path.
"""
import json
import time
from collections import Counter

import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg

DURATION = float(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 120.0
PROD = {"make", "create", "queue", "multiQueue", "build", "unitTransform",
        "buildWall", "research", "deleteObjects"}


def chan():
    ca = open("certificate-authority.pem", "rb").read()
    cert = open("cade-client.pem", "rb").read()
    key = open("cade-client.key", "rb").read()
    creds = grpc.ssl_channel_credentials(ca, key, cert)
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
                               options=[("grpc.ssl_target_name_override", "ca-game-api"),
                                        ("grpc.max_receive_message_length", 256 * 1024 * 1024)])


def fields(msg):
    return {f.name: getattr(msg, f.name) for f in msg.DESCRIPTOR.fields
            if f.label != f.LABEL_REPEATED or list(getattr(msg, f.name))}


def main():
    ch = chan()
    grpc.channel_ready_future(ch).result(timeout=8)
    stub = pbg.CadeRemoteStub(ch)
    info = stub.Info(pb.InfoRequest(), timeout=6)
    print(f"connected. gameVersion={info.gameVersion} apiVersion={info.apiVersion}")

    ct = Counter()
    prod_log = open("commands_log.jsonl", "w")
    first_patch_saved = False
    frames = seqs = 0
    last_time = 0
    t0 = time.time()
    try:
        for seq in stub.Frames(pb.FramesRequest(disableParticles=True), timeout=DURATION + 8):
            seqs += 1
            for fr in seq.frame:
                frames += 1
                last_time = fr.time
                if not first_patch_saved and fr.patch:
                    open("first_patch_new.bin", "wb").write(fr.patch)
                    first_patch_saved = True
                    print(f"saved first_patch_new.bin ({len(fr.patch)} bytes) at game time {fr.time}")
                for c in fr.command:
                    w = c.WhichOneof("command")
                    ct[w] += 1
                    if w in PROD:
                        sub = getattr(c, w)
                        rec = {"t": fr.time, "cmd": w}
                        for f in sub.DESCRIPTOR.fields:
                            v = getattr(sub, f.name)
                            if f.label == f.LABEL_REPEATED:
                                v = list(v)
                            elif f.message_type:
                                v = {sf.name: getattr(v, sf.name) for sf in f.message_type.fields}
                            rec[f.name] = v
                        prod_log.write(json.dumps(rec) + "\n")
            if seqs % 200 == 0:
                prod_log.flush()
                print(f"  ...{seqs} seqs, gametime={last_time}, cmds so far={sum(ct.values())}")
            if time.time() - t0 > DURATION:
                break
    except grpc.RpcError as e:
        if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
            print("rpc error:", e.code(), e.details())
    prod_log.close()
    print(f"\ndone. frames={frames} seqs={seqs} final_gametime={last_time}ms")
    print("command counts:", dict(ct.most_common()))
    print("production commands written to commands_log.jsonl")


if __name__ == "__main__":
    main()
