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

    def resolve_attack_gif(self, slug, name=""):
        """The unit's attack gif: local media first (full slug, then the
        civ-suffix-stripped form, then availability prefixes, then the DISPLAY
        name), else fetched once from the public bucket mirror
        (aoe2matchup.com/assets/gifs/<slug>.gif) and cached under the media root.
        Bucket keys derive from display names, so the project's staple slug
        'elite_elephant' lives there as 'elite_battle_elephant' and 'imp_slinger'
        as 'slinger'.

        SINGLE SOURCE OF TRUTH for gif lookup — the long-form intro card, the
        vertical reel intro and the reel's top band all go through this. Keeping
        them separate is what shipped a Slinger intro with no animation: the gif
        was sitting in gifs/slinger.gif while the intro card only ever looked at
        units/imp_slinger/attack.gif."""
        cands = [slug]
        stripped = slug.rsplit("_", 1)[0]
        if stripped != slug:
            cands.append(stripped)
        for pre in ("imp_", "elite_"):
            if slug.startswith(pre) and slug[len(pre):] not in cands:
                cands.append(slug[len(pre):])
        if name:
            from_name = name.lower().replace(" ", "_").replace("-", "_")
            if from_name not in cands:
                cands.append(from_name)
        for s in cands:
            p = self.attack_gif(s)
            if p is not None:
                return p
        if self.root is None:
            return None
        import urllib.request
        for s in cands:
            dest = self.root / "gifs" / f"{s}.gif"
            if dest.exists():
                return dest
            try:
                req = urllib.request.Request(
                    f"https://aoe2matchup.com/assets/gifs/{s}.gif")
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
                if data[:4] == b"GIF8":               # not an error page
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    print(f"[gif] fetched {s}.gif from the bucket -> {dest}")
                    return dest
            except Exception:
                continue
        return None

    def voice_lines(self, civ):
        """The civ's military attack barks (civs/voice_<civ>/attack_<n>.wav), ordered by
        <n>. These are the generic per-civ military lines — every melee unit of the civ
        shares them — so they key off the civ, not the unit slug."""
        if not self.root or not civ:
            return []
        d = self.root / "civs" / f"voice_{civ.lower()}"
        if not d.is_dir():
            return []

        def n(p):
            try:
                return int(p.stem.rsplit("_", 1)[1])
            except (IndexError, ValueError):
                return 0

        return sorted(d.glob("attack_*.wav"), key=n)
