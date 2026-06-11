"""Quick visual check of the redesigned HUD: render the top draining HP bar + bottom
cards at 1440p for two battle states, composited onto a real footage frame if given."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scenario_builder/
from PIL import Image
from overlay.hud import render_hud_frame
from overlay.overlay_data import get_unit_card

u1 = get_unit_card("Muisca", "elite_temple_guard_muisca")
u2 = get_unit_card("Aztecs", "elite_jaguar_warrior_aztecs")
SIZE = (2560, 1440)
bg_path = sys.argv[1] if len(sys.argv) > 1 else None
out_dir = Path(__file__).parent / "samples"
out_dir.mkdir(exist_ok=True)

states = [
    ("full", 23, 1.0, 30, 1.0, 0),
    ("mid", 12, 0.42, 26, 0.78, 12),
    ("late", 3, 0.10, 22, 0.61, 22),
]
for tag, c1, h1, c2, h2, t in states:
    hud = render_hud_frame(u1["name"], u1["icon"], 23, c1, h1,
                           u2["name"], u2["icon"], 30, c2, h2, t=t, size=SIZE)
    if bg_path:
        base = Image.open(bg_path).convert("RGBA").resize(SIZE, Image.LANCZOS)
        base.alpha_composite(hud)
        frame = base.convert("RGB")
    else:
        bg = Image.new("RGB", SIZE, (60, 90, 50))
        bg.paste(hud, (0, 0), hud)
        frame = bg
    p = out_dir / f"_hud_new_{tag}.png"
    frame.save(p)
    print("WROTE", p)
