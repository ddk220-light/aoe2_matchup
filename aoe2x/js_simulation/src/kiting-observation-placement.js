import { readFile } from "node:fs/promises";

import { placeArmy, sideCapacity } from "./placement.js";


const STANDARD_UNITS_SHA256 = "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D";
const HCA_CHAMPION_SHA256 = "EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5";
const truthCache = new Map();


function cellKey({ x, y }) {
  return `${x},${y}`;
}


function freezeCells(cells) {
  return Object.freeze(cells.map(({ x, y }) => Object.freeze({ x, y })));
}


async function loadTruth(root) {
  const key = String(root);
  if (!truthCache.has(key)) {
    truthCache.set(key, Promise.all([
      readFile(new URL(
        "calibration/fixtures/standard_units/standard_units_truth.json", root,
      ), "utf8").then(JSON.parse),
      readFile(new URL(
        "calibration/fixtures/hcavarcher_vs_champion_kiting_basics.json", root,
      ), "utf8").then(JSON.parse),
    ]).then(([standard, hcaChampion]) => {
      if (standard.archive?.zip_sha256 !== STANDARD_UNITS_SHA256) {
        throw new Error("standard-units placement fixture has the wrong archive hash");
      }
      if (hcaChampion.zip_sha256 !== HCA_CHAMPION_SHA256) {
        throw new Error("HCA-versus-Champion placement fixture has the wrong archive hash");
      }
      return Object.freeze({ standard, hcaChampion });
    }));
  }
  return truthCache.get(key);
}


function cellsByOwner(startingUnits) {
  const byOwner = { 2: [], 3: [] };
  for (const unit of startingUnits) {
    const owner = Number(unit.owner ?? unit[1]);
    const referenceId = Number(unit.id ?? unit[0]);
    const x = Number(unit.x ?? unit[3]);
    const y = Number(unit.y ?? unit[4]);
    if (!(owner in byOwner) || !Number.isFinite(referenceId)
        || !Number.isFinite(x) || !Number.isFinite(y)) {
      throw new Error("kiting placement fixture contains an invalid starting unit");
    }
    byOwner[owner].push({ referenceId, x, y });
  }
  for (const owner of [2, 3]) {
    byOwner[owner].sort((left, right) => left.referenceId - right.referenceId);
  }
  return byOwner;
}


function familyFallback({ owner, count, family, recorded }) {
  const selected = placeArmy({ owner, count, family });
  const selectedKeys = new Set(selected.map(cellKey));
  const ordered = recorded.filter((cell) => selectedKeys.has(cellKey(cell)));
  const orderedKeys = new Set(ordered.map(cellKey));
  ordered.push(...selected.filter((cell) => !orderedKeys.has(cellKey(cell))));
  if (ordered.length !== count) {
    throw new Error(`could not construct ${count}-unit ${family} placement for owner ${owner}`);
  }
  return ordered;
}


export async function kitingObservationPlacement(root, {
  matchup,
  family,
  count2,
  count3,
}) {
  const { standard, hcaChampion } = await loadTruth(root);
  const standardRow = standard.rows.find(({ id }) => id === matchup.id);
  if (!standardRow?.runs?.length) {
    throw new Error(`standard-units truth has no placement row ${matchup.id}`);
  }

  const dedicatedRatio = matchup.rangedSlug === "heavy_cav_archer"
      && matchup.meleeSlug === "champion"
    ? hcaChampion.ratios?.[`${count2}v${count3}`]
    : null;
  if (dedicatedRatio?.canonicalStartUnits) {
    const exact = cellsByOwner(dedicatedRatio.canonicalStartUnits);
    if (exact[2].length !== count2 || exact[3].length !== count3) {
      throw new Error(`dedicated ${count2}v${count3} placement has the wrong unit counts`);
    }
    return Object.freeze({
      2: freezeCells(exact[2]),
      3: freezeCells(exact[3]),
      source: "dedicated-tape-ratio",
    });
  }

  const recorded = cellsByOwner(standardRow.runs[0].starting_units);
  const counts = { 2: count2, 3: count3 };
  const exactCounts = {
    2: Number(standardRow.side2?.count ?? standardRow.runs[0].side2?.count),
    3: Number(standardRow.side3?.count ?? standardRow.runs[0].side3?.count),
  };
  const placement = {};
  let exact = true;
  for (const owner of [2, 3]) {
    if (counts[owner] > sideCapacity(owner, family)) {
      throw new RangeError(`owner ${owner} ${family} placement cannot hold ${counts[owner]} units`);
    }
    if (counts[owner] === exactCounts[owner]) {
      placement[owner] = freezeCells(recorded[owner]);
    } else {
      exact = false;
      placement[owner] = freezeCells(familyFallback({
        owner,
        count: counts[owner],
        family,
        recorded: recorded[owner],
      }));
    }
  }
  return Object.freeze({
    2: placement[2],
    3: placement[3],
    source: exact ? "standard-units-tape-row" : "family-count-fallback",
  });
}
