// Flat 2D grid renderer. World cells are squares [n,n+1]x[m,m+1] that
// project to 2:1 screen diamonds (classic AoE2 view). All shapes — cells,
// trees (1 cell), building footprints (2x2 / 4x4 cells) — are drawn by
// projecting their WORLD CORNERS, so footprints cover their cells exactly.
// Orientation matches the production replay SPA: sx=(x+y)k, sy=(y-x)k/2.
import { BUILDINGS } from "./constants.js";

const SPECIES_COLOR = {
  default: "#3f7a34", Olive: "#5a7d3a", Acacia: "#4a7a2e",
  "Italian Pine": "#2f6a3a", Pine: "#2f6a3a", Straggler: "#4d8a3c",
};
const BUILDING_STYLE = {
  town_center: { fill: "#8a6c41", inner: "#a8854f", label: "TC" },
  lumber_camp: { fill: "#7a5a34", inner: "#9a7240", label: "LC" },
  mill:        { fill: "#86683a", inner: "#a3854a", label: "M" },
  house:       { fill: "#7d6248", inner: "#97785a", label: "H" },
};

export function createRenderer(canvas, scenario) {
  const ctx = canvas.getContext("2d");

  // The DEFAULT camera frames the action (sim entities) at the close zoom.
  // The ground/grid + scenery span the WHOLE map so you can zoom out to it.
  const xs = scenario.entities.map((e) => e.x);
  const ys = scenario.entities.map((e) => e.y);
  const minX = Math.floor(Math.min(...xs)) - 3, maxX = Math.ceil(Math.max(...xs)) + 3;
  const minY = Math.floor(Math.min(...ys)) - 3, maxY = Math.ceil(Math.max(...ys)) + 3;

  const scenery = (scenario.scenery || []).slice().sort((a, b) => (a.x + a.y) - (b.x + b.y));
  const dim = scenario.map?.dimension || Math.max(maxX, maxY) + 3;
  // ground extent: full map when we have scenery, else just the action area
  const G = scenery.length
    ? { x0: 0, y0: 0, x1: dim, y1: dim }
    : { x0: minX, y0: minY, x1: maxX, y1: maxY };

  const cam = { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, k: 22 };

  function px(wx, wy) {
    const sx = (wx + wy - cam.cx - cam.cy) * cam.k;
    const sy = (wy - wx - (cam.cy - cam.cx)) * cam.k * 0.5;
    return [canvas.width / 2 + sx, canvas.height / 2 + sy];
  }

  // pan / zoom (inverse of px for drag deltas)
  let drag = null;
  canvas.addEventListener("mousedown", (e) => { drag = { x: e.clientX, y: e.clientY }; canvas.style.cursor = "grabbing"; });
  window.addEventListener("mouseup", () => { drag = null; canvas.style.cursor = "grab"; });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    const mx = (e.clientX - drag.x) / cam.k;
    const my = (e.clientY - drag.y) / (cam.k * 0.5);
    cam.cx -= (mx - my) / 2;
    cam.cy -= (mx + my) / 2;
    drag = { x: e.clientX, y: e.clientY };
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    // min 3 = whole 120-tile map fits; max 80 = closer than the default view
    cam.k = Math.max(3, Math.min(80, cam.k * (e.deltaY < 0 ? 1.12 : 0.89)));
  }, { passive: false });

  // rounded-rect path in screen space (sheep bodies, etc.)
  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // polygon through projected world points
  function poly(pts, fill, stroke, lw = 1) {
    ctx.beginPath();
    pts.forEach(([wx, wy], i) => {
      const [sx, sy] = px(wx, wy);
      if (i) ctx.lineTo(sx, sy); else ctx.moveTo(sx, sy);
    });
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.lineWidth = lw; ctx.strokeStyle = stroke; ctx.stroke(); ctx.lineWidth = 1; }
  }

  // world-space axis-aligned rect [x0,x1]x[y0,y1] -> projected diamond
  const rect = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  const cell = (n, m) => rect(n, m, n + 1, m + 1);

  // Is a tile's screen position within the canvas (with a margin)? Used to
  // cull the grid + scenery so any zoom level draws only what's visible.
  function onScreen(wx, wy, margin) {
    const [sx, sy] = px(wx, wy);
    return sx >= -margin && sx <= canvas.width + margin
        && sy >= -margin && sy <= canvas.height + margin;
  }

  function drawGrid() {
    // a flat base over the whole ground extent (one cheap diamond)
    poly(rect(G.x0, G.y0, G.x1, G.y1), "#52402d");
    // crisp per-tile checker only when zoomed in enough to read it; culled
    if (cam.k < 7) return;
    const m = cam.k * 1.5;
    for (let x = G.x0; x < G.x1; x++) {
      for (let y = G.y0; y < G.y1; y++) {
        if (!onScreen(x + 0.5, y + 0.5, m)) continue;
        poly(cell(x, y), ((x + y) & 1) ? "#5a4632" : "#52402d", "rgba(0,0,0,.15)");
      }
    }
  }

  const seedPool = new Map(scenario.entities
    .filter((e) => e.type === "tree" || e.type === "bush" || e.type === "herdable")
    .map((e) => [e.id, e.wood ?? e.food]));

  // remaining-stock ring shared by trees (pale green) and bushes (pink)
  function stockRing(e, left, color) {
    const f = left / (seedPool.get(e.id) || 100);
    const [sx, sy] = px(e.x, e.y);
    const r = cam.k * 0.30;
    ctx.lineWidth = Math.max(2, cam.k * 0.13);
    ctx.strokeStyle = "rgba(0,0,0,.45)";
    ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(sx, sy, r, -Math.PI / 2, -Math.PI / 2 + f * 2 * Math.PI);
    ctx.stroke();
    ctx.lineWidth = 1;
  }

  function drawTree(e) {
    const base = SPECIES_COLOR[e.species] || SPECIES_COLOR.default;
    poly(cell(Math.floor(e.x), Math.floor(e.y)),
         e.wood <= 0 ? "#6b5638" : base, "rgba(0,0,0,.35)");
    if (e.wood > 0) stockRing(e, e.wood, "#b6f09a");
  }

  function drawBush(e) {
    poly(cell(Math.floor(e.x), Math.floor(e.y)),
         e.food <= 0 ? "#6b5638" : "#8e3b46", "rgba(0,0,0,.35)");
    if (e.food > 0) stockRing(e, e.food, "#ff9aa8");
  }

  // Town Center quadrants (4x4 split into four 2x2). In this projection the
  // diamond's top corner is (max x, min y), so the BACK/solid quadrant is
  // high-x/low-y. Centre sits on a tile corner (integer).
  function tcParts(e) {
    const cx = Math.round(e.x), cy = Math.round(e.y);
    return {
      cx, cy,
      top:    rect(cx, cy - 2, cx + 2, cy),       // solid building mass (opaque)
      bottom: rect(cx - 2, cy, cx, cy + 2),       // open courtyard (no roof)
      left:   rect(cx - 2, cy - 2, cx, cy),        // transparent roof
      right:  rect(cx, cy, cx + 2, cy + 2),        // transparent roof
      fp:     rect(cx - 2, cy - 2, cx + 2, cy + 2),
    };
  }

  // BELOW units: the TC platform/floor. Units standing on the passable
  // quadrants (front courtyard + side overhangs) are drawn on top of this.
  function drawTCFloor(e) {
    const p = tcParts(e);
    if (!e.built) {
      poly(p.fp, "rgba(150,120,70,.35)");
      ctx.setLineDash([4, 3]); poly(p.fp, null, "#b8954f", 1.5); ctx.setLineDash([]);
      return;
    }
    poly(p.fp, "#574a34", "#2e2412", 2);          // stone base under the whole TC
    poly(p.bottom, "#6f6044");                     // open courtyard, slightly lighter
    poly(p.bottom, null, "rgba(0,0,0,.25)", 1);
  }

  // ABOVE units: the roofs. Top quadrant is the solid opaque building (hides
  // anything behind it); the two side quadrants are translucent overhangs so
  // villagers packed under them stay visible; the front courtyard has none.
  function drawTCRoof(e) {
    if (!e.built) return;
    const p = tcParts(e);
    ctx.globalAlpha = 0.5;                          // translucent side overhangs
    poly(p.left, "#8a6c41", "#3a2e16", 1.5);
    poly(p.right, "#8a6c41", "#3a2e16", 1.5);
    ctx.globalAlpha = 1;
    poly(p.top, "#8a6c41", "#2e2412", 2);          // opaque solid building
    const [ix, iy] = [p.cx + 1, p.cy - 1];          // top-quadrant centre
    poly(rect(ix - 0.6, iy - 0.6, ix + 0.6, iy + 0.6), "#a8854f");
    const [sx, sy] = px(ix, iy);
    ctx.fillStyle = "#1c1408";
    ctx.font = `${Math.round(cam.k * 0.5)}px sans-serif`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("TC", sx, sy);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  }

  function drawBuilding(e) {
    const half = (BUILDINGS[e.type]?.size ?? 2) / 2;
    const fp = rect(e.x - half, e.y - half, e.x + half, e.y + half);
    if (!e.built) {
      poly(fp, "rgba(150,120,70,.35)");
      ctx.setLineDash([4, 3]);
      poly(fp, null, "#b8954f", 1.5);
      ctx.setLineDash([]);
    } else {
      const st = BUILDING_STYLE[e.type] || BUILDING_STYLE.lumber_camp;
      poly(fp, st.fill, "#2e2412", 2);
      const ih = half * 0.55;
      poly(rect(e.x - ih, e.y - ih, e.x + ih, e.y + ih), st.inner);
      const [sx, sy] = px(e.x, e.y);
      ctx.fillStyle = "#1c1408";
      ctx.font = `${Math.round(cam.k * 0.55)}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(st.label, sx, sy);
      ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    }
  }

  // Herdable: alive = a sheep/goose body (gaia grey vs converted cream with a
  // player-blue outline + brief conversion pulse); dead = a carcass with a
  // pink food ring that shrinks as it's eaten and rots.
  function drawHerdable(e, nowT) {
    const [sx, sy] = px(e.x, e.y);
    const s = cam.k * 0.5;
    if (e.dead) {
      ctx.fillStyle = "rgba(0,0,0,.25)";
      ctx.beginPath(); ctx.ellipse(sx, sy + 2, s * 0.58, s * 0.4, 0, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = "#7c3030";              // carcass
      ctx.beginPath(); ctx.ellipse(sx, sy, s * 0.54, s * 0.36, 0, 0, 2 * Math.PI); ctx.fill();
      const seed = seedPool.get(e.id) || 100;
      const f = Math.max(0, (e.food ?? 0) / seed);
      const r = cam.k * 0.33;
      ctx.lineWidth = Math.max(2, cam.k * 0.12);
      ctx.strokeStyle = "rgba(0,0,0,.4)";
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2 * Math.PI); ctx.stroke();
      ctx.strokeStyle = "#ff9aa8";
      ctx.beginPath(); ctx.arc(sx, sy, r, -Math.PI / 2, -Math.PI / 2 + f * 2 * Math.PI); ctx.stroke();
      ctx.lineWidth = 1;
      return;
    }
    // conversion pulse (≈1.5s yellow ring after the scout flips it)
    if (e.convertedAt != null && nowT - e.convertedAt < 1.5) {
      const a = 1 - (nowT - e.convertedAt) / 1.5;
      ctx.strokeStyle = `rgba(240,210,90,${a.toFixed(2)})`;
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(sx, sy, s * (0.7 + (1 - a) * 0.6), 0, 2 * Math.PI); ctx.stroke();
      ctx.lineWidth = 1;
    }
    ctx.fillStyle = "rgba(0,0,0,.22)";
    roundRect(sx - s / 2, sy - s / 2 + 2, s, s, 4); ctx.fill();
    ctx.fillStyle = e.owner === 1 ? "#f1e8cf" : "#cdccc6";   // owned cream vs gaia grey
    roundRect(sx - s / 2, sy - s / 2, s, s, 4); ctx.fill();
    ctx.strokeStyle = e.owner === 1 ? "#4f7fd9" : "#6b6b64"; // converted = blue outline
    ctx.lineWidth = e.owner === 1 ? 2 : 1.2;
    roundRect(sx - s / 2, sy - s / 2, s, s, 4); ctx.stroke();
    ctx.lineWidth = 1;
    ctx.fillStyle = "#46443e";              // head dot
    ctx.beginPath(); ctx.arc(sx, sy - s * 0.12, s * 0.13, 0, 2 * Math.PI); ctx.fill();
  }

  function drawUnit(e) {
    // active path (debug): faint line from the unit through its waypoints
    if (e.path && e.path.length) {
      ctx.strokeStyle = "rgba(255,255,255,.30)";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      const [ux, uy] = px(e.x, e.y);
      ctx.moveTo(ux, uy);
      for (const [wx, wy] of e.path) {
        const [sx2, sy2] = px(wx, wy);
        ctx.lineTo(sx2, sy2);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }
    const [sx, sy] = px(e.x, e.y);
    const s = cam.k * 0.55;
    ctx.fillStyle = "rgba(0,0,0,.25)";
    ctx.fillRect(sx - s / 2, sy - s / 2 + 2, s, s);
    ctx.fillStyle = e.type === "scout" ? "#6f8fd9" : "#4f7fd9";
    ctx.fillRect(sx - s / 2, sy - s / 2, s, s);
    ctx.strokeStyle = "#15233f";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(sx - s / 2, sy - s / 2, s, s);
    ctx.lineWidth = 1;
    if (e.carry > 2) {        // carry pip: orange = wood, pink = food
      ctx.fillStyle = e.carryRes === "food" ? "#d9536a" : "#c98a3a";
      ctx.fillRect(sx + s / 2 - 4, sy - s / 2 - 4, 6, 6);
    }
    if (e.task === "to_build" || e.task === "building") {
      // hammer badge: grey head + angled wooden handle
      const bx = sx + s / 2 - 2, by = sy - s / 2 - 3;
      ctx.strokeStyle = "#8a6230";
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(bx - 4, by + 5); ctx.lineTo(bx + 2, by - 2); ctx.stroke();
      ctx.fillStyle = "#cfd2d6";
      ctx.fillRect(bx - 1, by - 4, 6, 4);
      ctx.lineWidth = 1;
    }
    // debug number (scout gets "S")
    ctx.fillStyle = "#fff";
    ctx.font = `bold ${Math.max(9, Math.round(s * 0.72))}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(e.type === "scout" ? "S" : String(e.num ?? "?"), sx, sy + 0.5);
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  function disc(sx, sy, r, fill, stroke) {
    ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2 * Math.PI);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  }
  function animalBlob(sx, sy, s, fill, stroke) {
    ctx.fillStyle = "rgba(0,0,0,.22)";
    ctx.beginPath(); ctx.ellipse(sx, sy + 1.5, s * 0.55, s * 0.36, 0, 0, 2 * Math.PI); ctx.fill();
    ctx.fillStyle = fill;
    ctx.beginPath(); ctx.ellipse(sx, sy, s * 0.5, s * 0.32, 0, 0, 2 * Math.PI); ctx.fill();
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  }

  // Static full-map decor: forests, gold/stone mines, forage, relics, and the
  // wildlife (far sheep/geese, boars, jaguars). Not part of the sim — drawn
  // beneath the live action, viewport-culled so any zoom stays cheap.
  function drawScenery() {
    const m = cam.k * 1.4;
    for (const o of scenery) {
      if (!onScreen(o.x, o.y, m)) continue;
      const [sx, sy] = px(o.x, o.y);
      const s = cam.k * 0.5;
      const c = cell(Math.floor(o.x), Math.floor(o.y));
      switch (o.type) {
        case "tree":   poly(c, SPECIES_COLOR.default, "rgba(0,0,0,.28)"); break;
        case "gold":   poly(c, "#5a4a22"); disc(sx, sy, cam.k * 0.22, "#e8c24a", "#7a5e18"); break;
        case "stone":  poly(c, "#494a4d"); disc(sx, sy, cam.k * 0.22, "#b8bcc0", "#5a5c5e"); break;
        case "bush":   poly(c, "#8e3b46", "rgba(0,0,0,.3)"); disc(sx, sy, cam.k * 0.16, "#ff9aa8"); break;
        case "herdable": animalBlob(sx, sy, s, "#cdccc6", "#6b6b64"); break;   // wild sheep/geese
        case "boar":   animalBlob(sx, sy, s * 1.3, "#2c2216", "#140e08"); break;
        case "predator": animalBlob(sx, sy, s * 1.05, "#b87a36", "#5a3a16"); break; // jaguar
        case "deer":   animalBlob(sx, sy, s, "#c8a368", "#7a5a30"); break;
        case "relic":  disc(sx, sy, cam.k * 0.26, "#d8b23c", "#7a5e10"); break;
      }
    }
  }

  function draw(g) {
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    ctx.fillStyle = "#1a2010";
    ctx.fillRect(0, 0, W, H);

    drawGrid();
    drawScenery();

    // The Town Center renders in two layers AROUND the units: its floor
    // below them (units stand visibly on the courtyard / under the overhangs)
    // and its roofs above them (opaque back, translucent sides). Everything
    // else is a single painter pass sorted back-to-front.
    for (const e of g.ents.values()) if (e.type === "town_center") drawTCFloor(e);

    const items = [...g.ents.values()]
      .filter((e) => e.type !== "town_center")
      .sort((a, b) => (a.x + a.y) - (b.x + b.y));
    for (const e of items) {
      if (e.type === "tree") drawTree(e);
      else if (e.type === "bush") drawBush(e);
      else if (e.type === "herdable") drawHerdable(e, g.t);
      else if (BUILDINGS[e.type]) drawBuilding(e);
      else if (e.type === "villager" || e.type === "scout") drawUnit(e);
    }

    for (const e of g.ents.values()) if (e.type === "town_center") drawTCRoof(e);
  }

  return { draw, cam };
}
