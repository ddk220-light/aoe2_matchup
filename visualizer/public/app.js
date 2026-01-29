/**
 * Main application - wires together renderer and playback
 */

class App {
  constructor() {
    this.renderer = null;
    this.playback = null;
    this.data = null;

    // UI elements
    this.canvas = document.getElementById("map-canvas");
    this.btnPlay = document.getElementById("btn-play");
    this.btnStart = document.getElementById("btn-start");
    this.btnEnd = document.getElementById("btn-end");
    this.btnStepForward = document.getElementById("btn-step-forward");
    this.btnStepBack = document.getElementById("btn-step-back");
    this.timeline = document.getElementById("timeline");
    this.currentTimeDisplay = document.getElementById("current-time");
    this.totalTimeDisplay = document.getElementById("total-time");
    this.zoomInBtn = document.getElementById("zoom-in");
    this.zoomOutBtn = document.getElementById("zoom-out");
    this.zoomLevel = document.getElementById("zoom-level");
    this.matchInfo = document.getElementById("match-info");
    this.playerLegend = document.getElementById("player-legend");
    this.playerTracker = document.getElementById("player-tracker");
    this.fileInput = document.getElementById("file-input");

    // Match browsing UI elements
    this.browseMatchesBtn = document.getElementById("browse-matches-btn");
    this.matchListOverlay = document.getElementById("match-list-overlay");
    this.matchListLoading = document.getElementById("match-list-loading");
    this.matchList = document.getElementById("match-list");
    this.closeMatchListBtn = document.getElementById("close-match-list");
    this.matchDetailOverlay = document.getElementById("match-detail-overlay");
    this.matchDetailContent = document.getElementById("match-detail-content");
    this.backToListBtn = document.getElementById("back-to-list");
    this.closeMatchDetailBtn = document.getElementById("close-match-detail");
    this.loadMatchBtn = document.getElementById("load-match-btn");
    this.loadingOverlay = document.getElementById("loading-overlay");
    this.loadingMessage = document.getElementById("loading-message");

    this.speedButtons = document.querySelectorAll(".speed-btn");

    // Render loop
    this.renderLoopId = null;

    // Player visibility
    this.playerVisibility = {};

    // Production tracking
    this.productionData = {}; // player -> { villagers: [], military: [] } - arrays of creation times
    this.lastTrackerUpdate = 0;

    // Track if controls have been set up
    this.controlsInitialized = false;

    // Match browsing state
    this.currentPlayer = { name: "ddk220", profileId: null };
    this.matches = [];
    this.selectedMatch = null;
  }

  async init() {
    // Setup event listeners for match browsing
    this.setupMatchBrowsing();
    this.setupFileUpload();

    try {
      // Try to load default replay data
      const response = await fetch("replay_data.json");
      if (response.ok) {
        this.data = await response.json();
        this.initializeWithData();
      } else {
        // No default data, show match list panel
        this.showMatchListPanel();
      }
    } catch (error) {
      console.error("Failed to initialize:", error);
      this.showMatchListPanel();
    }
  }

  showUploadPrompt() {
    document.querySelector(".loading")?.remove();
    this.matchInfo.textContent = "Click 'Browse Matches' to begin";
  }

  // ==================== Match Browsing ====================

  setupMatchBrowsing() {
    // Browse matches button
    this.browseMatchesBtn.addEventListener("click", () => {
      this.showMatchListPanel();
    });

    // Close buttons
    this.closeMatchListBtn.addEventListener("click", () => {
      this.hideMatchListPanel();
    });

    this.closeMatchDetailBtn.addEventListener("click", () => {
      this.hideMatchDetailPanel();
    });

    // Back to list
    this.backToListBtn.addEventListener("click", () => {
      this.hideMatchDetailPanel();
      this.showMatchListPanel();
    });

    // Load match button
    this.loadMatchBtn.addEventListener("click", () => {
      if (this.selectedMatch) {
        this.loadMatch(this.selectedMatch);
      }
    });

    // Click outside to close
    this.matchListOverlay.addEventListener("click", (e) => {
      if (e.target === this.matchListOverlay) {
        this.hideMatchListPanel();
      }
    });

    this.matchDetailOverlay.addEventListener("click", (e) => {
      if (e.target === this.matchDetailOverlay) {
        this.hideMatchDetailPanel();
      }
    });
  }

