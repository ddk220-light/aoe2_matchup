"""Record an already loaded Comp4 test; the caller starts it through the game UI.

No UI input is performed here. Full protobuf frames and per-owner HP are saved;
the old P2-versus-P3 end detector is intentionally not used for four allied pairs.
The recorder stops after ALL four pairs have a stable elimination, or at timeout.
"""
from __future__ import annotations
import argparse
import json
import struct
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'aoe2x/grpc'))
import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg
import decode_state_v2 as D
from auto import platform_io


def chan():
    """Same local mTLS endpoint as grpc_hp_log, without importing its CLI argv."""
    certs = ROOT / 'aoe2x/grpc'
    credentials = grpc.ssl_channel_credentials(
        (certs/'certificate-authority.pem').read_bytes(),
        (certs/'cade-client.key').read_bytes(), (certs/'cade-client.pem').read_bytes())
    return grpc.secure_channel('ipv6:[::1]:4341', credentials, options=[
        ('grpc.ssl_target_name_override', 'ca-game-api'),
        ('grpc.max_receive_message_length', 512*1024*1024)])


def owner_units(entities, masters=None):
    owners = {p: [] for p in range(1, 9)}
    for entity_id, entity in entities.items():
        owner, master, hp = entity.get(2), entity.get(1), entity.get(12)
        if owner in owners and entity.get('__type__') in (9, 11, 12) and master not in (1775,2551,1291) and (masters is None or master in masters) and isinstance(hp, (int, float)) and hp > 0:
            owners[owner].append({'id': str(entity_id), 'master': master, 'hp': hp,
                                  'x': entity.get(3), 'y': entity.get(4)})
    return owners


