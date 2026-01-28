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
    this.maxZoom = 4;
    this.panX = 0;
    this.panY = 0;

    // Dragging state
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;

    // Player colors
    this.playerColors = {};

    // Entity sizes
    this.sizes = {
      villager: 6,
      military: 8,
      scout: 8,
      building_small: 12,
      building_large: 20,
      towncenter: 24,
    };

    // Building types that are large
    this.largeBuildings = new Set([
      "towncenter",
      "castle",
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
    ]);

    this.setupCanvas();
    this.setupEventListeners();
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
    players.forEach((p) => {
      this.playerColors[p.name] = p.color_hex;
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

    // Draw filled diamond
    ctx.fillStyle = "#2d5a2d";
    ctx.beginPath();
    ctx.moveTo(top.x, top.y);
    ctx.lineTo(right.x, right.y);
    ctx.lineTo(bottom.x, bottom.y);
    ctx.lineTo(left.x, left.y);
    ctx.closePath();
    ctx.fill();

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

  // Draw a unit (villager or military)
  drawUnit(x, y, player, type, opacity = 1) {
    if (x === null || y === null) return;

    const pos = this.gameToCanvas(x, y);
    const color = this.playerColors[player] || "#ffffff";
    const size =
      (type === "villager" ? this.sizes.villager : this.sizes.military) *
      this.zoom;

    this.ctx.globalAlpha = opacity;
    this.ctx.fillStyle = color;
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.5)";
    this.ctx.lineWidth = 1;

    if (type === "villager") {
      // Circle for villagers
      this.ctx.beginPath();
      this.ctx.arc(pos.x, pos.y, size / 2, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();
    } else {
      // Triangle for military (pointing up)
      this.ctx.beginPath();
      this.ctx.moveTo(pos.x, pos.y - size / 2);
      this.ctx.lineTo(pos.x - size / 2, pos.y + size / 2);
      this.ctx.lineTo(pos.x + size / 2, pos.y + size / 2);
      this.ctx.closePath();
      this.ctx.fill();
      this.ctx.stroke();
    }

    this.ctx.globalAlpha = 1;
  }

  // Draw a building as an isometric diamond shape
  drawBuilding(x, y, player, buildingType, opacity = 1) {
    if (x === null || y === null) return;

    const pos = this.gameToCanvas(x, y);
    const color = this.playerColors[player] || "#ffffff";

    // Determine building size
    let size;
    const typeClean = buildingType.toLowerCase().replace(/\s/g, "");
    if (typeClean.includes("towncenter") || typeClean.includes("castle")) {
      size = this.sizes.towncenter;
    } else if (this.largeBuildings.has(typeClean)) {
      size = this.sizes.building_large;
    } else {
      size = this.sizes.building_small;
    }
    size *= this.zoom;

    this.ctx.globalAlpha = opacity;
    this.ctx.fillStyle = color;
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.5)";
    this.ctx.lineWidth = 1;

    // Draw as isometric diamond
    const halfW = size / 2;
    const halfH = size / 4; // Isometric height is half of width

    this.ctx.beginPath();
    this.ctx.moveTo(pos.x, pos.y - halfH); // Top
    this.ctx.lineTo(pos.x + halfW, pos.y); // Right
    this.ctx.lineTo(pos.x, pos.y + halfH); // Bottom
    this.ctx.lineTo(pos.x - halfW, pos.y); // Left
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();

    this.ctx.globalAlpha = 1;
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

  // Full render cycle
  render(state) {
    this.clear();
    this.drawMap();

    // Draw buildings
    for (const [name, building] of state.buildings) {
      const opacity = 1;
      this.drawBuilding(
        building.x,
        building.y,
        building.player,
        building.type,
        opacity,
      );
    }

    // Draw units
    for (const [name, unit] of state.units) {
      if (!unit.alive) continue;

      const opacity = unit.dying ? 0.5 : 1;
      this.drawUnit(unit.x, unit.y, unit.player, unit.type, opacity);
    }
  }
}

// Export for use in other modules
window.Renderer = Renderer;
