const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const code = fs.readFileSync(path.join(__dirname, '../apps/website/static/js/civilization-view.js'), 'utf8');
const context = vm.createContext({
    escapeHtml: value => String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'),
    hasSprite: () => false,
    spriteFor: () => '/legacy/idle.png',
    getIconUrl: () => '/legacy/icon.png',
    animFor: () => '/legacy/attack.webp',
    CIV_EMBLEM_BASE: '/legacy/emblems/',
    TIER_META: { good: { label: 'Good', hint: 'Above average.' } },
    COLUMN_ORDER: ['cavalry', 'ranged', 'infantry', 'siege', 'navy'],
    BUILDING_ORDER_CIV: ['barracks', 'archery_range', 'stable', 'castle', 'siege_workshop', 'dock'],
    BUILDING_LABELS: { barracks: 'Barracks', castle: 'Castle', dock: 'Dock' },
    LINE_NAMES: {},
    SUMMARY_TEMPLATES: {},
    window: {},
});
vm.runInContext(code, context);

const unit = {
    unit_name: 'Elite Jomsviking', unit_slug: 'elite_jomsviking', line_slug: 'jomsviking',
    building: 'barracks', is_unique: true,
    stats: { hp: 100, attack: 14, cost_food: 45, cost_wood: 0, cost_gold: 30 },
    bonus_abilities: ['Fast raid'], special_effects: ['Charged attack'],
    media: {
        icon: '/static/media/185872/jomsviking/icon.png',
        icon_transparent: '/static/media/185872/jomsviking/icon_transparent.png',
        idle: '/static/media/185872/jomsviking/idle.png',
        attack: '/static/media/185872/jomsviking/attack.webp',
    },
};

test('new unit card uses supplied media, costs and abilities without an invented tier', () => {
    const html = context.renderUnitBadge(unit, 'infantry');
    assert.match(html, /idle\.png/);
    assert.match(html, /icon\.png/);
    assert.match(html, /icon_transparent\.png/);
    assert.match(html, /data-preview-src="[^"]*attack\.webp"/);
    assert.match(html, /Attack preview/);
    assert.match(html, /45.*Food/s);
    assert.match(html, /30.*Gold/s);
    assert.doesNotMatch(html, /Wood|Coming soon|Unranked|data-anim-name|tier-good/);
    assert.match(html, /Fast raid|Charged attack/);
});

test('only available ship media controls render and supplied tiers use normal path', () => {
    const ship = { ...unit, unit_name: 'Elite Longship', building: 'dock', tier: 'good', score: 63,
        stats: { hp: 156, cost_food: 0, cost_wood: 80, cost_gold: 50 },
        media: { icon: '/ship/icon.png', idle: '/ship/idle.png', attack: '/ship/attack.webp' } };
    const html = context.renderUnitBadge(ship, 'navy');
    assert.match(html, /is-tier-good/);
    assert.match(html, /tier-good/);
    assert.match(html, /Effectiveness score: 63\.0/);
    assert.match(html, /\/ship\/attack\.webp/);
    assert.match(html, /80.*Wood/s);
    assert.match(html, /50.*Gold/s);
    assert.doesNotMatch(html, /Food|Transparent icon|Blue|idle_blue|icon_transparent/);
});

test('legacy card keeps catalog media behavior and explicit building groups new row', () => {
    const legacy = { unit_name: 'Paladin', unit_slug: 'paladin', line_slug: 'knight',
        stats: { hp: 180 }, tier: 'good' };
    assert.match(context.renderUnitBadge(legacy, 'cavalry'), /data-anim-name="Paladin"/);
    const groups = context.groupUnitsByBuilding({ infantry: { jomsviking: [unit] } });
    assert.equal(groups.barracks[0].unit.unit_name, 'Elite Jomsviking');
});

test('selecting Attack preview changes the visible detail image and active control', () => {
    const image = { src: '/ship/idle.png' };
    const idle = { dataset: { previewSrc: '/ship/idle.png' }, classList: { toggle(name, active) { this.active = active; } } };
    const attack = { dataset: { previewSrc: '/ship/attack.webp' }, classList: { toggle(name, active) { this.active = active; } } };
    const tooltip = {
        querySelector: selector => selector === '.anim-slot' ? image : null,
        querySelectorAll: () => [idle, attack],
    };
    assert.equal(context.activateCivMediaPreview(attack, tooltip), true);
    assert.equal(image.src, '/ship/attack.webp');
    assert.equal(attack.classList.active, true);
    assert.equal(idle.classList.active, false);
});

test('detail page selector follows a different civilization page while overview stays in place', () => {
    context.window.PRESELECT_CIV = 'Danes';
    assert.equal(context.shouldNavigateCivCard('Saxons'), true);
    assert.equal(context.shouldNavigateCivCard('Danes'), false);
    delete context.window.PRESELECT_CIV;
    assert.equal(context.shouldNavigateCivCard('Saxons'), false);
});
