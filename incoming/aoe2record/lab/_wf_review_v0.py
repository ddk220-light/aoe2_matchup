"""_wf_review_v0.py - run the existing scorer against the PRE-FIX decoder backup.

Loads decode_state_v2.pre_fix.bak.py under the module name 'decode_state_v2'
(preempting the scorer's own import via sys.modules), then executes
_wf_score_fix.py with --no-run1 (the run1 leg subprocess would use the NEW
module on disk, so it is skipped here).
"""
import importlib.util
import runpy
import sys

BAK = r"C:\dev\aoe2\aoe2record\lab\decode_state_v2.pre_fix.bak.py"
spec = importlib.util.spec_from_file_location("decode_state_v2", BAK)
mod = importlib.util.module_from_spec(spec)
sys.modules["decode_state_v2"] = mod
spec.loader.exec_module(mod)
assert sys.modules["decode_state_v2"].__file__ == BAK

sys.argv = [r"C:\dev\aoe2\aoe2record\lab\_wf_score_fix.py", "--no-run1"]
runpy.run_path(r"C:\dev\aoe2\aoe2record\lab\_wf_score_fix.py", run_name="__main__")
