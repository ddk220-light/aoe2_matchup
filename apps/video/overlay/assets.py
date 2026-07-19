# apps/video/overlay/assets.py
"""Resolve optional hi-res media (Windows box / bucket mirror). Returns None
when AOE2_MEDIA_DIR is unset or no candidate file exists — callers degrade to
static cards.

Two layouts are supported under the media root, checked in order:
  1. bucket mirror:  <root>/gifs/<slug>.gif, <root>/hires/<slug>.png
  2. in-repo tree:   <root>/units/<slug>/attack.gif,
                     <root>/units/<slug>/sprite_full.png
     (point AOE2_MEDIA_DIR at apps/video/media to use the checked-in assets).

attack_gif / hi_res_image return the first candidate that exists, else None."""
import os
from pathlib import Path


class AssetResolver:
    def __init__(self, root=None):
        env = os.environ.get("AOE2_MEDIA_DIR")
        self.root = Path(root or env) if (root or env) else None

    def _find(self, *rels):
        """First existing candidate (relative to the media root), else None."""
        if not self.root:
            return None
        for rel in rels:
            p = self.root / rel
            if p.exists():
                return p
        return None

    def hi_res_image(self, slug):
        return self._find(f"hires/{slug}.png", f"units/{slug}/sprite_full.png")

    def attack_gif(self, slug):
        return self._find(f"gifs/{slug}.gif", f"units/{slug}/attack.gif")
