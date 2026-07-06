# apps/video/tests/test_compose_args.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overlay.compose import extra_overlay_filters
from overlay.assets import AssetResolver


def test_extra_overlay_filters_chain():
    filters, n_inputs = extra_overlay_filters(
        [("banner.png", "0", "40", 0.0, 5.0, 0.4),
         ("caption.png", "(W-w)/2", "H-h-60", 1.0, 20.0, 0.0)],
        first_input_index=3, upstream="[v0]")
    assert n_inputs == 2
    joined = ";".join(filters)
    assert "enable='between(t,0.0,5.0)'" in joined
    assert "enable='between(t,1.0,20.0)'" in joined
    assert joined.count("overlay=") == 2


def test_asset_resolver_placeholders(tmp_path, monkeypatch):
    monkeypatch.delenv("AOE2_MEDIA_DIR", raising=False)
    r = AssetResolver()
    assert r.hi_res_image("elite_temple_guard_muisca") is None
    assert r.attack_gif("elite_temple_guard_muisca") is None
    monkeypatch.setenv("AOE2_MEDIA_DIR", str(tmp_path))
    (tmp_path / "gifs").mkdir()
    gif = tmp_path / "gifs" / "elite_temple_guard_muisca.gif"
    gif.write_bytes(b"GIF89a")
    assert AssetResolver().attack_gif("elite_temple_guard_muisca") == gif
