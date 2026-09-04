import assert from "node:assert/strict";
import test from "node:test";

import {
  fittedMapZoom,
  productionUnitBoxSize,
} from "../viewer/map-renderer.js";


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


test("production unit presentation scale halves sprites independently of camera zoom", () => {
  const normal = productionUnitBoxSize(0.2, 1.01);
  const compact = productionUnitBoxSize(0.2, 1.01, 0.5);
  assert.equal(compact, normal / 2);
});
