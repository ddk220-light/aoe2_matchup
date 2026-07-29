import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const DIR = "apps/website/static/js/engine";
const BANNED = /Math\.random|document\.|window\.|getElementById|requestAnimationFrame|performance\.now|new Image|fetch\(|alert\(/;

test("engine sources are DOM-free and Math.random-free", () => {
    for (const f of readdirSync(DIR).filter((f) => f.endsWith(".js"))) {
        const src = readFileSync(`${DIR}/${f}`, "utf8");
        const hit = src.match(BANNED);
        assert.equal(hit, null, `${f} contains banned token: ${hit && hit[0]}`);
    }
});
