"""aoe2x — the AoE2:DE data-engine library.

Layered packages (each independently consumable; downstream only refers
upstream):

    aoe2x.extract   patch-dependent .dat extraction          (layer 2)
    aoe2x.grpc      live-game gRPC capture/decode            (layer 2)
    aoe2x.dbgen     golden-database generators               (layer 3)
    aoe2x.sim       battle-simulation engines                (layer 4)
    aoe2x.advisor   matchup advisor                          (layer 4)
    aoe2x.rank      unit ranking / pool scoring              (layer 4)
    aoe2x.batch     batch sim runners + patch pipeline       (layer 4)
    aoe2x.replay    replay-understanding classifier + viewer (layer 4/5)

Committed golden data artifacts live in data/golden/ (see aoe2x.paths).
"""
