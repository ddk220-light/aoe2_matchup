const test = require("node:test");
const assert = require("node:assert/strict");

globalThis.RANKING_METHODS = require("../data/golden/derived_data_v3.metadata.json").methodology;
const scoreMethod = require("../apps/website/static/js/rankings_score_method.js");

test("land score help names the V3 matchups and settings", () => {
    const infantry = scoreMethod.buildHtml("infantry");
    assert.match(infantry, /1\/5.*Spanish Champion/s);
    assert.match(infantry, /Chinese Arbalester/);
    assert.match(infantry, /Turkish Cavalier/);
    assert.match(infantry, /27 units on the cheaper side/);
    assert.match(infantry, /three seeded runs/);
    assert.match(infantry, /use ten when/);
    assert.match(infantry, /surviving HP percentage/);
    assert.match(infantry, /50 is neutral/);
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

test("land categories use equal opponent weights without mobility adjustments", () => {
    for (const category of ["infantry", "archery", "stable"]) {
        const method = scoreMethod.getMethod(category);
        assert.equal(method.formula.length, category === "infantry" ? 5 : 7);
        assert.equal(method.adjustment, undefined);
        assert.match(method.finish, /No additional speed, range or cost multiplier/);
    }
});
