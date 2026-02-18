/* ==========================================================================
   OBSOLETE: No longer routed. Replaced by matchup.js served at /civilizations.
   AoE2 Unit Analyzer — Civilization Select Page
   Populates expansion civ grids with emblem cards.
   Depends on: constants.js (CIV_EMBLEM_BASE)
   ========================================================================== */

const EXPANSIONS = [
    {
        id: "aok-grid",
        ready: true,
        civs: [
            "Britons",
            "Byzantines",
            "Celts",
            "Chinese",
            "Franks",
            "Goths",
            "Japanese",
            "Mongols",
            "Persians",
            "Saracens",
            "Teutons",
            "Turks",
            "Vikings",
        ],
    },
    {
        id: "conquerors-grid",
        ready: true,
        civs: ["Aztecs", "Huns", "Koreans", "Mayans", "Spanish"],
    },
    {
        id: "forgotten-grid",
        ready: true,
        civs: ["Incas", "Italians", "Magyars", "Slavs"],
    },
    {
        id: "african-grid",
        ready: true,
        civs: ["Berbers", "Ethiopians", "Malians", "Portuguese"],
    },
    {
        id: "rajas-grid",
        ready: true,
        civs: ["Burmese", "Khmer", "Malay", "Vietnamese"],
    },
    {
        id: "khans-grid",
        ready: true,
        civs: ["Bulgarians", "Cumans", "Lithuanians", "Tatars"],
    },
    {
        id: "lotw-grid",
        ready: true,
        civs: ["Burgundians", "Sicilians"],
    },
    { id: "dotd-grid", ready: true, civs: ["Bohemians", "Poles"] },
    {
        id: "doi-grid",
        ready: true,
        civs: ["Bengalis", "Dravidians", "Gurjaras", "Hindustanis"],
    },
    { id: "ror-grid", ready: true, civs: ["Romans"] },
    {
        id: "tmr-grid",
        ready: true,
        civs: ["Armenians", "Georgians"],
    },
    {
        id: "ttk-grid",
        ready: true,
        civs: ["Jurchens", "Khitans", "Shu", "Wei", "Wu"],
    },
    {
        id: "tlc-grid",
        ready: false,
        civs: ["Mapuche", "Muisca", "Tupi"],
    },
];

const PLACEHOLDER_SVG = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="30" stroke="#5a4228" stroke-width="2" fill="#2c1e10"/><path d="M32 12L18 24v16l14 12 14-12V24L32 12z" stroke="#5a4228" stroke-width="1.5" fill="none"/></svg>')}`;

function createCivCard(name, ready) {
    const slug = name.toLowerCase();
    const card = document.createElement(ready ? "a" : "div");
    card.className = "civ-card " + (ready ? "ready" : "soon");
    if (ready) card.href = "/civilizations/" + name;

    const img = document.createElement("img");
    img.className = "civ-emblem";
    img.src = CIV_EMBLEM_BASE + slug + ".png";
    img.alt = name;
    img.loading = "lazy";
    img.onerror = function () {
        this.src = PLACEHOLDER_SVG;
    };

    const label = document.createElement("span");
    label.className = "civ-name";
    label.textContent = name;

    card.appendChild(img);
    card.appendChild(label);
    return card;
}

EXPANSIONS.forEach((exp) => {
    const grid = document.getElementById(exp.id);
    exp.civs.forEach((civ) => {
        grid.appendChild(createCivCard(civ, exp.ready));
    });
});
