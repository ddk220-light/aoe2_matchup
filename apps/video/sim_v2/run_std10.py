"""The 10 melee-vs-melee standard-unit pairs missing a corrected recording.

They fell through a seam: phase 2's matchup list deliberately skipped pairs phase 1
already covered, and phase 1's melee tapes all predate the melee-vs-melee template
(units 8.6 tiles apart, patrol AI) -- the same setup that inverted Paladin vs Elite
Steppe. melee_v2 re-recorded them on the correct template, but that whole session fell
inside the 07-30 21:00 -> 07-31 07:00 position-freeze window, so every melee_v2 tape is
unusable too. This is the first recording of these 10 pairs on BOTH the correct
template and a healthy position stream.
"""
import sys
from pathlib import Path

HERE = Path(r"C:\dev\aoe2\aoe2_matchup\.claude\worktrees\wonderful-pasteur-09eca0\apps\video")
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "sim_v2"))

OUT = Path(r"C:\Users\ddk22\Videos\aoe2_golden\std10")

from record_golden import record_many
import run_golden_overnight as R

PAIRS = [
    (("Chinese", "elite_fire_lancer"), ("Cumans", "elite_steppe")),
    (("Chinese", "elite_fire_lancer"), ("Chinese", "halberdier")),
    (("Chinese", "elite_fire_lancer"), ("Persians", "heavy_camel")),
    (("Chinese", "elite_fire_lancer"), ("Persians", "hussar")),
    (("Cumans", "elite_steppe"), ("Chinese", "halberdier")),
    (("Cumans", "elite_steppe"), ("Persians", "heavy_camel")),
    (("Cumans", "elite_steppe"), ("Persians", "hussar")),
    (("Chinese", "halberdier"), ("Persians", "heavy_camel")),
    (("Chinese", "halberdier"), ("Persians", "hussar")),
    (("Persians", "heavy_camel"), ("Persians", "hussar")),
]

print(f"recording {len(PAIRS)} melee-vs-melee fights -> {OUT}", flush=True)
res = record_many(OUT, PAIRS, followup=R.make_followup(OUT))
print("\n".join(f"  {t}: {s}" for t, s in res), flush=True)
print("DONE", flush=True)
