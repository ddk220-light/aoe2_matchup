"""Create ddkTesterAI3.per = ddkTesterAI2.per + ONE offset-safe token swap so SMALL groups
kite tighter / fire more instead of over-fleeing.

Rule #2170, line 36443: var124 = max(2, var104 / 7)  -> change the divisor 7 -> 12.
var104 = group unit count; var124 = allies-at-front required to keep firing. A bigger divisor
keeps var124 pinned at its floor of 2 for larger groups, so small groups stay willing to shoot.
Byte-level edit -> CRLF preserved, rule count unchanged (9736), all up-jump-direct indices valid.
"""
import os, sys

AI = r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\ai"
SRC = os.path.join(AI, "ddkTesterAI2.per")
DST = os.path.join(AI, "ddkTesterAI3.per")

EDITS = [
    (36443, b"varTmp4145 c:/ 7)", b"varTmp4145 c:/ 12)"),
]

raw = open(SRC, "rb").read()
assert b"\r\n" in raw, "source not CRLF?!"
lines = raw.split(b"\r\n")
rules_before = sum(ln.count(b"(defrule") for ln in lines)

for lineno, want, repl in EDITS:
    i = lineno - 1
    if lines[i].count(want) != 1:
        sys.exit(f"ABORT line {lineno}: '{want}' count={lines[i].count(want)} in {lines[i]!r}")
    assert b"\r" not in lines[i], f"line {lineno} has stray CR"
    lines[i] = lines[i].replace(want, repl)

out = b"\r\n".join(lines)
open(DST, "wb").write(out)

chk = open(DST, "rb").read()
rules_after = sum(ln.count(b"(defrule") for ln in chk.split(b"\r\n"))
lonelf = chk.count(b"\n") - chk.count(b"\r\n")
print(f"rules: {rules_before} -> {rules_after}  {'OK' if rules_before==rules_after else 'MISMATCH'}")
print(f"CRLF:  src={raw.count(chr(13).encode()+chr(10).encode())} dst={chk.count(b'\r\n')}  lone-LF={lonelf}  {'OK' if lonelf==0 else 'BAD'}")
print(f"size:  {len(raw)} -> {len(chk)}  (delta {len(chk)-len(raw):+d})")
sl, dl = raw.split(b"\r\n"), chk.split(b"\r\n")
diff = [i+1 for i in range(len(sl)) if sl[i] != dl[i]]
print(f"differing lines: {len(diff)} -> {diff}")
for lineno, _, _ in EDITS:
    print(f"  {lineno}: {dl[lineno-1].decode('latin-1').strip()}")
