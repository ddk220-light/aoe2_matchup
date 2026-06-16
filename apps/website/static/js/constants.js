/* ============================================
   AoE2 Unit Analyzer — Shared Constants

   SINGLE source of truth for frontend constants:
   ENABLED_CIVS, NAME_TO_ICON, UNIQUE_BUILDING,
   ICON_BASE, CIV_EMBLEM_BASE. Loaded by base.html
   before the page scripts — do NOT re-declare
   these in templates or page JS (the old
   per-template copies are gone). The Python civ
   list is validated server-side against
   aoe2_reference.db; keep ENABLED_CIVS in sync
   when a civ is added (see
   docs/architecture/runbooks.md).
   ============================================ */

/* --- Icon URLs --- */
const ICON_BASE = "/static/img/units/";
const CIV_EMBLEM_BASE =
    "https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/";

/* --- Enabled Civilizations --- */
const ENABLED_CIVS = [
    "Armenians",
    "Aztecs",
    "Bengalis",
    "Berbers",
    "Bohemians",
    "Britons",
    "Bulgarians",
    "Burgundians",
    "Burmese",
    "Byzantines",
    "Celts",
    "Chinese",
    "Cumans",
    "Dravidians",
    "Ethiopians",
    "Franks",
    "Georgians",
    "Goths",
    "Gurjaras",
    "Hindustanis",
    "Huns",
    "Incas",
    "Italians",
    "Japanese",
    "Jurchens",
    "Khitans",
    "Khmer",
    "Koreans",
    "Lithuanians",
    "Magyars",
    "Malay",
    "Malians",
    "Mapuche",
    "Mayans",
    "Mongols",
    "Muisca",
    "Persians",
    "Poles",
    "Portuguese",
    "Romans",
    "Saracens",
    "Shu",
    "Sicilians",
    "Slavs",
    "Spanish",
    "Tatars",
    "Teutons",
    "Tupi",
    "Turks",
    "Vietnamese",
    "Vikings",
    "Wei",
    "Wu",
];

