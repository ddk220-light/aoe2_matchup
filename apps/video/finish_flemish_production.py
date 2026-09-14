"""Complete the user-authorized Flemish package using the established publisher."""
import msvcrt
import time
import traceback
import finish_pending_production as production

production.EPISODES = [('flemish-militia', 'Flemish Militia', 'Burgundians', 'flemish_militia_burgundians')]
production.STATE = production.ROOT / 'data/local/flemish-production-status.json'

if __name__ == '__main__':
    lock = (production.ROOT / 'data/local/final-production.lock').open('a+b')
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        production.status('flemish-militia', 'WAITING_FOR_NARRATION')
        while not (production.ROOT / 'apps/video/intro/flemish-militia-cloned.json').exists():
            production.pause_check()
            overlays = production.LAB / 'campaigns/flemish-militia-final-overlays/status.json'
            shorts = production.LAB / 'shorts/flemish-militia-selected-10'
            if overlays.exists() and production.read(overlays)['state'] == 'COMPLETE':
                battles = production.LAB / 'compilations/flemish-militia-unique-units/final-cost-v2/battles-manifest.json'
                if not battles.exists():
                    production.status('flemish-militia', 'BATTLE_COMPILATION')
                    production.run('build_flemish_militia_final.py', '--battles-only')
                short_status = shorts / 'status.json'
                if not short_status.exists() or production.read(short_status)['state'] != 'COMPLETE':
                    production.status('flemish-militia', 'SHORTS')
                    production.run('prepare_flemish_militia_final_shorts.py')
                    production.run('render_selected_shorts.py', '--selection', shorts / 'selection.json', '--workers', '8')
                    assert production.read(short_status)['state'] == 'COMPLETE'
                    production.status('flemish-militia', 'WAITING_FOR_NARRATION')
            time.sleep(10)
        production.main()
    except Exception:
        production.status('flemish-militia', 'NEEDS_ATTENTION', error=traceback.format_exc())
        raise
