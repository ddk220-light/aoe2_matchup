"""User-approved analysis scope; exclusions never become validation evidence.

2026-11-12: the Berber Xebec and Chinese Fire Ship waivers were removed; those
roster rows are now dropped by the owner (curated.PROFILE_DROPS).
"""

DECISION_DATE = "2026-11-11"
AURA_ASSUMPTION = {
    "coverage": 1.0,
    "placementRequired": False,
    "infrastructureCostIncluded": False,
    "stacking": "one applicable benefit",
    "source": "User instruction, 2026-11-11",
}
GATHERING_VALIDATION_POLICY = {
    "requiredForRelease": False,
    "status": "deferred_by_user",
    "decisionDate": DECISION_DATE,
    "source": "User instruction 2026-11-11: forget in-game measurements for now; use estimates and an online pasture rate.",
    "accuracyClaim": "No claim of less-than-1% measured error.",
}


def exclusion_reason(issue):
    if issue["code"] == "dynamic_research_cost_unvalidated" and (
        issue.get("civ"), issue.get("technologyId")
    ) == ("Burgundians", 755):
        return "Flemish Revolution cost verification excluded; variable source formula remains explicitly unverified."
    if issue["code"] == "unresolved_economy_mechanic" and (
        issue.get("civ"), issue.get("technologyId")
    ) == ("Wei", 1061):
        return "Tuntian excluded from villager income; the remaining Wei economy is modeled without its income."
    return None


def excluded_record(issue, reason):
    return {**issue, "status": "excluded_by_user", "decisionDate": DECISION_DATE, "reason": reason}