/* --- Unit Icon Mapping (wiki infobox portraits) --- */
const NAME_TO_ICON = {
    // Generic infantry
    Spearman: "Spearman",
    Pikeman: "Pikeman",
    Halberdier: "Halberdier",
    "Man-at-Arms": "Man-at-Arms",
    "Long Swordsman": "Long_Swordsman",
    "Two-Handed Swordsman": "Two-Handed_Swordsman",
    Champion: "Champion",
    Legionary: "Legionary",
    "Eagle Scout": "Eagle_Scout",
    "Eagle Warrior": "Eagle_Warrior",
    "Elite Eagle Warrior": "Elite_Eagle_Warrior",
    // Generic ranged
    Archer: "Archer",
    Crossbowman: "Crossbowman",
    Arbalester: "Arbalester",
    Skirmisher: "Skirmisher",
    "Elite Skirmisher": "Elite_Skirmisher",
    "Cavalry Archer": "Cavalry_Archer",
    "Heavy Cavalry Archer": "Heavy_Cavalry_Archer",
    "Hand Cannoneer": "Hand_Cannoneer",
    // Generic cavalry
    "Scout Cavalry": "Scout_Cavalry",
    "Light Cavalry": "Light_Cavalry",
    Hussar: "Hussar",
    "Winged Hussar": "Winged_Hussar",
    Knight: "Knight",
    Cavalier: "Cavalier",
    Paladin: "Paladin",
    Savar: "Savar",
    "Camel Rider": "Camel_Rider",
    "Heavy Camel Rider": "Heavy_Camel_Rider",
    "Steppe Lancer": "Steppe_Lancer",
    "Elite Steppe Lancer": "Elite_Steppe_Lancer",
    // Siege
    "Battering Ram": "Battering_Ram",
    "Capped Ram": "Capped_Ram",
    "Siege Ram": "Siege_Ram",
    Mangonel: "Mangonel",
    Onager: "Onager",
    "Siege Onager": "Siege_Onager",
    Scorpion: "Scorpion",
    "Heavy Scorpion": "Heavy_Scorpion",
    "Bombard Cannon": "Bombard_Cannon",
    Houfnice: "Houfnice",  // Bohemian Bombard Cannon upgrade (UT)
    Trebuchet: "Trebuchet",
    // Regional
    Slinger: "Slinger",
    "Imperial Skirmisher": "Imperial_Skirmisher",
    Genitour: "Genitour",
    "Elite Genitour": "Elite_Genitour",
    "Imperial Camel Rider": "Imperial_Camel_Rider",
    "Battle Elephant": "Battle_Elephant",
    "Elite Battle Elephant": "Elite_Battle_Elephant",
    "Elephant Archer": "Elephant_Archer",
    "Elite Elephant Archer": "Elite_Elephant_Archer",
    "Armored Elephant": "Armored_Elephant",
    "Siege Elephant": "Siege_Elephant",
    // AoK/AoC unique units
    Longbowman: "Longbowman",
    "Elite Longbowman": "Elite_Longbowman",
    Cataphract: "Cataphract",
    "Elite Cataphract": "Elite_Cataphract",
    "Woad Raider": "Woad_Raider",
    "Elite Woad Raider": "Elite_Woad_Raider",
    "Chu Ko Nu": "Chu_Ko_Nu",
    "Elite Chu Ko Nu": "Elite_Chu_Ko_Nu",
    "Throwing Axeman": "Throwing_Axeman",
    "Elite Throwing Axeman": "Elite_Throwing_Axeman",
    Huskarl: "Huskarl",
    "Elite Huskarl": "Elite_Huskarl",
    Samurai: "Samurai",
    "Elite Samurai": "Elite_Samurai",
    Mangudai: "Mangudai",
    "Elite Mangudai": "Elite_Mangudai",
    "War Elephant": "War_Elephant",
    "Elite War Elephant": "Elite_War_Elephant",
    Mameluke: "Mameluke",
    "Elite Mameluke": "Elite_Mameluke",
    "Teutonic Knight": "Teutonic_Knight",
    "Elite Teutonic Knight": "Elite_Teutonic_Knight",
    Janissary: "Janissary",
    "Elite Janissary": "Elite_Janissary",
    Berserk: "Berserk",
    "Elite Berserk": "Elite_Berserk",
    "Jaguar Warrior": "Jaguar_Warrior",
    "Elite Jaguar Warrior": "Elite_Jaguar_Warrior",
    "Plumed Archer": "Plumed_Archer",
    "Elite Plumed Archer": "Elite_Plumed_Archer",
    Tarkan: "Tarkan",
    "Elite Tarkan": "Elite_Tarkan",
    "War Wagon": "War_Wagon",
    "Elite War Wagon": "Elite_War_Wagon",
    Conquistador: "Conquistador",
    "Elite Conquistador": "Elite_Conquistador",
    // The Forgotten
    Kamayuk: "Kamayuk",
    "Elite Kamayuk": "Elite_Kamayuk",
    "Genoese Crossbowman": "Genoese_Crossbowman",
    "Elite Genoese Crossbowman": "Elite_Genoese_Crossbowman",
    "Magyar Huszar": "Magyar_Huszar",
    "Elite Magyar Huszar": "Elite_Magyar_Huszar",
    Boyar: "Boyar",
    "Elite Boyar": "Elite_Boyar",
    Condottiero: "Condottiero",
    // African Kingdoms
    "Camel Archer": "Camel_Archer",
    "Elite Camel Archer": "Elite_Camel_Archer",
    "Shotel Warrior": "Shotel_Warrior",
    "Elite Shotel Warrior": "Elite_Shotel_Warrior",
    Gbeto: "Gbeto",
    "Elite Gbeto": "Elite_Gbeto",
    "Organ Gun": "Organ_Gun",
    "Elite Organ Gun": "Elite_Organ_Gun",
    // Rise of the Rajas
    Arambai: "Arambai",
    "Elite Arambai": "Elite_Arambai",
    "Ballista Elephant": "Ballista_Elephant",
    "Elite Ballista Elephant": "Elite_Ballista_Elephant",
    "Karambit Warrior": "Karambit_Warrior",
    "Elite Karambit Warrior": "Elite_Karambit_Warrior",
    "Rattan Archer": "Rattan_Archer",
    "Elite Rattan Archer": "Elite_Rattan_Archer",
    // Last Khans
    Konnik: "Konnik",
    "Elite Konnik": "Elite_Konnik",
    Keshik: "Keshik",
    "Elite Keshik": "Elite_Keshik",
    Kipchak: "Kipchak",
    "Elite Kipchak": "Elite_Kipchak",
    Leitis: "Leitis",
    "Elite Leitis": "Elite_Leitis",
    // Lords of the West / Dawn of the Dukes
    Coustillier: "Coustillier",
    "Elite Coustillier": "Elite_Coustillier",
    Serjeant: "Serjeant",
    "Elite Serjeant": "Elite_Serjeant",
    "Flemish Militia": "Flemish_Militia",
    Obuch: "Obuch",
    "Elite Obuch": "Elite_Obuch",
    "Hussite Wagon": "Hussite_Wagon",
    "Elite Hussite Wagon": "Elite_Hussite_Wagon",
    // Dynasties of India
    "Ratha (Melee)": "Ratha",
    "Elite Ratha (Melee)": "Elite_Ratha",
    "Ratha (Ranged)": "Ratha",
    "Elite Ratha (Ranged)": "Elite_Ratha",
    "Urumi Swordsman": "Urumi_Swordsman",
    "Elite Urumi Swordsman": "Elite_Urumi_Swordsman",
    "Shrivamsha Rider": "Shrivamsha_Rider",
    "Elite Shrivamsha Rider": "Elite_Shrivamsha_Rider",
    "Chakram Thrower": "Chakram_Thrower",
    "Elite Chakram Thrower": "Elite_Chakram_Thrower",
    Ghulam: "Ghulam",
    "Elite Ghulam": "Elite_Ghulam",
    "Imperial Camel Rider": "Imperial_Camel_Rider",
    // Return of Rome
    Centurion: "Centurion",
    "Elite Centurion": "Elite_Centurion",
    // The Mountain Royals
    "Composite Bowman": "Composite_Bowman",
    "Elite Composite Bowman": "Elite_Composite_Bowman",
    "Warrior Priest": "Warrior_Priest",
    Monaspa: "Monaspa",
    "Elite Monaspa": "Elite_Monaspa",
    // Three Kingdoms
    "Iron Pagoda": "Iron_Pagoda",
    "Elite Iron Pagoda": "Elite_Iron_Pagoda",
    Grenadier: "Grenadier",
    "Liao Dao": "Liao_Dao",
    "Elite Liao Dao": "Elite_Liao_Dao",
    "Mounted Trebuchet": "Mounted_Trebuchet",
    "White Feather Crossbowman": "White_Feather_Crossbowman",
    "Elite White Feather Crossbowman": "Elite_White_Feather_Crossbowman",
    "White Feather Guard": "White_Feather_Crossbowman",
    "Elite White Feather Guard": "Elite_White_Feather_Crossbowman",
    "Traction Trebuchet": "Traction_Trebuchet",
    "War Chariot": "War_Chariot",
    "Elite War Chariot": "Elite_War_Chariot",
    "Tiger Cavalry": "Tiger_Cavalry",
    "Elite Tiger Cavalry": "Elite_Tiger_Cavalry",
    "Xianbei Raider": "Xianbei_Raider",
    "Fire Archer": "Fire_Archer",
    "Elite Fire Archer": "Elite_Fire_Archer",
    "Jian Swordsman": "Jian_Swordsman",
    "Hei-Kuang Cavalry": "Hei-Kuang_Cavalry",
    "Heavy Hei-Kuang Cavalry": "Heavy_Hei-Kuang_Cavalry",
    "Rocket Cart": "Rocket_Cart",
    "Heavy Rocket Cart": "Heavy_Rocket_Cart",
    "Fire Lancer": "Fire_Lancer",
    "Elite Fire Lancer": "Elite_Fire_Lancer",
    // The Last Chieftains
    "Champi Runner": "Champi_Runner",
    "Champi Scout": "Champi_Scout",
    "Champi Warrior": "Champi_Warrior",
    "Elite Champi Warrior": "Elite_Champi_Warrior",
    "Guecha Warrior": "Guecha_Warrior",
    "Elite Guecha Warrior": "Elite_Guecha_Warrior",
    "Temple Guard": "Temple_Guard",
    "Elite Temple Guard": "Elite_Temple_Guard",
    Kona: "Kona",
    "Elite Kona": "Elite_Kona",
    "Bolas Rider": "Bolas_Rider",
    "Elite Bolas Rider": "Elite_Bolas_Rider",
    "Blackwood Archer": "Blackwood_Archer",
    "Elite Blackwood Archer": "Elite_Blackwood_Archer",
    "Ibirapema Warrior": "Ibirapema_Warrior",
    "Elite Ibirapema Warrior": "Elite_Ibirapema_Warrior",
    "War Dog": "War_Dog",
    "Elite War Dog": "Elite_War_Dog",
    // Naval — standard
    Galley: "Galley",
    "War Galley": "War_Galley",
    Galleon: "Galleon",
    "Fire Galley": "Fire_Galley",
    "Fire Ship": "Fire_Ship",
    "Fast Fire Ship": "Fast_Fire_Ship",
    Hulk: "Hulk",
    "War Hulk": "War_Hulk",
    Carrack: "Carrack",
    "Demo Raft": "Demo_Raft",
    "Demo Ship": "Demo_Ship",
    "Heavy Demo Ship": "Heavy_Demo_Ship",
    "Cannon Galleon": "Cannon_Galleon",
    "Elite Cannon Galleon": "Elite_Cannon_Galleon",
    // Naval — unique
    Longboat: "Longboat",
    "Elite Longboat": "Elite_Longboat",
    "Turtle Ship": "Turtle_Ship",
    "Elite Turtle Ship": "Elite_Turtle_Ship",
    Caravel: "Caravel",
    "Elite Caravel": "Elite_Caravel",
    Thirisadai: "Thirisadai",
    Dromon: "Dromon",
    "Lou Chuan": "Lou_Chuan",
    "Catapult Galleon": "Catapult_Galleon",
    Xebec: "Xebec",
};

