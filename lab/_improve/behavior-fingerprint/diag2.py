"""Diag2: claims for wR.Baxter (train) + truth ids for compbow/militia/scout."""
u = reload_uc()
u.UC_DEBUG_CLAIMS = dbg = []
ctx = u._run(MTS["train"])
tn = {int(k): (v.get("type"), round((v.get("created_ms") or 0) / 1000))
      for k, v in LBL["train"].items()}

P = "wR.Baxter"
print("--- truth wR.Baxter units of interest (id, type, created) ---")
for k, (t, cr) in sorted(tn.items()):
    if t in ("Composite Bowman", "Militia", "Scout Cavalry", "Trebuchet") and 1900 < cr < 2300:
        g = ctx.guesses.get(k)
        if g and g.player == P:
            print(f"  {k} {t}@{cr} pred={g.type}/{g.type_conf} fs={g.behavior.get('first_seen')} "
                  f"sig={g.signals} hm={bool(g.behavior.get('hard_mil'))}")

print("\n--- claims for wR.Baxter ---")
for phase, player, L, mm in dbg:
    if player != P or L not in ("unique", "inf", "cav"):
        continue
    items = sorted(mm.items())
    print(f"{phase} {L}: " + ", ".join(
        f"{c}->{t}(truth={tn.get(c, ('?',))[0]})" for c, t in items))
