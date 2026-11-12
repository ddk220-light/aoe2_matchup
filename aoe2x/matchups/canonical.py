"""Canonical JSON and the hashes the 2026 matchup campaigns used.

Byte-compatible ports of
  * ``hashCanonicalJson()`` - RB:aoe2x/js_simulation/src/canonical-json.js
    (keys sorted, no whitespace, numbers formatted as ``JSON.stringify``), and
  * ``combatProfileHash()`` - RB:aoe2x/js_simulation/node/ranking-equivalence.mjs
    (the mechanics object with only ``civilization`` removed).
RB = origin/simulations/civ-forecast-recovery-2026-11-10.

The number formatting matters: JavaScript prints ``1`` for ``1.0`` and
``1e-7`` for Python's ``1e-07``; any difference changes every hash.
"""
from __future__ import annotations

import hashlib
import json
import math

__all__ = ["canonical_json", "digest", "profile_hash", "js_number", "sha256_bytes", "key2"]


def js_number(value) -> str:
    """Format a number exactly as JavaScript's ``JSON.stringify`` does."""
    if isinstance(value, bool):
        raise TypeError("bool is not a number")
    if isinstance(value, int):
        if abs(value) >= 1e21:
            return js_number(float(value))
        return str(value)
    if not math.isfinite(value):
        raise TypeError("canonical JSON requires a finite number")
    if value == 0:
        return "0"
    # repr() gives the shortest round-trip digits, as ECMAScript Number::toString.
    text = repr(value)
    sign = ""
    if text[0] == "-":
        sign, text = "-", text[1:]
    if "e" in text:
        mantissa, exp = text.split("e")
        exponent = int(exp)
    else:
        mantissa, exponent = text, 0
    if "." in mantissa:
        whole, frac = mantissa.split(".")
    else:
        whole, frac = mantissa, ""
    digits = (whole + frac).lstrip("0")
    # n: position of the decimal point relative to the digit string.
    leading = len(whole + frac) - len((whole + frac).lstrip("0"))
    n = len(whole) + exponent - leading
    digits = digits.rstrip("0") or "0"
    k = len(digits)
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        es = ("+" if e >= 0 else "-") + str(abs(e))
        out = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + es
    return sign + out


def _encode(value, out: list) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(json.dumps(value, ensure_ascii=False))
    elif isinstance(value, (int, float)):
        out.append(js_number(value))
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, child in enumerate(value):
            if index:
                out.append(",")
            _encode(child, out)
        out.append("]")
    elif isinstance(value, dict):
        out.append("{")
        for index, key in enumerate(sorted(value)):
            if not isinstance(key, str):
                raise TypeError("canonical JSON keys must be strings")
            if index:
                out.append(",")
            out.append(json.dumps(key, ensure_ascii=False))
            out.append(":")
            _encode(value[key], out)
        out.append("}")
    else:
        raise TypeError(f"canonical JSON does not support {type(value).__name__}")


def canonical_json(value) -> str:
    out: list = []
    _encode(value, out)
    return "".join(out)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value) -> str:
    """``hashCanonicalJson(value)``."""
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def profile_hash(mechanics: dict) -> str:
    """``combatProfileHash(mechanics)``: every field except ``civilization``."""
    return digest({k: v for k, v in mechanics.items() if k != "civilization"})


def key2(a: str, b: str) -> str:
    """``key2()`` in RB phase-one.mjs: the two hashes in sorted order."""
    return f"{a}|{b}" if a <= b else f"{b}|{a}"
