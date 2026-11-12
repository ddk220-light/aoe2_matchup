"""Evaluate one head-to-head pair from the compiled runtime database.

Pure data accounting (no web framework). It reproduces what the former
``apps/website/services/army_context.py`` computed for a Battle Sim pair on
branch ``matchup-timings`` and adds the research breakdown the owner asked for
on 2026-11-12: for each army the *common* research (in the headline), the
*exclusive* research (the unshared part) and the *full* research package, each
with net cost, weighted cost, weighted villager-minutes and summed research time.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

from aoe2x.economy.accounting import (
    CONTEXT_SCHEMA_VERSION, add_costs, army_investment, compare_research, investment_comparison,
    queue_seconds, research_infrastructure, research_summary, research_totals, select_investment_route,
)
from aoe2x.economy.paths import RUNTIME_DB


class RuntimeData:
    """Read-only access to ``army_context.db`` (metadata, civilizations, units)."""

    def __init__(self, path=RUNTIME_DB):
        self.path = Path(path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"Army context database not found: {self.path}")
        self.metadata = self._read("metadata", ())
        if self.metadata.get("schemaVersion") != CONTEXT_SCHEMA_VERSION:
            raise ValueError("Unsupported army context schema")

    @lru_cache(maxsize=4096)
    def _read(self, table, keys):
        predicates = {"metadata": "id=1", "civilizations": "civ=?", "units": "civ=? AND unit_id=? AND mode=?"}
        with sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True) as db:
            row = db.execute(f"SELECT payload FROM {table} WHERE {predicates[table]}", keys).fetchone()
        if row is None:
            raise KeyError(f"{table} row missing: {keys}")
        return json.loads(row[0])

    def unit(self, civ, unit_id, mode="default"):
        return self._read("units", (civ, unit_id, mode))

    def civilization(self, civ):
        return self._read("civilizations", (civ,))

    def keys(self):
        with sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True) as db:
            return [tuple(r) for r in db.execute("SELECT civ, unit_id, mode FROM units ORDER BY civ, unit_id, mode")]


def _team(data, selection, population):
    civ, unit_id, mode, count = selection
    unit = deepcopy(data.unit(civ, unit_id, mode))
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count < len(unit["lookup"]):
        raise ValueError("count must be an integer between 0 and 27")
    unit["count"] = count
    unit["lookup"] = unit["lookup"][:count + 1]
    unit["startingArmy"] = unit["lookup"][count]
    spare = unit["startingArmy"]["surplusUnits"]
    unit["replacementLookup"] = []
    for n in range(count + 1):
        credited = min(n, spare)
        replacement = deepcopy(unit["lookup"][n - credited])
        replacement.update(count=n, initialSurplusUsed=credited,
                           surplusUnits=spare - credited + replacement["surplusUnits"])
        unit["replacementLookup"].append(replacement)
    unit["economy"] = deepcopy(data.civilization(civ))
    for package in ("military", "production", "economicSetup"):
        for tech in unit["research"][package]["technologies"]:
            variable = tech.get("variableCost")
            if variable and population is not None:
                tech["upfront"] = {r: v + variable["perVillager"][r] * population for r, v in variable["base"].items()}
                tech["net"] = {r: v - tech["refund"][r] for r, v in tech["upfront"].items()}
                tech["populationInput"] = population
                tech["costIsFixed"] = variable["status"] == "validated"
        unit["research"][package]["totals"] = research_totals(unit["research"][package]["technologies"])
    return unit


def evaluate_matchup(data, left, right, populations=(None, None)):
    """``left``/``right`` are ``(civ, unit_id, mode, count)``.

    Headline: army bill + 60-second production buildings + net cost of the
    research both armies share (common technology IDs), in weighted
    villager-minutes. ``researchSummary`` reports common / exclusive / full.
    """
    for population in populations:
        if population is not None and (isinstance(population, bool) or not isinstance(population, int)
                                       or not 0 <= population <= 1000):
            raise ValueError("convertedVillagers must be integers between 0 and 1000, or null")
    teams = [_team(data, selection, population) for selection, population in zip((left, right), populations)]
    comparison = compare_research(teams[0]["research"]["military"]["technologies"],
                                  teams[1]["research"]["military"]["technologies"])
    for index, unit in enumerate(teams):
        common = comparison["common"][index]
        prices = unit["economy"]["laborPrices"]
        start = unit["startingArmy"]
        production, alternatives = select_investment_route(
            unit["productionRoutes"], start["orders"], unit["pricing"]["unitsPerPurchase"],
            add_costs(start["cost"], common["net"]), prices)
        unit.update(production=production, alternativeRoutes=alternatives)
        unit["investment"] = army_investment(start["cost"], production, common, prices)
        for entry in unit["lookup"] + unit["replacementLookup"]:
            entry["trainingSeconds"] = queue_seconds(entry["orders"], production)
        research = unit["research"]
        all_techs = []
        for package in ("military", "production", "economicSetup"):
            ts = research[package]["technologies"]
            all_techs.extend(ts)
            research[package]["infrastructure"] = research_infrastructure(ts, production)
        research["infrastructure"] = research_infrastructure(
            research["military"]["technologies"] + research["production"]["technologies"], production)
        research["allInfrastructure"] = research_infrastructure(all_techs, production)
        unit["researchSummary"] = {
            "common": research_summary(common, prices),
            "exclusive": research_summary(comparison["exclusive"][index], prices),
            "full": research_summary(research["military"]["totals"], prices),
            "inHeadline": "common",
        }
    return {"schemaVersion": CONTEXT_SCHEMA_VERSION,
            "trainingWindowSeconds": data.metadata["trainingWindowSeconds"],
            "resourceWeights": data.metadata["resourceWeights"],
            "contextVersion": data.metadata["contextVersion"],
            "status": "estimate" if data.metadata["releaseReady"] else "review",
            "releaseReady": data.metadata["releaseReady"],
            "assumptions": data.metadata["assumptions"], "teams": teams,
            "scopeExceptions": data.metadata.get("scopeExceptions", []),
            "auraAssumption": data.metadata.get("auraAssumption"),
            "investmentComparison": investment_comparison(teams), "researchComparison": comparison}
