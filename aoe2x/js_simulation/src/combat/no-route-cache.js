// Exact negative reachability proofs, not approximated paths. The key contains
// every discrete input to canEnterFrom and the complete goal-cell mask. Costs
// and heuristic order cannot make a goal reachable after the heap is exhausted.
export class ExactNoRouteCache {
  constructor(limit = 128) {
    this.limit = limit;
    this.entries = new Map();
    this.hits = 0;
    this.misses = 0;
  }
  key(cols, rows, startIndex, fields) {
    const size = cols * rows;
    // Bound memory and spread argument counts. Larger maps simply use A*.
    if (size > 8192) return null;
    if (fields.some(field => !(field instanceof Uint8Array) || field.length !== size)) {
      throw new TypeError('no-route key requires full byte grids');
    }
    return `${cols}:${rows}:${startIndex}:` + fields.map(field => String.fromCharCode(...field)).join('');
  }
  has(key) {
    if (key === null) return false;
    if (!this.entries.has(key)) { this.misses++; return false; }
    this.hits++;
    this.entries.delete(key);
    this.entries.set(key, true);
    return true;
  }
  rememberExhausted(key) {
    if (key === null) return;
    this.entries.delete(key);
    this.entries.set(key, true);
    if (this.entries.size > this.limit) this.entries.delete(this.entries.keys().next().value);
  }
  statistics() { return {hits:this.hits,misses:this.misses,entries:this.entries.size}; }
}
