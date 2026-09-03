import {
  buildFightQuery,
  createBattleState,
  searchCatalogue,
  selectCivilization,
  selectUnit,
  selectionCapacity,
  setArmyCount,
  setBattleMode,
  setResourceBudget,
  unitsForCivilization,
} from "./battle-state.js";


const CIV_EMBLEM_BASE = "https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/";
const BUILDING_ORDER = ["Barracks", "Archery Range", "Stable", "Siege Workshop", "Monastery", "Castle", "Dock"];
const CLASS_TO_BUILDING = Object.freeze({
  Infantry: "Barracks",
  Archer: "Archery Range",
  "Cavalry Archer": "Archery Range",
  Cavalry: "Stable",
  "Siege Weapon": "Siege Workshop",
  Monk: "Monastery",
  Ship: "Dock",
});


const byId = (id) => document.getElementById(id);


function unitImage(name) {
  try {
    return typeof window.spriteFor === "function" ? window.spriteFor(name) : "";
  } catch {
    return "";
  }
}


function image(src, alt, className = "") {
  const node = document.createElement("img");
  node.src = src;
  node.alt = alt;
  if (className) node.className = className;
  node.addEventListener("error", () => { node.hidden = true; }, { once: true });
  return node;
}


function selectionBadge({ kind, name, subtitle, onChange }) {
  const row = document.createElement("div");
  row.className = "selection-badge";
  const src = kind === "civ"
    ? `${CIV_EMBLEM_BASE}${name.toLowerCase()}.png`
    : unitImage(name);
  if (src) row.append(image(src, name, kind === "unit" ? "sprite" : ""));
  const meta = document.createElement("span");
  meta.className = "selection-meta";
  const label = document.createElement("span");
  label.className = "badge-text";
  label.textContent = name;
  meta.append(label);
  if (subtitle) {
    const small = document.createElement("small");
    small.textContent = subtitle;
    meta.append(small);
  }
  const change = document.createElement("button");
  change.type = "button";
  change.className = "change-btn";
  change.textContent = "change";
  change.addEventListener("click", onChange);
  row.append(meta, change);
  return row;
}


function groupUnits(units) {
  const groups = new Map();
  for (const unit of units) {
    const building = unit.type === "unique"
      ? "Castle"
      : (CLASS_TO_BUILDING[unit.className] ?? "Castle");
    if (!groups.has(building)) groups.set(building, []);
    groups.get(building).push(unit);
  }
  return groups;
}


