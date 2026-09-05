import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildSelectionPreviewUnits,
  fittedMapZoom,
  productionProjectileElevation,
  productionProjectileScreenBend,
  productionProjectileStyle,
  productionProjectileTrailPoints,
  productionSpriteGroundOffset,
  productionUnitBoxSize,
} from "../viewer/map-renderer.js";

const websiteCss = await readFile(
  new URL("../../../apps/website/static/css/simulate.css", import.meta.url),
  "utf8",
);
const websitePage = await readFile(
  new URL("../../../apps/website/static/js/simulate.js", import.meta.url),
  "utf8",
);
const websiteTemplate = await readFile(
  new URL("../../../apps/website/templates/simulate.html", import.meta.url),
  "utf8",
);


test("portrait production framing fits the combat corridor by map height", () => {
  const fullMap = fittedMapZoom({
    width: 540,
    height: 720,
    spanX: 1376,
    spanY: 688,
  });
  const corridor = fittedMapZoom({
    width: 540,
    height: 720,
    spanX: 1376,
    spanY: 688,
    compact: true,
  });

  assert.equal(fullMap, 492 / 1376);
  assert.equal(corridor, 696 / 688);
  assert.ok(corridor > fullMap * 2.8,
    "the phone camera should crop scenery instead of fitting the full width");
});


test("landscape production framing also crops decorative side space", () => {
  const fullMap = fittedMapZoom({
    width: 1080,
    height: 680,
    spanX: 1376,
    spanY: 688,
  });
  const corridor = fittedMapZoom({
    width: 1080,
    height: 680,
    spanX: 1376,
    spanY: 688,
    compact: true,
  });

  assert.equal(fullMap, 1032 / 1376);
  assert.equal(corridor, 656 / 688);
  assert.ok(corridor > fullMap,
    "the desktop camera should use more of the canvas for the playable lane");
});


test("production unit presentation scale supports 90% sprites independently of camera zoom", () => {
  const normal = productionUnitBoxSize(0.2, 1.01);
  const compact = productionUnitBoxSize(0.2, 1.01, 0.9);
  assert.equal(compact, normal * 0.9);
  assert.match(websitePage, /unitScale:\s*0\.9/);
});


