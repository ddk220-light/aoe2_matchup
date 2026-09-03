import { createHash } from "node:crypto";


function canonicalJson(value, ancestors = new Set()) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("canonical JSON requires a finite number");
    return JSON.stringify(value);
  }
  if (!value || typeof value !== "object") {
    throw new TypeError(`canonical JSON does not support ${typeof value}`);
  }
  if (ancestors.has(value)) throw new TypeError("canonical JSON does not support cycles");

  ancestors.add(value);
  let serialized;
  if (Array.isArray(value)) {
    serialized = `[${value.map((child) => canonicalJson(child, ancestors)).join(",")}]`;
  } else {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new TypeError("canonical JSON requires plain objects");
    }
    serialized = `{${Object.keys(value).sort().map((key) => (
      `${JSON.stringify(key)}:${canonicalJson(value[key], ancestors)}`
    )).join(",")}}`;
  }
  ancestors.delete(value);
  return serialized;
}


export function hashCanonicalJson(value) {
  return createHash("sha256").update(canonicalJson(value)).digest("hex");
}