/* --- Unique Unit Building Overrides --- */
const UNIQUE_BUILDING = {
    "Jian Swordsman": "Barracks",
    "Xianbei Raider": "Archery Range",
    Grenadier: "Archery Range",
    "Warrior Priest": "Barracks",
    "Shrivamsha Rider": "Stable",
    "Elite Shrivamsha Rider": "Stable",
    "Mounted Trebuchet": "Siege Workshop",
    "Temple Guard": "Barracks",
    "Elite Temple Guard": "Barracks",
    "Bolas Rider": "Archery Range",
    "Elite Bolas Rider": "Archery Range",
    "Ibirapema Warrior": "Barracks",
    "Elite Ibirapema Warrior": "Barracks",
};

/* --- Icon Helpers --- */
function getIconUrl(name) {
    const id = NAME_TO_ICON[name];
    if (!id) return null;
    return `${ICON_BASE}${id}.png`;
}

/* Generated in-game idle sprite (red player-2 / blue player-1), transparent.
   Returns a sprite URL only for units with a square-enough sprite (UNIT_SPRITES,
   loaded from unit_sprites.js); everything else falls back to the portrait so the
   UI degrades cleanly. team===1 -> blue, otherwise red (team 2 / neutral display). */
function spriteFor(name, team) {
    const s = (typeof UNIT_SPRITES !== "undefined") ? UNIT_SPRITES[name] : null;
    if (s && s.url) {
        return team === 1 && s.url_blue ? s.url_blue : s.url;
    }
    return getIconUrl(name);
}

