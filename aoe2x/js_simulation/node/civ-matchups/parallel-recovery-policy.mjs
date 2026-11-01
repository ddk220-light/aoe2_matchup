export function workerBudget(mainRunning, priorHeld, policy) {
  return Math.max(1, (mainRunning ? policy.workersWhileMainActive : policy.workersAfterMainStops)
    - (priorHeld ? 1 : 0));
}

export function dispatchable(pending, active, held, failed, slots) {
  const result = [], seen = new Set(active);
  for (const item of pending) {
    if (active.size + result.length >= slots) break;
    const key = `${item.job.id}:${item.seed}`;
    if (seen.has(key) || key === held || failed.includes(key)) continue;
    seen.add(key); result.push({...item, key});
  }
  return result;
}
