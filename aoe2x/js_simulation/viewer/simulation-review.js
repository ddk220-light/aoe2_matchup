export const CHAMPION_RATIOS = Object.freeze(["1v1", "2v1", "2v3", "5v3", "6v3"]);
const STORAGE_KEY = "aoe2.cleanroom.champion.review.v1";
const MAX_NOTE_LENGTH = 2000;


function selection({ ratio, repeat }) {
  if (!CHAMPION_RATIOS.includes(ratio)) throw new TypeError("unknown Champion ratio");
  if (!Number.isInteger(repeat) || repeat < 1 || repeat > 3) {
    throw new TypeError("tape repeat must be 1, 2, or 3");
  }
  return { ratio, repeat };
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
      CHAMPION_RATIOS.includes(row?.ratio)
      && Number.isInteger(row?.repeat)
      && row.repeat >= 1
      && row.repeat <= 3
      && typeof row.flagged === "boolean"
      && typeof row.note === "string"
      && row.note.length <= MAX_NOTE_LENGTH
    )).map(({ ratio, repeat, flagged, note }) => ({ ratio, repeat, flagged, note }));
  } catch {
    return [];
  }
}


function sortRuns(runs) {
  return [...runs].sort((left, right) => (
    CHAMPION_RATIOS.indexOf(left.ratio) - CHAMPION_RATIOS.indexOf(right.ratio)
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

  function set({ ratio, repeat, flagged, note = "" }) {
    const key = selection({ ratio, repeat });
    if (typeof flagged !== "boolean") throw new TypeError("flagged must be a boolean");
    if (typeof note !== "string" || note.length > MAX_NOTE_LENGTH) {
      throw new TypeError(`note must be at most ${MAX_NOTE_LENGTH} characters`);
    }
    const row = { ...key, flagged, note };
    runs = runs.filter((candidate) => (
      candidate.ratio !== ratio || candidate.repeat !== repeat
    ));
    if (flagged || note.trim()) runs.push(row);
    save();
    return row;
  }

  return Object.freeze({
    set,
    flag({ ratio, repeat, note = "" }) {
      return set({ ratio, repeat, flagged: true, note });
    },
    get(key) {
      const valid = selection(key);
      return runs.find((row) => (
        row.ratio === valid.ratio && row.repeat === valid.repeat
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
  return CHAMPION_RATIOS.includes(ratio) && Number.isInteger(repeat) && repeat >= 1 && repeat <= 3
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
