#!/usr/bin/env python3
"""Generate the Python-reference expectations for the browser pair calculation.

    python tools/economy/build_matchup_parity_fixture.py           # writes tests/economy/fixtures/matchup-parity.json
    python tools/economy/build_matchup_parity_fixture.py --check   # exit 1 if the committed fixture is stale

Evaluates a deterministic sample of pairs with ``aoe2x.economy.matchup.evaluate_matchup``
(every civilization, unit and mode, mirrors, army sizes 0-27 and the special
cases) and stores, per pair, the SHA-256 of the *complete* result in a canonical
text form both languages can produce (sorted keys, ASCII-escaped strings,
numbers formatted like JavaScript's Number#toString, "-0" kept) plus a short
headline summary for readable failures. ``tests/economy/matchup-parity.test.mjs``
recomputes every pair with ``apps/web/src/features/economy/matchup.mjs``.

Needs CPython >= 3.12: its float sum() (Neumaier compensation) is the reference
the JS module mirrors; 3.11's plain summation differs in the last bits.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aoe2x.economy.matchup import RuntimeData, evaluate_matchup  # noqa: E402
from aoe2x.economy.paths import RUNTIME_ARTEFACT  # noqa: E402

FIXTURE = ROOT / "tests/economy/fixtures/matchup-parity.json"
SEED = 20261112
SPECIAL_NAMES = ("Winged Hussar", "Kona", "Blackwood", "Konnik", "Skirmisher", "Halberdier", "Warrior Priest",
                 "Galleon", "Dromon", "Traction Trebuchet", "Fire Lancer", "Shrivamsha", "Arbalester")
SPECIAL_CIVS = ("Wu", "Mapuche", "Burgundians", "Spanish", "Chinese", "Persians", "Danes", "Poles", "Khitans",
                "Saxons", "Tupi", "Bulgarians", "Lithuanians", "Shu", "Teutons", "Sicilians")


def js_number(x):
    """Python number -> the text JavaScript's String(x) gives (with "-0" for negative zero)."""
    if isinstance(x, int):
        return str(x)
    if not math.isfinite(x):
        raise ValueError("non-finite number")
    if x == 0:
        return "-0" if math.copysign(1, x) < 0 else "0"
    text = repr(x)
    sign = "-" if text.startswith("-") else ""
    mantissa, _, exponent = text.lstrip("-").partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = whole + fraction
    lead = len(digits) - len(digits.lstrip("0"))
    n = len(whole) + (int(exponent) if exponent else 0) - lead
    digits = digits[lead:].rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * -n + digits
    else:
        e = n - 1
        body = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + body


def canonical(value):
    if value is None:
        return "null"
    if value is True or value is False:
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=True) + ":" + canonical(value[k]) for k in sorted(value)) + "}"
    raise TypeError(type(value))


def digest(value):
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def summary(result):
    """Headline only, to make a failing pair readable; the hash covers everything."""
    teams = result["teams"]
    return {"labor": [t["investment"]["labor"]["seconds"] if t["investment"]["labor"] else None for t in teams],
            "lowerTeam": result["investmentComparison"]["lowerTeam"],
            "production": [[t["production"].get("id"), t["production"]["buildingCount"]] for t in teams]}


def cases(data):
    rng = random.Random(SEED)
    keys = data.keys()
    units = {k: data.unit(*k) for k in keys}
    out = []

    def add(left, right, counts=None, populations=(None, None)):
        a, b = counts or (rng.randint(0, 27), rng.randint(0, 27))
        out.append({"left": [*left, a], "right": [*right, b], "populations": list(populations)})

    for key in keys:  # every civilization, unit and mode, against a random opponent
        add(key, rng.choice(keys))
    for key in rng.sample(keys, 150):  # mirrors (same and different army sizes)
        add(key, key, (n := rng.randint(0, 27), n))
        add(key, key)
    for key in rng.sample(keys, 100):  # army-size extremes
        other = rng.choice(keys)
        for counts in ((0, 0), (1, 27), (27, 1), (27, 27)):
            add(key, other, counts)
    by_civ = {}
    for key in keys:
        by_civ.setdefault(key[0], []).append(key)
    for civ in sorted(by_civ):  # same civilization, different units
        for _ in range(2):
            add(rng.choice(by_civ[civ]), rng.choice(by_civ[civ]))
    special = [k for k in keys if k[0] in SPECIAL_CIVS or any(n in units[k]["name"] for n in SPECIAL_NAMES)
               or units[k]["pricing"]["unitsPerPurchase"] > 1 or any(r.get("completionRebate") for r in units[k]["productionRoutes"])]
    for key in special:
        add(key, rng.choice(keys), (rng.choice((1, 13, 27)), rng.randint(0, 27)))
        add(key, key, (27, 27))
    for key in by_civ["Burgundians"]:  # variable-cost research (Flemish Revolution)
        for populations in ((0, None), (37, 37), (1000, 0), (None, 250)):
            add(key, rng.choice(by_civ["Burgundians"]), populations=populations)
    for key in by_civ["Wu"]:  # Wu building rebate against Shu
        add(key, rng.choice(by_civ["Shu"]))
    left, right = keys[0], keys[1]
    for bad in ((28, 1), (-1, 1), (1.5, 1), (True, 1)):
        out.append({"left": [*left, bad[0]], "right": [*right, bad[1]], "populations": [None, None]})
    for populations in ((1001, None), (None, -1), (2.5, None)):
        out.append({"left": [*left, 3], "right": [*right, 3], "populations": list(populations)})
    return out


def expectation(data, case):
    try:
        result = evaluate_matchup(data, tuple(case["left"]), tuple(case["right"]), tuple(case["populations"]))
    except ValueError as error:
        return {**case, "error": str(error)}
    return {**case, "sha256": digest(result), "summary": summary(result)}


def build():
    if sys.version_info < (3, 12):
        raise SystemExit("Generate the fixture with CPython >= 3.12 (float sum() semantics)")
    data = RuntimeData(RUNTIME_ARTEFACT)
    rows = [expectation(data, case) for case in cases(data)]
    header = {"contextVersion": data.metadata["contextVersion"], "seed": SEED, "pairs": len(rows),
              "generator": "tools/economy/build_matchup_parity_fixture.py",
              "reference": "aoe2x.economy.matchup.evaluate_matchup (CPython >= 3.12)"}
    return "{\n\"header\": " + json.dumps(header, sort_keys=True) + ",\n\"cases\": [\n" + \
        ",\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows) + "\n]}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = build()
    if args.check:
        if not FIXTURE.exists() or FIXTURE.read_text() != text:
            raise SystemExit(f"Stale {FIXTURE.relative_to(ROOT)}; run {Path(__file__).name}")
        print("Parity fixture is current.")
        return
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text)
    print(f"Wrote {FIXTURE.relative_to(ROOT)} ({json.loads(text)['header']['pairs']} pairs, {len(text):,} bytes)")


if __name__ == "__main__":
    main()
