"""ddkMatchupAI.per = THE production matchup AI (byte-identical logic to ddkSquareV25).

ddkSquareV25 is the final proven square-patrol AI (continuous clockwise A->B->D->C loop,
arrival-gated march, -1-default-safe init) used by all golden matchup templates.
ddkMatchupAI is its production name; only the leading comment identifiers change.
(ddkCircleModel / ddkCircleModelCCW remain as earlier aliases; CCW is the reversed loop.)
"""
import io
SRC=r"apps\video\ai_experiments\ddkSquareV25.per"
DST=r"apps\video\ai_experiments\ddkMatchupAI.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
text=text.replace("ddkSquareV25","ddkMatchupAI").replace("ddkSquareV24","ddkMatchupAI(V24)")
io.open(DST,"w",encoding="utf-8",newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 133)")