export function createBattlePage({ catalogue, units, onStart, onPauseToggle, onNewBattle, onSpeedChange }) {
  let state = createBattleState({ catalogue, units });
  let battleActive = false;
  let busy = false;

  function setHint(message, isError = false) {
    const hint = byId("startHint");
    hint.textContent = message;
    hint.classList.toggle("is-error", isError);
    hint.hidden = false;
  }

  function ready() {
    return Boolean(state.teams[1].engineSlug && state.teams[2].engineSlug);
  }

  function syncReady() {
    byId("startBtn").disabled = busy || !ready();
    if (ready() && !busy) byId("startHint").hidden = true;
    else if (!busy && !ready()) setHint("Pick a calibrated civ & unit for both teams to start");
  }

  function syncCapacity() {
    const capacity = selectionCapacity(state);
    for (const team of [1, 2]) {
      const max = capacity[`team${team}`];
      const input = byId(`team${team}Count`);
      input.max = String(max);
      if (Number(input.value) > max) input.value = String(max);
      byId(`team${team}Limit`).textContent = `Maximum ${max}${capacity.family ? ` · ${capacity.family} formation` : ""}`;
      if (state.counts[team] > max) state = setArmyCount(state, team, max);
    }
  }

  function civCard(civ, team) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "civ-card";
    button.append(image(`${CIV_EMBLEM_BASE}${civ.toLowerCase()}.png`, civ));
    const label = document.createElement("span");
    label.textContent = civ;
    button.append(label);
    button.addEventListener("click", () => {
      state = selectCivilization(state, team, civ);
      renderTeam(team);
      syncCapacity();
      syncReady();
    });
    return button;
  }

  function unitCard(unit, team) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `unit-pick${unit.enabled ? "" : " is-disabled"}`;
    button.disabled = !unit.enabled;
    button.setAttribute("aria-disabled", String(!unit.enabled));
    button.title = unit.enabled ? `Select ${unit.name}` : `${unit.name} · Not yet calibrated`;
    const src = unitImage(unit.name);
    if (src) button.append(image(src, unit.name, "sprite"));
    const text = document.createElement("span");
    text.textContent = unit.name;
    if (!unit.enabled) {
      const status = document.createElement("small");
      status.className = "availability-label";
      status.textContent = "Not yet calibrated";
      text.append(status);
    }
    button.append(text);
    if (unit.enabled) {
      button.addEventListener("click", () => {
        state = selectUnit(state, team, unit.catalogueKey);
        renderTeam(team);
        syncCapacity();
        syncReady();
      });
    }
    return button;
  }

  function renderTeam(team) {
    const container = byId(`team${team}Selection`);
    const selected = state.teams[team];
    container.replaceChildren();
    if (!selected.civ) {
      const grid = document.createElement("div");
      grid.className = "civ-grid";
      for (const civilization of catalogue.civilizations) {
        grid.append(civCard(civilization.name, team));
      }
      container.append(grid);
      return;
    }

    container.append(selectionBadge({
      kind: "civ",
      name: selected.civ,
      onChange: () => {
        state = selectCivilization(state, team, selected.civ);
        state = Object.freeze({
          ...state,
          teams: Object.freeze({
            ...state.teams,
            [team]: Object.freeze({ civ: null, catalogueKey: null, engineSlug: null, name: null, class: null }),
          }),
        });
        renderTeam(team);
        syncCapacity();
        syncReady();
      },
    }));

    if (selected.engineSlug) {
      container.append(selectionBadge({
        kind: "unit",
        name: selected.name,
        subtitle: "Live-capture measured profile",
        onChange: () => {
          state = selectCivilization(state, team, selected.civ);
          renderTeam(team);
          syncCapacity();
          syncReady();
        },
      }));
      return;
    }

    const groups = groupUnits(unitsForCivilization(state, selected.civ));
    for (const building of BUILDING_ORDER) {
      const rows = groups.get(building);
      if (!rows?.length) continue;
      const section = document.createElement("section");
      section.className = "unit-grid-section";
      const heading = document.createElement("h4");
      heading.textContent = building;
      const grid = document.createElement("div");
      grid.className = "unit-grid";
      grid.append(...rows.map((unit) => unitCard(unit, team)));
      section.append(heading, grid);
      container.append(section);
    }
  }

  function clearSearch(team) {
    byId(`team${team}Search`).value = "";
    const results = byId(`team${team}SearchResults`);
    results.hidden = true;
    results.replaceChildren();
  }

  function renderSearch(team) {
    const input = byId(`team${team}Search`);
    const container = byId(`team${team}SearchResults`);
    const matches = searchCatalogue(state, input.value);
    container.replaceChildren();
    if (!input.value.trim()) {
      container.hidden = true;
      return;
    }
    if (!matches.length) {
      const empty = document.createElement("div");
      empty.className = "search-empty";
      empty.textContent = "No civilization or unit matches";
      container.append(empty);
      container.hidden = false;
      return;
    }
    for (const match of matches) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `search-result${match.enabled ? "" : " is-disabled"}`;
      button.disabled = !match.enabled;
      const src = match.type === "civilization"
        ? `${CIV_EMBLEM_BASE}${match.civ.toLowerCase()}.png`
        : unitImage(match.name);
      if (src) button.append(image(src, "", match.type === "civilization" ? "emblem" : ""));
      const name = document.createElement("span");
      name.className = "sr-name";
      name.textContent = match.name;
      const sub = document.createElement("span");
      sub.className = match.enabled ? "sr-sub" : "sr-status";
      sub.textContent = match.enabled
        ? (match.type === "civilization" ? "Civ" : match.civ)
        : "Not calibrated";
      button.append(name, sub);
      if (match.enabled) {
        button.addEventListener("click", () => {
          state = selectCivilization(state, team, match.civ);
          if (match.type === "unit") state = selectUnit(state, team, match.catalogueKey);
          clearSearch(team);
          renderTeam(team);
          syncCapacity();
          syncReady();
        });
      }
      container.append(button);
    }
    container.hidden = false;
  }

  function readOptions() {
    const selectedMode = document.querySelector('input[name="armyMode"]:checked')?.value ?? "count";
    state = setBattleMode(state, selectedMode);
    if (selectedMode === "resources") {
      state = setResourceBudget(state, Number(byId("totalResources").value));
    } else {
      state = setArmyCount(state, 1, Number(byId("team1Count").value));
      state = setArmyCount(state, 2, Number(byId("team2Count").value));
    }
  }

  function updateOptionsSummary() {
    const mode = document.querySelector('input[name="armyMode"]:checked')?.value ?? "count";
    byId("optionsCurrent").textContent = mode === "resources"
      ? `${byId("totalResources").value || "3000"} Resources`
      : `${byId("team1Count").value || "21"} vs ${byId("team2Count").value || "21"}`;
  }

  function setBusy(value) {
    busy = Boolean(value);
    byId("startBtn").textContent = busy ? "Running engine…" : "Start Battle";
    if (busy) setHint("Running the deterministic simulation engine…");
    syncReady();
  }

  function setBattleActive(value) {
    battleActive = Boolean(value);
    byId("simStage").classList.toggle("battle-active", battleActive);
    byId("startBtn").hidden = battleActive;
    byId("battleTimer").hidden = !battleActive;
    byId("simControls").hidden = !battleActive;
    byId("dmgToggle").hidden = !battleActive;
    byId("team1Live").hidden = !battleActive;
    byId("team2Live").hidden = !battleActive;
    byId("startHint").hidden = battleActive || ready();
  }

  function applyFightResult(result) {
    setBusy(false);
    setBattleActive(true);
    byId("simOptions").open = false;
    byId("team1Count").value = String(result.side2.count);
    byId("team2Count").value = String(result.side3.count);
    byId("prog1Name").textContent = `${result.side2.civ} ${result.side2.label}`;
    byId("prog2Name").textContent = `${result.side3.civ} ${result.side3.label}`;
    byId("prog1Units").textContent = String(result.side2.count);
    byId("prog2Units").textContent = String(result.side3.count);
    byId("prog1Res").textContent = state.mode === "resources" ? state.budget.toLocaleString() : "Custom count";
    byId("prog2Res").textContent = state.mode === "resources" ? state.budget.toLocaleString() : "Custom count";
    updateOptionsSummary();
  }

  function updateLive({ tick, team1Alive, team2Alive, team1Hp, team2Hp, team1Total, team2Total }) {
    byId("battleTimer").textContent = `${(tick / 60).toFixed(1)}s`;
    byId("prog1Units").textContent = `${team1Alive}/${team1Total}`;
    byId("prog2Units").textContent = `${team2Alive}/${team2Total}`;
    byId("prog1Hp").textContent = `${team1Hp.toLocaleString()} HP`;
    byId("prog2Hp").textContent = `${team2Hp.toLocaleString()} HP`;
    byId("prog1Lost").textContent = team1Alive ? "Fighting" : "Defeated";
    byId("prog2Lost").textContent = team2Alive ? "Fighting" : "Defeated";
  }

  function setPlaybackState({ playing, atEnd }) {
    byId("pauseBtn").textContent = playing ? "Pause" : atEnd ? "Replay" : "Resume";
    byId("playPause").textContent = playing ? "Pause" : atEnd ? "Replay" : "Play";
  }

  for (const team of [1, 2]) {
    renderTeam(team);
    const search = byId(`team${team}Search`);
    search.addEventListener("input", () => renderSearch(team));
    search.addEventListener("focus", () => renderSearch(team));
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") clearSearch(team);
    });
    search.addEventListener("blur", () => {
      setTimeout(() => { byId(`team${team}SearchResults`).hidden = true; }, 160);
    });
  }

  document.querySelectorAll('input[name="armyMode"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      const resources = radio.value === "resources" && radio.checked;
      if (radio.checked) {
        byId("countInputs").hidden = resources;
        byId("resourceInput").hidden = !resources;
        updateOptionsSummary();
      }
    });
  });
  for (const id of ["team1Count", "team2Count", "totalResources"]) {
    byId(id).addEventListener("input", updateOptionsSummary);
  }

  byId("startBtn").addEventListener("click", async () => {
    try {
      readOptions();
      setBusy(true);
      await onStart(buildFightQuery(state), state);
    } catch (error) {
      setBusy(false);
      setHint(error.message, true);
    }
  });
  byId("pauseBtn").addEventListener("click", onPauseToggle);
  byId("resetBtn").addEventListener("click", () => {
    setBattleActive(false);
    onNewBattle();
    syncReady();
  });
  byId("speedSlider").addEventListener("input", (event) => {
    byId("speedLabel").textContent = `${event.currentTarget.value}x`;
    onSpeedChange(Number(event.currentTarget.value));
  });
  byId("dmgToggle").addEventListener("click", () => {
    const panel = byId("debugPanel");
    panel.hidden = !panel.hidden;
    byId("dmgToggle").setAttribute("aria-expanded", String(!panel.hidden));
  });

  syncCapacity();
  syncReady();
  updateOptionsSummary();

  return Object.freeze({
    applyFightResult,
    currentState: () => state,
    setBattleActive,
    setBusy,
    setHint,
    setPlaybackState,
    updateLive,
  });
}
