"""Background-keyed cutout for FLUX studio renders.

Why not rembg: semantic segmentation drops subject parts that are DETACHED from the body
(the Fire Archer's flaming arrowhead). This keys on the uniform backdrop instead:

  1. flood fill the backdrop inward from the border  -> removes the surround
  2. sweep up enclosed backdrop pockets (e.g. the gap inside a drawn bow), identified by a
     TIGHT colour match so light subject parts (silver armour) are never eaten
  3. bleed transparency one pixel into near-backdrop edge pixels to kill the halo
"""
import sys
import numpy as np
from PIL import Image
from collections import deque

src, dst = sys.argv[1], sys.argv[2]
TOL_FILL = int(sys.argv[3]) if len(sys.argv) > 3 else 26   # generous: fill continuity
TOL_TIGHT = 12                                             # strict: "this really is backdrop"
MIN_POCKET = 120

im = Image.open(src).convert('RGB')
a = np.asarray(im).astype(int)
h, w, _ = a.shape
corners = np.array([a[0, 0], a[0, w - 1], a[h - 1, 0], a[h - 1, w - 1]])
bg = np.median(corners, axis=0)
diff = np.abs(a - bg[None, None, :]).max(2)
close = diff <= TOL_FILL

def flood(seeds):
    seen = np.zeros((h, w), bool)
    q = deque()
    for y, x in seeds:
        if close[y, x] and not seen[y, x]:
            seen[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and close[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    return seen

border = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)] \
       + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
bgmask = flood(border)

# --- enclosed pockets -------------------------------------------------------
todo = close & ~bgmask
visited = np.zeros((h, w), bool)
pockets = 0
ys, xs = np.nonzero(todo)
for sy, sx in zip(ys, xs):
    if visited[sy, sx]:
        continue
    comp, q = [], deque([(sy, sx)])
    visited[sy, sx] = True
    while q:
        y, x = q.popleft(); comp.append((y, x))
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and todo[ny, nx]:
                visited[ny, nx] = True; q.append((ny, nx))
    if len(comp) < MIN_POCKET:
        continue
    cy, cx = zip(*comp)
    if diff[cy, cx].mean() <= TOL_TIGHT:      # genuinely backdrop, not pale armour
        bgmask[cy, cx] = True
        pockets += 1

# --- halo bleed -------------------------------------------------------------
edge = np.zeros((h, w), bool)
edge[1:, :] |= bgmask[:-1, :]; edge[:-1, :] |= bgmask[1:, :]
edge[:, 1:] |= bgmask[:, :-1]; edge[:, :-1] |= bgmask[:, 1:]
bgmask |= (edge & (diff <= TOL_FILL))

alpha = np.where(bgmask, 0, 255).astype(np.uint8)
# A hard threshold leaves a 1px ring of half-blended backdrop (visible as a pale fringe over
# a dark thumbnail). Erode one pixel to drop those, then feather for anti-aliasing.
from PIL import ImageFilter
alpha_img = Image.fromarray(alpha, 'L').filter(ImageFilter.MinFilter(3))
alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(0.6))
alpha = np.asarray(alpha_img)
img = Image.fromarray(np.dstack([a.astype(np.uint8), alpha]), 'RGBA')
img = img.crop(img.getbbox())
img.save(dst)
print(f'bg={bg.tolist()}  pockets_removed={pockets}  kept={(alpha>0).mean():.1%}  -> {img.size}')
