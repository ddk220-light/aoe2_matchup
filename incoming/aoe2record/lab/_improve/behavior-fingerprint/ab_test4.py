def run(name, **kw):
    u = reload_uc()
    for k, v in kw.items():
        setattr(u, k, v)
    print(f"--- {name} ---")
    print(score_all(verbose=False))


run("base")
run("BATCH_PAIRS", FP_BATCH_PAIRS=True)
