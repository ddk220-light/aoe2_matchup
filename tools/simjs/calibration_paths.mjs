import path from "node:path";

export function calibrationPaths(repoRoot) {
    const repo = path.resolve(repoRoot);
    const root = path.join(repo, "calibration");
    const fixtures = path.join(root, "fixtures");
    return {
        root,
        fixtures,
        manifest: path.join(fixtures, "manifest.json"),
        combatDicts: path.join(fixtures, "combat_dicts.json"),
        spawns: path.join(fixtures, "spawns.json"),
        fightSets: path.join(fixtures, "fight_sets.json"),
        runs: path.join(root, "runs"),
    };
}
