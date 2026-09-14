"""Finish the Elite Obuch package after recorded upload authorization."""
import argparse
import msvcrt
import time
import traceback
import finish_pending_production as production

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upload-authorized', action='store_true')
    args = parser.parse_args()
    if not args.upload_authorized:
        parser.error('Use individual offline stages until upload authorization is recorded')
    production.EPISODES = [('elite-obuch', 'Elite Obuch', 'Poles', 'elite_obuch_poles')]
    production.STATE = production.ROOT / 'data/local/elite-obuch-production-status.json'
    lock = (production.ROOT / 'data/local/final-production.lock').open('a+b')
    lock.write(b'0'); lock.flush(); lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        # The owner requested one subject's media at a time, followed by Obuch
        # uploads and then the revised Blackwood upload. Capture is already done.
        blackwood = production.LAB / 'compilations/blackwood-archer-five-hussars/final/manifest.json'
        production.status('elite-obuch', 'WAITING_FOR_BLACKWOOD_LOCAL_MASTER')
        while not blackwood.exists():
            production.pause_check()
            time.sleep(10)
        assert production.read(blackwood)['fullDecode'] == 'passed'
        overlays = production.LAB / 'campaigns/elite-obuch-final-overlays/status.json'
        production.status('elite-obuch', 'OVERLAYS')
        if not overlays.exists() or production.read(overlays)['state'] != 'COMPLETE':
            production.run('render_campaign_overlays.py', '--manifest', 'aoe2lab.overlays.elite-obuch-final.json',
                           '--output', overlays.parent, '--workers', '8', '--recording-status',
                           production.LAB / 'campaigns/elite-obuch-canonical/status.json')
        if production.read(overlays)['state'] != 'COMPLETE':
            production.status('elite-obuch', 'RECOVERING_HP_ALIGNMENT')
            production.run('recover_campaign_alignments.py', overlays, '--workers', '3')
            production.run('render_campaign_overlays.py', '--manifest', 'aoe2lab.overlays.elite-obuch-final.json',
                           '--output', overlays.parent, '--workers', '3', '--recording-status',
                           production.LAB / 'campaigns/elite-obuch-canonical/status.json')
        assert production.read(overlays)['state'] == 'COMPLETE', 'Review remaining overlay failures'
        out = production.LAB / 'compilations/elite-obuch-unique-units/final-cost-v2'
        production.status('elite-obuch', 'BATTLE_COMPILATION')
        if not (out / 'battles-manifest.json').exists():
            production.run('build_elite_obuch_final.py', '--battles-only')
        production.run('build_campaign_thumbnail.py', '--plan', 'apps/video/intro/elite-obuch.json',
                       '--prefix', 'apps/video/intro/thumbnails/elite-obuch', '--title', 'Elite Obuch')
        production.status('elite-obuch', 'SHORTS')
        shorts = production.LAB / 'shorts/elite-obuch-selected-10'
        if not (shorts / 'selection.json').exists():
            production.run('prepare_elite_obuch_final_shorts.py')
        production.run('render_selected_shorts.py', '--selection', shorts / 'selection.json', '--workers', '8')
        assert production.read(shorts / 'status.json')['state'] == 'COMPLETE'
        production.status('elite-obuch', 'WAITING_FOR_POLISH_NARRATION')
        while not (production.ROOT / 'apps/video/intro/elite-obuch-cloned.json').exists():
            production.pause_check()
            time.sleep(10)
        production.main()
        production.run('publish_blackwood_five_hussars.py', '--upload-authorized')
    except Exception:
        production.status('elite-obuch', 'NEEDS_ATTENTION', error=traceback.format_exc())
        raise
