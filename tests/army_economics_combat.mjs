// Exercise real combat with explicit armies before/after a cost-only overlay.
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {runFight} from "../aoe2x/js_simulation/src/fight.js";
import {buildArenaPhysicsMap} from "../aoe2x/js_simulation/src/arena-physics-map.js";
import {unitDescriptorFromMechanics} from "../aoe2x/js_simulation/src/mechanics-schema.js";

const outputs = [];
for (const config of JSON.parse(readFileSync(0, "utf8"))) {
    const [a, b] = config.teams, s = config.scenario;
    const trace = createHash("sha256");
    const result = await runFight(new URL("../aoe2x/js_simulation/", import.meta.url), {
        side2Slug: a.mechanics.unit_slug, n2: a.count, side3Slug: b.mechanics.unit_slug, n3: b.count,
        map: buildArenaPhysicsMap(s.mapFixture), placementByOwner: s.placementByOwner,
        openingPatrolByOwner: s.openingPatrolByOwner, placementSource: s.goldenSha256,
        preserveOwnerOrientation: s.preserveOwnerOrientation === true,
        auxiliaryArmiesByOwner: s.auxiliaryArmiesByOwner, diplomacyByOwner: s.diplomacyByOwner,
        triggers: s.triggers, victoryTeams: s.victoryTeams, openingSeed: config.seed,
        disableAiOrders: true, disableKiting: true, retainSnapshots: false,
        mechanicsBySide: {2: a.mechanics, 3: b.mechanics},
        unitDescriptorBySide: {2: unitDescriptorFromMechanics(a.mechanics), 3: unitDescriptorFromMechanics(b.mechanics)},
        onSnapshot: snapshot => trace.update(JSON.stringify([snapshot.tick, snapshot.units])),
    });
    outputs.push({trace: trace.digest("hex"), events: result.eventLogHash, ticks: result.ticks,
        winner: result.winnerOwner, remaining: result.remainingByOwner});
}
process.stdout.write(JSON.stringify(outputs));
