import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildSelectionPreviewUnits,
  fittedMapZoom,
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