def opening_matches(owners, plan=None):
    """Validate the exact authored IDs and approved HP before any battle damage.

    Post-Imperial placed units can retain their editor master in the stream.
    The original capture demonstrates 1800 with 50 HP, then the specified injury.
    Do not demand a different catalog ID as evidence of successful capture.
    """
    if plan:
        for pair in plan['pairs']:
            p,q=pair['subjectOwner'],pair['opponentOwner']
            if len(owners[p])!=pair['subjectCount'] or len(owners[q])!=len(pair['opponentHP']):return False
            if any(u['master']!=plan['subjectMaster'] or abs(u['hp']-plan['subjectHP'][str(p)])>.05 for u in owners[p]):return False
            if any(u['master']!=plan['expectedGrpcOpponentMaster'] for u in owners[q]):return False
            if any(abs(a-b)>.05 for a,b in zip(sorted(u['hp'] for u in owners[q]),sorted(pair['opponentHP']))):return False
        return True
    return (
        [len(owners[p]) for p in range(1, 9)] == [8, 8, 8, 8, 6, 7, 7, 7]
        and all(all(u['master'] == 2554 and u['hp'] == hp for u in owners[p])
                for p, hp in [(1,65), (2,80), (3,65), (4,65)])
        and all(u['master'] == 1800 for p in (5,6,7,8) for u in owners[p])
        and sorted(u['hp'] for u in owners[5]) == [30,50,50,50,50,50]
        and all(all(u['hp'] == 50 for u in owners[p]) for p in (6,7,8))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    out = args.out
    plan=json.loads(args.plan.read_text()) if args.plan else None
    stopped = threading.Event()
    status = {'state': 'ARMING', 'pairs': {}, 'initialVerified': False,'plan':str(args.plan) if args.plan else None}
    def save_status():
        tmp=out/'status.tmp.json';tmp.write_text(json.dumps(status, indent=2), encoding='utf-8');tmp.replace(out/'status.json')
    save_status()
    started = time.time()
    recorder = platform_io.recorder_start(out / 'raw.mp4', cap=args.seconds+10, fps=60, w=2560, h=1440)
    status.update(state='ARMED', recorderStartedEpoch=started, recorderReadyEpoch=time.time())
    save_status()

    def stream():
        doc = world = None
        entities = None
        last_t = None
        zero_since = {}
        armed = False
        previous_second = None
        sequences = 0
        try:
            with (out / 'frames.bin').open('wb') as frames, (out / 'timeline.jsonl').open('w', encoding='utf-8') as timeline, (out / 'sequence-times.jsonl').open('w') as timings:
                while not stopped.is_set() and time.time()-started < args.seconds:
                    try:
                        with chan() as channel:
                            grpc.channel_ready_future(channel).result(timeout=5)
                            stub = pbg.CadeRemoteStub(channel)
                            status['gameVersion'] = stub.Info(pb.InfoRequest(), timeout=5).gameVersion
                            required=(plan or {}).get('runtimeAdjustment') or {}
                            if required.get('gameVersion') and str(status['gameVersion'])!=str(required['gameVersion']):
                                raise ValueError('Runtime opening profile requires game build '+str(required['gameVersion']))
                            stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5)
                            for sequence in stub.Frames(pb.FramesRequest(disableParticles=True), timeout=args.seconds):
                                wall = time.time()
                                data = sequence.SerializeToString()
                                offset = frames.tell()
                                frames.write(struct.pack('<I', len(data))); frames.write(data); frames.flush()
                                timings.write(json.dumps({'offset': offset, 'wallEpoch': wall, 'times': [f.time for f in sequence.frame]})+'\n'); timings.flush()
                                sequences += 1
                                for frame in sequence.frame:
                                    t = frame.time / 1000
                                    patch = frame.patch
                                    if last_t is not None and t < last_t-2:
                                        doc = entities = world = None
                                        armed = False; zero_since = {}; status['pairs'] = {}; status['initialVerified'] = False
                                    if patch and len(patch) > 400000:
                                        seed = out / f'seed-{sequences}.bin'
                                        seed.write_bytes(patch)
                                        doc = D.Doc(); entities = {}
                                        _, world = D.seed_from_snapshot(str(seed), doc, entities)
                                    elif entities is not None and patch:
                                        D.apply_patch(doc, patch, entities, world)
                                    last_t = t
                                    if entities is None:
                                        continue
                                    owners = owner_units(entities)
                                    totals = {p: {'count': len(units), 'hp': sum(u['hp'] for u in units)} for p, units in owners.items()}
                                    # This exact pre-combat state must actually occur in
                                    # the game. A plan file alone cannot pass this check.
                                    expected_counts=([p['subjectCount'] for p in plan['pairs']]+[len(p['opponentHP']) for p in plan['pairs']]) if plan else [8,8,8,8,6,7,7,7]
                                    correct_counts = [len(owners[p]) for p in range(1,9)] == expected_counts
                                    if not status['initialVerified'] and t<=2 and opening_matches(owners,plan):
                                        status['initialVerified'] = True
                                        status['initial'] = {'gameSeconds': t, 'owners': owners, 'totals': totals}
                                        (out/'initial-verified.json').write_text(json.dumps(status['initial'], indent=2))
                                    if correct_counts and not armed:
                                        armed = True
                                        status['firstRoster'] = {'gameSeconds': t, 'owners': owners, 'totals': totals}
                                    row = {'gameSeconds': t, 'wallEpoch': wall, 'owners': owners, 'totals': totals}
                                    timeline.write(json.dumps(row)+'\n')
                                    if armed:
                                        for p in range(1,5):
                                            q = p+4
                                            if not owners[p] or not owners[q]:
                                                if p not in zero_since:
                                                    zero_since[p]={'subjectOwner':p, 'opponentOwner':q,
                                                        'endGameSeconds':t,'endWallEpoch':wall, 'winnerOwner':p if owners[p] else q if owners[q] else None,
                                                        'subject':totals[p].copy(), 'opponent':totals[q].copy()}
                                                if t-zero_since[p]['endGameSeconds'] >= 1:
                                                    status['pairs'][str(p)] = zero_since[p]
                                            else:
                                                zero_since.pop(p, None); status['pairs'].pop(str(p), None)
                                    if int(t) != previous_second:
                                        previous_second = int(t)
                                        status.update(state='CAPTURING', gameSeconds=t, totals=totals, sequences=sequences)
                                        save_status(); timeline.flush()
                                    if len(status['pairs']) == 4 and wall-max(r['endWallEpoch'] for r in status['pairs'].values())>=3:
                                        status['state'] = 'COMPLETE' if status['initialVerified'] else 'INITIAL_VALIDATION_FAILED'
                                        stopped.set(); break
                                if stopped.is_set() or wall-started >= args.seconds:
                                    break
                    except (grpc.RpcError, grpc.FutureTimeoutError):
                        if not stopped.is_set():
                            time.sleep(.5)
        except Exception as error:
            status.update(state='ERROR', error=f'{type(error).__name__}: {error}')
        finally:
            if status['state'] in ('ARMED','CAPTURING'):
                status['state']='TIMEOUT'
            stopped.set(); save_status()
    worker = threading.Thread(target=stream, daemon=True)
    worker.start()
    while not stopped.wait(.25):
        if (out/'STOP').exists() or time.time()-started > args.seconds:
            stopped.set()
    platform_io.recorder_stop(recorder, out/'raw.mp4')
    worker.join(timeout=8)
    status['recorderExitCode']=recorder.poll()
    status['finishedEpoch']=time.time()
    save_status()
    print(json.dumps(status, indent=2))
    return 0 if status['state']=='COMPLETE' and status['recorderExitCode']==0 else 2


if __name__ == '__main__':
    sys.exit(main())
