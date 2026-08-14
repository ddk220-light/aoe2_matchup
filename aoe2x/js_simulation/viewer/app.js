import { validateMapFixture } from "../src/map-model.js";
import { formationUnits, validateFormationFixture } from "../src/formation-model.js";
import { createBattlePage } from "./battle-page.js";
import { kitingFightHref, kitingFightRequest, soloMovementRequest } from "./battle-state.js";
import { createMapRenderer } from "./map-renderer.js";
import {
  createPlaybackCursor,
  createReviewFeedback,
  downloadJsonDocument,
} from "./simulation-review.js";


const byId = (id) => document.getElementById(id);
const TICKS_PER_SECOND = 60;


function prettyName(value) {
  return String(value ?? "Unknown").toLowerCase().replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function deepFreeze(value, visited = new Set()) {
  if (!value || typeof value !== "object" || visited.has(value)) return value;
  visited.add(value);
  for (const child of Object.values(value)) deepFreeze(child, visited);
  return Object.freeze(value);
}


function setSelection(record) {
  byId("selectionEmpty").hidden = Boolean(record);
  byId("selectionDetails").hidden = !record;
  if (!record) return;
  const position = record.position ?? { x: record.x, y: record.y };
  const isUnit = record.owner !== undefined || record.player_id !== undefined;
  byId("selectedName").textContent = prettyName(record.name ?? record.label);
  byId("selectedPlayer").textContent = isUnit
    ? `Player ${record.player_id ?? record.owner}` : "Gaia";
  byId("selectedId").textContent = String(record.unit_const ?? record.unitMaster ?? "—");
  byId("selectedReference").textContent = String(record.reference_id ?? record.referenceId ?? "—");
  byId("selectedPosition").textContent = Number.isFinite(position?.x) && Number.isFinite(position?.y)
    ? `${position.x.toFixed(2)}, ${position.y.toFixed(2)}` : "—";
  const rotation = record.rotation ?? record.facing;
  byId("selectedRotation").textContent = Number.isFinite(rotation)
    ? `${rotation.toFixed(3)} rad` : "—";
}


function renderInventory(counts) {
  const rows = Object.entries(counts).sort(([, left], [, right]) => right - left).map(([key, count]) => {
    const row = document.createElement("div");
    row.className = "inventory-row";
    const label = document.createElement("span");
    label.textContent = prettyName(key.split(":")[1]);
    const value = document.createElement("b");
    value.textContent = String(count);
    row.append(label, value);
    return row;
  });
  byId("objectInventory").replaceChildren(...rows);
}


function targetLabel({ pursuitTargetId, engagedTargetId, attackTargetId }) {
  const values = [
    ["P", pursuitTargetId], ["E", engagedTargetId], ["A", attackTargetId],
  ].filter(([, target]) => target !== null);
  return values.length ? values.map(([kind, target]) => `${kind}:${target}`).join(" · ") : "no target";
}


function renderUnitTelemetry(snapshot, index) {
  const rows = snapshot.units.map(([referenceId, , , , hp, alive, action,
    pursuitTargetId, engagedTargetId, attackTargetId]) => {
    const meta = index[referenceId];
    const row = document.createElement("div");
    row.className = `telemetry-row owner-${meta.owner}${alive ? "" : " is-dead"}`;
    const identity = document.createElement("span");
    identity.textContent = `T${meta.owner - 1} · ${referenceId}`;
    const hpText = document.createElement("span");
    hpText.textContent = `${hp}/${meta.maxHp} HP`;
    const meter = document.createElement("i");
    meter.style.setProperty("--hp", `${Math.max(0, hp / meta.maxHp * 100)}%`);
    const detail = document.createElement("small");
    detail.textContent = `${alive ? action : "dead"} · ${targetLabel(
      { pursuitTargetId, engagedTargetId, attackTargetId })}`;
    row.append(identity, hpText, meter, detail);
    return row;
  });
  byId("unitTelemetry").replaceChildren(...rows);
  const live = snapshot.units.filter(([, , , , , alive]) => alive).length;
  byId("unitCount").textContent = `${live}/${snapshot.units.length} alive`;
}


function setMapStatus(text, { loading = false } = {}) {
  const light = document.createElement("span");
  light.className = `status-light${loading ? " is-loading" : ""}`;
  byId("mapStatus").replaceChildren(light, document.createTextNode(text));
}


function eventLabel(event) {
  const subject = event.targetId === undefined
    ? `${event.actorId}` : `${event.actorId} → ${event.targetId}`;
  if (event.type === "damage") return `${subject} · −${event.amount} · ${event.hpAfter} HP`;
  if (event.type === "death") return `${subject} · eliminated`;
  return subject;
}


function renderTimeline(events, tick) {
  const firstFuture = events.findIndex((event) => event.tick > tick);
  const split = firstFuture === -1 ? events.length : firstFuture;
  const visible = events.slice(Math.max(0, split - 8), Math.min(events.length, split + 4));
  const rows = visible.map((event) => {
    const row = document.createElement("li");
    row.className = event.tick === tick ? "is-current" : event.tick > tick ? "is-future" : "";
    const time = document.createElement("time");
    time.textContent = `T${String(event.tick).padStart(4, "0")}`;
    const body = document.createElement("span");
    const kind = document.createElement("b");
    kind.textContent = event.type.replaceAll("-", " ");
    const detail = document.createElement("small");
    detail.textContent = eventLabel(event);
    body.append(kind, detail);
    row.append(time, body);
    return row;
  });
  byId("eventTimeline").replaceChildren(...rows);
  byId("eventCount").textContent = `${events.filter((event) => event.tick <= tick).length}/${events.length}`;
}


function renderDamageBreakdown(result, events) {
  const summary = new Map([[2, { damage: 0, hits: 0, kills: 0 }], [3, { damage: 0, hits: 0, kills: 0 }]]);
  for (const event of events) {
    const owner = result.unitIndex[event.actorId]?.owner;
    if (!summary.has(owner)) continue;
    if (event.type === "damage") {
      summary.get(owner).damage += event.amount ?? 0;
      summary.get(owner).hits += 1;
    } else if (event.type === "death") {
      const defeatedOwner = result.unitIndex[event.actorId]?.owner;
      const winnerOwner = defeatedOwner === 2 ? 3 : 2;
      summary.get(winnerOwner).kills += 1;
    }
  }
  const cards = [result.side2, result.side3].map((side, index) => {
    const owner = index + 2;
    const values = summary.get(owner);
    const card = document.createElement("section");
    card.className = `debug-section team${index + 1}`;
    const heading = document.createElement("h4");
    heading.textContent = `${side.civ} ${side.label}`;
    const body = document.createElement("p");
    body.textContent = `${values.damage.toLocaleString()} damage · ${values.hits.toLocaleString()} hits · ${values.kills} kills`;
    card.append(heading, body);
    return card;
  });
  byId("debugContent").replaceChildren(...cards);
}


async function start() {
  const soloRequest = soloMovementRequest(window.location.href);
  const kitingRequest = kitingFightRequest(window.location.href);
  const navigationRequest = soloRequest ?? kitingRequest;
  const [mapResponse, formationResponse, unitsResponse, catalogueResponse] = await Promise.all([
    fetch("api/map", { cache: "no-store" }),
    fetch("api/formation", { cache: "no-store" }),
    fetch("api/units", { cache: "no-store" }),
    fetch("api/catalogue", { cache: "no-store" }),
  ]);
  for (const [label, response] of [
    ["Map", mapResponse], ["Formation", formationResponse], ["Units", unitsResponse],
    ["Catalogue", catalogueResponse],
  ]) {
    if (!response.ok) throw new Error(`${label} API returned ${response.status}`);
  }

  const units = deepFreeze(await unitsResponse.json());
  const catalogue = deepFreeze(await catalogueResponse.json());
  const fixture = validateMapFixture(await mapResponse.json());
  const formation = validateFormationFixture(await formationResponse.json());
  const formationRoster = formationUnits(formation);
  const canvas = byId("mapCanvas");
  const renderer = createMapRenderer(canvas, fixture.map);
  renderer.setUnits(formationRoster);
  const feedback = createReviewFeedback({ storage: localStorage });

  byId("sourceBadge").replaceChildren();
  const sourceDot = document.createElement("span");
  sourceDot.className = "local-engine-dot";
  byId("sourceBadge").append(sourceDot, document.createTextNode(
    `${catalogue.enabled.length} calibrated combinations · local engine`,
  ));
  byId("clockRate").textContent = `${TICKS_PER_SECOND} Hz`;
  byId("mapSize").textContent = `${fixture.map.width} × ${fixture.map.height}`;
  byId("tileCount").textContent = fixture.map.tiles.length.toLocaleString();
  byId("objectCount").textContent = fixture.map.gaia_objects.length.toLocaleString();
  byId("sourceFile").textContent = fixture.source.filename;
  byId("sourceHash").textContent = fixture.source.sha256;
  byId("sourceVersion").textContent = `Scenario ${fixture.source.scenario_version} · ${fixture.source.parser} ${fixture.source.parser_version}`;
  renderInventory(fixture.object_counts);
  setMapStatus("Golden Arena ready · choose both armies");

  let activeResult = null;
  let activeBattleState = null;
  let eventLog = [];
  let cursor = null;
  let playing = false;
  let animationFrame = null;
  let lastFrameAt = null;
  let tickAccumulator = 0;
  let speedMultiplier = Number(byId("speedSlider").value);
  let requestSerial = 0;
  let page;

  const unitsBySlug = new Map(units.units.map((unit) => [unit.slug, unit]));
  const soloUnit = soloRequest ? unitsBySlug.get(soloRequest.unit) : null;
  const kitingRangedSlug = kitingRequest?.ranged ?? "hand_cannoneer";
  const kitingMeleeSlug = kitingRequest?.melee ?? "champion";
  const kitingMatchup = kitingRequest
    ? units.kitingObservationMatchups.find(({ rangedSlug, meleeSlug }) => (
      rangedSlug === kitingRangedSlug && meleeSlug === kitingMeleeSlug
    ))
    : null;

  if (soloRequest) {
    if (!soloUnit || !units.soloMovementSlugs.includes(soloRequest.unit)) {
      throw new Error(`Solo movement unit ${soloRequest.unit} is not available`);
    }
    document.body.classList.add("solo-movement-mode");
    document.querySelector(".page-header h1").textContent = `${soloUnit.label} Movement Lab`;
    document.querySelector(".page-header .subtitle").textContent =
      `21 ${soloUnit.civ} ${soloUnit.label}s · engine team 2 · enemy-free AI-order loop`;
    byId("team1Rail").querySelector(".rail-title").textContent = "Engine Team 2";
    byId("optionsCurrent").textContent = `21 ${soloUnit.label}s · solo movement`;
    const unitSelect = byId("soloMovementUnit");
    for (const slug of units.soloMovementSlugs) {
      const unit = unitsBySlug.get(slug);
      if (!unit) throw new Error(`Solo movement registry is missing ${slug}`);
      unitSelect.append(new Option(`${unit.label} · ${unit.civ}`, slug));
    }
    unitSelect.value = soloRequest.unit;
    byId("navigationVariant").value = soloRequest.navigation;
  } else if (kitingRequest) {
    const ranged = unitsBySlug.get(kitingRangedSlug);
    const melee = unitsBySlug.get(kitingMeleeSlug);
    if (!ranged || !melee || !kitingMatchup) {
      throw new Error(`Kiting matchup ${kitingRangedSlug} vs ${kitingMeleeSlug} is unavailable`);
    }
    const family = ranged.class === "siege_ranged" ? "siege" : "kite";
    const capacity = units.capacityByFamily[family];
    const rangedCount = kitingRequest.n2 ?? kitingMatchup.rangedCount;
    const meleeCount = kitingRequest.n3 ?? kitingMatchup.meleeCount;
    const rosterLabel = kitingRequest.n2 === undefined ? "Tape roster" : "Custom roster";
    document.body.classList.add("kiting-observation-mode");
    document.querySelector(".page-header h1").textContent =
      `${ranged.label} vs ${melee.label} Kiting Lab`;
    document.querySelector(".page-header .subtitle").textContent =
      `${rosterLabel}: ${rangedCount} ${ranged.civ} ${ranged.label}`
        + `${rangedCount === 1 ? "" : "s"} group-kiting while `
        + `${meleeCount} ${melee.civ} ${melee.label}`
        + `${meleeCount === 1 ? "" : "s"} pursue`;
    byId("team1Rail").querySelector(".rail-title").textContent =
      `${ranged.label}${rangedCount === 1 ? "" : "s"} · Engine Team 2`;
    byId("team2Rail").querySelector(".rail-title").textContent =
      `${melee.label}${meleeCount === 1 ? "" : "s"} · Engine Team 3`;
    byId("optionsCurrent").textContent =
      `${rosterLabel} · ${rangedCount} vs ${meleeCount}`;
    byId("soloMovementUnit").closest(".navigation-lab-field").hidden = true;
    const rangedSelect = byId("kitingRangedUnit");
    const rangedOrder = ["hand_cannoneer", "arbalester", "heavy_cav_archer", "heavy_scorpion"];
    for (const slug of rangedOrder) {
      if (!units.kitingObservationMatchups.some(({ rangedSlug }) => rangedSlug === slug)) continue;
      const unit = unitsBySlug.get(slug);
      rangedSelect.append(new Option(`${unit.label} · ${unit.civ}`, slug));
    }
    rangedSelect.value = kitingRangedSlug;
    const meleeSelect = byId("kitingMeleeUnit");
    for (const { meleeSlug } of units.kitingObservationMatchups.filter(
      ({ rangedSlug }) => rangedSlug === kitingRangedSlug,
    )) {
      if ([...meleeSelect.options].some(({ value }) => value === meleeSlug)) continue;
      const unit = unitsBySlug.get(meleeSlug);
      meleeSelect.append(new Option(`${unit.label} · ${unit.civ}`, meleeSlug));
    }
    meleeSelect.value = kitingMeleeSlug;
    const rangedCountInput = byId("kitingRangedCount");
    rangedCountInput.max = String(capacity.side2);
    rangedCountInput.value = String(rangedCount);
    const meleeCountInput = byId("kitingMeleeCount");
    meleeCountInput.max = String(capacity.side3);
    meleeCountInput.value = String(meleeCount);
    byId("kitingRangedField").hidden = false;
    byId("kitingRangedCountField").hidden = false;
    byId("kitingMeleeField").hidden = false;
    byId("kitingMeleeCountField").hidden = false;
    byId("navigationVariant").value = kitingRequest.navigation;
  }

  function renderNavigationStats(navigation) {
    if (!navigationRequest || !navigation) return;
    const names = {
      baseline: "Baseline direct movement",
      "per-unit-grid": "Per-unit obstacle grid",
      cohesive: "Cohesive formation",
    };
    byId("navigationStatsTitle").textContent = names[navigation.variant] ?? navigation.variant;
    const phaseNames = {
      direct: "Direct orders",
      "awaiting-first-order": "Holding for first AI order",
      "forming-first-order": "Forming at first AI order",
      routing: "Group kiting route",
    };
    byId("navPhase").textContent = phaseNames[navigation.phase] ?? navigation.phase ?? "—";
    byId("navCohesion").textContent = `${navigation.cohesionRadius.toFixed(2)} tiles`;
    byId("navSlotError").textContent = `${navigation.maxSlotError.toFixed(2)} tiles`;
    byId("navBlocked").textContent = String(navigation.blockedCount);
    byId("navReplans").textContent = String(navigation.replans);
    byId("navDistance").textContent = `${navigation.totalAnchorDistance.toFixed(1)} tiles`;
    byId("navStall").textContent = `${(navigation.stalledTicks / TICKS_PER_SECOND).toFixed(2)} s`;
    byId("navContactMode").textContent = activeResult.contactSteeringMode
      === "preventive-contact-graph" ? "Prevent compact stacks" : "Standard collision";
    const contactSummary = activeResult.contactSteeringSummary;
    byId("navContactSteps").textContent = contactSummary
      ? `${contactSummary.steeredSteps} (${contactSummary.steeredUnitCount} units)`
      : "0";
  }

  function liveSummary(snapshot) {
    const totals = { 2: 0, 3: 0 };
    const alive = { 2: 0, 3: 0 };
    const hp = { 2: 0, 3: 0 };
    for (const [referenceId, , , , unitHp, unitAlive] of snapshot.units) {
      const owner = activeResult.unitIndex[referenceId].owner;
      totals[owner] += 1;
      hp[owner] += unitHp;
      if (unitAlive) alive[owner] += 1;
    }
    page.updateLive({
      tick: snapshot.tick,
      team1Alive: alive[2], team2Alive: alive[3],
      team1Hp: hp[2], team2Hp: hp[3],
      team1Total: totals[2], team2Total: totals[3],
    });
  }

  function present(snapshot) {
    renderer.setSimulationSnapshot(Object.freeze({
      tick: snapshot.tick,
      units: Object.freeze(snapshot.units.map(
        ([referenceId, x, y, facing, hp, alive, action,
          pursuitTargetId, engagedTargetId, attackTargetId]) => {
          const meta = activeResult.unitIndex[referenceId];
          return Object.freeze({
            referenceId, x, y, facing, hp, action,
            pursuitTargetId, engagedTargetId, attackTargetId,
            alive: alive === 1,
            owner: meta.owner,
            label: meta.label,
            unitMaster: meta.master,
            mechanics: Object.freeze({
              hp: meta.maxHp,
              attack_range_tiles: meta.attackRange,
              collision_size_tiles: Object.freeze({ x: meta.collisionRadius }),
            }),
          });
        })),
      events: snapshot.events,
      ...(snapshot.navigation ? { navigation: snapshot.navigation } : {}),
    }));
    byId("tickReadout").textContent = String(snapshot.tick).padStart(4, "0");
    byId("secondsReadout").textContent = (snapshot.tick / TICKS_PER_SECOND).toFixed(3);
    renderUnitTelemetry(snapshot, activeResult.unitIndex);
    renderTimeline(eventLog, snapshot.tick);
    liveSummary(snapshot);
    renderNavigationStats(snapshot.navigation);
    setMapStatus(activeResult.mode === "solo-movement"
      ? `21 ${activeResult.side2.label}s · owner 2 AI kite movement · no enemies`
      : `${activeResult.side2.label} ${activeResult.side2.count} vs ${activeResult.side3.label} ${activeResult.side3.count}`);
    if (cursor?.atEnd() && activeResult.mode !== "solo-movement") setPlaying(false);
  }

  function animate(timestamp) {
    if (!playing) return;
    if (lastFrameAt === null) lastFrameAt = timestamp;
    tickAccumulator += (timestamp - lastFrameAt) * TICKS_PER_SECOND * speedMultiplier / 1000;
    lastFrameAt = timestamp;
    const steps = Math.min(60, Math.floor(tickAccumulator));
    tickAccumulator -= steps;
    for (let index = 0; index < steps && !cursor.atEnd(); index += 1) cursor.step();
    if (cursor.atEnd()) {
      if (activeResult?.mode === "solo-movement") cursor.reset();
      else setPlaying(false);
    }
    if (playing) animationFrame = requestAnimationFrame(animate);
  }

  function setPlaying(value) {
    if (value && cursor?.atEnd()) cursor.reset();
    playing = Boolean(value) && Boolean(cursor) && !cursor.atEnd();
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    animationFrame = null;
    lastFrameAt = null;
    tickAccumulator = 0;
    byId("playbackMode").textContent = playing ? `running · ${speedMultiplier}x` : "paused";
    page?.setPlaybackState({ playing, atEnd: Boolean(cursor?.atEnd()) });
    if (playing) animationFrame = requestAnimationFrame(animate);
  }

  function feedbackKey() {
    if (!activeResult || activeResult.mode === "solo-movement") return null;
    return {
      pair: `${activeResult.side2.slug}-vs-${activeResult.side3.slug}`,
      ratio: `${activeResult.side2.count}v${activeResult.side3.count}`,
      repeat: 1,
    };
  }

  function displayFeedback() {
    const key = feedbackKey();
    const row = key ? feedback.get(key) : { flagged: false, note: "" };
    byId("runFlagged").checked = row.flagged;
    byId("reviewNote").value = row.note;
  }

  async function loadSimulation(query, battleState, endpoint = "api/fight") {
    const serial = ++requestSerial;
    setPlaying(false);
    setMapStatus("Running deterministic engine…", { loading: true });
    const response = await fetch(`${endpoint}${query ? `?${query}` : ""}`, { cache: "no-store" });
    if (serial !== requestSerial) return;
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.error ?? `Simulation API returned ${response.status}`);
    }
    const result = deepFreeze(await response.json());
    if (serial !== requestSerial) return;
    activeResult = result;
    activeBattleState = battleState;
    eventLog = result.snapshots.flatMap(({ events }) => events);
    page.applyFightResult(result);
    byId("simWinner").textContent = result.mode === "solo-movement"
      ? "Movement loop" : (result.winnerOwner === null ? "Draw" : `Team ${result.winnerOwner - 1}`);
    byId("simWinnerHp").textContent = `${result.winnerHp.toLocaleString()} HP`;
    byId("finalStateHash").textContent = result.finalStateHash;
    byId("eventLogHash").textContent = result.eventLogHash;
    byId("player2Name").textContent = result.side2.label;
    byId("player3Name").textContent = result.side3.label;
    byId("player2Count").textContent = String(result.side2.count);
    byId("player3Count").textContent = String(result.side3.count);
    byId("placementAudit").textContent = result.mode === "solo-movement"
      ? "21 owner-2 kite spawn cells · AI move orders every 80 ticks · no enemy roster"
      : `${result.side2.count + result.side3.count} spawn cells · ${result.family} block`
        + (result.orientationNormalised ? " · measured orientation" : "");
    byId("ledgerNumber").textContent = result.mode === "solo-movement"
      ? "SOLO 21" : `${result.side2.count}V${result.side3.count}`;
    renderDamageBreakdown(result, eventLog);
    displayFeedback();
    cursor = createPlaybackCursor({ snapshots: result.snapshots, onSnapshot: present });
    setPlaying(true);
  }

  function newBattle() {
    requestSerial += 1;
    setPlaying(false);
    cursor = null;
    renderer.showFormation();
    setMapStatus("Golden Arena ready · adjust armies or start again");
    byId("playbackMode").textContent = "formation";
  }

  page = createBattlePage({
    catalogue,
    units,
    onStart: loadSimulation,
    onPauseToggle: () => setPlaying(!playing),
    onNewBattle: newBattle,
    onSpeedChange: (value) => {
      speedMultiplier = value;
      byId("playbackMode").textContent = playing ? `running · ${speedMultiplier}x` : "paused";
    },
  });

  if (navigationRequest) {
    byId("resetBtn").hidden = true;
    if (soloRequest) {
      byId("dmgToggle").hidden = true;
      byId("soloMovementUnit").addEventListener("change", (event) => {
        const next = new URL(window.location.href);
        next.searchParams.set("unit", event.target.value);
        window.location.assign(next.href);
      });
    } else if (kitingRequest) {
      const navigateKitingUnits = () => {
        const rangedSlug = byId("kitingRangedUnit").value;
        const options = {
          ranged: rangedSlug,
          melee: byId("kitingMeleeUnit").value,
        };
        if (kitingRequest.n2 !== undefined) {
          const rangedUnit = unitsBySlug.get(rangedSlug);
          const family = rangedUnit.class === "siege_ranged" ? "siege" : "kite";
          const capacity = units.capacityByFamily[family];
          options.n2 = byId("kitingRangedCount").valueAsNumber;
          options.n3 = byId("kitingMeleeCount").valueAsNumber;
          options.max2 = capacity.side2;
          options.max3 = capacity.side3;
        }
        window.location.assign(kitingFightHref(window.location.href, options));
      };
      const navigateKitingCounts = () => {
        const rangedCount = byId("kitingRangedCount");
        const meleeCount = byId("kitingMeleeCount");
        if (!rangedCount.checkValidity()) {
          rangedCount.reportValidity();
          return;
        }
        if (!meleeCount.checkValidity()) {
          meleeCount.reportValidity();
          return;
        }
        const rangedSlug = byId("kitingRangedUnit").value;
        const rangedUnit = unitsBySlug.get(rangedSlug);
        const family = rangedUnit.class === "siege_ranged" ? "siege" : "kite";
        const capacity = units.capacityByFamily[family];
        window.location.assign(kitingFightHref(window.location.href, {
          ranged: rangedSlug,
          melee: byId("kitingMeleeUnit").value,
          n2: rangedCount.valueAsNumber,
          n3: meleeCount.valueAsNumber,
          max2: capacity.side2,
          max3: capacity.side3,
        }));
      };
      byId("kitingRangedUnit").addEventListener("change", navigateKitingUnits);
      byId("kitingMeleeUnit").addEventListener("change", navigateKitingUnits);
      byId("kitingRangedCount").addEventListener("change", navigateKitingCounts);
      byId("kitingMeleeCount").addEventListener("change", navigateKitingCounts);
    }
    byId("navigationVariant").addEventListener("change", (event) => {
      const next = new URL(window.location.href);
      next.searchParams.set("navigation", event.target.value);
      window.location.assign(next.href);
    });
  }

  for (const [elementId, option] of [
    ["gridToggle", "grid"], ["objectsToggle", "objects"],
    ["footprintsToggle", "footprints"], ["labelsToggle", "labels"],
    ["navigationDebugToggle", "navigation"],
  ]) {
    byId(elementId).addEventListener("change", (event) => {
      renderer.setOption(option, event.currentTarget.checked);
    });
  }
  byId("topDownToggle").addEventListener("change", (event) => {
    renderer.setProjection(event.currentTarget.checked ? "orthographic" : "isometric");
  });
  byId("resetView").addEventListener("click", () => renderer.resetView());

  byId("playPause").addEventListener("click", () => setPlaying(!playing));
  byId("resetPlayback").addEventListener("click", () => {
    setPlaying(false);
    cursor?.reset();
  });
  byId("stepTick").addEventListener("click", () => {
    setPlaying(false);
    cursor?.step();
  });
  byId("nextEvent").addEventListener("click", () => {
    setPlaying(false);
    cursor?.nextEvent();
  });
  byId("returnFormation").addEventListener("click", () => {
    setPlaying(false);
    renderer.showFormation();
    setMapStatus("Locked 21 vs 21 source formation");
    byId("playbackMode").textContent = "formation";
  });

  function saveFeedback() {
    const key = feedbackKey();
    if (!key) return;
    feedback.set({
      ...key,
      flagged: byId("runFlagged").checked,
      note: byId("reviewNote").value,
    });
  }
  byId("runFlagged").addEventListener("change", saveFeedback);
  byId("reviewNote").addEventListener("input", saveFeedback);
  byId("clearFeedback").addEventListener("click", () => {
    feedback.clear();
    displayFeedback();
  });
  byId("exportFeedback").addEventListener("click", () => {
    const value = feedback.exportJson();
    value.visibleRun = activeResult ? {
      pair: `${activeResult.side2.slug}-vs-${activeResult.side3.slug}`,
      mode: activeBattleState?.mode ?? null,
      budget: activeBattleState?.mode === "resources" ? activeBattleState.budget : null,
      counts: { team1: activeResult.side2.count, team2: activeResult.side3.count },
      winner: activeResult.winnerOwner === null ? null : activeResult.winnerOwner - 1,
      winnerHp: activeResult.winnerHp,
      finalStateHash: activeResult.finalStateHash,
      eventLogHash: activeResult.eventLogHash,
    } : null;
    downloadJsonDocument({ value, filename: "cleanroom-battle-review.json" });
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea, select, button")) return;
    if (event.code === "Space") {
      event.preventDefault();
      setPlaying(!playing);
    } else if (event.key === "ArrowRight" && event.shiftKey) {
      event.preventDefault();
      byId("nextEvent").click();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      byId("stepTick").click();
    } else if (event.key === "Home") {
      event.preventDefault();
      byId("resetPlayback").click();
    }
  });

  const pointers = new Map();
  let moved = false;
  let lastCentroid = null;
  let lastDistance = null;

  function pointerCentroid() {
    const values = [...pointers.values()];
    return {
      x: values.reduce((sum, point) => sum + point.x, 0) / values.length,
      y: values.reduce((sum, point) => sum + point.y, 0) / values.length,
    };
  }
  function pointerDistance() {
    const values = [...pointers.values()];
    return values.length < 2 ? null : Math.hypot(
      values[0].x - values[1].x, values[0].y - values[1].y,
    );
  }
  canvas.addEventListener("pointerdown", (event) => {
    canvas.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.offsetX, y: event.offsetY });
    moved = false;
    lastCentroid = pointerCentroid();
    lastDistance = pointerDistance();
  });
  canvas.addEventListener("pointermove", (event) => {
    const inspection = renderer.inspectAt(event.offsetX, event.offsetY);
    const inMap = inspection.tile.x >= 0 && inspection.tile.x < fixture.map.width
      && inspection.tile.y >= 0 && inspection.tile.y < fixture.map.height;
    byId("cursorReadout").textContent = inMap
      ? `Tile ${inspection.tile.x.toFixed(2)}, ${inspection.tile.y.toFixed(2)}` : "Tile —, —";
    if (!pointers.has(event.pointerId)) {
      renderer.setHovered(inspection.object);
      return;
    }
    pointers.set(event.pointerId, { x: event.offsetX, y: event.offsetY });
    const centroid = pointerCentroid();
    const distance = pointerDistance();
    const deltaX = centroid.x - lastCentroid.x;
    const deltaY = centroid.y - lastCentroid.y;
    if (Math.abs(deltaX) + Math.abs(deltaY) > 0.5) moved = true;
    renderer.panBy(deltaX, deltaY);
    if (distance && lastDistance && Math.abs(distance - lastDistance) > 0.5) {
      renderer.zoomAt(distance / lastDistance, centroid.x, centroid.y);
      moved = true;
    }
    lastCentroid = centroid;
    lastDistance = distance;
  });
  function releasePointer(event) {
    if (!pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    if (!moved && pointers.size === 0) {
      const inspection = renderer.inspectAt(event.offsetX, event.offsetY);
      renderer.setSelected(inspection.unit ? null : inspection.object);
      renderer.setSelectedUnit(inspection.unit);
      setSelection(inspection.unit || inspection.object);
    }
    lastCentroid = pointers.size ? pointerCentroid() : null;
    lastDistance = pointerDistance();
  }
  canvas.addEventListener("pointerup", releasePointer);
  canvas.addEventListener("pointercancel", releasePointer);
  canvas.addEventListener("pointerleave", () => renderer.setHovered(null));
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    renderer.zoomAt(event.deltaY < 0 ? 1.12 : 0.89, event.offsetX, event.offsetY);
  }, { passive: false });

  const observer = new ResizeObserver(() => renderer.resize());
  observer.observe(canvas);
  renderer.resize();
  if (navigationRequest) {
    await loadSimulation(navigationRequest.query, null, navigationRequest.endpoint);
  }
}


function showError(error) {
  const panel = byId("errorPanel");
  panel.hidden = false;
  panel.textContent = `The local Battle Simulation could not continue: ${error.message}`;
  console.error(error);
}


start().catch(showError);
