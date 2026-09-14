from aoe2x.lab.postprocess_campaign import can_schedule, comparison_failures


def test_parallel_capacity_is_per_lane_and_never_duplicates():
    active = {("simulation", str(i)): None for i in range(5)}
    active[("overlay", "x")] = None
    assert can_schedule(active, {}, "simulation", 6)
    assert not can_schedule(active, {}, "overlay", 6)
    active[("simulation", "sixth")] = None
    assert not can_schedule(active, {}, "simulation", 6)
    for status in ("running", "complete", "failed"):
        assert not can_schedule({}, {"simulation": {"status": status}}, "simulation", 6)


def test_requested_failure_cutoff_and_wrong_winner():
    def row(delta, agreement, status="complete"):
        return {"jobId": str(delta), "civ": "Wei", "unit": "Opponent", "simulation": {
            "status": status, "seeds": [None]*5, "winnerAgreement": agreement,
            "deltaPoints": delta, "liveWinner": 2}}
    rows = comparison_failures({"jobs": [row(20,5),row(-20,5),row(20.01,5),row(-21,5),row(2,4),row(80,0,"failed")]})
    assert [r["deltaPoints"] for r in rows] == [20.01,-21,2]
    assert [r["wrongWinners"] for r in rows] == [0,0,1]