  async showMatchListPanel() {
    document.querySelector(".loading")?.remove();
    this.matchListOverlay.classList.remove("hidden");
    this.matchListLoading.classList.remove("hidden");
    this.matchList.innerHTML = "";

    try {
      await this.fetchMatches();
      this.renderMatchList();
    } catch (error) {
      console.error("Failed to fetch matches:", error);
      this.matchList.innerHTML = `<div class="error-message">Failed to load matches: ${error.message}</div>`;
    }

    this.matchListLoading.classList.add("hidden");
  }

  hideMatchListPanel() {
    this.matchListOverlay.classList.add("hidden");
  }

  showMatchDetailPanel(match) {
    this.selectedMatch = match;
    this.hideMatchListPanel();
    this.matchDetailOverlay.classList.remove("hidden");
    this.renderMatchDetail(match);
  }

  hideMatchDetailPanel() {
    this.matchDetailOverlay.classList.add("hidden");
    this.selectedMatch = null;
  }

  showLoadingOverlay(message) {
    this.loadingMessage.textContent = message;
    this.loadingOverlay.classList.remove("hidden");
  }

  hideLoadingOverlay() {
    this.loadingOverlay.classList.add("hidden");
  }

  async fetchMatches() {
    const response = await fetch("/api/matches");
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to fetch matches");
    }