/* Does this unit have a usable sprite at all? Includes off-shape (borderline /
   extreme) sprites, not just square — only truly spriteless units (naval) miss.
   Call sites use this to switch layout (drop the circle/frame) when a real sprite
   shows; aspect is handled per-view with object-fit: contain + sane bounds. */
function hasSprite(name) {
    const s = (typeof UNIT_SPRITES !== "undefined") ? UNIT_SPRITES[name] : null;
    return !!(s && s.url);
}

/* Sprite aspect ratio (longer:shorter side) or null — lets a view clamp the
   off-shape sprites (tall pikes, wide cavalry) so they never bleed their box. */
function spriteRatio(name) {
    const s = (typeof UNIT_SPRITES !== "undefined") ? UNIT_SPRITES[name] : null;
    return s && s.ratio ? s.ratio : null;
}

/* --- Building Config --- */
const CLASS_TO_BUILDING = {
    Infantry: "Barracks",
    Archer: "Archery Range",
    "Hand Cannoneer": "Archery Range",
    "Cavalry Archer": "Archery Range",
    Cavalry: "Stable",
    "Siege Weapon": "Siege Workshop",
    Ballista: "Siege Workshop",
    "Unpacked Siege Unit": "Castle",
};
const BUILDING_ORDER = [
    "Barracks", "Archery Range", "Stable", "Castle", "Siege Workshop",
];
const BUILDING_ICONS = {
    Barracks: 12, "Archery Range": 87, Stable: 101,
    "Siege Workshop": 49, Castle: 82,
};

/* --- HTML Escaping ---
   Escape a string so it is safe to interpolate into an innerHTML template
   literal. For attributes, make sure the attribute is quoted — this escaping
   turns `&`, `<`, `>`, `"` into character entities via DOM textContent. */
function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}
