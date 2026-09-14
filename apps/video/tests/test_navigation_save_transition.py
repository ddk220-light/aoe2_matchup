"""Exercise navigation timing without importing desktop-control dependencies."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class SaveTransition(unittest.TestCase):
    def test_slow_save_prompt_gets_a_fresh_bounded_load_wait(self):
        source = Path(__file__).parents[1] / 'auto/orchestrate_matchup.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == '_navigate_fast')
        clock = [0.0]
        dismissed = [False]

        def click(point):
            # OCR plus clicking No used the entire original transition budget.
            clock[0] = 10.1
            dismissed[0] = True

        def find(image, text, region=None):
            if text == 'No':
                return (100, 100)
            return (200, 200) if dismissed[0] else None

        row = Mock(return_value=True)
        env = dict(time=SimpleNamespace(monotonic=lambda: clock[0],
                                       sleep=lambda _: None),
                   vision=SimpleNamespace(grab=lambda: None, find_text=find,
                                          ocr_text=lambda *_: 'save your changes'),
                   ui=SimpleNamespace(click=click), log=Mock(),
                   _click_frac=Mock(), _wait_text=Mock(return_value=True),
                   _wait_editor=Mock(return_value=True), find_and_click=row)
        for name in ('FP_MENU', 'FP_LOAD_MENU', 'FP_LOAD_BTN', 'R_LOAD_MENU',
                     'R_LOAD_BTN', 'R_SAVE', 'R_LIST', 'R_TEST'):
            env[name] = (0, 0)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), env)
        self.assertTrue(env['_navigate_fast']('main_menu', 'Matchup Run', None))
        self.assertEqual(row.call_args.args[0], 'Matchup Run')


if __name__ == '__main__':
    unittest.main()