    const data = await response.json();
    this.players = data.players;
    this.matches = data.matches;
  }

  renderMatchList() {
    this.matchList.innerHTML = "";

    if (this.matches.length === 0) {
      this.matchList.innerHTML =
        '<div class="no-matches">No matches found</div>';
      return;
    }

    for (const match of this.matches) {
      const item = document.createElement("div");
      item.className = "match-item";
      item.addEventListener("click", () => this.showMatchDetailPanel(match));

      // Format date
      const date = new Date(match.started);
      const dateStr =
        date.toLocaleDateString() +
        " " +
        date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      // Calculate duration
      const duration = this.formatMatchDuration(match.started, match.finished);

      // Find if any of our tracked players are in this match and their result
      let targetWon = null;
      const playerIds = new Set((this.players || []).map((p) => p.profileId));
      for (const team of match.teams || []) {
        for (const player of team.players || []) {
          if (playerIds.has(player.profileId)) {
            targetWon = player.won;
            break;
          }
        }
        if (targetWon !== null) break;
      }

      // Get team summaries - show all players
      const teamSummaries = (match.teams || []).map((team) => {
        const names = team.players.map((p) => p.name);
        const won = team.players[0]?.won;
        return { names: names.join(", "), won };
      });

      item.innerHTML = `
        <div class="match-item-header">
          <span class="match-map">${match.mapName || "Unknown Map"}</span>
          <span class="match-date">${dateStr}</span>
        </div>
        <div class="match-item-body">
          <div class="match-teams">
            ${teamSummaries
              .map(
                (t, i) => `
              <span class="match-team ${t.won ? "winner" : "loser"}">${t.names}</span>
              ${i < teamSummaries.length - 1 ? '<span class="match-vs">vs</span>' : ""}
            `,
              )
              .join("")}
          </div>
          <div class="match-meta">
            <span class="match-duration">${duration}</span>
            ${targetWon !== null ? `<span class="match-result-indicator ${targetWon ? "win" : "loss"}">${targetWon ? "WIN" : "LOSS"}</span>` : ""}
          </div>
        </div>
      `;

      this.matchList.appendChild(item);
    }
  }

  renderMatchDetail(match) {
    // Format date
    const date = new Date(match.started);
    const dateStr =
      date.toLocaleDateString() +
      " " +
      date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Calculate duration
    const duration = this.formatMatchDuration(match.started, match.finished);

    // Build teams HTML
    const playerIds = new Set((this.players || []).map((p) => p.profileId));
    const teamsHtml = (match.teams || [])
      .map((team) => {
        const isWinner = team.players[0]?.won;
        const playersHtml = team.players
          .map((player) => {
            const isTracked = playerIds.has(player.profileId);
            return `
            <div class="player-row">
              <img class="player-civ-icon" src="${player.civImageUrl || ""}" alt="${player.civName}" onerror="this.style.display='none'">
              <div class="player-info">
                <div class="player-name ${isTracked ? "target" : ""}">${player.name}</div>
                <div class="player-civ">${player.civName || "Unknown"}</div>
              </div>
              <div class="player-rating">${player.rating || "?"}</div>
            </div>
          `;
          })
          .join("");

        return `
        <div class="team-section">
          <div class="team-header ${isWinner ? "winner" : ""}">
            Team ${team.teamId} ${isWinner ? "- VICTORY" : "- DEFEAT"}
          </div>
          ${playersHtml}
        </div>
      `;
      })
      .join("");

    this.matchDetailContent.innerHTML = `
      <div class="match-detail-header">
        <h3>${match.mapName || "Unknown Map"}</h3>
        <div class="match-meta">${dateStr} | ${duration} | ${match.leaderboardName || "Unknown Mode"}</div>
      </div>
      <div class="match-teams-detail">
        ${teamsHtml}
      </div>
    `;
  }

  formatMatchDuration(started, finished) {
    if (!started || !finished) return "Unknown";
    const start = new Date(started);
    const end = new Date(finished);
    const diffMs = end - start;
    const diffMins = Math.floor(diffMs / 60000);
    const diffSecs = Math.floor((diffMs % 60000) / 1000);
    return `${diffMins}:${diffSecs.toString().padStart(2, "0")}`;
  }

  async loadMatch(match) {
    this.hideMatchDetailPanel();
    this.showLoadingOverlay("Downloading replay...");

    // Find a tracked player in this match to use for download perspective
    const playerIds = new Set((this.players || []).map((p) => p.profileId));
    let profileIdForDownload = 612690; // Default to ddk220
    for (const team of match.teams || []) {
      for (const player of team.players || []) {
        if (playerIds.has(player.profileId)) {
          profileIdForDownload = player.profileId;
          break;
        }
      }
    }

    try {
      const response = await fetch("/api/load-match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          matchId: match.matchId,
          profileId: profileIdForDownload,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to load match");
      }

      this.showLoadingOverlay("Processing replay...");
      this.data = await response.json();

      // Stop existing render loop if any
      if (this.renderLoopId) {
        cancelAnimationFrame(this.renderLoopId);
      }

      // Reinitialize with new data
      this.initializeWithData();
      this.hideLoadingOverlay();
    } catch (error) {
      console.error("Failed to load match:", error);
      this.hideLoadingOverlay();
      alert(`Failed to load match: ${error.message}`);
    }
  }

  initializeWithData() {
    // Initialize renderer
    this.renderer = new Renderer(this.canvas, this.data.match.map_size);
    this.renderer.setPlayerColors(this.data.players);

    // Initialize playback
    this.playback = new Playback(this.data);
    this.playback.onTimeUpdate = (time) => this.onTimeUpdate(time);

    // Preprocess production data from DE_QUEUE actions
    this.preprocessProductionData();

    // Setup UI
    this.setupUI();
    this.setupKeyboardShortcuts();

    // Initial render
    this.startRenderLoop();

    // Remove loading state
    document.querySelector(".loading")?.remove();
  }

  preprocessProductionData() {
    // Reset production data
    this.productionData = {};
    for (const player of this.data.players) {
      this.productionData[player.name] = {
        villagers: [],
        military: [],
      };
    }

    // Villager unit types
    const villagerTypes = new Set([
      "villager",
      "villagermale",
      "villagerfemale",
    ]);

    // Process all DE_QUEUE actions
    for (const action of this.data.actions) {
      if (action.type === "DE_QUEUE" && action.target && action.player) {
        const unitType = action.target.toLowerCase();
        const playerData = this.productionData[action.player];

        if (playerData) {
          if (villagerTypes.has(unitType)) {
            playerData.villagers.push(action.time);
          } else {
            // All non-villager units are military
            playerData.military.push(action.time);
          }
        }
      }
    }

    // Sort by time
    for (const player of Object.keys(this.productionData)) {
      this.productionData[player].villagers.sort((a, b) => a - b);
      this.productionData[player].military.sort((a, b) => a - b);
    }
  }

  setupFileUpload() {
    this.fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (file.name.endsWith(".json")) {
        // Load pre-processed JSON file directly
        await this.loadJsonFile(file);
      } else if (file.name.endsWith(".aoe2record")) {
        // Try to upload to server API
        await this.uploadReplay(file);
      } else {
        alert("Please select a .aoe2record or .json file");
      }
    });
  }

  async loadJsonFile(file) {
    this.matchInfo.textContent = `Loading ${file.name}...`;

    try {
      const text = await file.text();
      this.data = JSON.parse(text);

      // Stop existing render loop if any
      if (this.renderLoopId) {
        cancelAnimationFrame(this.renderLoopId);
      }

      // Reinitialize with new data
      this.initializeWithData();
    } catch (error) {
      console.error("Failed to load JSON:", error);
      alert(`Failed to load JSON: ${error.message}`);
      this.matchInfo.textContent = "Load failed - try again";
    }

    this.fileInput.value = "";
  }

  async uploadReplay(file) {
    // Show loading state
    this.matchInfo.textContent = `Processing ${file.name}...`;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Upload failed");
      }

      this.data = await response.json();

      // Stop existing render loop if any
      if (this.renderLoopId) {
        cancelAnimationFrame(this.renderLoopId);
      }

      // Reinitialize with new data
      this.initializeWithData();
    } catch (error) {
      console.error("Upload failed:", error);
      alert(
        `Failed to process replay. If using cloud version, try uploading a pre-processed .json file instead.\n\nError: ${error.message}`,
      );
      this.matchInfo.textContent = "Upload failed - try JSON file";
    }

    // Reset file input
    this.fileInput.value = "";
  }

  setupUI() {
    // Match info
    this.matchInfo.textContent = `${this.data.match.map_name} | ${this.data.match.duration_formatted} | ${this.data.players.length} players`;

    // Total time
    this.totalTimeDisplay.textContent = this.playback.formatTime(
      this.data.match.duration_seconds,
    );

    // Timeline
    this.timeline.max = this.data.match.duration_seconds;
    this.timeline.value = 0;

    // Player legend
    this.setupPlayerLegend();

    // Reset play button state
    this.btnPlay.textContent = "Play";
    this.btnPlay.classList.remove("playing");

    // Only add event listeners once
    if (!this.controlsInitialized) {
      this.controlsInitialized = true;

      // Playback controls
      this.btnPlay.addEventListener("click", () => this.togglePlay());
      this.btnStart.addEventListener("click", () => this.playback.goToStart());
      this.btnEnd.addEventListener("click", () => this.playback.goToEnd());
      this.btnStepForward.addEventListener("click", () =>
        this.playback.stepForward(),
      );
      this.btnStepBack.addEventListener("click", () =>
        this.playback.stepBackward(),
      );

      // Timeline scrubbing
      this.timeline.addEventListener("input", (e) => {
        this.playback.seekTo(parseFloat(e.target.value));
      });

      // Speed buttons
      this.speedButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          const speed = parseInt(btn.dataset.speed);
          this.setSpeed(speed);
        });
      });

      // Zoom controls
      this.zoomInBtn.addEventListener("click", () => {
        const newZoom = this.renderer.setZoom(this.renderer.zoom * 1.5);
        this.updateZoomDisplay(newZoom);
      });

      this.zoomOutBtn.addEventListener("click", () => {
        const newZoom = this.renderer.setZoom(this.renderer.zoom / 1.5);
        this.updateZoomDisplay(newZoom);
      });
    }

    // Set initial speed
    this.setSpeed(1);
  }

  setupPlayerLegend() {
    this.playerLegend.innerHTML = "<h3>Players</h3>";

    for (const player of this.data.players) {
      this.playerVisibility[player.name] = true;

      const civ = player.civilization ? ` (${player.civilization})` : "";
      const item = document.createElement("div");
      item.className = "player-item";
      item.innerHTML = `
                <input type="checkbox" id="player-${player.color_id}" checked>
                <div class="player-color" style="background-color: ${player.color_hex}"></div>
                <label for="player-${player.color_id}">${player.name}${civ}</label>
            `;

      const checkbox = item.querySelector("input");
      checkbox.addEventListener("change", (e) => {
        this.playerVisibility[player.name] = e.target.checked;
      });

      this.playerLegend.appendChild(item);
    }
  }

  setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      // Ignore if typing in an input
      if (e.target.tagName === "INPUT") return;

      switch (e.code) {
        case "Space":
          e.preventDefault();
          this.togglePlay();
          break;
        case "ArrowRight":
          e.preventDefault();
          this.playback.stepForward();
          break;
        case "ArrowLeft":
          e.preventDefault();
          this.playback.stepBackward();
          break;
        case "Home":
          e.preventDefault();
          this.playback.goToStart();
          break;
        case "End":
          e.preventDefault();
          this.playback.goToEnd();
          break;
        case "Digit1":
          this.setSpeed(1);
          break;
        case "Digit2":
          this.setSpeed(2);
          break;
        case "Digit4":
          this.setSpeed(4);
          break;
        case "Digit8":
          this.setSpeed(8);
          break;
      }
    });
  }

  togglePlay() {
    const isPlaying = this.playback.togglePlayPause();
    this.btnPlay.textContent = isPlaying ? "Pause" : "Play";
    this.btnPlay.classList.toggle("playing", isPlaying);
  }

  setSpeed(speed) {
    this.playback.setSpeed(speed);
    this.speedButtons.forEach((btn) => {
      btn.classList.toggle("active", parseInt(btn.dataset.speed) === speed);
    });
  }

  updateZoomDisplay(zoom) {
    this.zoomLevel.textContent = `${zoom.toFixed(1)}x`;
  }

  onTimeUpdate(time) {
    this.currentTimeDisplay.textContent = this.playback.formatTime(time);
    this.timeline.value = time;

    // Update player tracker every second (avoid excessive updates)
    if (Math.abs(time - this.lastTrackerUpdate) >= 1) {
      this.lastTrackerUpdate = time;
      this.updatePlayerTracker(time);
    }
  }

  calculateProductionRates(currentTime) {
    // Calculate rates for the last minute (or from start if less than 1 min)
    const windowStart = Math.max(0, currentTime - 60);
    const windowDuration = currentTime - windowStart;

    if (windowDuration < 1) {
      // Not enough time elapsed
      return this.data.players.map((p) => ({
        name: p.name,
        color: p.color_hex,
        villagerRate: 0,
        militaryRate: 0,
      }));
    }

    const rates = [];
    for (const player of this.data.players) {
      const data = this.productionData[player.name];
      if (!data) {
        rates.push({
          name: player.name,
          color: player.color_hex,
          villagerRate: 0,
          militaryRate: 0,
        });
        continue;
      }

      // Count units created in the window
      const villagerCount = data.villagers.filter(
        (t) => t >= windowStart && t <= currentTime,
      ).length;
      const militaryCount = data.military.filter(
        (t) => t >= windowStart && t <= currentTime,
      ).length;

      // Calculate rate per minute
      const minutesFraction = windowDuration / 60;
      rates.push({
        name: player.name,
        color: player.color_hex,
        villagerRate: villagerCount / minutesFraction,
        militaryRate: militaryCount / minutesFraction,
      });
    }

    return rates;
  }

  updatePlayerTracker(currentTime) {
    const rates = this.calculateProductionRates(currentTime);

    // Sort to find rankings for color coding
    const villagerRanked = [...rates].sort(
      (a, b) => b.villagerRate - a.villagerRate,
    );
    const militaryRanked = [...rates].sort(
      (a, b) => b.militaryRate - a.militaryRate,
    );

    // Build rank maps
    const villagerRank = {};
    const militaryRank = {};
    villagerRanked.forEach((r, i) => (villagerRank[r.name] = i));
    militaryRanked.forEach((r, i) => (militaryRank[r.name] = i));

    const numPlayers = rates.length;

    // Helper to get CSS class for rate
    const getRateClass = (rank, total) => {
      if (rank === 0) return "rate-top-1";
      if (rank < 3) return "rate-top";
      if (rank === total - 1) return "rate-bottom-1";
      if (rank >= total - 3) return "rate-bottom";
      return "";
    };

    // Build tracker HTML
    let html = `
      <div class="tracker-header">
        <span>Player</span>
        <span>Vill/min</span>
        <span>Mil/min</span>
      </div>
    `;

    for (const rate of rates) {
      const vRank = villagerRank[rate.name];
      const mRank = militaryRank[rate.name];
      const vClass = getRateClass(vRank, numPlayers);
      const mClass = getRateClass(mRank, numPlayers);

      html += `
        <div class="tracker-row">
          <span class="tracker-player" style="color: ${rate.color}">${rate.name}</span>
          <span class="tracker-rate ${vClass}">${rate.villagerRate.toFixed(1)}</span>
          <span class="tracker-rate ${mClass}">${rate.militaryRate.toFixed(1)}</span>
        </div>
      `;
    }

    this.playerTracker.innerHTML = html;
  }

  startRenderLoop() {
    const render = () => {
      const state = this.playback.getState();

      // Filter by player visibility
      const filteredState = {
        units: new Map(
          [...state.units].filter(
            ([name, unit]) => this.playerVisibility[unit.player] !== false,
          ),
        ),
        buildings: new Map(
          [...state.buildings].filter(
            ([name, building]) =>
              this.playerVisibility[building.player] !== false,
          ),
        ),
        walls: (state.walls || []).filter(
          (wall) => this.playerVisibility[wall.player] !== false,
        ),
        actionLines: state.actionLines.filter(
          (line) => this.playerVisibility[line.player] !== false,
        ),
      };

      this.renderer.render(filteredState);
      this.renderLoopId = requestAnimationFrame(render);
    };

    render();
  }
}

// Initialize on load
document.addEventListener("DOMContentLoaded", () => {
  // Add loading overlay
  const loading = document.createElement("div");
  loading.className = "loading";
  loading.textContent = "Loading replay data...";
  document.body.appendChild(loading);

  // Start app
  const app = new App();
  app.init();
});
