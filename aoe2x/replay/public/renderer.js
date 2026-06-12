/**
 * Renderer module - handles all canvas drawing operations
 * Uses isometric diamond projection matching AoE2's view
 */

class Renderer {
  constructor(canvas, mapSize = 220) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.mapSize = mapSize;
    this.tileSize = 3; // Base pixels per tile (adjusted for isometric)

    // Isometric projection: tile width is 2x tile height
    this.tileWidth = this.tileSize * 2;
    this.tileHeight = this.tileSize;

    // Zoom and pan state
    this.zoom = 1;
    this.minZoom = 0.25;
    this.maxZoom = 8;
    this.panX = 0;
    this.panY = 0;

    // Dragging state
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;

    // Player colors
    this.playerColors = {};
    // Player civ name (for the base-label emblem) and a cache of emblem images.
    this.playerCivs = {};
    this.civImages = {}; // normalized civ name -> Image | null (loading) | false

    // Entity sizes
    this.sizes = {
      villager: 5,
      infantry: 6,
      archer: 6,
      cavalry: 8,
      siege: 10,
      monk: 5,
      ship: 12,
      king: 6,
      military: 6,
      building_small: 12,
      building_large: 20,
      towncenter: 28,
      castle: 32,
    };

    // Building types that are large
    this.largeBuildings = new Set([
      "monastery",
      "university",
      "siegeworkshop",
      "stable",
      "archeryrange",
      "barracks",
      "market",
      "blacksmith",
      "mill",
      "lumbercamp",
      "miningcamp",
      "dock",
      "harbor",
    ]);

    // Debug mode: show type labels (for sprite verification). Off — units are
    // rendered as plain circles with no labels until identification is verified.
    this.showTypeLabels = false;

    // Sprite system
    this.spritesLoaded = false;
    this.spriteData = null;
    this.spriteImages = {}; // Cache loaded sprite images
    // Unit types whose icon lives under a different (closest-match) sprite name.
    this.spriteAlias = { camelscout: "camelrider" };