test("mobile picker and battle share the same portrait canvas camera", () => {
  assert.match(websiteCss, /@media \(max-width: 768px\)[\s\S]*#battleCanvas \{ aspect-ratio: 3 \/ 4; \}/);
  assert.doesNotMatch(
    websiteCss,
    /\.sim-stage\.battle-active #battleCanvas \{ aspect-ratio: 3 \/ 4; \}/,
  );
});


test("desktop battle shell fits below navigation and centers equal transport buttons", () => {
  assert.match(
    websiteCss,
    /@media \(min-width: 1025px\) and \(min-height: 560px\)[\s\S]*height: calc\(100svh - var\(--nav-h, 56px\) - 16px\)/,
  );
  assert.match(websiteCss, /\.player-button \{[\s\S]*width: 50px;[\s\S]*height: 50px;/);
  assert.match(websiteCss, /\.transport-controls \{[\s\S]*justify-content: center;/);
  assert.match(websiteTemplate, /id="restartBtn"[\s\S]*id="playPauseBtn"/);
  assert.match(websiteTemplate, /class="transport-controls"/);
});


test("mobile unit picker uses larger seven-column cards", () => {
  assert.match(
    websiteCss,
    /@media \(max-width: 768px\)[\s\S]*\.rail-picker > \.unit-grid \{[\s\S]*grid-template-columns: repeat\(7, minmax\(0, 1fr\)\);/,
  );
  assert.match(
    websiteCss,
    /\.rail-picker > \.unit-grid \.unit-pick img[\s\S]*width: 1\.68rem;[\s\S]*height: 1\.68rem;/,
  );
});


test("roster changes remain available during active playback", () => {
  assert.doesNotMatch(websiteCss, /\.battle-running \.change-btn\s*\{[^}]*display:\s*none/);
  assert.match(
    websitePage,
    /function leaveBattleForRosterEdit\(\)[\s\S]*pageSim\.reset\(\);[\s\S]*setSimPhase\(false\);/,
  );
});


test("team cards expose live health and matchup-specific combat metrics", () => {
  for (const team of [1, 2]) {
    assert.match(websiteTemplate, new RegExp(`id="prog${team}HealthFill"`));
    assert.match(websiteTemplate, new RegExp(`id="prog${team}Damage"`));
    assert.match(websiteTemplate, new RegExp(`id="prog${team}Dps"`));
    assert.match(websiteTemplate, new RegExp(`id="prog${team}Ttk"`));
    assert.match(websiteTemplate, new RegExp(`id="prog${team}Callouts"`));
  }
  assert.match(websitePage, /summarizeMatchup/);
  assert.match(websitePage, /function scheduleMatchupPreview/);
  assert.match(websiteCss, /\.progress-card\.team1 \.progress-health-fill/);
  assert.match(websiteCss, /\.progress-card\.team2 \.progress-health-fill/);
  assert.match(websiteCss, /\.matchup-metrics \{[\s\S]*grid-template-columns: repeat\(3/);
});


test("attack sprites sit lower than idle sprites to meet their ground shadow", () => {
  assert.equal(productionSpriteGroundOffset(100, false), 2.5);
  assert.ok(Math.abs(productionSpriteGroundOffset(100, true) - 7) < 1e-9);
  assert.ok(
    productionSpriteGroundOffset(64, true) > productionSpriteGroundOffset(64, false),
  );
});


test("production arrows arc for foot and cavalry archer families only", () => {
  assert.equal(productionProjectileStyle({ slug: "arbalester" }).flight, "arc");
  assert.equal(productionProjectileStyle({ slug: "heavy_cav_archer" }).flight, "arc");
  assert.equal(productionProjectileStyle({ slug: "elite_chu_ko_nu_chinese" }).flight, "arc");
  assert.equal(productionProjectileStyle({ slug: "elite_throwing_axeman" }).flight, "linear");
  assert.equal(productionProjectileStyle({ slug: "elite_mameluke" }).flight, "linear");
  assert.equal(productionProjectileStyle({ slug: "hand_cannoneer" }).flight, "linear");
});


test("production arrow curve preserves launch and impact while peaking mid-flight", () => {
  const projectile = {
    start: { x: 2, y: 4 },
    end: { x: 10, y: 4 },
    style: productionProjectileStyle({ slug: "arbalester" }),
  };
  const launch = productionProjectileElevation(projectile, 0);
  const middle = productionProjectileElevation(projectile, 0.5);
  const impact = productionProjectileElevation(projectile, 1);

  assert.equal(launch, 0.18);
  assert.equal(impact, 0.18);
  assert.ok(middle > launch + 2);
  assert.equal(
    productionProjectileElevation(projectile, 0.25),
    productionProjectileElevation(projectile, 0.75),
  );
});


test("production arrow trail follows only the traveled arc", () => {
  const projectile = {
    start: { x: 2, y: 4 },
    end: { x: 10, y: 4 },
    style: productionProjectileStyle({ slug: "arbalester" }),
  };
  const trail = productionProjectileTrailPoints(projectile, 0.8, 7);

  assert.equal(trail.length, 7);
  assert.equal(trail[0].progress, 0);
  assert.ok(Math.abs(trail.at(-1).progress - 0.8) < 1e-9);
  assert.ok(trail.every((point) => point.progress <= 0.8 + Number.EPSILON));
  assert.ok(trail.some((point) => point.elevation > trail.at(-1).elevation));
});


test("production arrow perspective bend preserves endpoints and bows mid-flight", () => {
  const projectile = { id: "arrow:42" };
  assert.equal(productionProjectileScreenBend(projectile, 0), 0);
  assert.equal(productionProjectileScreenBend(projectile, 1), 0);
  assert.equal(Math.abs(productionProjectileScreenBend(projectile, 0.5)), 1);
  assert.equal(
    productionProjectileScreenBend(projectile, 0.25),
    productionProjectileScreenBend(projectile, 0.75),
  );
});


test("non-arrow projectile families retain a flat visual trajectory", () => {
  const projectile = {
    start: { x: 2, y: 4 },
    end: { x: 10, y: 4 },
    style: productionProjectileStyle({ slug: "elite_throwing_axeman" }),
  };

  assert.equal(productionProjectileElevation(projectile, 0), 0.18);
  assert.equal(productionProjectileElevation(projectile, 0.5), 0.18);
  assert.equal(productionProjectileElevation(projectile, 1), 0.18);
});


test("selection preview stays empty until a team picks a unit", () => {
  const placements = {
    2: [{ x: 12.5, y: 2.5, rotation: 2.75 }],
    3: [{ x: 3.5, y: 12.5, rotation: 1.18 }],
  };
  assert.deepEqual(buildSelectionPreviewUnits({}, placements, { 1: 1, 2: 1 }), []);

  const teamA = buildSelectionPreviewUnits(
    { 1: { unitName: "Arbalester" } },
    placements,
    { 1: 1, 2: 1 },
  );
  assert.equal(teamA.length, 1);
  assert.equal(teamA[0].player_id, 2);
  assert.equal(teamA[0].name, "Arbalester");

  const both = buildSelectionPreviewUnits(
    {
      1: { unitName: "Arbalester" },
      2: { unitName: "Paladin" },
    },
    placements,
    { 1: 1, 2: 1 },
  );
  assert.deepEqual(both.map(({ player_id: owner }) => owner), [2, 3]);
});
