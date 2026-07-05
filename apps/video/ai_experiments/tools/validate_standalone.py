"""Standalone .per validation (for fresh files like ddkMeleeV1): paren balance,
one => per rule, <=32 elements, NO absolute jumps, every token proven in the
known-good pool (CoreG + MicroV9 + MicroV1) or defconst'd locally."""
import io, re, sys

DER = io.open(sys.argv[1], encoding="utf-8").read()
POOL = "".join(io.open(p, encoding="utf-8").read() for p in (
    r"apps\video\ai_experiments\ddkImmortalCoreG.per",
    r"apps\video\ai_experiments\ddkMicroV9.per",
    r"apps\video\ai_experiments\ddkMicroV1.per"))

def strip(t):
    t = re.sub(r";[^\n]*", "", t)
    return re.sub(r'"[^"]*"', '""', t)

fails = []
s = strip(DER); d = 0
for ch in s:
    if ch == "(": d += 1
    elif ch == ")": d -= 1
    if d < 0: fails.append("negative depth"); break
if d != 0: fails.append(f"unbalanced: {d}")

rules, i = [], 0
while (j := s.find("(defrule", i)) >= 0:
    dep, k = 0, j
    while True:
        if s[k] == "(": dep += 1
        elif s[k] == ")":
            dep -= 1
            if dep == 0: break
        k += 1
    rules.append(s[j:k + 1]); i = k + 1
print(f"{len(rules)} defrules")
for idx, r in enumerate(rules):
    if r.count("=>") != 1: fails.append(f"rule {idx}: {r.count('=>')} arrows")
    if (n := r.count("(") - 1) > 32: fails.append(f"rule {idx}: {n} elements")

if "up-jump-direct" in s: fails.append("contains up-jump-direct (numbering hazard)")

tok = lambda t: set(re.findall(r"[A-Za-z_][A-Za-z0-9_:%-]*", strip(t)))
defc = set(re.findall(r"\(defconst\s+(\S+)", DER))
unknown = sorted(tok(DER) - tok(POOL) - defc)
if unknown: fails.append(f"unknown tokens: {unknown}")

names = re.findall(r"\(defconst\s+(\S+)\s+(-?\d+)\)", DER)
seen = {}
for n, v in names:
    if n in seen and seen[n] != v: fails.append(f"defconst {n}: {seen[n]} -> {v}")
    seen[n] = v

print("FAIL:\n" + "\n".join(fails) if fails else "ALL CHECKS PASS")
sys.exit(1 if fails else 0)
