"""Discovered schema patches for gameVersion 177723 (new-patch model drift).
Each entry: model_type -> {field_idx: ('scalar', rust) | ('string',) | ('ref',)}.
Discovered empirically by tracing first_patch_seg2.bin and resolving each desync.

NOTE for the World.entities path (path A, recommended): you do NOT need the
master-entity patches below to recover initial entities. The Entity model
(types 9-14) is STABLE across 177723. Only the GameOptions/PlayerGameOptions
patches matter if you parse the snapshot head; the master-entity definitions
(types 16-21, 47, 49) are the drift zone and are best SKIPPED by seeking
straight to the World.entities band (see decode guidance).
"""

PATCHES = {
    35: {  # GameOptions  (confirmed: snapshot head)
        48: ("scalar", "f32"),   # observed 1.69; sits between ending_age(15) and player_info(17)
        50: ("scalar", "u8"),    # observed 0x01  (guessed width, low confidence)
        51: ("scalar", "i32"),   # observed 2     (guessed width, low confidence)
    },
    36: {  # PlayerGameOptions  (confirmed: snapshot head, player slots)
        18: ("scalar", "i32"),   # observed 100 (0x64) on every player slot
        19: ("scalar", "u64"),   # steam_id-like u64; 0xffffffffffffffff for AI/gaia slots
    },
    # ---- master-entity drift zone (only needed if decoding master defs in place) ----
    # These are GUESSED widths from lookahead; treat as low-confidence. The new model
    # types 47 and 49 have entirely unknown field layouts. Prefer skipping this region.
    1: {   # World
        29: ("scalar", "i32"),   # new World field, observed 2
    },
}


def apply(schema):
    for ty, fields in PATCHES.items():
        schema.setdefault(ty, {})
        for f, kind in fields.items():
            schema[ty][f] = kind
    return schema
