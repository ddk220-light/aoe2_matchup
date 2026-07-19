"""ddkCircleModel.per = production alias of the proven ddkSquareV25 (continuous clockwise
square patrol for a ranged-unit ball).  V25 is the working baseline; ddkCircleModel is the
name used as the RANGED-unit personality in the matchup templates/scenarios.

Content is byte-for-byte V25 except the leading comment identifiers are renamed
ddkSquareV25/V24 -> ddkCircleModel so the file self-documents.  The AI's in-game name comes
from the FILENAME, so this deploys as ddkCircleModel(.per/.ai).
"""
import io
SRC=r"apps\video\ai_experiments\ddkSquareV25.per"
DST=r"apps\video\ai_experiments\ddkCircleModel.per"
text=io.open(SRC,encoding="utf-8",newline="").read()
# comment-only identifier renames (goal names/logic untouched)
text=text.replace("ddkSquareV25","ddkCircleModel").replace("ddkSquareV24","ddkCircleModel(V24)")
io.open(DST,"w",encoding="utf-8",newline="").write(text)
print(f"wrote {DST}: {text.count('(defrule')} defrules (expect 133)")
