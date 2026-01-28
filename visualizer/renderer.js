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

  // Draw a unit based on its type
  drawUnit(x, y, player, type, opacity = 1) {
    if (x === null || y === null) return;

    const pos = this.gameToCanvas(x, y);
    const color = this.playerColors[player] || "#ffffff";
    const size = (this.sizes[type] || this.sizes.military) * this.zoom;

    this.ctx.globalAlpha = opacity;
    this.ctx.fillStyle = color;
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    this.ctx.lineWidth = 1;

    switch (type) {
      case "villager":
        // Small circle for villagers
        this.ctx.beginPath();
        this.ctx.arc(pos.x, pos.y, size / 2, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.stroke();
        break;

      case "infantry":
        // Shield shape (rounded rectangle) for infantry
        this.drawShield(pos.x, pos.y, size);
        break;

      case "archer":
        // Diamond/arrow shape for archers
        this.drawArcher(pos.x, pos.y, size, color);
        break;

      case "cavalry":
        // Horizontal oval/horse shape for cavalry
        this.drawCavalry(pos.x, pos.y, size, color);
        break;

      case "siege":
        // Square for siege units
        this.ctx.fillRect(pos.x - size / 2, pos.y - size / 2, size, size);
        this.ctx.strokeRect(pos.x - size / 2, pos.y - size / 2, size, size);
        break;

      case "monk":
        // Cross shape for monks
        this.drawMonk(pos.x, pos.y, size, color);
        break;

      case "ship":
        // Boat shape for ships
        this.drawShip(pos.x, pos.y, size, color);
        break;

      case "king":
        // Star/crown for king
        this.drawKing(pos.x, pos.y, size, color);
        break;

      default:
        // Triangle for unknown military
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

  // Draw a building based on its type
  drawBuilding(x, y, player, buildingType, opacity = 1) {
    if (x === null || y === null) return;

    const pos = this.gameToCanvas(x, y);
    const color = this.playerColors[player] || "#ffffff";
    const typeClean = buildingType.toLowerCase().replace(/\s/g, "");

    this.ctx.globalAlpha = opacity;
    this.ctx.fillStyle = color;
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    this.ctx.lineWidth = 1;

    // Draw different building types
    if (typeClean.includes("towncenter")) {
      this.drawTownCenter(pos.x, pos.y, color);
    } else if (typeClean.includes("castle")) {
      this.drawCastle(pos.x, pos.y, color);
    } else if (this.largeBuildings.has(typeClean)) {
      this.drawLargeBuilding(
        pos.x,
        pos.y,
        this.sizes.building_large * this.zoom,
      );
    } else {
      this.drawSmallBuilding(
        pos.x,
        pos.y,
        this.sizes.building_small * this.zoom,
      );
    }

    this.ctx.globalAlpha = 1;
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

  // Town Center - large building with flag
  drawTownCenter(x, y, color) {
    const size = this.sizes.towncenter * this.zoom;
    const halfW = size / 2;
    const halfH = size / 4;

    // Main building (isometric box shape)
    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH);
    this.ctx.lineTo(x + halfW, y);
    this.ctx.lineTo(x, y + halfH);
    this.ctx.lineTo(x - halfW, y);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();

    // Roof (darker shade)
    const roofHeight = size / 3;
    this.ctx.fillStyle = this.darkenColor(color, 0.3);
    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH - roofHeight);
    this.ctx.lineTo(x + halfW * 0.8, y - halfH * 0.3);
    this.ctx.lineTo(x, y - halfH + roofHeight * 0.5);
    this.ctx.lineTo(x - halfW * 0.8, y - halfH * 0.3);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();

    // Flag pole
    this.ctx.strokeStyle = "#8B4513";
    this.ctx.lineWidth = 2 * this.zoom;
    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH - roofHeight);
    this.ctx.lineTo(x, y - halfH - roofHeight - size / 3);
    this.ctx.stroke();

    // Flag
    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH - roofHeight - size / 3);
    this.ctx.lineTo(x + size / 4, y - halfH - roofHeight - size / 4);
    this.ctx.lineTo(x, y - halfH - roofHeight - size / 6);
    this.ctx.closePath();
    this.ctx.fill();

    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    this.ctx.lineWidth = 1;
  }

  // Castle - fortress with towers
  drawCastle(x, y, color) {
    const size = this.sizes.castle * this.zoom;
    const halfW = size / 2;
    const halfH = size / 4;

    // Main keep (center)
    this.ctx.beginPath();
    this.ctx.moveTo(x, y - halfH);
    this.ctx.lineTo(x + halfW, y);
    this.ctx.lineTo(x, y + halfH);
    this.ctx.lineTo(x - halfW, y);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();

    // Tower positions (4 corners)
    const towerSize = size / 4;
    const towerHeight = size / 3;
    const towers = [
      { dx: -halfW * 0.7, dy: 0 }, // Left
      { dx: halfW * 0.7, dy: 0 }, // Right
      { dx: 0, dy: -halfH * 0.8 }, // Top
      { dx: 0, dy: halfH * 0.8 }, // Bottom
    ];

    // Draw towers
    this.ctx.fillStyle = this.darkenColor(color, 0.2);
    for (const tower of towers) {
      const tx = x + tower.dx;
      const ty = y + tower.dy;

      // Tower base
      this.ctx.beginPath();
      this.ctx.arc(tx, ty, towerSize / 2, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();

      // Tower top (crenellations implied by darker top)
      this.ctx.fillStyle = this.darkenColor(color, 0.4);
      this.ctx.beginPath();
      this.ctx.arc(tx, ty - towerHeight / 3, towerSize / 3, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.fillStyle = this.darkenColor(color, 0.2);
    }

    // Center tower (taller)
    this.ctx.fillStyle = this.darkenColor(color, 0.3);
    this.ctx.beginPath();
    this.ctx.arc(x, y - towerHeight / 2, towerSize / 2, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.stroke();

    this.ctx.fillStyle = color;
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
