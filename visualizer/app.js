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
    this.actionLog = document.getElementById("action-log");
    this.fileInput = document.getElementById("file-input");

    this.speedButtons = document.querySelectorAll(".speed-btn");

    // Render loop
    this.renderLoopId = null;

    // Player visibility
    this.playerVisibility = {};

    // Action log entries (keep last 50)
    this.maxLogEntries = 50;

    // Track if controls have been set up
    this.controlsInitialized = false;
  }

  async init() {
    try {
      // Try to load default replay data
      const response = await fetch("replay_data.json");
      if (response.ok) {
        this.data = await response.json();
        this.initializeWithData();
      } else {
        // No default data, show upload prompt
        this.showUploadPrompt();
      }

      // Setup file upload handler
      this.setupFileUpload();
    } catch (error) {
      console.error("Failed to initialize:", error);
      this.showUploadPrompt();
      this.setupFileUpload();
    }
  }

  showUploadPrompt() {
    document.querySelector(".loading")?.remove();
    this.matchInfo.textContent = "Upload a replay file to begin";
  }

  initializeWithData() {
    // Initialize renderer
    this.renderer = new Renderer(this.canvas, this.data.match.map_size);
    this.renderer.setPlayerColors(this.data.players);

    // Initialize playback
    this.playback = new Playback(this.data);
    this.playback.onTimeUpdate = (time) => this.onTimeUpdate(time);
    this.playback.onActionProcessed = (action) =>
      this.onActionProcessed(action);

    // Setup UI
    this.setupUI();
    this.setupKeyboardShortcuts();

    // Initial render
    this.startRenderLoop();

    // Remove loading state
    document.querySelector(".loading")?.remove();
  }

  setupFileUpload() {
    this.fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (!file.name.endsWith(".aoe2record")) {
        alert("Please select a valid .aoe2record file");
        return;
      }

      await this.uploadReplay(file);
    });
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

      // Clear action log
      this.actionLog.innerHTML = "";

      // Reinitialize with new data
      this.initializeWithData();
    } catch (error) {
      console.error("Upload failed:", error);
      alert(`Failed to process replay: ${error.message}`);
      this.matchInfo.textContent = "Upload failed - try again";
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

      const item = document.createElement("div");
      item.className = "player-item";
      item.innerHTML = `
                <input type="checkbox" id="player-${player.color_id}" checked>
                <div class="player-color" style="background-color: ${player.color_hex}"></div>
                <label for="player-${player.color_id}">${player.name}</label>
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
  }

  onActionProcessed(action) {
    // Add to action log
    const entry = document.createElement("div");
    entry.className = "action-log-entry";

    const player = this.data.players.find((p) => p.name === action.player);
    const color = player ? player.color_hex : "#fff";

    const timeStr = this.playback.formatTime(action.time);
    const subjects =
      action.subjects.length > 0 ? action.subjects.join(", ") : "";
    const target = action.target ? ` -> ${action.target}` : "";

    entry.innerHTML = `
            <span class="time">[${timeStr}]</span>
            <span class="player" style="color: ${color}">${action.player}</span>
            <span class="action-type">${action.type}</span>
            ${subjects ? `<span class="subject">${subjects}</span>` : ""}
            ${target ? `<span class="target">${target}</span>` : ""}
        `;

    this.actionLog.appendChild(entry);

    // Keep only last N entries
    while (this.actionLog.children.length > this.maxLogEntries) {
      this.actionLog.removeChild(this.actionLog.firstChild);
    }

    // Auto-scroll to bottom
    this.actionLog.scrollTop = this.actionLog.scrollHeight;
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
