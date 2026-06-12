// Flat 2D grid renderer. World cells are squares [n,n+1]x[m,m+1] that
// project to 2:1 screen diamonds (classic AoE2 view). All shapes — cells,
// trees (1 cell), building footprints (2x2 / 4x4 cells) — are drawn by
// projecting their WORLD CORNERS, so footprints cover their cells exactly.
// Orientation matches the production replay SPA: sx=(x+y)k, sy=(y-x)k/2.
const SPECIES_COLOR = {
  default: "#3f7a34", Olive: "#5a7d3a", Acacia: "#4a7a2e",
  "Italian Pine": "#2f6a3a", Pine: "#2f6a3a", Straggler: "#4d8a3c",
};

export function createRenderer(canvas, scenario) {
  const ctx = canvas.getContext("2d");

  const xs = scenario.entities.map((e) => e.x);
  const ys = scenario.entities.map((e) => e.y);
  const minX = Math.floor(Math.min(...xs)) - 3, maxX = Math.ceil(Math.max(...xs)) + 3;
  const minY = Math.floor(Math.min(...ys)) - 3, maxY = Math.ceil(Math.max(...ys)) + 3;

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
    cam.k = Math.max(8, Math.min(64, cam.k * (e.deltaY < 0 ? 1.12 : 0.89)));
  }, { passive: false });

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

  function drawGrid() {
    for (let x = minX; x <= maxX; x++) {
      for (let y = minY; y <= maxY; y++) {
        poly(cell(x, y), ((x + y) & 1) ? "#5a4632" : "#52402d", "rgba(0,0,0,.15)");
      }
    }
  }

  const seedWood = new Map(
    scenario.entities.filter((e) => e.type === "tree").map((e) => [e.id, e.wood]));

  function drawTree(e) {
    const n = Math.floor(e.x), m = Math.floor(e.y);
    const base = SPECIES_COLOR[e.species] || SPECIES_COLOR.default;
    poly(cell(n, m), e.wood <= 0 ? "#6b5638" : base, "rgba(0,0,0,.35)");
    if (e.wood > 0) {
      // wood-left circle: ring fills proportionally to remaining wood
      const f = e.wood / (seedWood.get(e.id) || 100);
      const [sx, sy] = px(e.x, e.y);
      const r = cam.k * 0.30;
      ctx.lineWidth = Math.max(2, cam.k * 0.13);
      ctx.strokeStyle = "rgba(0,0,0,.45)";
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2 * Math.PI); ctx.stroke();
      ctx.strokeStyle = "#b6f09a";
      ctx.beginPath();
      ctx.arc(sx, sy, r, -Math.PI / 2, -Math.PI / 2 + f * 2 * Math.PI);
      ctx.stroke();
      ctx.lineWidth = 1;
    }
  }

  function drawBuilding(e) {
    const half = e.type === "town_center" ? 2 : 1;
    const built = e.type !== "lumber_camp" || e.built;
    const fp = rect(e.x - half, e.y - half, e.x + half, e.y + half);
    if (!built) {
      poly(fp, "rgba(150,120,70,.35)");
      ctx.setLineDash([4, 3]);
      poly(fp, null, "#b8954f", 1.5);
      ctx.setLineDash([]);
    } else {
      poly(fp, e.type === "town_center" ? "#8a6c41" : "#7a5a34", "#2e2412", 2);
      const ih = half * 0.55;
      poly(rect(e.x - ih, e.y - ih, e.x + ih, e.y + ih),
           e.type === "town_center" ? "#a8854f" : "#9a7240");
      const [sx, sy] = px(e.x, e.y);
      ctx.fillStyle = "#1c1408";
      ctx.font = `${Math.round(cam.k * 0.55)}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(e.type === "town_center" ? "TC" : "LC", sx, sy);
      ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    }
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
    if (e.carry > 2) {
      ctx.fillStyle = "#c98a3a";
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

  function draw(g) {
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    ctx.fillStyle = "#1a2010";
    ctx.fillRect(0, 0, W, H);

    drawGrid();

    const items = [...g.ents.values()].sort((a, b) => (a.x + a.y) - (b.x + b.y));
    for (const e of items) {
      if (e.type === "tree") drawTree(e);
      else if (e.type === "town_center" || e.type === "lumber_camp") drawBuilding(e);
      else if (e.type === "villager" || e.type === "scout") drawUnit(e);
    }
  }

  return { draw, cam };
}
