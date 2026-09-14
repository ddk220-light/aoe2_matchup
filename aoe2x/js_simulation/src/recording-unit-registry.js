// Live-game recording metadata for units without measured simulator fixtures.
// baseCost is legacy descriptive metadata; Lab purchases use recording-costs.js.
// These rows must not imply support for JavaScript combat simulation.
import { unitBySlug } from "./unit-registry.js";
import { readFileSync } from "node:fs";

const RECORDING_UNITS = JSON.parse(readFileSync(
  new URL("../../../data/unique-unit-roster.json", import.meta.url), "utf8",
)).units;
const RECORDING_SUBJECTS = JSON.parse(readFileSync(
  new URL("../../../data/recording-subjects.json", import.meta.url), "utf8",
)).units;

export function recordingUnitBySlug(slug) {
  return unitBySlug(slug) ?? RECORDING_UNITS.find((row) => row.slug === slug)
    ?? RECORDING_SUBJECTS.find((row) => row.slug === slug);
}
