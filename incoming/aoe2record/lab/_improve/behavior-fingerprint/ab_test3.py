"""A/B: claim order + phase-2 pin slots."""
def run(name, **kw):
    u = reload_uc()
    for k, v in kw.items():
        setattr(u, k, v)
    print(f"--- {name} ---")
    print(score_all(verbose=False))


run("base (current)")
run("CLAIM_ORDER", FP_CLAIM_ORDER=True)
run("PIN_SLOT_P2", FP_PIN_SLOT_P2=True)
run("both", FP_CLAIM_ORDER=True, FP_PIN_SLOT_P2=True)
