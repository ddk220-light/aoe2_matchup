# apps/video/tests/test_pure_module.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_pure_imports_without_nav_stack():
    for m in ("auto.vision", "auto.platform_io", "auto.grpc_capture"):
        sys.modules.pop(m, None)
    from auto import pure  # noqa: F401
    assert "auto.vision" not in sys.modules
    assert "auto.platform_io" not in sys.modules


def test_equal_resource_counts_moved(monkeypatch):
    # real signature is (civ1, slug1, civ2, slug2, unit_cap=30); per-unit weighted
    # cost comes from overlay_data.get_unit_card — patch it, mirroring test_pure.py.
    import overlay.overlay_data as od
    monkeypatch.setattr(od, "get_unit_card", lambda civ, slug, *a, **k: {
        "cost": {"weighted": 50.0 if slug == "a" else 100.0}})
    from auto.pure import equal_resource_counts, RES_BUDGET
    c1, c2 = equal_resource_counts("C1", "a", "C2", "b")
    assert c1 > 0 and c1 > c2 and RES_BUDGET > 0    # side 1 cheaper -> more of it
