// Observability for an isolated copy of the frozen campaign runtime.
// No attack, movement, targeting, or random-number behavior is changed.
export function instrumentSource(path, source) {
  const replaceOnce = (before, after) => {
    if (source.split(before).length !== 2) throw new Error(`diagnostic hook mismatch: ${path}`);
    source = source.replace(before, after);
  };
  if (path.endsWith('/src/fight.js')) {
    replaceOnce('const MAX_TICKS = 9000;',
      'const MAX_TICKS = globalThis.__rankingDiagnostic.maxTicks;');
  } else if (path.endsWith('/src/combat/world.js')) {
    replaceOnce('const MAX_WORLD_TICKS = 9000;',
      'const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;');
    replaceOnce('  let current = world;\n  publish(current);',
      '  let current = world;\n  globalThis.__rankingDiagnostic.observe(current);\n  publish(current);');
    replaceOnce('  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {\n    current = stepWorld(current);\n    publish(current);',
      '  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {\n'
      + '    globalThis.__rankingDiagnostic.beforeStep(current);\n'
      + '    current = stepWorld(current);\n'
      + '    globalThis.__rankingDiagnostic.observe(current);\n'
      + '    publish(current);');
    replaceOnce('    if (result !== null) return compactResult(result, current);\n    current = compactWorld(current);',
      '    if (result !== null) return compactResult(result, current);\n'
      + '    if (globalThis.__rankingDiagnostic.stopRequested()) {\n'
      + '      return compactResult(worldResult(current, "timeout"), current);\n'
      + '    }\n    current = compactWorld(current);');
  }
  return source;
}
