"""Structural validator for derived .per variants.
usage: validate_variant.py <base.per> <derived.per> <expected-changed-indices-csv|-> <expected-added-rules>
Checks: paren balance, one => per rule, <=32 elements/rule (ERR6002), jump-direct set
unchanged and <=76, base rules differ ONLY at whitelisted indices (comments/strings
stripped), every token proven in a known-good file or defconst'd in the derived file.
Known-good token pool = base file + ddkMicroV9.per (proves up-point-contains / up-path-distance
/ up-jump-rule) + the derived file's own defconsts.
"""
import io, re, sys

base_p, der_p, changed_csv, added_s = sys.argv[1:5]
BASE = io.open(base_p, encoding="utf-8").read()
DER = io.open(der_p, encoding="utf-8").read()
POOL = (BASE + io.open(r"apps\video\ai_experiments\ddkMicroV9.per", encoding="utf-8").read()
        + io.open(r"apps\video\ai_experiments\ddkMicroV1.per", encoding="utf-8").read())
EXP_CHANGED = set() if changed_csv == "-" or changed_csv.startswith("set") else {int(x) for x in changed_csv.split(",")}
EXP_ADDED = int(added_s)

def strip(t):
    t = re.sub(r";[^\n]*", "", t)
    return re.sub(r'"[^"]*"', '""', t)

def rules(t):
    s, out, i = strip(t), [], 0
    while (j := s.find("(defrule", i)) >= 0:
        d, k = 0, j
        while True:
            if s[k] == "(": d += 1
            elif s[k] == ")":
                d -= 1
                if d == 0: break
            k += 1
        out.append(s[j:k + 1]); i = k + 1
    return out

fails = []
sD = strip(DER); d = 0
for ch in sD:
    if ch == "(": d += 1
    elif ch == ")": d -= 1
    if d < 0: fails.append("negative paren depth"); break
if d != 0: fails.append(f"unbalanced parens: {d}")

rB, rD = rules(BASE), rules(DER)
print(f"rules: base={len(rB)} derived={len(rD)} (expect +{EXP_ADDED})")
if len(rD) != len(rB) + EXP_ADDED:
    fails.append(f"rule count: expected {len(rB)+EXP_ADDED}, got {len(rD)}")
for i, r in enumerate(rD):
    if r.count("=>") != 1: fails.append(f"rule {i}: {r.count('=>')} arrows")
    if (n := r.count("(") - 1) > 32: fails.append(f"rule {i}: {n} elements > 32")

jB = sorted(re.findall(r"up-jump-direct c: (\d+)", BASE))
jD = sorted(re.findall(r"up-jump-direct c: (\d+)", DER))
if jB != jD: fails.append(f"jump set changed: {jB} -> {jD}")
if any(int(t) > 76 for t in jD): fails.append("jump target > 76")

norm = lambda r: re.sub(r"\s+", " ", r).strip()
if changed_csv.startswith("set"):
    # insertion mode: indices shift, so check as multisets; "set:N" = exactly N base
    # rules are expected to be intentionally altered (they show as missing)
    from collections import Counter
    allowed = int(changed_csv.split(":")[1]) if ":" in changed_csv else 0
    cB, cD = Counter(map(norm, rB)), Counter(map(norm, rD))
    missing = list((cB - cD).elements())
    print(f"base rules missing from derived: {len(missing)} (allowed {allowed})")
    for m in missing:
        print("  ALTERED:", m[:120])
    if len(missing) != allowed:
        fails.append(f"{len(missing)} base rules altered, expected {allowed}")
else:
    changed = [i for i in range(min(len(rB), len(rD))) if norm(rB[i]) != norm(rD[i])]
    print(f"changed base rules: {changed}")
    if not set(changed) <= EXP_CHANGED:
        fails.append(f"unexpected edits: {sorted(set(changed) - EXP_CHANGED)}")

tok = lambda t: set(re.findall(r"[A-Za-z_][A-Za-z0-9_:%-]*", strip(t)))
defc = set(re.findall(r"\(defconst\s+(\S+)", DER))
unknown = sorted(tok(DER) - tok(POOL) - defc)
if unknown: fails.append(f"unknown tokens: {unknown}")

names = re.findall(r"\(defconst\s+(\S+)\s+(-?\d+)\)", DER)
seen = {}
for n, v in names:
    if n in seen and seen[n] != v: fails.append(f"defconst {n} redefined {seen[n]}->{v}")
    seen[n] = v

print("FAIL:\n" + "\n".join(fails) if fails else "ALL CHECKS PASS")
sys.exit(1 if fails else 0)
