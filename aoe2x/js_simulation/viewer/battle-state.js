const RANGED_CLASSES = new Set(["mobile_ranged", "siege_ranged"]);
const ROLE_CLASS_BY_FAMILY = Object.freeze({
  kite: "mobile_ranged",
  siege: "siege_ranged",
});


export function soloMovementRequest(urlValue) {
  let url;
  try {
    url = new URL(urlValue, "http://127.0.0.1/");
  } catch {
    return null;
  }
  const keys = [...url.searchParams.keys()];
  if (keys.some((key) => key !== "mode" && key !== "navigation")) return null;
  if (!keys.includes("mode") || url.searchParams.getAll("mode").length !== 1
      || url.searchParams.getAll("navigation").length > 1) return null;
  const values = url.searchParams.getAll("mode");
  if (values.length !== 1 || values[0] !== "hand-cannoneer-solo-movement") return null;
  const navigation = url.searchParams.get("navigation") ?? "cohesive";
  if (!["baseline", "per-unit-grid", "cohesive"].includes(navigation)) return null;
  return Object.freeze({
    endpoint: "api/solo-hand-cannoneers",
    navigation,
    query: `navigation=${navigation}`,
  });
}


function requireTeam(team) {
  if (team !== 1 && team !== 2) throw new RangeError(`team must be 1 or 2, got ${team}`);
}


function cloneTeams(state, team, replacement) {
  return Object.freeze({ ...state, teams: Object.freeze({ ...state.teams, [team]: replacement }) });
}


function familyFor(leftClass, rightClass) {
  if (RANGED_CLASSES.has(leftClass) && RANGED_CLASSES.has(rightClass)) return "rvr";
  if (leftClass === "mobile_ranged" || rightClass === "mobile_ranged") return "kite";
  if (leftClass === "siege_ranged" || rightClass === "siege_ranged") return "siege";
  return "waves";
}


export function createBattleState({ catalogue, units }) {
  if (catalogue?.schemaVersion !== 1 || !Array.isArray(catalogue.civilizations)) {
    throw new TypeError("invalid viewer catalogue");
  }
  if (!units?.capacityByFamily) throw new TypeError("unit capacities are required");
  const enabledByKey = new Map((catalogue.enabled ?? []).map((row) => [row.catalogueKey, row]));
  const catalogueByCiv = new Map(catalogue.civilizations.map((civilization) => [
    civilization.name,
    civilization,
  ]));
  return Object.freeze({
    catalogue,
    units,
    enabledByKey,
    catalogueByCiv,
    teams: Object.freeze({
      1: Object.freeze({ civ: null, catalogueKey: null, engineSlug: null, name: null, class: null }),
      2: Object.freeze({ civ: null, catalogueKey: null, engineSlug: null, name: null, class: null }),
    }),
    mode: "count",
    counts: Object.freeze({ 1: 21, 2: 21 }),
    budget: 3000,
  });
}


export function selectCivilization(state, team, civ) {
  requireTeam(team);
  if (!state.catalogueByCiv.has(civ)) throw new RangeError(`unknown civilization ${civ}`);
  return cloneTeams(state, team, Object.freeze({
    civ, catalogueKey: null, engineSlug: null, name: null, class: null,
  }));
}


export function selectUnit(state, team, catalogueKey) {
  requireTeam(team);
  const enabled = state.enabledByKey.get(catalogueKey);
  if (!enabled) throw new RangeError(`unit ${catalogueKey} is not calibrated`);
  if (state.teams[team].civ !== enabled.civ) {
    throw new RangeError(`${enabled.name} does not belong to selected civilization ${state.teams[team].civ}`);
  }
  return cloneTeams(state, team, Object.freeze({
    civ: enabled.civ,
    catalogueKey,
    engineSlug: enabled.engineSlug,
    name: enabled.name,
    class: enabled.class,
  }));
}


export function unitsForCivilization(state, civ) {
  const civilization = state.catalogueByCiv.get(civ);
  if (!civilization) return [];
  return civilization.units.map((unit) => {
    const enabled = state.enabledByKey.get(unit.catalogueKey);
    return Object.freeze({ ...unit, enabled: Boolean(enabled), engineSlug: enabled?.engineSlug ?? null });
  });
}


export function searchCatalogue(state, rawQuery, limit = 40) {
  const query = String(rawQuery ?? "").trim().toLowerCase();
  if (!query) return [];
  const matches = [];
  for (const civilization of state.catalogue.civilizations) {
    if (civilization.name.toLowerCase().includes(query)) {
      matches.push(Object.freeze({
        type: "civilization", name: civilization.name, civ: civilization.name, enabled: true,
      }));
    }
    for (const unit of civilization.units) {
      if (!`${unit.name} ${civilization.name}`.toLowerCase().includes(query)) continue;
      const enabled = state.enabledByKey.get(unit.catalogueKey);
      matches.push(Object.freeze({
        type: "unit",
        name: unit.name,
        civ: civilization.name,
        catalogueKey: unit.catalogueKey,
        enabled: Boolean(enabled),
        engineSlug: enabled?.engineSlug ?? null,
      }));
    }
  }
  return matches.slice(0, limit);
}


export function selectionCapacity(state) {
  const leftClass = state.teams[1].class;
  const rightClass = state.teams[2].class;
  if (!leftClass || !rightClass) {
    return { family: null, team1: 21, team2: 21, orientationNormalised: false };
  }
  const family = familyFor(leftClass, rightClass);
  const internal = state.units.capacityByFamily[family];
  if (!internal) throw new RangeError(`missing capacity for ${family}`);
  const roleClass = ROLE_CLASS_BY_FAMILY[family];
  const orientationNormalised = roleClass !== undefined && rightClass === roleClass;
  return Object.freeze({
    family,
    team1: orientationNormalised ? internal.side3 : internal.side2,
    team2: orientationNormalised ? internal.side2 : internal.side3,
    orientationNormalised,
  });
}


export function setArmyCount(state, team, count) {
  requireTeam(team);
  const capacity = selectionCapacity(state)[`team${team}`];
  if (!Number.isSafeInteger(count) || count < 1 || count > capacity) {
    throw new RangeError(`count must be an integer 1-${capacity}, got ${count}`);
  }
  return Object.freeze({ ...state, counts: Object.freeze({ ...state.counts, [team]: count }) });
}


export function setBattleMode(state, mode) {
  if (mode === "resources_upgrades") throw new RangeError("upgrade-inclusive mode is not calibrated");
  if (mode !== "count" && mode !== "resources") throw new RangeError(`unknown battle mode ${mode}`);
  return Object.freeze({ ...state, mode });
}


export function setResourceBudget(state, budget) {
  if (!Number.isSafeInteger(budget) || budget < 100 || budget > 20000) {
    throw new RangeError(`budget must be an integer 100-20000, got ${budget}`);
  }
  return Object.freeze({ ...state, budget });
}


export function buildFightQuery(state) {
  const left = state.teams[1];
  const right = state.teams[2];
  if (!left.engineSlug || !right.engineSlug) throw new RangeError("both teams need calibrated units");
  const params = new URLSearchParams();
  params.set("side2", left.engineSlug);
  params.set("side3", right.engineSlug);
  if (state.mode === "resources") {
    params.set("budget", String(state.budget));
  } else {
    params.set("n2", String(state.counts[1]));
    params.set("n3", String(state.counts[2]));
  }
  return params.toString();
}
