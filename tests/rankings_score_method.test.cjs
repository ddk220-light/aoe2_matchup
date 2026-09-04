const test = require("node:test");
const assert = require("node:assert/strict");

const scoreMethod = require("../apps/website/static/js/rankings_score_method.js");

test("land score help names the V3 matchups and settings", () => {
    const infantry = scoreMethod.buildHtml("infantry");
    assert.match(infantry, /75%.*Champion, Paladin, and Arbalester/s);
    assert.match(infantry, /10%.*Paladin matchup/s);
    assert.match(infantry, /15%.*Halberdier, Elite Skirmisher, and Hussar/s);
    assert.match(infantry, /equal resources/);
    assert.match(infantry, /27-unit cap/);
    assert.match(infantry, /five seeded runs/);
    assert.match(infantry, /remaining HP percentage/);
    assert.doesNotMatch(infantry, /General Combat|Anti-Cavalry|Anti-Trash/);
});

test("each ranking category has selectable score-method content", () => {
    for (const category of ["infantry", "archery", "stable", "siege", "naval"]) {
        const html = scoreMethod.buildHtml(category);
        assert.match(html, /how it is calculated/);
        assert.match(html, /Matchups and weights/);
        assert.match(html, /Higher is better/);
    }
});

test("ranged and stable help exposes their final mobility adjustment", () => {
    assert.match(scoreMethod.buildHtml("archery"), /movement speed and \(range \+ 1\)/);
    assert.match(scoreMethod.buildHtml("stable"), /multiplied by movement speed/);
});
