// Calibration-only renderer: unit geometry is the simulation's collision body.
// This module is deliberately served only by HC Field Lab; the production site
// continues to use SimRenderer's readable sprite/portrait presentation.
import { SimRenderer } from "./sim_renderer.js";
import { TILE_SIZE } from "./engine/constants.js";

const TEAM_FILL = { 1: "#3498db", 2: "#e74c3c" };
const TEAM_HP = { 1: "#62b8ff", 2: "#ff6961" };

function drawPhysicsUnit(ctx, unit) {
  const radius = unit.radius;
  if (!Number.isFinite(radius) || radius <= 0) return;

  ctx.save();
  ctx.globalAlpha = unit.state === "dead" ? 0.28 : 0.92;
  ctx.beginPath();
  ctx.arc(unit.x, unit.y, radius, 0, Math.PI * 2);
  ctx.fillStyle = TEAM_FILL[unit.team] || "#999";
  ctx.fill();

  // Stroke inward: its outer edge is exactly the collision-circle boundary.
  const lineWidth = Math.min(1.5, radius);
  ctx.beginPath();
  ctx.arc(unit.x, unit.y, Math.max(0, radius - lineWidth / 2), 0, Math.PI * 2);
  ctx.strokeStyle = unit.attackAnimTimer > 0 ? "#fff" : "rgba(8, 12, 16, 0.88)";
  ctx.lineWidth = lineWidth;
  ctx.stroke();

  // Kiting is an interior marker, never a larger ring.
  if (unit.state === "kiting") {
    ctx.beginPath();
    ctx.arc(unit.x, unit.y, Math.max(1, radius * 0.32), 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.82)";
    ctx.fill();
  }

  if (unit.state !== "dead") {
    const hpFraction = Math.max(0, Math.min(1, unit.currentHp / unit.maxHp));
    const barWidth = Math.max(12, radius * 2);
    const barHeight = 3;
    const barX = unit.x - barWidth / 2;
    const barY = unit.y - radius - 6;
    ctx.globalAlpha = 1;
    ctx.fillStyle = "rgba(0,0,0,0.62)";
    ctx.fillRect(barX, barY, barWidth, barHeight);
    ctx.fillStyle = TEAM_HP[unit.team] || "#ddd";
    ctx.fillRect(barX, barY, barWidth * hpFraction, barHeight);
  }
  ctx.restore();
}

function drawTileRuler(ctx, height) {
  const x = 20;
  const y = height - 22;
  ctx.save();
  ctx.globalAlpha = 0.92;
  ctx.strokeStyle = "#f5ead7";
  ctx.fillStyle = "#f5ead7";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + TILE_SIZE, y);
  ctx.moveTo(x, y - 4);
  ctx.lineTo(x, y + 4);
  ctx.moveTo(x + TILE_SIZE, y - 4);
  ctx.lineTo(x + TILE_SIZE, y + 4);
  ctx.stroke();
  ctx.font = "11px 'Source Sans 3', Arial, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`1 tile (${TILE_SIZE}px)`, x + TILE_SIZE + 7, y + 4);
  ctx.restore();
}

function drawWinner(ctx, sim, labels, width, height) {
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,0.7)";
  ctx.fillRect(0, 0, width, height);
  let title = "Draw!";
  let color = "#cdac50";
  if (sim.winner === 1) {
    title = `${labels.team1Civ || "Team 1"} ${labels.team1Unit || ""}`.trim();
    color = TEAM_FILL[1];
  } else if (sim.winner === 2) {
    title = `${labels.team2Civ || "Team 2"} ${labels.team2Unit || ""}`.trim();
    color = TEAM_FILL[2];
  }
  ctx.fillStyle = color;
  ctx.font = "bold 34px Cinzel, serif";
  ctx.textAlign = "center";
  ctx.fillText(title, width / 2, height / 2 - 10);
  if (sim.winner === 1 || sim.winner === 2) {
    ctx.fillStyle = "#cdac50";
    ctx.font = "bold 22px Cinzel, serif";
    ctx.fillText("Victory!", width / 2, height / 2 + 22);
  }
  ctx.fillStyle = "#ece1cd";
  ctx.font = "16px 'Source Sans 3', sans-serif";
  ctx.fillText(`Battle time: ${sim.battleTime.toFixed(1)}s`, width / 2, height / 2 + 50);
  ctx.restore();
}

export class PhysicsSimRenderer extends SimRenderer {
  renderEmpty() {
    super.renderEmpty();
    drawTileRuler(this.ctx, this.H);
  }

  render(sim) {
    const team1 = sim.team1;
    const team2 = sim.team2;
    const winner = sim.winner;

    // Let the shared renderer paint its canonical field/projectile/effect layers,
    // but give it no units. Suppress its winner overlay until physics discs are
    // down so the overlay remains the final canvas layer.
    try {
      sim.team1 = [];
      sim.team2 = [];
      sim.winner = null;
      super.render(sim);
    } finally {
      sim.team1 = team1;
      sim.team2 = team2;
      sim.winner = winner;
      this._sim = sim;
    }

    const ctx = this.ctx;
    ctx.save();
    ctx.setTransform(this.renderScaleX, 0, 0, this.renderScaleY, 0, 0);
    const allUnits = [...team1, ...team2];
    for (const unit of allUnits.filter((item) => item.state === "dead")) drawPhysicsUnit(ctx, unit);
    for (const unit of allUnits.filter((item) => item.state !== "dead")) drawPhysicsUnit(ctx, unit);
    drawTileRuler(ctx, this.H);
    if (winner !== null) drawWinner(ctx, sim, this.labels, this.W, this.H);
    ctx.restore();
  }
}
