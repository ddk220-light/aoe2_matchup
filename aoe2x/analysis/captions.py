"""Template 'why' captions from classification factors + real stat values.

Basic but correct: expected/unexpected win/counter each get a template that
cites the real bonus pairs (from the ref DB attacks/armors) or, for no-bonus
upsets, a hidden-mechanic phrase read off the ability columns.
"""


def _fmt_bonuses(pairs):
    return ", ".join(f"+{int(amt)} vs {cls}" for cls, amt in pairs)


def hidden_mechanics(row):
    """Human phrases for ability columns that explain no-bonus upsets.
    `row` is a dict-like ref_units row (sqlite3.Row or plain dict)."""
    out = []
    if row["armor_strip_per_hit"]:
        out.append(f"strips {int(row['armor_strip_per_hit'])} armor per hit")
    if row["charge_attack_melee"]:
        out.append(f"+{int(row['charge_attack_melee'])} charged attack"
                   f" every {int(row['charge_recharge_time'])}s")
    if row["bleed_dps"]:
        out.append(f"bleed {int(row['bleed_dps'])} dps for"
                   f" {int(row['bleed_duration'])}s (ignores armor)")
    if row["trample_percent"]:
        out.append(f"trample splash ({int(row['trample_percent'])}%)")
    if row["splash_on_hit_radius"]:
        out.append("splash damage on hit")
    if row["attack_bonus_per_kill"]:
        out.append(f"+{int(row['attack_bonus_per_kill'])} attack per kill")
    if row["dodge_shield_max"]:
        out.append(f"dodges first {int(row['dodge_shield_max'])} hits")
    return out


def why_caption(r, *, subject_name, opp_name, subject_bonus_vs_opp,
                opp_bonus_vs_subject, mechanics):
    cat = r["category"]
    if cat == "expected_win":
        if subject_bonus_vs_opp:
            return (f"{subject_name}'s {_fmt_bonuses(subject_bonus_vs_opp)} "
                    f"applies — {opp_name} melts.")
        return f"No counter relationship — {subject_name} simply out-stats it."
    if cat == "unexpected_win":
        if opp_bonus_vs_subject:
            return (f"{opp_name} lands {_fmt_bonuses(opp_bonus_vs_subject)} all "
                    f"fight — {subject_name} tanks it and wins with "
                    f"{max(int(r['S']), 0)}% of the army left.")
        return f"The prior said no — {subject_name} wins anyway."
    if cat == "expected_counter":
        if r["kited"]:
            return (f"{opp_name} kites — {subject_name} never gets to swing. "
                    f"Range beats slow melee, no bonus needed.")
        if opp_bonus_vs_subject:
            return (f"The textbook answer: {opp_name}'s "
                    f"{_fmt_bonuses(opp_bonus_vs_subject)} shreds {subject_name}.")
        return f"{opp_name} is simply the wrong fight to take."
    # unexpected_counter
    if mechanics:
        return (f"No meaningful bonus either way — but {opp_name} "
                f"{mechanics[0]}, and the 'safe' brawl falls apart.")
    return (f"A straight melee fight {subject_name} should survive — "
            f"{opp_name} wins it on raw output.")
