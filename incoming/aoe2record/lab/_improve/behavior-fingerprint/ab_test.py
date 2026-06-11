"""A/B the previous attempt's fingerprint features (exec'd inside the driver)."""
FLAGS = ["FP_PIN_TREB", "FP_PIN_RELIC", "FP_MIL_MOVES", "FP_EXCL_VIL",
         "FP_SIEGE_FENCE", "FP_PIN_SLOT"]


def run(combo_name, off):
    u = reload_uc()
    for f in off:
        setattr(u, f, False)
    txt = score_all(verbose=False)
    print(f"--- {combo_name} ---")
    print(txt)


run("ALL ON (current)", [])
run("ALL OFF (~production)", FLAGS)
for f in FLAGS:
    run(f"OFF: {f}", [f])
