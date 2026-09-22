"""Local environment and first-export gate for the six ready V8 Shorts."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
os.environ['PATH'] = r'D:/AI/environments/comfy-env/.pixi/envs/geometrypack-nodes/Library/bin;' + os.environ['PATH']
os.environ['AOE2_GAME_DIR'] = 'D:/SteamLibrary/steamapps/common/AoE2DE'
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path[:0] = [str(ROOT/'apps/video'),str(ROOT)]
import google
google.__path__ = [str(ROOT/'apps/video/.venv/Lib/site-packages/google'),*google.__path__]
from build_story_batch import main

if __name__ == '__main__':
    manifest = str(Path(__file__).with_name('batch.json'))
    print(f'Batch runner PID {os.getpid()}', flush=True)
    sys.argv = ['build_story_batch.py',manifest,'--numbers','3']
    if main():
        raise SystemExit('First export failed; remaining GPU jobs were not started.')
    sys.argv = ['build_story_batch.py',manifest,'--numbers','4','5','6','7','8']
    raise SystemExit(main())