    this.setupCanvas();
    this.setupEventListeners();
    this.loadSprites();
  }

  // Load sprite metadata and images
  async loadSprites() {
    try {
      // Load sprite metadata
      const response = await fetch("/assets/sprites/sprites.json");
      this.spriteData = await response.json();

      // Load all available sprites
      const loadPromises = [];

      // Load all unit sprites
      for (const [name, info] of Object.entries(this.spriteData.units || {})) {
        if (info.available) {
          loadPromises.push(this.loadSpriteImage(name, info.file));
        }
      }

      // Load all building sprites
      for (const [name, info] of Object.entries(
        this.spriteData.buildings || {},
      )) {
        if (info.available) {
          loadPromises.push(this.loadSpriteImage(name, info.file));
        }
      }

      await Promise.all(loadPromises);
      this.spritesLoaded = true;
      console.log(
        "Sprites loaded:",
        Object.keys(this.spriteImages).length,
        "total",
      );
    } catch (error) {
      console.warn("Failed to load sprites:", error);
      this.spritesLoaded = false;
    }
  }

  // Normalize a unit/building key so server-emitted types, sprites.json keys,
  // and icon filenames all match regardless of case, spaces, or punctuation.
  normKey(name) {
    return (name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  // Load a single sprite image
  loadSpriteImage(name, file) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        this.spriteImages[this.normKey(name)] = img;
        resolve();
      };
      img.onerror = () => {
        console.warn(`Failed to load sprite: ${name}`);
        resolve();
      };
      img.src = `/assets/sprites/${file}`;
    });
  }

  // Get sprite image for a unit/building type (normalized match)
  getSprite(name) {
    return this.spriteImages[this.normKey(name)] || null;
  }

  // Lazily load a civ emblem (e.g. "Mongols" -> /assets/civs/mongols.png) into
  // the cache. Stored as null while loading, false on failure, Image on success.
  loadCivEmblem(civ) {
    if (!civ) return;
    const key = this.normKey(civ);
    if (key in this.civImages) return;
    this.civImages[key] = null;
    const img = new Image();
    img.onload = () => {
      this.civImages[key] = img;
    };
    img.onerror = () => {
      this.civImages[key] = false;
    };
    img.src = `/assets/civs/${key}.png`;
  }

  // Loaded civ emblem for a civ name, or null if not (yet) available.
  getCivEmblem(civ) {
    const img = this.civImages[this.normKey(civ)];
    return img && img !== true ? (typeof img === "object" ? img : null) : null;
  }

  setupCanvas() {
    const container = this.canvas.parentElement;
    this.canvas.width = container.clientWidth;
    this.canvas.height = container.clientHeight;

    // Center the map initially
    this.centerMap();
  }

  centerMap() {
    // Diamond dimensions in game units
    // Width spans from left (0,0) to right (maxX, maxY): (maxX + maxY) * tileWidth/2
    // Height spans from top (maxX, 0) to bottom (0, maxY): (maxX + maxY) * tileHeight/2
    const mapPixelWidth = this.mapSize * this.tileWidth * this.zoom;
    const mapPixelHeight = this.mapSize * this.tileHeight * this.zoom;

    // Calculate zoom to fit the map in the canvas while maintaining aspect ratio
    const scaleX = this.canvas.width / mapPixelWidth;
    const scaleY = this.canvas.height / mapPixelHeight;
    const fitScale = Math.min(scaleX, scaleY) * 0.9; // 90% to leave some margin

    // Apply fit scale only on initial center (when zoom is 1)
    if (this.zoom === 1) {
      this.zoom = fitScale;
    }

    // Recalculate map dimensions with current zoom
    const finalMapWidth = this.mapSize * this.tileWidth * this.zoom;
    const finalMapHeight = this.mapSize * this.tileHeight * this.zoom;

    // Center the map in the canvas
    this.panX = (this.canvas.width - finalMapWidth) / 2;
    this.panY = this.canvas.height / 2;
  }

  setupEventListeners() {
    // Mouse wheel zoom
    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
      this.zoomAt(mouseX, mouseY, zoomDelta);
    });

    // Mouse drag for panning
    this.canvas.addEventListener("mousedown", (e) => {
      this.isDragging = true;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    this.canvas.addEventListener("mousemove", (e) => {
      if (this.isDragging) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        this.panX += dx;
        this.panY += dy;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
      }
    });

    this.canvas.addEventListener("mouseup", () => {
      this.isDragging = false;
    });

    this.canvas.addEventListener("mouseleave", () => {
      this.isDragging = false;
    });

    // Touch: one finger pans, two fingers pinch-zoom
    let lastTouchDist = null;
    this.canvas.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length === 1) {
          this.isDragging = true;
          this.lastMouseX = e.touches[0].clientX;
          this.lastMouseY = e.touches[0].clientY;
        } else if (e.touches.length === 2) {
          this.isDragging = false;
          lastTouchDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY,
          );
        }
      },
      { passive: false },
    );

    this.canvas.addEventListener(
      "touchmove",
      (e) => {
        e.preventDefault(); // stop the page from scrolling/zooming over the map
        if (e.touches.length === 1 && this.isDragging) {
          const t = e.touches[0];
          this.panX += t.clientX - this.lastMouseX;
          this.panY += t.clientY - this.lastMouseY;
          this.lastMouseX = t.clientX;
          this.lastMouseY = t.clientY;
        } else if (e.touches.length === 2 && lastTouchDist !== null) {
          const dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY,
          );
          const rect = this.canvas.getBoundingClientRect();
          const midX =
            (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
          const midY =
            (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
          this.zoomAt(midX, midY, dist / lastTouchDist);
          lastTouchDist = dist;
        }
      },
      { passive: false },
    );

    const endTouch = (e) => {
      if (e.touches.length === 0) {
        this.isDragging = false;
        lastTouchDist = null;
      } else if (e.touches.length === 1) {
        // Going from two fingers back to one: resume panning from that finger.
        lastTouchDist = null;
        this.isDragging = true;
        this.lastMouseX = e.touches[0].clientX;
        this.lastMouseY = e.touches[0].clientY;
      }
    };
    this.canvas.addEventListener("touchend", endTouch);
    this.canvas.addEventListener("touchcancel", endTouch);

    // Handle resize
    window.addEventListener("resize", () => {
      this.setupCanvas();
    });
  }

  zoomAt(x, y, factor) {
    const oldZoom = this.zoom;
    this.zoom = Math.max(
      this.minZoom,
      Math.min(this.maxZoom, this.zoom * factor),
    );

    if (this.zoom !== oldZoom) {
      // Adjust pan to zoom toward mouse position
      const zoomRatio = this.zoom / oldZoom;
      this.panX = x - (x - this.panX) * zoomRatio;
      this.panY = y - (y - this.panY) * zoomRatio;
    }

    return this.zoom;
  }

  setZoom(level) {
    const centerX = this.canvas.width / 2;
    const centerY = this.canvas.height / 2;
    const factor = level / this.zoom;
    return this.zoomAt(centerX, centerY, factor);
  }

  setPlayerColors(players) {
    this.playerTeams = {};
    players.forEach((p) => {
      this.playerColors[p.name] = p.color_hex;
      if (p.civilization) {
        this.playerCivs[p.name] = p.civilization;
        this.loadCivEmblem(p.civilization); // preload the emblem image
      }
    });
    // Assign a stable team number per distinct team roster (FFA -> own team).
    const keyToNum = new Map();
    let next = 1;
    players.forEach((p) => {
      const roster = p.team && p.team.length ? p.team.slice() : [p.name];
      if (!roster.includes(p.name)) roster.push(p.name);
      const key = roster.slice().sort().join("|");
      if (!keyToNum.has(key)) keyToNum.set(key, next++);
      this.playerTeams[p.name] = keyToNum.get(key);
    });
  }

  // Convert game coordinates to isometric canvas coordinates
  // Diamond orientation: (0,0) at left, X goes to top, Y goes to bottom
  gameToCanvas(gameX, gameY) {
    // Rotated isometric projection:
    // - Left corner: (0, 0)
    // - Top corner: (maxX, 0)
    // - Bottom corner: (0, maxY)
    // - Right corner: (maxX, maxY)
    const isoX = (gameX + gameY) * (this.tileWidth / 2) * this.zoom;
    const isoY = (gameY - gameX) * (this.tileHeight / 2) * this.zoom;

    return {
      x: this.panX + isoX,
      y: this.panY + isoY,
    };
  }

  // Draw the base map as a diamond
  // Receive the starting-map data (terrain grid + GAIA objects) and pre-render
  // it once to an offscreen canvas used as the static map backdrop.
  setMapData(terrain, mapObjects, animals) {
    this.terrain = terrain || null;
    this.mapObjects = mapObjects || null;
    // Huntable/herdable animals are drawn live (not baked) so each can vanish
    // once a player takes control of it (currentTime >= gone_at).
    this.animals = animals || null;
    this.mapLayer = null;
    if (this.terrain && this.terrain.ids) {
      this.buildMapLayer();
    }
  }

  buildMapLayer() {
    const dim = this.terrain.dimension;

    // Render the backdrop at a higher tile resolution than the on-screen base
    // (tileWidth=6) so it stays crisp when zoomed in. Pick the largest tile
    // size that keeps the offscreen canvas under a mobile-safe pixel budget
    // (iOS caps canvas area around ~16.7M px). Area = dim^2 * OTW^2 / 2.
    const PIXEL_BUDGET = 14_000_000;
    let otw = Math.floor(Math.sqrt((PIXEL_BUDGET * 2) / (dim * dim)));
    otw = Math.max(this.tileWidth, Math.min(28, otw)); // >= native, <= 28
    const oth = otw / 2;
    const originY = (dim * oth) / 2; // shift so projected Y is >= 0

    const off = document.createElement("canvas");
    off.width = Math.ceil(dim * otw) + 2;
    off.height = Math.ceil(dim * oth) + 2;
    const c = off.getContext("2d");

    // Iso projection in offscreen space (zoom=1, pan=0) at the higher tile size.
    const proj = (x, y) => ({
      x: (x + y) * (otw / 2),
      y: (y - x) * (oth / 2) + originY,
    });

    // Terrain tiles (filled diamonds). Stroke each in its own color to hide
    // sub-pixel seams between adjacent tiles.
    const ids = this.terrain.ids;
    const pal = this.terrain.palette || {};
    c.lineWidth = 1;
    for (let ty = 0; ty < dim; ty++) {
      for (let tx = 0; tx < dim; tx++) {
        const color = pal[ids[ty * dim + tx]] || "#4f7a36";
        const a = proj(tx, ty);
        const b = proj(tx + 1, ty);
        const d = proj(tx + 1, ty + 1);
        const e = proj(tx, ty + 1);
        c.fillStyle = color;
        c.strokeStyle = color;
        c.beginPath();
        c.moveTo(a.x, a.y);
        c.lineTo(b.x, b.y);
        c.lineTo(d.x, d.y);
        c.lineTo(e.x, e.y);
        c.closePath();
        c.fill();
        c.stroke();
      }
    }

    // Resource / tree objects as colored dots, ~one tile across.
    const colors = {
      tree: "#2f5a2a",
      gold: "#ffcc33",
      stone: "#c2c2c2",
      forage: "#d4486a",
      boar: "#7a4a2a",
      hunt: "#b5894e",
      relic: "#c45ad6",
      fish: "#3aa0c0",
      sheep: "#e6ddcb",
    };
    const rDot = oth * 0.55;
    for (const o of this.mapObjects || []) {
      const p = proj(o.x, o.y);
      c.fillStyle = colors[o.c] || "#ffffff";
      c.beginPath();
      c.arc(p.x, p.y, o.c === "tree" ? rDot * 0.9 : rDot, 0, Math.PI * 2);
      c.fill();
    }

    this.mapLayer = off;
    this.mapOriginY = originY;
    // Scale between offscreen pixels and native world pixels, for blitting.
    this.mapLayerScale = this.tileWidth / otw;
  }

  drawMap() {
    const ctx = this.ctx;

    // Dark background
    ctx.fillStyle = "#1a3d1a";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // Get the four corners of the diamond
    // With current projection: (0,0)=left, (maxX,0)=top, (0,maxY)=bottom, (maxX,maxY)=right
    const left = this.gameToCanvas(0, 0);
    const top = this.gameToCanvas(this.mapSize, 0);
    const right = this.gameToCanvas(this.mapSize, this.mapSize);
    const bottom = this.gameToCanvas(0, this.mapSize);

    if (this.mapLayer) {
      // Blit the pre-rendered terrain backdrop. The offscreen is at a higher
      // tile resolution, so scale by zoom * (native/offscreen tile size).
      const s = this.zoom * this.mapLayerScale;
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(
        this.mapLayer,
        this.panX,
        this.panY - s * this.mapOriginY,
        this.mapLayer.width * s,
        this.mapLayer.height * s,
      );
    } else {
      // Fallback: flat green diamond (uploads / replays without terrain data)
      ctx.fillStyle = "#2d5a2d";
      ctx.beginPath();
      ctx.moveTo(top.x, top.y);
      ctx.lineTo(right.x, right.y);
      ctx.lineTo(bottom.x, bottom.y);
      ctx.lineTo(left.x, left.y);
      ctx.closePath();
      ctx.fill();
    }

    // Draw grid lines if zoomed in enough
    if (this.zoom >= 1.5) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
      ctx.lineWidth = 1;

      const gridSpacing = 20; // Every 20 tiles

      // Lines parallel to the right edge (constant X)
      for (let i = 0; i <= this.mapSize; i += gridSpacing) {
        const start = this.gameToCanvas(i, 0);
        const end = this.gameToCanvas(i, this.mapSize);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
      }

      // Lines parallel to the left edge (constant Y)
      for (let i = 0; i <= this.mapSize; i += gridSpacing) {
        const start = this.gameToCanvas(0, i);
        const end = this.gameToCanvas(this.mapSize, i);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
      }
    }

    // Draw diamond border
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(top.x, top.y);
    ctx.lineTo(right.x, right.y);
    ctx.lineTo(bottom.x, bottom.y);
    ctx.lineTo(left.x, left.y);
    ctx.closePath();
    ctx.stroke();
  }

  // Draw a unit based on its type
  // unitName is the full name like "knight_Player1_1" for label display
  drawUnit(
    x,
    y,
    player,
    type,
    opacity = 1,
    unitName = null,
    pxOffsetX = 0,
    pxOffsetY = 0,
    sizeScale = 1,
  ) {
    if (x === null || y === null) return;

    // Base position is projected from game coords; the spread offset is added in
    // screen pixels so a group reads as a true circular blob on screen.
    const pos = this.gameToCanvas(x, y);
    const cx = pos.x + pxOffsetX;
    const cy = pos.y + pxOffsetY;
    const color = this.playerColors[player] || "#ffffff";

    // A unit occupies at most one tile: its diameter fits within the tile's
    // short diagonal (tileHeight). sizeScale enlarges the centre of big groups.
    const tileShort = this.tileHeight * this.zoom;
    const size = Math.max(3, tileShort * 0.9 * 1.25) * sizeScale;

    // Villagers stay as plain player-colored dots. Military units show their
    // unit icon on a player-colored circle. A unit with no matching icon falls
    // back to a plain circle too — never a geometric shape, never a text label.
    const actualType = unitName ? this.extractUnitType(unitName) : type;
    let sprite = null;
    if (actualType && actualType !== "villager") {
      sprite =
        this.getSprite(actualType) ||
        this.getSprite(this.spriteAlias[actualType]);
    }

    if (sprite) {
      this.drawSpriteWithPlayerColor(cx, cy, sprite, color, size, opacity);
      return;
    }

    this.ctx.globalAlpha = opacity;
    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.6)";
    this.ctx.lineWidth = Math.max(0.5, size * 0.08);
    this.ctx.stroke();
    this.ctx.globalAlpha = 1;
  }

  // Draw a sprite with player color indicator (circle for units).
  // `diameter` is the full circle diameter (one tile = tileHeight*zoom).
  drawSpriteWithPlayerColor(x, y, sprite, playerColor, diameter, opacity = 1) {
    const ctx = this.ctx;
    ctx.globalAlpha = opacity;
    const r = diameter / 2;

    // Player-color circle (this is the full unit footprint, ~one tile)
    ctx.fillStyle = playerColor;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();

    // Thin black outline (scales with size)
    ctx.strokeStyle = "rgba(0, 0, 0, 0.6)";
    ctx.lineWidth = Math.max(0.5, diameter * 0.08);
    ctx.stroke();

    // Sprite inset slightly so a thin player-color rim shows around it
    const sd = diameter * 0.82;
    ctx.drawImage(sprite, x - sd / 2, y - sd / 2, sd, sd);

    ctx.globalAlpha = 1;
  }

  // Draw a building sprite with player color indicator (isometric diamond shape)
  // Sprite is rotated and skewed to match isometric perspective
  drawBuildingSpriteWithPlayerColor(
    x,
    y,
    sprite,
    playerColor,
    size,
    opacity = 1,
  ) {
    const ctx = this.ctx;
    ctx.globalAlpha = opacity * 0.7; // Reduced opacity for buildings

    // Draw player color background as isometric diamond
    const halfW = size / 2 + 2;
    const halfH = size / 4 + 2;
    ctx.fillStyle = playerColor;
    ctx.beginPath();
    ctx.moveTo(x, y - halfH);
    ctx.lineTo(x + halfW, y);
    ctx.lineTo(x, y + halfH);
    ctx.lineTo(x - halfW, y);
    ctx.closePath();
    ctx.fill();

    // Draw black outline
    ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    ctx.lineWidth = 1;
    ctx.stroke();

    // Draw the sprite with isometric transformation
    // Transform the square sprite into an isometric diamond shape
    ctx.save();
    ctx.translate(x, y);

    // Apply isometric transformation matrix:
    // Scale horizontally, skew to create diamond effect
    // The transform creates a 2:1 isometric projection
    ctx.transform(1, 0.5, -1, 0.5, 0, 0);

    // Scale so the sprite roughly fills its tile footprint (slight overhang).
    const scaleFactor = (size / sprite.width) * 0.55;
    ctx.scale(scaleFactor, scaleFactor);

    // Draw centered
    ctx.drawImage(sprite, -sprite.width / 2, -sprite.height / 2);

    ctx.restore();
    ctx.globalAlpha = 1;
  }

  // Extract the unit type from the full unit name
  // e.g., "knight_PlayerName_1" -> "knight"
  // e.g., "cavalryarcher_PlayerName_2" -> "cavalryarcher"
  extractUnitType(unitName) {
    if (!unitName) return "unknown";
    // Unit names are formatted as: type_playerName_number
    // Split by underscore and take the first part
    const firstUnderscore = unitName.indexOf("_");
    if (firstUnderscore === -1) return unitName;
    return unitName.substring(0, firstUnderscore);
  }

  // Draw a text label below the unit/building
  drawTypeLabel(x, y, label, size) {
    const ctx = this.ctx;
    const labelY = y + size + 8 * this.zoom;

    // Only show labels when zoomed in enough to read them
    if (this.zoom < 0.5) return;

    const fontSize = Math.max(8, Math.min(12, 10 * this.zoom));
    ctx.font = `bold ${fontSize}px Arial`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    // Draw background for readability
    const textWidth = ctx.measureText(label).width;
    ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
    ctx.fillRect(
      x - textWidth / 2 - 2,
      labelY - 1,
      textWidth + 4,
      fontSize + 2,
    );

    // Draw text
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, x, labelY);
  }

  // Shield shape for infantry
  drawShield(x, y, size) {
    const ctx = this.ctx;
    const w = size * 0.8;
    const h = size;

    ctx.beginPath();
    ctx.moveTo(x - w / 2, y - h / 2);
    ctx.lineTo(x + w / 2, y - h / 2);
    ctx.lineTo(x + w / 2, y + h / 4);
    ctx.lineTo(x, y + h / 2);
    ctx.lineTo(x - w / 2, y + h / 4);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  // Arrow/diamond shape for archers
  drawArcher(x, y, size, color) {
    const ctx = this.ctx;

    // Diamond body
    ctx.beginPath();
    ctx.moveTo(x, y - size / 2);
    ctx.lineTo(x + size / 3, y);
    ctx.lineTo(x, y + size / 2);
    ctx.lineTo(x - size / 3, y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Arrow line
    ctx.strokeStyle = color;
    ctx.lineWidth = 2 * this.zoom;
    ctx.beginPath();
    ctx.moveTo(x, y - size / 2);
    ctx.lineTo(x, y - size);
    ctx.stroke();
    ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    ctx.lineWidth = 1;
  }

  // Oval shape for cavalry
  drawCavalry(x, y, size, color) {
    const ctx = this.ctx;

    // Horse body (horizontal ellipse)
    ctx.beginPath();
    ctx.ellipse(x, y, size / 2, size / 3, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Horse head (small circle)
    ctx.beginPath();
    ctx.arc(x + size / 3, y - size / 4, size / 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  // Cross shape for monks
  drawMonk(x, y, size, color) {
    const ctx = this.ctx;
    const armWidth = size / 3;

    // Vertical bar
    ctx.fillRect(x - armWidth / 2, y - size / 2, armWidth, size);
    // Horizontal bar
    ctx.fillRect(x - size / 3, y - size / 4, (size * 2) / 3, armWidth);

    ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    ctx.strokeRect(x - armWidth / 2, y - size / 2, armWidth, size);
  }

  // Boat shape for ships
  drawShip(x, y, size, color) {
    const ctx = this.ctx;

    // Hull
    ctx.beginPath();
    ctx.moveTo(x - size / 2, y);
    ctx.lineTo(x - size / 3, y + size / 3);
    ctx.lineTo(x + size / 3, y + size / 3);
    ctx.lineTo(x + size / 2, y);
    ctx.lineTo(x + size / 3, y - size / 4);
    ctx.lineTo(x - size / 3, y - size / 4);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Mast
    ctx.strokeStyle = color;
    ctx.lineWidth = 2 * this.zoom;
    ctx.beginPath();
    ctx.moveTo(x, y - size / 4);
    ctx.lineTo(x, y - size / 2 - size / 4);
    ctx.stroke();
    ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    ctx.lineWidth = 1;
  }

  // Crown/star for king
  drawKing(x, y, size, color) {
    const ctx = this.ctx;

    // Circle base
    ctx.beginPath();
    ctx.arc(x, y, size / 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Crown points
    ctx.fillStyle = "#FFD700"; // Gold
    const crownSize = size / 3;
    ctx.beginPath();
    ctx.moveTo(x - crownSize, y - size / 3);
    ctx.lineTo(x - crownSize / 2, y - size / 2 - crownSize / 2);
    ctx.lineTo(x, y - size / 3);
    ctx.lineTo(x + crownSize / 2, y - size / 2 - crownSize / 2);
    ctx.lineTo(x + crownSize, y - size / 3);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = color;
  }

  // Building footprint in tiles (NxN). Approximate AoE2 DE values.
  buildingFootprint(type, alt = "") {
    const F = {
      towncenter: 4,
      castle: 4,
      wonder: 5,
      farm: 3,
      barracks: 3,
      archeryrange: 3,
      stable: 3,
      blacksmith: 3,
      market: 4,
      monastery: 3,
      university: 4,
      siegeworkshop: 4,
      dock: 3,
      house: 2,
      mill: 2,
      lumbercamp: 2,
      miningcamp: 2,
      outpost: 1,
      watchtower: 1,
      guardtower: 1,
      keep: 1,
      bombardtower: 1,
    };
    if (F[type] !== undefined) return F[type];
    if (F[alt] !== undefined) return F[alt];
    if (type.includes("wall") || type.includes("gate") || type.includes("tower"))
      return 1;
    return 2; // sensible default for unknown buildings
  }

  // Vertical "height" (canvas px, pre-zoom) for buildings, so they read as
  // raised 3D blocks in the isometric view. Height scales with footprint:
  // castle/TC/towers are special, farms stay flat, 3x3+ are 5px, 2x2 (and
  // smaller) are 2px. 0 = flat (drawn on the ground).
  buildingHeight(spriteType, typeClean, footprint) {
    if (spriteType === "castle") return 18;
    if (spriteType === "towncenter") return 11;
    if (/tower|keep|outpost|turret|donjon/.test(typeClean)) return 14;
    if (/farm/.test(typeClean)) return 0; // farms lie flat on the ground
    if (footprint >= 3) return 5;
    return 2; // 2x2 and smaller
  }

  // Draw a raised isometric block (the two viewer-facing vertical faces) under a
  // building so it appears to have height. The building's own diamond/sprite is
  // drawn elevated by `heightPx` and serves as the top cap of the block.
  drawIsoExtrusion(x, y, footprint, heightPx, color, opacity = 1) {
    const ctx = this.ctx;
    const halfW = (footprint * this.tileWidth * this.zoom) / 2;
    const halfH = (footprint * this.tileHeight * this.zoom) / 2;

    // Ground diamond's lower corners (left, bottom, right) and their raised twins.
    const gL = { x: x - halfW, y: y };
    const gB = { x: x, y: y + halfH };
    const gR = { x: x + halfW, y: y };
    const tL = { x: gL.x, y: gL.y - heightPx };
    const tB = { x: gB.x, y: gB.y - heightPx };
    const tR = { x: gR.x, y: gR.y - heightPx };

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.lineWidth = 1;
    ctx.lineJoin = "round";

    // Left face (darker) — L -> B -> B' -> L'
    ctx.fillStyle = this.darkenColor(color, 0.5);
    ctx.beginPath();
    ctx.moveTo(gL.x, gL.y);
    ctx.lineTo(gB.x, gB.y);
    ctx.lineTo(tB.x, tB.y);
    ctx.lineTo(tL.x, tL.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Right face (a touch lighter) — B -> R -> R' -> B'
    ctx.fillStyle = this.darkenColor(color, 0.3);
    ctx.beginPath();
    ctx.moveTo(gB.x, gB.y);
    ctx.lineTo(gR.x, gR.y);
    ctx.lineTo(tR.x, tR.y);
    ctx.lineTo(tB.x, tB.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.restore();
  }

  // Draw a building based on its type
  drawBuilding(x, y, player, buildingType, opacity = 1) {
    if (x === null || y === null) return;

    const pos = this.gameToCanvas(x, y);
    const color = this.playerColors[player] || "#ffffff";
    const typeClean = buildingType.toLowerCase().replace(/\s/g, "");

    let spriteType = typeClean;
    if (typeClean.includes("towncenter")) spriteType = "towncenter";
    else if (typeClean.includes("castle")) spriteType = "castle";

    // A building spans its real tile footprint: the player-color diamond is
    // N tiles wide (N*tileWidth), so it covers an NxN tile area on the map.
    const footprint = this.buildingFootprint(spriteType, typeClean);
    const size = footprint * this.tileWidth * this.zoom;

    // Landmark buildings are drawn as procedural isometric 3D structures (no
    // sprite image) so their silhouette reads at a glance: the town centre's
    // central keep + barn wings + courtyard, the castle's crenellated tiers and
    // round/square corner towers.
    if (spriteType === "towncenter") {
      this.drawTownCenter3D(pos.x, pos.y, footprint, color, opacity);
      return;
    }
    if (spriteType === "castle") {
      this.drawCastle3D(pos.x, pos.y, footprint, color, opacity);
      return;
    }

    // Tall structures (TC / castle / towers) sit on a raised iso block; their
    // sprite/shape is drawn elevated onto the top of it.
    const heightPx =
      this.buildingHeight(spriteType, typeClean, footprint) * this.zoom;
    let drawX = pos.x;
    let drawY = pos.y;
    if (heightPx > 0) {
      this.drawIsoExtrusion(pos.x, pos.y, footprint, heightPx, color, opacity);
      drawY = pos.y - heightPx;
    }

    // Try to use sprite (exact match only)
    const sprite = this.getSprite(spriteType);
    if (sprite) {
      this.drawBuildingSpriteWithPlayerColor(
        drawX,
        drawY,
        sprite,
        color,
        size,
        opacity,
      );
    } else {
      // Fallback to geometric shapes
      this.ctx.globalAlpha = opacity;
      this.ctx.fillStyle = color;
      this.ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
      this.ctx.lineWidth = 1;

      if (typeClean.includes("towncenter")) {
        this.drawTownCenter(drawX, drawY, color);
      } else if (typeClean.includes("castle")) {
        this.drawCastle(drawX, drawY, color);
      } else if (this.largeBuildings.has(typeClean)) {
        this.drawLargeBuilding(
          drawX,
          drawY,
          this.sizes.building_large * this.zoom,
        );
      } else {
        this.drawSmallBuilding(
          drawX,
          drawY,
          this.sizes.building_small * this.zoom,
        );
      }

      this.ctx.globalAlpha = 1;
    }

    // No labels for buildings - sprites or geometric shapes are sufficient
  }

  // Simple isometric diamond for small buildings
  drawSmallBuilding(x, y, size) {
    const halfW = size / 2;
    const halfH = size / 4;

    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH);
    this.ctx.lineTo(x + halfW, y);
    this.ctx.lineTo(x, y + halfH);
    this.ctx.lineTo(x - halfW, y);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();
  }

  // Larger isometric diamond for production buildings
  drawLargeBuilding(x, y, size) {
    const halfW = size / 2;
    const halfH = size / 4;

    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH);
    this.ctx.lineTo(x + halfW, y);
    this.ctx.lineTo(x, y + halfH);
    this.ctx.lineTo(x - halfW, y);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();

    // Inner detail
    const innerSize = size * 0.5;
    const innerHalfW = innerSize / 2;
    const innerHalfH = innerSize / 4;
    this.ctx.strokeStyle = "rgba(255, 255, 255, 0.3)";
    this.ctx.beginPath();
    this.ctx.moveTo(x, y - innerHalfH);
    this.ctx.lineTo(x + innerHalfW, y);
    this.ctx.lineTo(x, y + innerHalfH);
    this.ctx.lineTo(x - innerHalfW, y);
    this.ctx.closePath();
    this.ctx.stroke();
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
  }

  // ---- Procedural isometric building primitives -------------------------
  //
  // All of these work in screen space. A footprint diamond centred at screen
  // (cx, cy) has half-extents halfW (along the L<->R screen axis) and halfH
  // (along the T<->B axis); elevations are measured in canvas px upward from
  // the ground centre, so blocks can be stacked into tiers.

  // Draw an isometric box: its top cap plus the two viewer-facing vertical
  // faces (left = L->B edge, right = B->R edge). Returns the four top-cap
  // corners [x,y] so callers can add roofs / crenellations on top.
  _isoBox(cx, cyGround, halfW, halfH, elevBottom, elevTop, colors, opacity) {
    const ctx = this.ctx;
    const yB = cyGround - elevBottom;
    const yT = cyGround - elevTop;
    const Lb = [cx - halfW, yB];
    const Bb = [cx, yB + halfH];
    const Rb = [cx + halfW, yB];
    const Lt = [cx - halfW, yT];
    const Tt = [cx, yT - halfH];
    const Rt = [cx + halfW, yT];
    const Bt = [cx, yT + halfH];

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.lineJoin = "round";
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(0,0,0,0.5)";

    // left vertical face
    ctx.fillStyle = colors.left;
    ctx.beginPath();
    ctx.moveTo(Lb[0], Lb[1]);
    ctx.lineTo(Bb[0], Bb[1]);
    ctx.lineTo(Bt[0], Bt[1]);
    ctx.lineTo(Lt[0], Lt[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // right vertical face
    ctx.fillStyle = colors.right;
    ctx.beginPath();
    ctx.moveTo(Bb[0], Bb[1]);
    ctx.lineTo(Rb[0], Rb[1]);
    ctx.lineTo(Rt[0], Rt[1]);
    ctx.lineTo(Bt[0], Bt[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // top cap
    ctx.fillStyle = colors.top;
    ctx.beginPath();
    ctx.moveTo(Lt[0], Lt[1]);
    ctx.lineTo(Tt[0], Tt[1]);
    ctx.lineTo(Rt[0], Rt[1]);
    ctx.lineTo(Bt[0], Bt[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.restore();
    return { Lt, Tt, Rt, Bt };
  }

  // Stand crenellations (alternating merlons of height `mh`) up along a screen
  // edge p1 -> p2.
  _crenellateEdge(p1, p2, mh, n, side, opacity) {
    const ctx = this.ctx;
    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.lineJoin = "round";
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(0,0,0,0.5)";
    ctx.fillStyle = side;
    const segs = n * 2 - 1;
    for (let i = 0; i < segs; i += 2) {
      const a = i / segs;
      const b = (i + 1) / segs;
      const ax = p1[0] + (p2[0] - p1[0]) * a;
      const ay = p1[1] + (p2[1] - p1[1]) * a;
      const bx = p1[0] + (p2[0] - p1[0]) * b;
      const by = p1[1] + (p2[1] - p1[1]) * b;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.lineTo(bx, by - mh);
      ctx.lineTo(ax, ay - mh);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }

  // Pyramidal (hip) roof over a top diamond given by its corners. Returns the
  // peak point.
  _hipRoof(corners, peakH, leftColor, rightColor, opacity) {
    const ctx = this.ctx;
    const { Lt, Tt, Rt, Bt } = corners;
    const cx = (Lt[0] + Rt[0]) / 2;
    const cy = (Lt[1] + Rt[1]) / 2;
    const peak = [cx, cy - peakH];

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.lineJoin = "round";
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(0,0,0,0.5)";

    // back faces (mostly hidden behind the ridge)
    ctx.fillStyle = this.darkenColor(leftColor, 0.12);
    ctx.beginPath();
    ctx.moveTo(Lt[0], Lt[1]);
    ctx.lineTo(Tt[0], Tt[1]);
    ctx.lineTo(peak[0], peak[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(Tt[0], Tt[1]);
    ctx.lineTo(Rt[0], Rt[1]);
    ctx.lineTo(peak[0], peak[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // front-left face
    ctx.fillStyle = leftColor;
    ctx.beginPath();
    ctx.moveTo(Lt[0], Lt[1]);
    ctx.lineTo(Bt[0], Bt[1]);
    ctx.lineTo(peak[0], peak[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // front-right face
    ctx.fillStyle = rightColor;
    ctx.beginPath();
    ctx.moveTo(Bt[0], Bt[1]);
    ctx.lineTo(Rt[0], Rt[1]);
    ctx.lineTo(peak[0], peak[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.restore();
    return peak;
  }

  // Round tower (cylinder) with a crenellated top rim.
  _roundTower(px, py, rx, H, body, topColor, crenH, opacity) {
    const ctx = this.ctx;
    const ry = rx * 0.5;
    const yTop = py - H;

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.lineJoin = "round";
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(0,0,0,0.5)";

    // cylinder body: up the left side, across the (hidden) top, down the right
    // side, then the front-bottom bulge back to the start
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.moveTo(px - rx, yTop);
    ctx.lineTo(px - rx, py);
    const N = 12;
    for (let i = 0; i <= N; i++) {
      const th = Math.PI - (Math.PI * i) / N; // PI (left) -> 0 (right)
      ctx.lineTo(px + rx * Math.cos(th), py + ry * Math.sin(th));
    }
    ctx.lineTo(px + rx, yTop);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // subtle right-side shading for roundness
    ctx.fillStyle = this.darkenColor(body, 0.16);
    ctx.beginPath();
    ctx.moveTo(px + rx * 0.35, yTop);
    ctx.lineTo(px + rx * 0.35, py + ry * 0.78);
    for (let i = 0; i <= 6; i++) {
      const th = (Math.PI * 0.32 * i) / 6; // toward the right edge
      ctx.lineTo(px + rx * Math.cos(th), py + ry * Math.sin(th));
    }
    ctx.lineTo(px + rx, yTop);
    ctx.closePath();
    ctx.fill();

    // top cap
    ctx.fillStyle = topColor;
    ctx.beginPath();
    ctx.ellipse(px, yTop, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // crenellations around the front of the rim (right -> left)
    const n = 6;
    ctx.fillStyle = body;
    for (let i = 0; i < n; i++) {
      const th = Math.PI * (0.1 + 0.8 * (i / (n - 1)));
      const ex = px + rx * Math.cos(th);
      const ey = yTop + ry * Math.sin(th);
      const w = rx * 0.13;
      ctx.beginPath();
      ctx.rect(ex - w, ey - crenH, 2 * w, crenH);
      ctx.fill();
      ctx.stroke();
    }

    ctx.restore();
  }

  // Square corner tower: a tall iso box with crenellations along its two
  // viewer-facing top edges.
  _squareTower(px, py, hw, hh, H, crenH, colors, opacity) {
    const c = this._isoBox(px, py, hw, hh, 0, H, colors, opacity);
    this._crenellateEdge(c.Lt, c.Bt, crenH, 3, colors.left, opacity);
    this._crenellateEdge(c.Bt, c.Rt, crenH, 3, colors.right, opacity);
    return c;
  }

  // Town Center: a tall central keep flanked by two lower barn wings, with an
  // open courtyard at the front. Drawn back-to-front from the ground up.
  drawTownCenter3D(cx, cy, footprint, color, opacity = 1) {
    const z = this.zoom;
    const HW = (footprint * this.tileWidth * z) / 2;
    const HH = (footprint * this.tileHeight * z) / 2;

    const wall = {
      top: this.lightenColor(color, 0.14),
      left: this.darkenColor(color, 0.12),
      right: this.darkenColor(color, 0.34),
    };
    const roofL = this.darkenColor(color, 0.5);
    const roofR = this.darkenColor(color, 0.66);

    // place a sub-centre at diamond coords u (L->R) / v (T->B), |u|+|v| < 1
    const at = (u, v) => [cx + u * HW, cy + v * HH];

    // foundation slab over the whole footprint
    this._isoBox(
      cx,
      cy,
      HW * 0.98,
      HH * 0.98,
      0,
      1.5 * z,
      {
        top: this.darkenColor(color, 0.04),
        left: this.darkenColor(color, 0.2),
        right: this.darkenColor(color, 0.4),
      },
      opacity,
    );

    // central keep (set back, tallest) with a peaked roof up to the max height
    {
      const [kx, ky] = at(0, -0.18);
      const cap = this._isoBox(
        kx,
        ky,
        HW * 0.34,
        HH * 0.34,
        1.5 * z,
        6.5 * z,
        wall,
        opacity,
      );
      this._hipRoof(cap, 4.5 * z, roofL, roofR, opacity);
    }

    // two barn wings (left + right, slightly forward), lower with gable roofs
    for (const u of [-0.46, 0.46]) {
      const [bx, by] = at(u, 0.12);
      const cap = this._isoBox(
        bx,
        by,
        HW * 0.3,
        HH * 0.3,
        1.5 * z,
        4 * z,
        wall,
        opacity,
      );
      this._hipRoof(cap, 2.5 * z, roofL, roofR, opacity);
    }

    // courtyard gate posts framing the front opening
    for (const u of [-0.16, 0.16]) {
      const [gx, gy] = at(u, 0.52);
      this._isoBox(gx, gy, HW * 0.05, HH * 0.05, 1.5 * z, 4 * z, wall, opacity);
    }
  }

  // Castle: a crenellated curtain wall, a taller inner keep, and four corner
  // towers (two round, two square) reaching the max height. Drawn back-to-front.
  drawCastle3D(cx, cy, footprint, color, opacity = 1) {
    const z = this.zoom;
    const HW = (footprint * this.tileWidth * z) / 2;
    const HH = (footprint * this.tileHeight * z) / 2;

    const wall = {
      top: this.lightenColor(color, 0.12),
      left: this.darkenColor(color, 0.1),
      right: this.darkenColor(color, 0.32),
    };
    const at = (u, v) => [cx + u * HW, cy + v * HH];

    const wallH = 8 * z; // curtain wall
    const towerH = 14 * z; // corner towers (+ crenellations)
    const keepBot = wallH;
    const keepTop = 15.5 * z; // inner keep second tier
    const crenH = 2 * z;
    const tHW = HW * 0.2;
    const tHH = HH * 0.2;
    const tR = HW * 0.2;
    const corner = 0.82; // how far towers sit toward each footprint corner

    // 1. back corner tower (round)
    {
      const [tx, ty] = at(0, -corner);
      this._roundTower(tx, ty, tR, towerH, wall.left, wall.top, crenH, opacity);
    }

    // 2. curtain wall (full footprint) + crenellations along its front edges
    {
      const c = this._isoBox(cx, cy, HW * 0.9, HH * 0.9, 0, wallH, wall, opacity);
      this._crenellateEdge(c.Lt, c.Bt, crenH, 5, wall.left, opacity);
      this._crenellateEdge(c.Bt, c.Rt, crenH, 5, wall.right, opacity);

      // gatehouse: a dark arch on the front-right wall face
      const gm = at(0.45, 0.45);
      const gW = HW * 0.1;
      const gH = wallH * 0.7;
      this.ctx.save();
      this.ctx.globalAlpha = opacity;
      this.ctx.fillStyle = "rgba(22,16,11,0.9)";
      this.ctx.beginPath();
      this.ctx.moveTo(gm[0] - gW, gm[1] - gW * 0.4);
      this.ctx.lineTo(gm[0] - gW, gm[1] - gH);
      this.ctx.quadraticCurveTo(
        gm[0],
        gm[1] - gH - gW * 0.5,
        gm[0] + gW,
        gm[1] - gH,
      );
      this.ctx.lineTo(gm[0] + gW, gm[1] - gW * 0.4);
      this.ctx.lineTo(gm[0], gm[1] + gW * 0.4);
      this.ctx.closePath();
      this.ctx.fill();
      this.ctx.restore();
    }

    // 3. inner keep (central second tier, tallest) + crenellations
    {
      const [kx, ky] = at(0, -0.05);
      const c = this._isoBox(
        kx,
        ky,
        HW * 0.4,
        HH * 0.4,
        keepBot,
        keepTop,
        wall,
        opacity,
      );
      this._crenellateEdge(c.Lt, c.Bt, crenH * 1.2, 3, wall.left, opacity);
      this._crenellateEdge(c.Bt, c.Rt, crenH * 1.2, 3, wall.right, opacity);
    }

    // 4. left + right corner towers (square)
    {
      const [lx, ly] = at(-corner, 0);
      this._squareTower(lx, ly, tHW, tHH, towerH, crenH, wall, opacity);
      const [rx, ry] = at(corner, 0);
      this._squareTower(rx, ry, tHW, tHH, towerH, crenH, wall, opacity);
    }

    // 5. front corner tower (round, closest — drawn last)
    {
      const [bx, by] = at(0, corner);
      this._roundTower(bx, by, tR, towerH, wall.left, wall.top, crenH, opacity);
    }
  }

  // Helper to lighten a color toward white by `amount` (0..1)
  lightenColor(color, amount) {
    if (color.startsWith("#")) {
      const r = parseInt(color.slice(1, 3), 16);
      const g = parseInt(color.slice(3, 5), 16);
      const b = parseInt(color.slice(5, 7), 16);
      const L = (c) => Math.round(c + (255 - c) * amount);
      return `rgb(${L(r)}, ${L(g)}, ${L(b)})`;
    }
    return color;
  }

  // Helper to darken a color
  darkenColor(color, amount) {
    // Simple darkening for hex colors
    if (color.startsWith("#")) {
      const r = Math.max(0, parseInt(color.slice(1, 3), 16) * (1 - amount));
      const g = Math.max(0, parseInt(color.slice(3, 5), 16) * (1 - amount));
      const b = Math.max(0, parseInt(color.slice(5, 7), 16) * (1 - amount));
      return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
    }
    return color;
  }

  // Draw a movement or attack line
  drawActionLine(fromX, fromY, toX, toY, player, actionType = "move") {
    if (fromX === null || fromY === null || toX === null || toY === null)
      return;

    const from = this.gameToCanvas(fromX, fromY);
    const to = this.gameToCanvas(toX, toY);
    const color = this.playerColors[player] || "#ffffff";

    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 2 * this.zoom;
    this.ctx.globalAlpha = 0.5;

    if (actionType === "attack" || actionType === "order") {
      // Dashed line for attacks/orders
      this.ctx.setLineDash([5, 5]);
    } else {
      this.ctx.setLineDash([]);
    }

    this.ctx.beginPath();
    this.ctx.moveTo(from.x, from.y);
    this.ctx.lineTo(to.x, to.y);
    this.ctx.stroke();

    // Draw arrowhead
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const arrowSize = 8 * this.zoom;
    this.ctx.beginPath();
    this.ctx.moveTo(to.x, to.y);
    this.ctx.lineTo(
      to.x - arrowSize * Math.cos(angle - Math.PI / 6),
      to.y - arrowSize * Math.sin(angle - Math.PI / 6),
    );
    this.ctx.lineTo(
      to.x - arrowSize * Math.cos(angle + Math.PI / 6),
      to.y - arrowSize * Math.sin(angle + Math.PI / 6),
    );
    this.ctx.closePath();
    this.ctx.fillStyle = color;
    this.ctx.fill();

    this.ctx.setLineDash([]);
    this.ctx.globalAlpha = 1;
  }

  // Draw selection highlight
  drawSelection(x, y, size = 12) {
    if (x === null || y === null) return;

    const pos = this.gameToCanvas(x, y);
    const s = size * this.zoom;

    this.ctx.strokeStyle = "#ffffff";
    this.ctx.lineWidth = 2;
    this.ctx.setLineDash([3, 3]);

    // Isometric selection diamond
    const halfW = s / 2;
    const halfH = s / 4;
    this.ctx.beginPath();
    this.ctx.moveTo(pos.x, pos.y - halfH);
    this.ctx.lineTo(pos.x + halfW, pos.y);
    this.ctx.lineTo(pos.x, pos.y + halfH);
    this.ctx.lineTo(pos.x - halfW, pos.y);
    this.ctx.closePath();
    this.ctx.stroke();

    this.ctx.setLineDash([]);
  }

  // Clear the canvas
  clear() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  // Starting GAIA animals (sheep / boar / deer) drawn as small icon tiles.
  // Each disappears once a player takes control of it (currentTime >= gone_at),
  // mirroring the game where it is herded or hunted and is no longer neutral.
  ANIMAL_STYLES = {
    sheep: { border: "#e8e2cf", glyph: "🐑" },
    boar: { border: "#6b4a30", glyph: "🐗" },
    deer: { border: "#c79a5b", glyph: "🦌" },
  };

  drawAnimals(currentTime) {
    if (!this.animals || !this.animals.length) return;
    const ctx = this.ctx;

    // 0.75x a villager. Villager diameter in drawUnit is tileShort*0.8*1.25
    // (== tileShort), so the animal tile is tileShort * 0.75 — really small.
    const villagerSize = this.tileHeight * this.zoom * 0.8 * 1.25;
    const size = Math.max(4, villagerSize * 0.75);
    const half = size / 2;
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `${Math.round(size * 0.78)}px sans-serif`;
    ctx.lineWidth = Math.max(1, size * 0.08);

    for (const a of this.animals) {
      if (a.gone_at != null && currentTime >= a.gone_at) continue; // taken/hunted
      const p = this.gameToCanvas(a.x, a.y);
      const s = this.ANIMAL_STYLES[a.c] || this.ANIMAL_STYLES.deer;
      // Square tile backing so the icon reads against any terrain.
      ctx.fillStyle = "rgba(255, 255, 255, 0.82)";
      ctx.strokeStyle = s.border;
      ctx.fillRect(p.x - half, p.y - half, size, size);
      ctx.strokeRect(p.x - half, p.y - half, size, size);
      ctx.fillText(s.glyph, p.x, p.y + size * 0.06);
    }
    ctx.restore();
  }

  // ---- Player base territory outlines ----
  // A base is a cluster of >= MIN_BASE_BUILDINGS buildings near each other; it
  // grows as more buildings are placed nearby. Its boundary is drawn as a dotted
  // line in the player's colour, BASE_BUFFER tiles out from the outer buildings.
  BASE_LINK_DIST = 18; // tiles: buildings within this of the cluster join it
  MIN_BASE_BUILDINGS = 5;
  BASE_BUFFER = 5; // tiles of margin around the outer buildings
  BUILDING_HALF = 1.5; // approx building half-footprint (tiles) for hull corners
  BASE_FILL_ALPHA = 0.1; // very light player-colour tint inside a base

  drawBaseBoundaries(state) {
    if (!state || !state.buildings || state.buildings.size === 0) return;

    // Recompute only when the visible building set changes (global signature,
    // since one player's boundary depends on nearby players' buildings too).
    let cnt = 0, sx = 0, sy = 0;
    for (const [, b] of state.buildings) {
      if (b.x == null || b.y == null) continue;
      cnt++;
      sx += b.x;
      sy += b.y;
    }
    const sig = `${cnt}:${Math.round(sx)}:${Math.round(sy)}`;
    if (this._baseSig !== sig) {
      this._bases = this.computeAllBases(state.buildings);
      this._baseSig = sig;
    }

    const bases = this._bases;
    for (const b of bases) {
      // Bases of OTHER players that are newer bite into this one. The newer base
      // keeps its natural shape; this older one is drawn as its shape minus the
      // newer ones, so its line follows just behind the newer boundary.
      const newer = bases.filter(
        (c) => c !== b && c.player !== b.player && this.baseLosesTo(b, c),
      );
      this.drawBaseOutline(b, newer);
    }
  }

  // Base name/team labels, drawn last so they always sit above buildings/units.
  drawBaseLabels() {
    if (!this._bases) return;
    for (const b of this._bases) this.drawBaseLabel(b);
  }

  // Is base `b` the one that yields (gets bitten) versus base `c`? The more
  // recently built base wins; ties broken deterministically so only one yields.
  baseLosesTo(b, c) {
    if (b.recency !== c.recency) return b.recency < c.recency;
    return b.player < c.player;
  }

  // Draw base `b`'s dotted outline as its natural shape minus the `newer` bases.
  // Done with canvas clipping (no polygon-boolean math): the parts of b outside
  // the newer bases, plus the newer borders that fall inside b (drawn in b's
  // colour, so b's line hugs just behind each newer boundary).
  drawBaseOutline(b, newer) {
    if (!newer || newer.length === 0) {
      this.fillPolygon(b.poly, b.color, this.BASE_FILL_ALPHA);
      this.drawDottedPolygon(b.poly, b.color);
      return;
    }
    const ctx = this.ctx;

    // Pass 1: b's own fill + border, clipped to outside every newer base.
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ctx.canvas.width, ctx.canvas.height);
    for (const c of newer) this._addPolyPath(c.poly);
    ctx.clip("evenodd"); // canvas minus the newer polygons
    this.fillPolygon(b.poly, b.color, this.BASE_FILL_ALPHA);
    this.drawDottedPolygon(b.poly, b.color);
    ctx.restore();

    // Pass 2: the newer borders that lie inside b, drawn in b's colour.
    ctx.save();
    ctx.beginPath();
    this._addPolyPath(b.poly);
    ctx.clip();
    for (const c of newer) this.drawDottedPolygon(c.poly, b.color);
    ctx.restore();
  }

  // Append a closed polygon (game coords) to the current canvas path.
  _addPolyPath(poly) {
    const ctx = this.ctx;
    for (let i = 0; i < poly.length; i++) {
      const p = this.gameToCanvas(poly[i].x, poly[i].y);
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
  }

  // Compute every base's natural outline for every player: cluster -> buffered
  // hull -> clipped to the map. Overlap between players is resolved at draw time
  // (newer bases bite into older ones), so the geometry here stays natural.
  computeAllBases(buildings) {
    // Group buildings by player, ignoring walls/gates and tagging each with its
    // kind so a Town Center can seed a base and a Castle can reach further.
    const byPlayer = new Map();
    for (const [, b] of buildings) {
      if (b.x == null || b.y == null) continue;
      const kind = this.buildingKind(b.type);
      if (kind === "wall") continue; // walls don't count toward a base
      b._kind = kind;
      if (!byPlayer.has(b.player)) byPlayer.set(b.player, []);
      byPlayer.get(b.player).push(b);
    }

    const dim = this.mapSize;
    const h = this.BUILDING_HALF;
    // A castle reaches about double a normal building, so its hull-corner extent
    // (which the buffer is added to) is sized so total reach ≈ 2x normal.
    const castleHalf = (this.BUILDING_HALF + this.BASE_BUFFER) * 2 - this.BASE_BUFFER;
    const bases = [];
    for (const [player, bldgs] of byPlayer) {
      const color = this.playerColors[player] || "#ffffff";
      const team = this.playerTeams ? this.playerTeams[player] : null;
      const label = team ? `(${team}) ${player}` : player;

      for (const cl of this.clusterBuildings(bldgs, this.BASE_LINK_DIST)) {
        // A Town Center counts as a whole base on its own (weight = MIN);
        // everything else contributes 1.
        let weight = 0;
        for (const b of cl) {
          weight += b._kind === "tc" ? this.MIN_BASE_BUILDINGS : 1;
        }
        if (weight < this.MIN_BASE_BUILDINGS) continue;

        const pts = [];
        for (const b of cl) {
          const hb = b._kind === "castle" ? castleHalf : h;
          pts.push(
            { x: b.x - hb, y: b.y - hb }, { x: b.x + hb, y: b.y - hb },
            { x: b.x + hb, y: b.y + hb }, { x: b.x - hb, y: b.y + hb },
          );
        }
        const hull = this.convexHull(pts);
        if (hull.length < 3) continue;
        let poly = this.bufferHull(hull, this.BASE_BUFFER);
        poly = this.clipToMap(poly, dim); // keep inside the map
        if (poly.length < 3) continue;

        // recency = most recent construction in this base (drives who bites whom)
        let cx = 0, cy = 0, recency = -Infinity;
        for (const b of cl) {
          cx += b.x;
          cy += b.y;
          if (b.time != null && b.time > recency) recency = b.time;
        }
        bases.push({
          player,
          color,
          poly,
          recency,
          center: { x: cx / cl.length, y: cy / cl.length },
          label,
        });
      }
    }
    return bases;
  }

  // Classify a building by name for base detection.
  buildingKind(type) {
    const t = (type || "").toLowerCase();
    if (/wall|palisade|gate/.test(t)) return "wall";
    if (/town\s*cent|\btc\b/.test(t)) return "tc";
    if (/castle|krepost/.test(t)) return "castle";
    return "other";
  }

  // Clip a convex polygon by the half-plane f(point) <= 0 (Sutherland-Hodgman).
  clipByLinear(poly, f) {
    if (poly.length === 0) return poly;
    const out = [];
    const n = poly.length;
    for (let i = 0; i < n; i++) {
      const cur = poly[i];
      const prev = poly[(i + n - 1) % n];
      const fc = f(cur);
      const fp = f(prev);
      const curIn = fc <= 0;
      const prevIn = fp <= 0;
      if (curIn) {
        if (!prevIn) {
          const t = fp / (fp - fc);
          out.push({ x: prev.x + (cur.x - prev.x) * t, y: prev.y + (cur.y - prev.y) * t });
        }
        out.push(cur);
      } else if (prevIn) {
        const t = fp / (fp - fc);
        out.push({ x: prev.x + (cur.x - prev.x) * t, y: prev.y + (cur.y - prev.y) * t });
      }
    }
    return out;
  }

  // Keep the polygon within the [0, dim] map square.
  clipToMap(poly, dim) {
    poly = this.clipByLinear(poly, (p) => -p.x);
    poly = this.clipByLinear(poly, (p) => p.x - dim);
    poly = this.clipByLinear(poly, (p) => -p.y);
    poly = this.clipByLinear(poly, (p) => p.y - dim);
    return poly;
  }

  // Base label at its centre, in the player's colour, laid out as
  // "(team) <civ emblem> Player Name". The emblem is sized to the font height.
  // The whole thing is centred on the base centroid.
  drawBaseLabel(base) {
    const ctx = this.ctx;
    const p = this.gameToCanvas(base.center.x, base.center.y);
    const fontSize = 13;
    const color = base.color;

    ctx.save();
    ctx.font = `bold ${fontSize}px sans-serif`;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    const team = this.playerTeams ? this.playerTeams[base.player] : null;
    const prefix = team ? `(${team}) ` : "";
    const name = base.player;
    const emblem = this.getCivEmblem(
      this.playerCivs ? this.playerCivs[base.player] : null,
    );
    const emblemW = emblem ? fontSize * 1.25 : 0; // slightly larger than text
    const gap = emblem ? 3 : 0;
    const prefixW = prefix ? ctx.measureText(prefix).width : 0;
    const nameW = ctx.measureText(name).width;
    const total = prefixW + emblemW + gap + nameW;

    let x = p.x - total / 2;
    const drawText = (t, tx) => {
      ctx.lineWidth = 3;
      ctx.strokeStyle = "rgba(0, 0, 0, 0.8)";
      ctx.strokeText(t, tx, p.y);
      ctx.fillStyle = color;
      ctx.fillText(t, tx, p.y);
    };

    if (prefix) {
      drawText(prefix, x);
      x += prefixW;
    }
    if (emblem) {
      ctx.drawImage(emblem, x, p.y - emblemW / 2, emblemW, emblemW);
      x += emblemW + gap;
    }
    drawText(name, x);
    ctx.restore();
  }

  // Union-find single-linkage clustering of buildings by centre distance. A
  // castle links from double the normal distance (it pulls farther buildings
  // into the base).
  clusterBuildings(bldgs, linkDist) {
    const n = bldgs.length;
    const parent = Array.from({ length: n }, (_, i) => i);
    const find = (x) => {
      while (parent[x] !== x) {
        parent[x] = parent[parent[x]];
        x = parent[x];
      }
      return x;
    };
    const d2 = linkDist * linkDist;
    const d2Castle = (linkDist * 2) * (linkDist * 2);
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = bldgs[i].x - bldgs[j].x;
        const dy = bldgs[i].y - bldgs[j].y;
        const limit =
          bldgs[i]._kind === "castle" || bldgs[j]._kind === "castle"
            ? d2Castle
            : d2;
        if (dx * dx + dy * dy <= limit) parent[find(i)] = find(j);
      }
    }
    const groups = new Map();
    for (let i = 0; i < n; i++) {
      const r = find(i);
      if (!groups.has(r)) groups.set(r, []);
      groups.get(r).push(bldgs[i]);
    }
    return [...groups.values()];
  }

  // Convex hull (Andrew's monotone chain). Returns ordered hull vertices.
  convexHull(points) {
    const pts = points
      .slice()
      .sort((a, b) => a.x - b.x || a.y - b.y);
    const cross = (o, a, b) =>
      (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
    const lower = [];
    for (const p of pts) {
      while (
        lower.length >= 2 &&
        cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0
      )
        lower.pop();
      lower.push(p);
    }
    const upper = [];
    for (let i = pts.length - 1; i >= 0; i--) {
      const p = pts[i];
      while (
        upper.length >= 2 &&
        cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0
      )
        upper.pop();
      upper.push(p);
    }
    lower.pop();
    upper.pop();
    return lower.concat(upper);
  }

  // Expand a convex hull outward by r tiles with rounded corners (Minkowski sum
  // with a disk): offset each edge along its outward normal, join with corner arcs.
  bufferHull(hull, r) {
    const n = hull.length;
    let cx = 0, cy = 0;
    for (const p of hull) {
      cx += p.x;
      cy += p.y;
    }
    cx /= n;
    cy /= n;

    // Outward unit normal per edge (sign chosen to point away from the centroid).
    const norm = [];
    for (let i = 0; i < n; i++) {
      const a = hull[i];
      const b = hull[(i + 1) % n];
      let nx = b.y - a.y;
      let ny = -(b.x - a.x);
      const len = Math.hypot(nx, ny) || 1;
      nx /= len;
      ny /= len;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      if ((mx - cx) * nx + (my - cy) * ny < 0) {
        nx = -nx;
        ny = -ny;
      }
      norm.push({ x: nx, y: ny });
    }

    const out = [];
    for (let i = 0; i < n; i++) {
      const a = hull[i];
      const b = hull[(i + 1) % n];
      const ni = norm[i];
      out.push({ x: a.x + ni.x * r, y: a.y + ni.y * r });
      out.push({ x: b.x + ni.x * r, y: b.y + ni.y * r });
      // Rounded corner at b, sweeping from this edge's normal to the next edge's.
      const nj = norm[(i + 1) % n];
      const a1 = Math.atan2(ni.y, ni.x);
      const a2 = Math.atan2(nj.y, nj.x);
      let da = a2 - a1;
      while (da <= -Math.PI) da += 2 * Math.PI;
      while (da > Math.PI) da -= 2 * Math.PI;
      const steps = Math.max(1, Math.round(Math.abs(da) / (Math.PI / 8)));
      for (let s = 1; s < steps; s++) {
        const ang = a1 + (da * s) / steps;
        out.push({ x: b.x + Math.cos(ang) * r, y: b.y + Math.sin(ang) * r });
      }
    }
    return out;
  }

  // Stroke a closed polygon (game-coord points) as a dotted line in `color`.
  drawDottedPolygon(poly, color) {
    if (!poly || poly.length < 3) return;
    const ctx = this.ctx;
    ctx.save();
    ctx.beginPath();
    for (let i = 0; i < poly.length; i++) {
      const p = this.gameToCanvas(poly[i].x, poly[i].y);
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
    ctx.setLineDash([5, 5]);
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.85;
    ctx.stroke();
    ctx.restore();
  }

  // Fill a closed polygon (game-coord points) with a faint player-colour tint.
  fillPolygon(poly, color, alpha) {
    if (!poly || poly.length < 3) return;
    const ctx = this.ctx;
    ctx.save();
    ctx.beginPath();
    this._addPolyPath(poly);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();
  }

  // Full render cycle
  render(state) {
    this.clear();
    this.drawMap();

    // Player base territory outlines sit on the ground, under everything else.
    this.drawBaseBoundaries(state);

    // Starting animals sit on the ground, below walls/buildings/units.
    this.drawAnimals(state.currentTime || 0);

    // Draw walls first (below buildings and units)
    for (const wall of state.walls || []) {
      this.drawWall(wall);
    }

    // Draw buildings with age-based opacity
    // 100% for first 30s, fade to 50% by 30s, then to 25% by 5 minutes
    for (const [name, building] of state.buildings) {
      const age = building.age || 0;
      let opacity;
      if (age < 10) {
        opacity = 1; // Full opacity for first 10 seconds
      } else if (age < 300) {
        // Smooth fade from 1.0 down to 0.25 between 10s and 5 minutes
        opacity = 1 - ((age - 10) / 290) * 0.75;
      } else {
        opacity = 0.25; // 25% after 5 minutes
      }

      this.drawBuilding(
        building.x,
        building.y,
        building.player,
        building.type,
        opacity,
      );
    }

    // Draw units - separate idle villagers (drawn first, below) from active units
    // Group by position to spread overlapping units
    const idleVillagersByPosition = new Map();
    const activeUnitsByPosition = new Map();

    for (const [name, unit] of state.units) {
      if (!unit.alive) continue;

      // Round position to group nearby units
      const key = `${Math.round(unit.x * 2) / 2}_${Math.round(unit.y * 2) / 2}`;

      // Separate idle villagers from active units
      if (unit.idleVillager) {
        if (!idleVillagersByPosition.has(key)) {
          idleVillagersByPosition.set(key, []);
        }
        idleVillagersByPosition.get(key).push({ name, unit });
      } else {
        if (!activeUnitsByPosition.has(key)) {
          activeUnitsByPosition.set(key, []);
        }
        activeUnitsByPosition.get(key).push({ name, unit });
      }
    }

    // Golden angle (~137.5°): consecutive points spiral to fill a disc evenly.
    const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

    // Helper function to draw co-located units as one tight "army blob".
    const drawUnitGroup = (unitsByPosition, isIdleVillagerGroup = false) => {
      for (const [posKey, units] of unitsByPosition) {
        const count = units.length;

        // Vogel sunflower spiral in screen pixels: radius = ringStep·√k, angle =
        // k·goldenAngle. ringStep is set so neighbouring icons overlap ~10%,
        // giving a dense blob that reads as a massed army rather than a grid.
        const baseSize = Math.max(3, this.tileHeight * this.zoom * 0.9 * 1.25);
        const OVERLAP = 0.1; // icons overlap up to ~10%
        const ringStep = (baseSize * (1 - OVERLAP)) / 1.9;

        // Per-type representative sizing: a group can mix unit types, so we
        // enlarge ONE unit per distinct type (its first occurrence in the
        // spiral), sized by how many of that type are present — normal up to 5,
        // +2/3 of normal per extra 5, capped at 3× (~16-20). A 15-archer +
        // 1-elephant army then shows a big archer and a small elephant, so the
        // army's composition reads at a glance.
        const typeOf = (m) =>
          (m.name ? this.extractUnitType(m.name) : null) ||
          m.unit.type ||
          "unit";

        // Stable order (sort by name) so slots don't jitter frame-to-frame.
        const sorted =
          count > 1
            ? [...units].sort((a, b) =>
                a.name < b.name ? -1 : a.name > b.name ? 1 : 0,
              )
            : units;

        const typeCounts = new Map();
        for (const m of sorted)
          typeCounts.set(typeOf(m), (typeCounts.get(typeOf(m)) || 0) + 1);

        // One representative per type (first seen) + everyone else.
        const reps = [];
        const rest = [];
        const seen = new Set();
        for (const m of sorted) {
          const t = typeOf(m);
          if (!seen.has(t)) {
            seen.add(t);
            reps.push({ m, n: typeCounts.get(t), t });
          } else {
            rest.push(m);
          }
        }
        // Most numerous type sits dead centre and is largest; ties by type name.
        reps.sort((a, b) => b.n - a.n || (a.t < b.t ? -1 : 1));

        // Spiral order: representatives fill the centre, the rest pack outward.
        const spiral = [...reps.map((r) => r.m), ...rest];
        const scaleOf = new Map();
        for (const r of reps)
          scaleOf.set(
            r.m.name,
            1 + (Math.min(3, Math.floor((r.n - 1) / 5)) * 2) / 3,
          );

        // Draw outermost first so larger central representatives land on top.
        for (let k = spiral.length - 1; k >= 0; k--) {
          const { name, unit } = spiral[k];
          let opacity = unit.dying ? 0.5 : 1;

          // Idle villagers: 50% opacity after 30s, fading to 25% by 5 minutes
          if (isIdleVillagerGroup) {
            const idleTime = unit.idleTime || 0;
            if (idleTime < 300) {
              opacity *= 0.5 - ((idleTime - 30) / 270) * 0.25;
            } else {
              opacity *= 0.25;
            }
          }

          let pxX = 0;
          let pxY = 0;
          if (count > 1) {
            const radius = ringStep * Math.sqrt(k);
            const angle = k * GOLDEN_ANGLE;
            pxX = radius * Math.cos(angle);
            pxY = radius * Math.sin(angle);
          }
          // A trebuchet the engine considers actively firing is drawn at 3× so
          // a siege in progress stands out.
          const scale = unit.firing ? 3 : scaleOf.get(name) || 1;

          this.drawUnit(
            unit.x,
            unit.y,
            unit.player,
            unit.type,
            opacity,
            name,
            pxX,
            pxY,
            scale,
          );
        }
      }
    };

    // Draw idle villagers first (below layer) at 50% opacity
    drawUnitGroup(idleVillagersByPosition, true);

    // Draw active units on top at full opacity
    drawUnitGroup(activeUnitsByPosition, false);

    // Draw attack arrows
    for (const attack of state.attacks || []) {
      this.drawAttackArrow(
        attack.fromX,
        attack.fromY,
        attack.toX,
        attack.toY,
        attack.player,
        attack.opacity,
      );
    }

    // Trebuchet shots: arcing flaming balls from siege to the building.
    for (const tp of state.trebProjectiles || []) {
      this.drawTrebProjectiles(tp);
    }

    // Base labels last, so player names always stay in the foreground.
    this.drawBaseLabels();
  }

  // Draw a trebuchet's in-flight shots as flaming balls arcing along a parabola
  // from the siege unit to its target, with a flash on impact. Drawn with
  // NORMAL blending and a dark rim so the balls stay visible over the bright
  // map (additive "lighter" washed out against light terrain), plus a motion
  // trail and a faint trajectory guide so the arc is unmistakable.
  drawTrebProjectiles(tp) {
    if (tp.fromX === null || tp.toX === null) return;
    const from = this.gameToCanvas(tp.fromX, tp.fromY);
    const to = this.gameToCanvas(tp.toX, tp.toY);
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const dist = Math.hypot(dx, dy);
    const unitPx = this.tileHeight * this.zoom * 0.9 * 1.25;
    const bombard = tp.kind === "bombard";
    // Bombard cannon: a flat, fast cannonball. Trebuchet: a high, slow lob.
    const arcH = bombard
      ? Math.max(unitPx * 0.5, Math.min(40, dist * 0.16))
      : Math.max(unitPx * 1.8, Math.min(120, dist * 0.5));
    const r = Math.max(3, unitPx * (bombard ? 0.4 : 0.5));
    const ctx = this.ctx;

    // Position along the parabola at parameter q in [0,1].
    const arcPos = (q) => ({
      x: from.x + dx * q,
      y: from.y + dy * q - arcH * 4 * q * (1 - q),
    });

    for (const p of tp.shots) {
      const pt = arcPos(p);

      if (p > 0.88) {
        this.drawImpactFlash(to.x, to.y, (p - 0.88) / 0.12, bombard);
      }

      ctx.save();
      if (bombard) {
        // Grey smoke trail behind the cannonball.
        for (let i = 4; i >= 1; i--) {
          const q = Math.max(0, p - i * 0.05);
          const tpos = arcPos(q);
          ctx.globalAlpha = 0.07 * (5 - i);
          ctx.fillStyle = "#9a9a9a";
          ctx.beginPath();
          ctx.arc(tpos.x, tpos.y, r * (0.5 + 0.13 * (5 - i)), 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
        // Solid black iron ball with a thin rim + small highlight (sheen).
        ctx.fillStyle = "#0b0b0b";
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(0, 0, 0, 0.9)";
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.fillStyle = "rgba(230, 230, 230, 0.4)";
        ctx.beginPath();
        ctx.arc(pt.x - r * 0.32, pt.y - r * 0.32, r * 0.3, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Flaming boulder: orange body, bright core, glowing trail.
        for (let i = 4; i >= 1; i--) {
          const q = Math.max(0, p - i * 0.05);
          const tpos = arcPos(q);
          ctx.globalAlpha = 0.1 * (5 - i);
          ctx.fillStyle = "#ff8a1e";
          ctx.beginPath();
          ctx.arc(tpos.x, tpos.y, r * (0.45 + 0.1 * (5 - i)), 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
        ctx.fillStyle = "rgba(40, 12, 0, 0.9)";
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, r + 1.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#ff7415";
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#fff2b0";
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, r * 0.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  // Expanding burst at the impact point; t in 0..1 over the last bit of flight.
  // Bombard impacts puff grey smoke; trebuchet impacts flash fire.
  drawImpactFlash(x, y, t, bombard = false) {
    const ctx = this.ctx;
    const radius = (6 + 16 * t) * Math.max(0.6, this.zoom);
    ctx.save();
    const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
    if (bombard) {
      g.addColorStop(0, `rgba(180, 180, 180, ${0.75 * (1 - t)})`);
      g.addColorStop(0.6, `rgba(90, 90, 90, ${0.45 * (1 - t)})`);
      g.addColorStop(1, "rgba(60, 60, 60, 0)");
    } else {
      g.addColorStop(0, `rgba(255, 240, 180, ${0.95 * (1 - t)})`);
      g.addColorStop(0.5, `rgba(255, 130, 20, ${0.7 * (1 - t)})`);
      g.addColorStop(1, "rgba(180, 40, 0, 0)");
    }
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // Draw an attack arrow from attacker to target
  drawAttackArrow(fromX, fromY, toX, toY, player, opacity = 1) {
    if (fromX === null || fromY === null || toX === null || toY === null)
      return;

    const from = this.gameToCanvas(fromX, fromY);
    const to = this.gameToCanvas(toX, toY);
    const color = this.playerColors[player] || "#ffffff";

    this.ctx.save();
    this.ctx.globalAlpha = opacity * 0.8;

    // Draw the arrow line
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 2 * this.zoom;
    this.ctx.lineCap = "round";

    this.ctx.beginPath();
    this.ctx.moveTo(from.x, from.y);
    this.ctx.lineTo(to.x, to.y);
    this.ctx.stroke();

    // Draw arrowhead
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const arrowSize = 10 * this.zoom;

    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.moveTo(to.x, to.y);
    this.ctx.lineTo(
      to.x - arrowSize * Math.cos(angle - Math.PI / 6),
      to.y - arrowSize * Math.sin(angle - Math.PI / 6),
    );
    this.ctx.lineTo(
      to.x - arrowSize * Math.cos(angle + Math.PI / 6),
      to.y - arrowSize * Math.sin(angle + Math.PI / 6),
    );
    this.ctx.closePath();
    this.ctx.fill();

    this.ctx.restore();
  }

  // Draw a wall segment
  drawWall(wall) {
    const start = this.gameToCanvas(wall.x_start, wall.y_start);
    const end = this.gameToCanvas(wall.x_end, wall.y_end);
    const color = this.playerColors[wall.player] || "#888888";

    // Determine wall style based on type (half the previous thickness). Each
    // wall also gets a small height so it reads as a raised 3D ribbon.
    let wallWidth = 2 * this.zoom;
    let wallColor = color;
    let height = 5 * this.zoom;

    if (wall.type.includes("stone") || wall.type.includes("fortified")) {
      wallWidth = 3 * this.zoom;
      wallColor = this.darkenColor(color, 0.2);
      height = 8 * this.zoom;
    } else if (wall.type.includes("palisade")) {
      wallWidth = 1.5 * this.zoom;
      height = 4 * this.zoom;
    }

    // Raised twins of the segment endpoints (lifted straight up the screen).
    const sTop = { x: start.x, y: start.y - height };
    const eTop = { x: end.x, y: end.y - height };

    // Walls render at half opacity so they read as lighter, thinner ribbons.
    this.ctx.save();
    this.ctx.globalAlpha = 0.5;
    this.ctx.lineCap = "round";
    this.ctx.lineJoin = "round";

    // Vertical face of the wall (the "height"), a darker shade of the colour.
    this.ctx.fillStyle = this.darkenColor(wallColor, 0.45);
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.6)";
    this.ctx.lineWidth = 1 * this.zoom;
    this.ctx.beginPath();
    this.ctx.moveTo(start.x, start.y);
    this.ctx.lineTo(end.x, end.y);
    this.ctx.lineTo(eTop.x, eTop.y);
    this.ctx.lineTo(sTop.x, sTop.y);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();

    // Top cap of the wall, in the player colour.
    this.ctx.strokeStyle = wallColor;
    this.ctx.lineWidth = wallWidth;
    this.ctx.beginPath();
    this.ctx.moveTo(sTop.x, sTop.y);
    this.ctx.lineTo(eTop.x, eTop.y);
    this.ctx.stroke();

    // Raised end posts.
    const postSize = wallWidth * 1.5;
    this.ctx.fillStyle = this.darkenColor(wallColor, 0.3);
    this.ctx.beginPath();
    this.ctx.arc(sTop.x, sTop.y, postSize / 2, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.beginPath();
    this.ctx.arc(eTop.x, eTop.y, postSize / 2, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.restore();
  }
}

// Export for use in other modules
window.Renderer = Renderer;
