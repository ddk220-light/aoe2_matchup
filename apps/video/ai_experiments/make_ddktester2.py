"""Create ddkTesterAI2.per = ddkTesterAI.per + 9 offset-safe token swaps, BYTE-LEVEL so the
original CRLF line endings are preserved exactly (only the 9 target lines may change)."""
import os, sys

AI = r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\ai"
SRC = os.path.join(AI, "ddkTesterAI.per")
DST = os.path.join(AI, "ddkTesterAI2.per")

EDITS = [
    (104756, b"skirmisher",               b"class-conquistador"),
    (104758, b"cavalry-archer",           b"mameluke"),
    (104760, b"elite-kipchak-mercenary",  b"throwing-axeman"),
    (104795, b"skirmisher",               b"class-conquistador"),
    (104817, b"cavalry-archer",           b"mameluke"),
    (104839, b"elite-kipchak-mercenary",  b"throwing-axeman"),
    (104857, b"skirmisher",               b"class-conquistador"),
    (104859, b"cavalry-archer",           b"mameluke"),
    (104861, b"elite-kipchak-mercenary",  b"throwing-axeman"),
]

raw = open(SRC, "rb").read()
assert b"\r\n" in raw, "source not CRLF?!"
lines = raw.split(b"\r\n")          # 115902 parts; join with \r\n reconstructs exactly
rules_before = sum(ln.count(b"(defrule") for ln in lines)

for lineno, old, new in EDITS:
    i = lineno - 1
    want = b"c: " + old + b" c:"
    repl = b"c: " + new + b" c:"
    if lines[i].count(want) != 1:
        sys.exit(f"ABORT line {lineno}: '{want}' count={lines[i].count(want)} in {lines[i]!r}")
    assert b"\r" not in lines[i], f"line {lineno} already has stray CR"
    lines[i] = lines[i].replace(want, repl)

out = b"\r\n".join(lines)
open(DST, "wb").write(out)

# verify
chk = open(DST, "rb").read()
rules_after = sum(ln.count(b"(defrule") for ln in chk.split(b"\r\n"))
crlf_src, crlf_dst = raw.count(b"\r\n"), chk.count(b"\r\n")
lonelf = chk.count(b"\n") - chk.count(b"\r\n")
print(f"rules: {rules_before} -> {rules_after}  {'OK' if rules_before==rules_after else 'MISMATCH'}")
print(f"CRLF:  src={crlf_src} dst={crlf_dst}  lone-LF={lonelf}  {'OK' if crlf_src==crlf_dst and lonelf==0 else 'BAD'}")
print(f"size:  {len(raw)} -> {len(chk)}  (delta {len(chk)-len(raw):+d} bytes)")
# how many lines differ vs source (must be exactly 9)
sl, dl = raw.split(b"\r\n"), chk.split(b"\r\n")
diff = [i+1 for i in range(len(sl)) if sl[i] != dl[i]]
print(f"differing lines: {len(diff)} -> {diff}")
for lineno, _, _ in EDITS:
    print(f"  {lineno}: {dl[lineno-1].decode('latin-1').strip()}")
