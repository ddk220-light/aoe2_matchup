from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "video"))

from auto import orchestrate_matchup as nav
from auto import record_until_end as watcher


def test_result_watcher_accepts_game_end_without_wins_banner(monkeypatch):
    from PIL import Image
    from auto import vision
    frame = Image.new("RGB", (2560, 1440))
    for text in ("you are victorious!", "you have been defeated!", "elite gbeto wins!"):
        monkeypatch.setattr(vision, "ocr_text", lambda *a, text=text: text)
        assert vision.ResultWatcher().check(frame)
    monkeypatch.setattr(vision, "ocr_text", lambda *a: "war chariot 5 elite gbeto 7")
    assert not vision.ResultWatcher().check(frame)


def test_missing_named_scenario_never_loads_another_row(monkeypatch):
    clicks = []
    monkeypatch.setattr(nav, "find_and_click", lambda *a, **k: False)
    monkeypatch.setattr(nav, "_click_frac", lambda *a, **k: clicks.append(a))
    assert not nav._navigate_fast("load_dialog", "Matchup Run", None)
    assert not clicks


def test_end_flag_does_not_wait_for_minimum_fight_or_ocr(monkeypatch, tmp_path):
    import time
    end = tmp_path / "match.END"
    end.write_text("finished")
    monkeypatch.setattr(watcher.vision, "grab", lambda: (_ for _ in ()).throw(AssertionError("OCR should not run")))
    start = time.time()
    assert watcher.watch_until_result(start, min_fight=8, end_flag=end)
    assert time.time() - start < 0.5


def test_completed_test_cleanup_stops_if_menu_is_missing(monkeypatch):
    keys = []
    monkeypatch.setattr(nav, "_in_editor", lambda: False)
    monkeypatch.setattr(nav.vision, "detect_end", lambda *a: False)
    monkeypatch.setattr(nav.platform_io, "key", keys.append)
    monkeypatch.setattr(nav, "find_and_click", lambda *a, **k: False)
    assert not nav.return_to_editor(None, completed_test=True)
    assert keys == ["f10"]


def test_banner_keeps_stream_alive_until_terminal_patch(monkeypatch):
    from types import SimpleNamespace
    clock = [0.0]
    monkeypatch.setattr(watcher.time, "time", lambda: clock[0])
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(watcher, "_focus_game", lambda: None)
    monkeypatch.setattr(watcher.vision, "grab", lambda: None)
    monkeypatch.setattr(watcher.vision, "ResultWatcher", lambda: SimpleNamespace(check=lambda image: True))
    monkeypatch.setattr(watcher.os.path, "exists", lambda path: clock[0] >= 4.0)
    assert watcher.watch_until_result(0, min_fight=0, end_flag="capture.END")
    assert 4.0 <= clock[0] < 4.2


def test_banner_fallback_remains_bounded_when_logger_cannot_finish(monkeypatch):
    from types import SimpleNamespace
    clock = [0.0]
    monkeypatch.setattr(watcher.time, "time", lambda: clock[0])
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(watcher, "_focus_game", lambda: None)
    monkeypatch.setattr(watcher.vision, "grab", lambda: None)
    monkeypatch.setattr(watcher.vision, "ResultWatcher", lambda: SimpleNamespace(check=lambda image: True))
    monkeypatch.setattr(watcher.os.path, "exists", lambda path: False)
    assert watcher.watch_until_result(0, min_fight=0, end_flag="capture.END")
    assert 5.0 <= clock[0] < 5.2


def test_completed_game_end_uses_continue_instead_of_test_menu(monkeypatch):
    editor_states = iter((False, False, True))
    clicks, keys = [], []
    monkeypatch.setattr(nav, "_in_editor", lambda *a: next(editor_states))
    monkeypatch.setattr(nav, "_focus_game", lambda: None)
    monkeypatch.setattr(nav.vision, "grab", lambda: object())
    monkeypatch.setattr(nav.vision, "detect_end", lambda *a: True)
    monkeypatch.setattr(nav.vision, "find_text", lambda img, text, **kw: (500, 700) if text == "Continue" else None)
    monkeypatch.setattr(nav.ui, "click", clicks.append)
    monkeypatch.setattr(nav.platform_io, "key", keys.append)
    monkeypatch.setattr(nav.time, "sleep", lambda *a: None)
    assert nav.return_to_editor(None, completed_test=True)
    assert clicks == [(500, 700)]
    assert not keys


def test_cached_row_is_revalidated_and_relocated(monkeypatch):
    from PIL import Image
    region = (0.12, 0.49, 0.60, 0.53)
    monkeypatch.setattr(nav, "_ROW_REGIONS", {"Matchup Run": region})
    monkeypatch.setattr(nav, "_focus_game", lambda: None)
    monkeypatch.setattr(nav.vision, "grab", lambda: Image.new("RGB", (2560, 1440)))
    calls, clicks = [], []
    def find(img, pattern, region):
        calls.append(region)
        return None if len(calls) == 1 else (500, 700)
    monkeypatch.setattr(nav.vision, "find_text", find)
    monkeypatch.setattr(nav.ui, "click", clicks.append)
    assert nav.find_and_click("Matchup Run", nav.R_LIST, None)
    assert calls == [region, nav.R_LIST]
    assert clicks == [(500, 700)]
