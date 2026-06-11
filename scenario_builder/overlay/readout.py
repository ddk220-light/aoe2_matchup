"""readout.py — parse the in-game live readout / title line 'Unit A: N vs Unit B: M'.

The ONE place count-parsing lives: the live screen watcher (auto.vision.read_counts)
and the footage OCR (overlay.video_extract) both call parse_counts, so a parsing fix
lands in both automatically.
"""
from __future__ import annotations

import re

# OCR digit-lookalike repairs inside count tokens: '30' is regularly read as '3O'/'3o'
# (letter o), '1' as 'l'/'I'/'i' or '|'. Applied ONLY to the digit tokens after the
# colons — never to the unit names.
_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "i": "1", "l": "1", "|": "1"})
_TOKEN = re.compile(r":([0-9OoIil|]+)")


def _tok_ok(x: str) -> bool:
    """A count token must contain a real digit — EXCEPT a short all-lookalike token:
    a lone '0' is regularly OCR'd as the letter 'o' (the army-wiped reading!), and a
    lone '1' as 'l'. Longer letter-only runs (':Ilo') stay rejected as noise."""
    return bool(re.search(r"\d", x)) or len(x) <= 2


def parse_counts(text: str):
    """'Unit A: N  VS  Unit B: M' -> (N, M); None if it doesn't parse.

    The live readout is '<name>: N  vs  <name>: M', so the two counts are the tokens
    right after the colons. We grab THOSE — robust to OCR dropping the spaces around
    'vs' (a digit and 'v' have no word boundary between them, which broke a \\bvs\\b
    split) and to digit-lookalike misreads (':3Ovs' is '30' with the zero read as a
    letter — taking only \\d+ silently turned 30 into 3; ':o' is a wiped army's '0').
    Falls back to a plain 'vs' split for the colon-less title form. Case-insensitive."""
    t = text.replace(" ", "")
    toks = [x for x in _TOKEN.findall(t) if _tok_ok(x)]
    if len(toks) >= 2:
        return int(toks[0].translate(_DIGIT_FIX)), int(toks[1].translate(_DIGIT_FIX))
    parts = re.split(r"vs", t.lower(), maxsplit=1)
    if len(parts) == 2:
        a = re.findall(r"\d+", parts[0])
        b = re.findall(r"\d+", parts[1])
        if a and b:
            return int(a[0]), int(b[0])
    return None
