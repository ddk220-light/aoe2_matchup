// Isometric canvas renderer for the engine viewer. Pure drawing — reads the
// engine state each frame, owns only camera/sprite concerns.
const TILE_W = 2;   // screen px per tile unit at zoom 1 (scaled by cam.zoom)

export function createRenderer(canvas, scenario) {
  const ctx = canvas.getContext("2d");
  const sprites = {};
  for (const [key, file] of Object.entries({
    villager: "assets/villager.png",
    scout: "assets/scoutcavalry.webp",
  })) {
    const img = new Image();
    img.src = file;
    img.onload = () => (sprites[key] = img);
  }

  // Camera centered between TC and tree.
  const tc = scenario.entities.find((e) => e.type === "town_center");
  const tree = scenario.entities.find((e) => e.type === "tree");
  const cam = {
    cx: (tc.x + tree.x) / 2, cy: (tc.y + tree.y) / 2 - 1,
    zoom: 26,
    px(x, y) {  // world -> screen
      const sx = (x - y) * 0.5 * this.zoom * TILE_W;
      const sy = (x + y) * 0.25 * this.zoom * TILE_W;
      const cx0 = (this.cx - this.cy) * 0.5 * this.zoom * TILE_W;
      const cy0 = (this.cx + this.cy) * 0.25 * this.zoom * TILE_W;
      return [canvas.width / 2 + sx - cx0, canvas.height / 2 + sy - cy0];
    },
  };

  // Pan / zoom
  let drag = null;
  canvas.addEventListener("mousedown", (e) => {
    drag = { x: e.clientX, y: e.clientY };
    canvas.style.cursor = "grabbing";
  });
  window.addEventListener("mouseup", () => {
    drag = null;
    canvas.style.cursor = "grab";
  });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    const dx = (e.clientX - drag.x) / (cam.zoom * TILE_W);
    const dy = (e.clientY - drag.y) / (cam.zoom * TILE_W);
    cam.cx -= dx - 2 * dy;
    cam.cy += dx + 2 * dy;
    drag = { x: e.clientX, y: e.clientY };
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    cam.zoom = Math.max(8, Math.min(64, cam.zoom * (e.deltaY < 0 ? 1.12 : 0.89)));
  }, { passive: false });

  function diamond(x, y, w, h, fill, stroke) {
    const [sx, sy] = cam.px(x, y);
    ctx.beginPath();
    ctx.moveTo(sx, sy - h);
    ctx.lineTo(sx + w, sy);
    ctx.lineTo(sx, sy + h);
    ctx.lineTo(sx - w, sy);
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
  }

  function drawPropTree(x, y, big = false) {
    const [sx, sy] = cam.px(x, y);
    const s = cam.zoom / 26 * (big ? 1.35 : 1);
    ctx.fillStyle = "#4a3520";
    ctx.fillRect(sx - 1.5 * s, sy - 8 * s, 3 * s, 9 * s);
    ctx.fillStyle = big ? "#3f7a2e" : "#2f5a24";
    ctx.beginPath(); ctx.arc(sx, sy - 12 * s, 7.5 * s, 0, 7); ctx.fill();
    ctx.fillStyle = big ? "#5a9c3f" : "#3c6e2d";
    ctx.beginPath(); ctx.arc(sx - 3 * s, sy - 9 * s, 5.5 * s, 0, 7); ctx.fill();
  }

  function drawStump(x, y) {
    const [sx, sy] = cam.px(x, y);
    const s = cam.zoom / 26;
    ctx.fillStyle = "#6b5230";
    ctx.beginPath();
    ctx.ellipse(sx, sy - 1.5 * s, 4.5 * s, 2.5 * s, 0, 0, 7);
    ctx.fill();
  }

  // Procedural isometric Dark Age town center: stone base, timber walls,
  // thatched roof. (No usable TC sprite exists in the borrowed asset set.)
  function drawTownCenter(e) {
    const k = cam.zoom * TILE_W * 0.5;       // half-tile in screen px
    const [sx, sy] = cam.px(e.x, e.y);
    const P = (wx, wy, lift = 0) => {
      const [a, b] = cam.px(wx, wy);
      return [a, b - lift];
    };
    const H = 1.5 * k;                       // wall height (screen px)
    const R = 2.6 * k;                       // roof peak height
    const c = { x: e.x, y: e.y };
    const corner = {
      top: [c.x - 2, c.y - 2], right: [c.x + 2, c.y - 2],
      bot: [c.x + 2, c.y + 2], left: [c.x - 2, c.y + 2],
    };
    const poly = (pts, fill, stroke) => {
      ctx.beginPath();
      pts.forEach(([px2, py2], i) => (i ? ctx.lineTo(px2, py2) : ctx.moveTo(px2, py2)));
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
    };
    // shadow + stone base pad
    poly([P(...corner.top), P(...corner.right), P(...corner.bot), P(...corner.left)],
         "rgba(0,0,0,.30)");
    poly([P(c.x - 1.7, c.y - 1.7), P(c.x + 1.7, c.y - 1.7),
          P(c.x + 1.7, c.y + 1.7), P(c.x - 1.7, c.y + 1.7)], "#8d8474", "#5d574b");
    // walls (two visible faces)
    const w = 1.45;
    const wt = P(c.x - w, c.y - w), wr = P(c.x + w, c.y - w);
    const wb = P(c.x + w, c.y + w), wl = P(c.x - w, c.y + w);
    const wrU = [wr[0], wr[1] - H], wbU = [wb[0], wb[1] - H], wlU = [wl[0], wl[1] - H];
    poly([wl, wb, wbU, wlU], "#6e5634", "#46361e");          // left face
    poly([wb, wr, wrU, wbU], "#8a6c41", "#46361e");          // right face
    // door on right face
    const dx = (wb[0] + wr[0]) / 2, dy = (wb[1] + wr[1]) / 2;
    poly([[dx - 0.25 * k, dy - 0.1 * k], [dx + 0.25 * k, dy - 0.22 * k],
          [dx + 0.25 * k, dy - 1.0 * k], [dx - 0.25 * k, dy - 0.9 * k]], "#3a2b15");
    // thatched roof: peak ridge over the diamond
    const peakT = [sx - 0.9 * k, sy - R], peakB = [sx + 0.9 * k, sy - R + 0.45 * k];
    poly([wlU, wbU, peakB, peakT], "#b89552", "#7d6231");    // left slope
    poly([wbU, wrU, peakT, peakB], "#cfa95e", "#7d6231");    // right slope
    // banner pole
    ctx.strokeStyle = "#3c2f18";
    ctx.beginPath(); ctx.moveTo(sx, sy - R - 0.1 * k); ctx.lineTo(sx, sy - R - 1.1 * k); ctx.stroke();
    ctx.fillStyle = "#4f7fd9";
    poly([[sx, sy - R - 1.1 * k], [sx + 0.7 * k, sy - R - 0.95 * k], [sx, sy - R - 0.78 * k]],
         "#4f7fd9");
  }

  function drawUnit(e, color) {
    const [sx, sy] = cam.px(e.x, e.y);
    const s = cam.zoom / 26;
    ctx.fillStyle = "rgba(0,0,0,.35)";
    ctx.beginPath(); ctx.ellipse(sx, sy, 7 * s, 3.5 * s, 0, 0, 7); ctx.fill();
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.ellipse(sx, sy + 1 * s, 6 * s, 3 * s, 0, 0, 7); ctx.fill();
    const img = sprites[e.type];
    const H = (e.type === "scout" ? 30 : 24) * s;
    if (img) {
      const W = H * (img.width / img.height);
      ctx.drawImage(img, sx - W / 2, sy - H + 2 * s, W, H);
    } else {
      ctx.fillStyle = "#d8c9a0";
      ctx.fillRect(sx - 2.5 * s, sy - 12 * s, 5 * s, 12 * s);
    }
    if (e.carry > 2) {  // carrying wood: small log bundle
      ctx.fillStyle = "#8a6230";
      ctx.fillRect(sx + 4 * s, sy - 10 * s, 7 * s, 3 * s);
      ctx.strokeStyle = "#5d401c";
      ctx.strokeRect(sx + 4 * s, sy - 10 * s, 7 * s, 3 * s);
    }
  }

  function draw(g, scen) {
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W || canvas.height !== H) {
      canvas.width = W; canvas.height = H;
    }
    const grd = ctx.createLinearGradient(0, 0, 0, H);
    grd.addColorStop(0, "#2a3417");
    grd.addColorStop(1, "#222a13");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, W, H);

    // subtle tile grid around the action
    ctx.strokeStyle = "rgba(255,255,255,.04)";
    for (let gx = 8; gx <= 30; gx++)
      for (let gy = 58; gy <= 84; gy++) {
        diamond(gx, gy, cam.zoom * TILE_W * 0.5, cam.zoom * TILE_W * 0.25,
                null, "rgba(255,255,255,.03)");
      }

    // draw order: far -> near by (x+y)
    const items = [];
    for (const p of scen.props) items.push({ k: "prop", x: p.x, y: p.y });
    for (const e of g.ents.values()) items.push({ k: e.type, e, x: e.x, y: e.y });
    if (!g.ents.has(scen.treeId) && g.treeWasRemoved) {
      items.push({ k: "stump", x: scen.treeX, y: scen.treeY });
    }
    items.sort((a, b) => a.x + a.y - (b.x + b.y));

    for (const it of items) {
      if (it.k === "prop") drawPropTree(it.x, it.y);
      else if (it.k === "stump") drawStump(it.x, it.y);
      else if (it.k === "tree") {
        drawPropTree(it.e.x, it.e.y, true);
        // remaining-wood ring
        const [sx, sy] = cam.px(it.e.x, it.e.y);
        const s = cam.zoom / 26;
        const frac = it.e.wood / 100;
        ctx.strokeStyle = "rgba(0,0,0,.5)";
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(sx, sy - 12 * s, 11 * s, 0, 7); ctx.stroke();
        ctx.strokeStyle = "#6fbf5f";
        ctx.beginPath();
        ctx.arc(sx, sy - 12 * s, 11 * s, -Math.PI / 2, -Math.PI / 2 + frac * 2 * Math.PI);
        ctx.stroke();
        ctx.lineWidth = 1;
      } else if (it.k === "town_center") {
        drawTownCenter(it.e);
      } else if (it.k === "villager" || it.k === "scout") {
        drawUnit(it.e, "rgba(79,127,217,.85)");
      }
    }
  }

  return { draw, cam };
}
