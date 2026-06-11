"""Round 2: single-feature-ON and promising combos."""
FLAGS = ["FP_PIN_TREB", "FP_PIN_RELIC", "FP_MIL_MOVES", "FP_EXCL_VIL",
         "FP_SIEGE_FENCE", "FP_PIN_SLOT"]


def run(combo_name, on):
    u = reload_uc()
    for f in FLAGS:
        setattr(u, f, f in on)
    txt = score_all(verbose=False)
    print(f"--- ON: {combo_name} ---")
    print(txt)


for f in FLAGS:
    run(f, [f])
run("TREB+SLOT", ["FP_PIN_TREB", "FP_PIN_SLOT"])
run("TREB+RELIC+EXCL", ["FP_PIN_TREB", "FP_PIN_RELIC", "FP_EXCL_VIL"])
run("all but SLOT", [f for f in FLAGS if f != "FP_PIN_SLOT"])
run("all but SLOT,MOVES", [f for f in FLAGS if f not in ("FP_PIN_SLOT", "FP_MIL_MOVES")])
run("all but SLOT,TREB", [f for f in FLAGS if f not in ("FP_PIN_SLOT", "FP_PIN_TREB")])
run("EXCL+FENCE", ["FP_EXCL_VIL", "FP_SIEGE_FENCE"])
run("EXCL+RELIC", ["FP_EXCL_VIL", "FP_PIN_RELIC"])
