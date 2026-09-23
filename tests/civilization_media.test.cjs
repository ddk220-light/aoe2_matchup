const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const context = vm.createContext({
    escapeHtml: value => String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'),
    hasSprite: () => true,
    spriteFor: name => '/assets/img/unit_sprites/' + name.toLowerCase().replace(/ /g, '_') + '.png',
    getIconUrl: name => '/assets/img/units/' + name.replace(/ /g, '_') + '.png',
    animFor: name => '/assets/anim/' + name.toLowerCase().replace(/ /g, '_') + '.webp',
    CIV_EMBLEM_BASE: '/legacy/emblems/',
    TIER_META: { good: { label: 'Good', hint: 'Above average.' } },
    COLUMN_ORDER: ['cavalry', 'ranged', 'infantry', 'siege', 'navy'],
    BUILDING_ORDER_CIV: ['barracks', 'archery_range', 'stable', 'castle', 'siege_workshop', 'dock'],
    BUILDING_LABELS: { barracks: 'Barracks', castle: 'Castle', dock: 'Dock' },
    LINE_NAMES: {},
    SUMMARY_TEMPLATES: {},
    window: {},
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../apps/website/static/js/civilization-view.js'), 'utf8'), context);

const unit = {
    unit_name: 'Elite Jomsviking', unit_slug: 'elite_jomsviking', line_slug: 'jomsviking',
    building: 'castle', is_unique: true,
    stats: { hp: 100, attack: 14, cost_food: 45, cost_wood: 0, cost_gold: 30 },
    bonus_abilities: ['Fast raid'], special_effects: ['Charged attack'],
};

test('new and existing units use the same normal popup without extra media or focus controls', () => {
    for (const name of ['Elite Jomsviking', 'Elite Varangian Guard', 'Hussar', 'Paladin']) {
        const html = context.renderUnitBadge({ ...unit, unit_name: name }, 'infantry');
        assert.ok(html.includes('data-anim-name="' + name + '"'));
        assert.ok(html.includes('/assets/img/unit_sprites/' + name.toLowerCase().replace(/ /g, '_') + '.png'));
        assert.doesNotMatch(html, /tt-media-control|data-preview-src|data-anim-src|tabindex|Details for/);
        assert.match(html, /45.*Food/s);
        assert.match(html, /30.*Gold/s);
        assert.match(html, /\/resources\/food\.png/);
        assert.match(html, /\/resources\/gold\.png/);
        assert.doesNotMatch(html, /\/resources\/wood\.png|Coming soon|Unranked/);
        assert.match(html, /Fast raid|Charged attack/);
    }
});

test('supplied real ranks and resource costs retain their existing rendering', () => {
    const html = context.renderUnitBadge({ ...unit, tier: 'good', score: 63,
        stats: { hp: 156, cost_food: 0, cost_wood: 80, cost_gold: 50 } }, 'navy');
    assert.match(html, /is-tier-good/);
    assert.match(html, /Effectiveness score: 63\.0/);
    assert.match(html, /80.*Wood/s);
    assert.match(html, /50.*Gold/s);
    assert.doesNotMatch(html, /\/resources\/food\.png/);
});

test('shared hover animation plays and restores the still without a per-card override', () => {
    const handlers = {};
    const hoverContext = vm.createContext({
        window: {
            SITE_CATALOG: { civilizations: [], icon_names: {}, unique_buildings: {} },
            _ASSET_ANIMS: { 'Elite Jarl': '/assets/anim/elite_jarl.webp' },
        },
        document: { addEventListener: (event, handler) => { handlers[event] = handler; } },
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../apps/website/static/js/constants.js'), 'utf8'), hoverContext);
    const image = { src: '/assets/img/unit_sprites/elite_jarl.png', dataset: {}, getAttribute: () => image.src };
    const badge = { dataset: { animName: 'Elite Jarl' }, querySelector: () => image, contains: () => false };
    const target = { closest: () => badge };
    handlers.mouseover({ target, relatedTarget: null });
    assert.equal(image.src, '/assets/anim/elite_jarl.webp');
    handlers.mouseout({ target, relatedTarget: null });
    assert.equal(image.src, '/assets/img/unit_sprites/elite_jarl.png');
});

test('new units remain grouped by their actual building', () => {
    const groups = context.groupUnitsByBuilding({ infantry: { jomsviking: [unit] } });
    assert.equal(groups.castle[0].unit.unit_name, 'Elite Jomsviking');
});

test('choosing another civilization on a detail page stays in place', () => {
    const cards = ['Danes', 'Saxons'].map(name => ({
        dataset: { civ: name },
        addEventListener(event, handler) { this.click = handler; },
    }));
    let selected = null;
    const picker = vm.createContext({
        CIVS: ['Danes', 'Saxons'],
        civGrid: { querySelectorAll: () => cards },
        window: { PRESELECT_CIV: 'Danes' },
        onCivClick: name => { selected = name; },
    });
    const source = fs.readFileSync(path.join(__dirname, '../apps/website/static/js/matchup.js'), 'utf8');
    // Exercise the actual picker registration, isolated from its asynchronous data loader.
    vm.runInContext(source.slice(source.indexOf('CIVS.forEach('),
        source.indexOf('/* ---- Per-civ landing page preselect')), picker);
    let prevented = false;
    cards[1].click({ preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assert.equal(selected, 'Saxons');
});
