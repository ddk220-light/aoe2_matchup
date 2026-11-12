"""Read-only, versioned army context. No solver or review database at runtime."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

from aoe2x.army_economics import (
    CONTEXT_SCHEMA_VERSION, add_costs, army_investment, compare_research, investment_comparison,
    queue_seconds, research_infrastructure, research_totals, select_investment_route,
)
from aoe2x.dbgen.v3_mechanics import mechanics_hash


class ContextUnavailable(RuntimeError):
    pass


def _stamp(path):
    try:
        p = Path(path).resolve()
        s = p.stat()
        return str(p), s.st_mtime_ns, s.st_size
    except (OSError, TypeError) as exc:
        raise ContextUnavailable("Army context database unavailable") from exc


@lru_cache(maxsize=256)
def _read(stamp, table, keys=()):
    predicates = {"metadata": "id=1", "civilizations": "civ=?",
                  "units": "civ=? AND unit_id=? AND mode=?"}
    try:
        with sqlite3.connect(Path(stamp[0]).as_uri() + "?mode=ro", uri=True) as db:
            row = db.execute(f"SELECT payload FROM {table} WHERE {predicates[table]}", keys).fetchone()
        if row is None:
            raise ContextUnavailable("Selected unit is missing army context")
        return json.loads(row[0])
    except (sqlite3.DatabaseError, ValueError) as exc:
        raise ContextUnavailable("Army context database is invalid") from exc


class ArmyContext:
    def __init__(self, path, mode):
        if mode not in ("review", "released"):
            raise ContextUnavailable("Army economics is disabled")
        self.stamp = _stamp(path)
        self.metadata = _read(self.stamp, "metadata")
        self.mode = mode
        if self.metadata.get("schemaVersion") != CONTEXT_SCHEMA_VERSION:
            raise ContextUnavailable("Unsupported army context schema")
        if mode == "released" and not self.metadata.get("releaseReady"):
            raise ContextUnavailable("Army economics has unresolved release requirements")

    def unit(self, team):
        unit = _read(self.stamp, "units", (team["civ"], team["mechanics"]["unit_master"], team["mode"]))
        original_hash = team.get("sourceMechanicsHash", team["mechanics_hash"])
        if unit["sourceMechanicsHash"] != original_hash:
            raise ContextUnavailable("Army context and combat data versions differ")
        return unit

    def apply_cost(self, team):
        """One cost policy for both count resolution and the economy display."""
        unit = self.unit(team)
        team["sourceMechanicsHash"] = team["mechanics_hash"]
        team["mechanics"]["cost"] = {
            r: unit["pricing"]["physicalUnitCost"][r] for r in ("food", "wood", "gold")}
        team["mechanics_hash"] = mechanics_hash(team["mechanics"])
        team["armyContextVersion"] = self.metadata["contextVersion"]

    def response(self, config, populations=None):
        populations = [None, None] if populations is None else populations
        if not isinstance(populations, list) or len(populations) != 2:
            raise ValueError("convertedVillagers must contain two optional population counts")
        for population in populations:
            if population is not None and (isinstance(population, bool) or not isinstance(population, int)
                                           or not 0 <= population <= 1000):
                raise ValueError("convertedVillagers must be integers between 0 and 1000, or null")
        teams = []
        for team, population in zip(config["teams"], populations):
            unit = deepcopy(self.unit(team))
            unit["count"] = team["count"]
            unit["lookup"] = unit["lookup"][:team["count"] + 1]
            unit["startingArmy"] = unit["lookup"][team["count"]]
            spare = unit["startingArmy"]["surplusUnits"]
            unit["replacementLookup"] = []
            for count in range(team["count"] + 1):
                credited = min(count, spare)
                replacement = deepcopy(unit["lookup"][count - credited])
                replacement.update(count=count, initialSurplusUsed=credited,
                                   surplusUnits=spare - credited + replacement["surplusUnits"])
                unit["replacementLookup"].append(replacement)
            unit["mechanicsHash"] = team["mechanics_hash"]
            economy = deepcopy(_read(self.stamp, "civilizations", (team["civ"],)))
            unit["economy"] = economy
            for package in ("military", "production", "economicSetup"):
                for tech in unit["research"][package]["technologies"]:
                    variable = tech.get("variableCost")
                    if variable and population is not None:
                        tech["upfront"] = {r: v + variable["perVillager"][r] * population
                                           for r, v in variable["base"].items()}
                        tech["net"] = {r: v - tech["refund"][r] for r, v in tech["upfront"].items()}
                        tech["populationInput"] = population
                        # Supplied population resolves the variable, not the
                        # outstanding compiled-engine validation dependency.
                        tech["costIsFixed"] = variable["status"] == "validated"
                unit["research"][package]["totals"] = research_totals(unit["research"][package]["technologies"])
            teams.append(unit)
        comparison = compare_research(teams[0]["research"]["military"]["technologies"],
                                      teams[1]["research"]["military"]["technologies"])
        for index, unit in enumerate(teams):
            common = comparison["common"][index]
            start = unit["startingArmy"]
            production, alternatives = select_investment_route(
                unit["productionRoutes"], start["orders"], unit["pricing"]["unitsPerPurchase"],
                add_costs(start["cost"], common["net"]), unit["economy"]["laborPrices"])
            unit.update(production=production, alternativeRoutes=alternatives)
            unit["investment"] = army_investment(start["cost"], production, common, unit["economy"]["laborPrices"])
            # Replacement queues reuse the starting army's buildings and techs.
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
        return {"schemaVersion": CONTEXT_SCHEMA_VERSION,
                "trainingWindowSeconds": self.metadata["trainingWindowSeconds"],
                "resourceWeights": self.metadata["resourceWeights"],
                "contextVersion": self.metadata["contextVersion"],
                "status": "review" if not self.metadata["releaseReady"] else
                          "validated" if self.metadata.get("gatheringValidation", {}).get("status") == "validated" else "estimate",
                "releaseReady": self.metadata["releaseReady"], "source": self.metadata["source"],
                "gatheringValidationPolicy": self.metadata.get("gatheringValidationPolicy"),
                "assumptions": self.metadata["assumptions"], "teams": teams,
                "scopeExceptions": self.metadata.get("scopeExceptions", []),
                "auraAssumption": self.metadata.get("auraAssumption"),
                "investmentComparison": investment_comparison(teams), "researchComparison": comparison}
