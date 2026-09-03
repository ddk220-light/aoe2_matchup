export const CHAMPION_RATIOS = Object.freeze(["1v1", "2v1", "2v3", "5v3", "6v3"]);
// Any NvM engagement ratio. Matchup fixtures go beyond the five champion
// ratios, and free-form ratios synthesize a formation server-side, so the
// review selection validates SHAPE, not membership in a fixed list.
export const RATIO_PATTERN = /^[1-9]\d?v[1-9]\d?$/;
// Optional matchup identity for a review row. Rows written before free unit
// selection have no pair; omitting the field entirely keeps them readable and
// keeps the stored shape unchanged for them.
export const PAIR_PATTERN = /^[a-z_]+-vs-[a-z_]+$/;
const STORAGE_KEY = "aoe2.cleanroom.champion.review.v1";
const MAX_NOTE_LENGTH = 2000;


function ratioRank(ratio) {
  const [left, right] = ratio.split("v").map(Number);
  return left * 100 + right;
}


function selection({ ratio, repeat, pair }) {
  if (typeof ratio !== "string" || !RATIO_PATTERN.test(ratio)) {
    throw new TypeError("ratio must look like 6v3");
  }
  if (!Number.isInteger(repeat) || repeat < 1 || repeat > 3) {
    throw new TypeError("tape repeat must be 1, 2, or 3");
  }
  if (pair === undefined) return { ratio, repeat };
  if (typeof pair !== "string" || !PAIR_PATTERN.test(pair)) {
    throw new TypeError("pair must look like champion-vs-paladin");
  }
  return { pair, ratio, repeat };
}


function snapshotIsImmutable(snapshot) {
  return (
    Object.isFrozen(snapshot)
    && Number.isInteger(snapshot.tick)
    && snapshot.tick >= 0
    && Array.isArray(snapshot.units)
    && Object.isFrozen(snapshot.units)
    && Array.isArray(snapshot.events)
    && Object.isFrozen(snapshot.events)
  );
}


export function createPlaybackCursor({ snapshots, onSnapshot = () => {} }) {
  if (
    !Array.isArray(snapshots)
    || !Object.isFrozen(snapshots)
    || snapshots.length === 0
    || snapshots.some((snapshot, index) => (
      !snapshotIsImmutable(snapshot) || snapshot.tick !== index
    ))
  ) {
    throw new TypeError("playback requires contiguous immutable snapshots");
  }
  let index = 0;

  function publish(nextIndex) {
    index = Math.max(0, Math.min(snapshots.length - 1, nextIndex));
    onSnapshot(snapshots[index]);
    return snapshots[index];
  }

  publish(0);
  return Object.freeze({
    current() { return snapshots[index]; },
    step() { return publish(index + 1); },
    reset() { return publish(0); },
    nextEvent() {
      const next = snapshots.findIndex((snapshot, candidate) => (
        candidate > index && snapshot.events.length > 0
      ));
      return publish(next === -1 ? snapshots.length - 1 : next);
    },
    seekTick(tick) {
      if (!Number.isInteger(tick)) throw new TypeError("tick must be an integer");
      return publish(tick);
    },
    atEnd() { return index === snapshots.length - 1; },
  });
}


function readRuns(storage) {
  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((row) => (
      typeof row?.ratio === "string"
      && RATIO_PATTERN.test(row.ratio)
      && Number.isInteger(row?.repeat)
      && row.repeat >= 1
      && row.repeat <= 3
      && typeof row.flagged === "boolean"
      && typeof row.note === "string"
      && row.note.length <= MAX_NOTE_LENGTH
      // pair is optional -- rows written before it existed have none, and
      // those must keep loading unchanged -- but if present it must validate,
      // the same as every other field here.
      && (row.pair === undefined || (typeof row.pair === "string" && PAIR_PATTERN.test(row.pair)))
    )).map(({ ratio, repeat, pair, flagged, note }) => (
      pair === undefined ? { ratio, repeat, flagged, note } : { pair, ratio, repeat, flagged, note }
    ));
  } catch {
    return [];
  }
}


function sortRuns(runs) {
  return [...runs].sort((left, right) => (
    ratioRank(left.ratio) - ratioRank(right.ratio)
    || left.repeat - right.repeat
  ));
}


export function createReviewFeedback({ storage, now = () => new Date().toISOString() }) {
  if (!storage || typeof storage.getItem !== "function" || typeof storage.setItem !== "function") {
    throw new TypeError("feedback requires Web Storage");
  }
  let runs = readRuns(storage);

  function save() {
    storage.setItem(STORAGE_KEY, JSON.stringify(sortRuns(runs)));
  }

  function set({ ratio, repeat, pair, flagged, note = "" }) {
    const key = selection({ ratio, repeat, pair });
    if (typeof flagged !== "boolean") throw new TypeError("flagged must be a boolean");
    if (typeof note !== "string" || note.length > MAX_NOTE_LENGTH) {
      throw new TypeError(`note must be at most ${MAX_NOTE_LENGTH} characters`);
    }
    const row = { ...key, flagged, note };
    runs = runs.filter((candidate) => (
      candidate.ratio !== ratio || candidate.repeat !== repeat
      || (candidate.pair ?? undefined) !== pair
    ));
    if (flagged || note.trim()) runs.push(row);
    save();
    return row;
  }

  return Object.freeze({
    set,
    flag({ ratio, repeat, pair, note = "" }) {
      return set({ ratio, repeat, pair, flagged: true, note });
    },
    get(key) {
      const valid = selection(key);
      return runs.find((row) => (
        row.ratio === valid.ratio && row.repeat === valid.repeat
        && (row.pair ?? undefined) === valid.pair
      )) ?? { ...valid, flagged: false, note: "" };
    },
    clear() {
      runs = [];
      storage.removeItem?.(STORAGE_KEY);
    },
    exportJson() {
      return {
        schemaVersion: 1,
        exportedAt: now(),
        runs: sortRuns(runs),
      };
    },
  });
}


export function parseReviewSelection(urlValue) {
  const url = new URL(urlValue);
  const ratio = url.searchParams.get("ratio");
  const repeat = Number(url.searchParams.get("repeat"));
  return typeof ratio === "string" && RATIO_PATTERN.test(ratio)
    && Number.isInteger(repeat) && repeat >= 1 && repeat <= 3
    ? { ratio, repeat }
    : { ratio: "1v1", repeat: 1 };
}


export function selectionUrl(urlValue, value) {
  const valid = selection(value);
  const url = new URL(urlValue);
  url.searchParams.set("ratio", valid.ratio);
  url.searchParams.set("repeat", String(valid.repeat));
  return url.href;
}


export function downloadJsonDocument({
  value,
  filename,
  documentRef = document,
  urlApi = URL,
  BlobCtor = Blob,
  schedule = setTimeout,
}) {
  if (!filename || typeof filename !== "string") throw new TypeError("download requires a filename");
  const body = `${JSON.stringify(value, null, 2)}\n`;
  const href = urlApi.createObjectURL(new BlobCtor([body], { type: "application/json" }));
  const link = documentRef.createElement("a");
  link.href = href;
  link.download = filename;
  link.hidden = true;
  documentRef.body.append(link);
  link.click();
  link.remove();
  schedule(() => urlApi.revokeObjectURL(href), 0);
}
