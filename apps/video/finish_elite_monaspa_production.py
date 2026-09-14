"""Complete the user-authorized Monaspa package using the established publisher."""
import msvcrt
import time
import traceback
import finish_pending_production as production

production.EPISODES = [('elite-monaspa', 'Elite Monaspa', 'Georgians', 'elite_monaspa_georgians')]
production.STATE = production.ROOT / 'data/local/elite_monaspa-production-status.json'

if __name__ == '__main__':
    lock = (production.ROOT / 'data/local/final-production.lock').open('a+b')
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        production.status('elite-monaspa', 'WAITING_FOR_NARRATION')
        while not (production.ROOT / 'apps/video/intro/elite-monaspa-cloned.json').exists():
            production.pause_check()
            overlays = production.LAB / 'campaigns/elite-monaspa-final-overlays/status.json'
            shorts = production.LAB / 'shorts/elite-monaspa-selected-10'
            if overlays.exists() and production.read(overlays)['state'] == 'COMPLETE':
                battles = production.LAB / 'compilations/elite-monaspa-unique-units/final-cost-v2/battles-manifest.json'
                if not battles.exists():
                    production.status('elite-monaspa', 'BATTLE_COMPILATION')
                    production.run('build_elite_monaspa_final.py', '--battles-only')
                short_status = shorts / 'status.json'
                if not short_status.exists() or production.read(short_status)['state'] != 'COMPLETE':
                    production.status('elite-monaspa', 'SHORTS')
                    production.run('prepare_elite_monaspa_final_shorts.py')
                    production.run('render_selected_shorts.py', '--selection', shorts / 'selection.json', '--workers', '8')
                    assert production.read(short_status)['state'] == 'COMPLETE'
                    production.status('elite-monaspa', 'WAITING_FOR_NARRATION')
            time.sleep(10)
        production.main()
    except Exception:
        production.status('elite-monaspa', 'NEEDS_ATTENTION', error=traceback.format_exc())
        raise
