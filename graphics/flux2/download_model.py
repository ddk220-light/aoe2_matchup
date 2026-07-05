"""One-time download of FLUX.2-dev-bnb-4bit from HuggingFace (~32 GB).

Run once before using generate.py:
  python graphics/flux2/download_model.py

Uses resume_download=True so it's safe to interrupt and re-run.
The model caches to the default HuggingFace hub dir:
  Windows: C:\\Users\\<you>\\.cache\\huggingface\\hub\\
"""
import time
from huggingface_hub import snapshot_download

t0 = time.time()
path = snapshot_download(
    'diffusers/FLUX.2-dev-bnb-4bit',
    max_workers=8,
    resume_download=True,
)
print(f'Downloaded in {round((time.time()-t0)/60, 1)} min -> {path}', flush=True)
