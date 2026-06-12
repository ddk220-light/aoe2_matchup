// Flat 2D grid renderer. The world is a grid of diamond (isometric) tiles;
// units are axis-aligned squares occupying one tile; resources occupy one
// tile; buildings span their footprint. Orientation matches the production
// replay SPA: screenX = (x+y)·k, screenY = (y-x)·k.
const SPECIES_COLOR = {
  default: "#3f7a34", Olive: "#5a7d3a", Acacia: "#4a7a2e",
  "Italian Pine": "#2f6a3a", Pine: "#2f6a3a",
};

export function createRenderer(canvas, scenario) {
  const ctx = canvas.getContext("2d");

  // World bounds from all entities (+ margin) to frame the camera/grid.
  const xs = scenario.entities.map((e) => e.x);
  const ys = scenario.entities.map((e) => e.y);
  const minX = Math.min(...xs) - 3, maxX = Math.max(...xs) + 3;
  const minY = Math.min(...ys) - 3, maxY = Math.max(...ys) + 3;
  const cx0 = (minX + maxX) / 2, cy0 = (minY + maxY) / 2;

  const cam = { cx: cx0, cy: cy0, k: 17 };  // k = screen px per tile half-step

  // world -> screen (production-SPA orientation)
  function px(x, y) {
    const sx = (x + y - cam.cx - cam.cy) * cam.k;
    const sy = (y - x - (cam.cy - cam.cx)) * cam.k;
    return [canvas.width / 2 + sx, canvas.height / 2 + sy];
  }

  // pan / zoom
  let drag = null;
  canvas.addEventListener("mousedown", (e) => { drag = { x: e.clientX, y: e.clientY }; canvas.style.cursor = "grabbing"; });
  window.addEventListener("mouseup", () => { drag = null; canvas.style.cursor = "grab"; });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    const dxp = (e.clientX - drag.x) / cam.k, dyp = (e.clientY - drag.y) / cam.k;
    // invert the projection deltas
    cam.cx -= (dxp - dyp) / 2;
    cam.cy -= (dxp + dyp) / 2;
    drag = { x: e.clientX, y: e.clientY };
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    cam.k = Math.max(7, Math.min(48, cam.k * (e.deltaY < 0 ? 1.12 : 0.89)));
  }, { passive: false });

  // a 1x1 tile diamond centered on (x,y)
  function tilePath(x, y) {
    const [ax, ay] = px(x, y - 0.5);
    const [bx, by] = px(x + 0.5, y);
    const [cx, cy] = px(x, y + 0.5);
    const [dx, dy] = px(x - 0.5, y);
    ctx.beginPath();
    ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.lineTo(cx, cy); ctx.lineTo(dx, dy);
    ctx.closePath();
  }

  // a footprint diamond spanning n×n tiles centered on (x,y)
  function footPath(x, y, half) {
    const [ax, ay] = px(x, y - half);
    const [bx, by] = px(x + half, y);
    const [cx, cy] = px(x, y + half);
    const [dx, dy] = px(x - half, y);
    ctx.beginPath();
    ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.lineTo(cx, cy); ctx.lineTo(dx, dy);
    ctx.closePath();
  }

  function drawGrid() {
    ctx.lineWidth = 1;
    for (let x = Math.floor(minX); x <= Math.ceil(maxX); x++) {
      for (let y = Math.floor(minY); y <= Math.ceil(maxY); y++) {
        tilePath(x, y);
        ctx.fillStyle = ((x + y) & 1) ? "#3c4a26" : "#41502a";
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,.18)";
        ctx.stroke();
      }
    }
  }

  function drawTree(e) {
    tilePath(e.x, e.y);
    const base = SPECIES_COLOR[e.species] || SPECIES_COLOR.default;
    ctx.fillStyle = e.wood <= 0 ? "#5b4a2e" : base;   // stump brown when empty
    ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.stroke();
    if (e.wood > 0) {
      // wood-remaining inner diamond (shrinks as depleted)
      const f = Math.max(0.12, e.wood / 100);
      const [sx, sy] = px(e.x, e.y);
      const w = cam.k * 0.62 * f, h = cam.k * 0.31 * f;
      ctx.beginPath();
      ctx.moveTo(sx, sy - h); ctx.lineTo(sx + w, sy);
      ctx.lineTo(sx, sy + h); ctx.lineTo(sx - w, sy); ctx.closePath();
      ctx.fillStyle = "rgba(20,40,16,.55)"; ctx.fill();
    }
  }

  function drawBuilding(e) {
    const half = e.type === "town_center" ? 2 : 1;
    const built = e.type !== "lumber_camp" || e.built;
    footPath(e.x, e.y, half);
    if (!built) {
      ctx.fillStyle = "rgba(150,120,70,.35)";          // foundation
      ctx.fill();
      ctx.setLineDash([4, 3]); ctx.strokeStyle = "#b8954f"; ctx.stroke();
      ctx.setLineDash([]);
    } else {
      ctx.fillStyle = e.type === "town_center" ? "#8a6c41" : "#7a5a34";
      ctx.fill();
      ctx.strokeStyle = "#2e2412"; ctx.lineWidth = 2; ctx.stroke(); ctx.lineWidth = 1;
      // roof highlight diamond
      footPath(e.x, e.y, half * 0.55);
      ctx.fillStyle = e.type === "town_center" ? "#a8854f" : "#9a7240"; ctx.fill();
      // label
      const [sx, sy] = px(e.x, e.y);
      ctx.fillStyle = "#1c1408"; ctx.font = `${Math.round(cam.k * 0.5)}px sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(e.type === "town_center" ? "TC" : "LC", sx, sy);
    }
  }

  function drawUnit(e) {
    const [sx, sy] = px(e.x, e.y);
    const s = cam.k * 0.6;                              // square side
    // shadow
    ctx.fillStyle = "rgba(0,0,0,.25)";
    ctx.fillRect(sx - s / 2, sy - s / 2 + 2, s, s);
    // body — player blue; scout slightly different
    ctx.fillStyle = e.type === "scout" ? "#6f8fd9" : "#4f7fd9";
    ctx.fillRect(sx - s / 2, sy - s / 2, s, s);
    ctx.strokeStyle = "#15233f"; ctx.lineWidth = 1.5;
    ctx.strokeRect(sx - s / 2, sy - s / 2, s, s);
    ctx.lineWidth = 1;
    // carrying-wood pip
    if (e.carry > 2) {
      ctx.fillStyle = "#c98a3a";
      ctx.fillRect(sx + s / 2 - 4, sy - s / 2 - 4, 6, 6);
    }
  }

  function draw(g) {
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    ctx.fillStyle = "#1a2010"; ctx.fillRect(0, 0, W, H);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";

    drawGrid();

    // depth-sorted entities (far first: smaller x+y on top-back)
    const items = [...g.ents.values()].sort((a, b) => (a.x + a.y) - (b.x + b.y));
    for (const e of items) {
      if (e.type === "tree") drawTree(e);
      else if (e.type === "town_center" || e.type === "lumber_camp") drawBuilding(e);
      else if (e.type === "villager" || e.type === "scout") drawUnit(e);
    }
  }

  return { draw, cam };
}
