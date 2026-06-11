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
    this.saveRecordBtn = document.getElementById("save-record-btn");

    // Share-clip UI elements
    this.shareClipBtn = document.getElementById("share-clip-btn");
    this.clipOverlay = document.getElementById("clip-overlay");
    this.closeClipBtn = document.getElementById("close-clip");
    this.clipPlayerSelect = document.getElementById("clip-player-select");
    this.clipGenerateBtn = document.getElementById("clip-generate-btn");
    this.clipStatus = document.getElementById("clip-status");
    this.clipResult = document.getElementById("clip-result");
    this.clipVideo = document.getElementById("clip-video");
    this.clipUrlInput = document.getElementById("clip-url-input");
    this.clipViewInput = document.getElementById("clip-view-input");
    this.copyClipUrlBtn = document.getElementById("copy-clip-url");
    this.copyClipViewBtn = document.getElementById("copy-clip-view");
    // The aoe2 match id + download profile id of the currently loaded replay.
    // Only set for replays loaded from the browser / deep-link (not uploads),
    // since the server needs them to re-download the replay for clip export.
    this.currentMatchId = null;
    this.currentProfileId = null;

    // Timeline scrubbing state: while the user drags the marker we pause the
    // engine and stop the play loop from yanking the thumb back, then resume.
    this.isScrubbing = false;
    this._wasPlayingBeforeScrub = false;
    // Last play/pause state pushed to the button label (so the render loop only
    // touches the DOM when it actually changes).
    this._btnPlayState = null;

    // Match browsing UI elements
    this.browseMatchesBtn = document.getElementById("browse-matches-btn");
    this.matchListOverlay = document.getElementById("match-list-overlay");
    this.matchListTitle = document.getElementById("match-list-title");
    this.matchListLoading = document.getElementById("match-list-loading");
    this.matchList = document.getElementById("match-list");
    this.closeMatchListBtn = document.getElementById("close-match-list");

    // Player-search step elements
    this.playerSearchStep = document.getElementById("player-search-step");
    this.playerMatchesStep = document.getElementById("player-matches-step");
    this.playerSearchForm = document.getElementById("player-search-form");
    this.playerSearchInput = document.getElementById("player-search-input");
    this.playerSearchLoading = document.getElementById("player-search-loading");
    this.playerResults = document.getElementById("player-results");
    this.selectedPlayerHeader = document.getElementById(
      "selected-player-header",
    );
    this.backToPlayerSearchBtn = document.getElementById(
      "back-to-player-search",
    );
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

    // Technology tracking
    this.researchData = {}; // player -> [{ time, tech }] - sorted by time
    this.playerAges = {}; // player -> [{ time, age }] - age transitions
    this.techTracker = document.getElementById("tech-tracker");
    this.teams = []; // Cached team groupings

    // Building tracking (for storyteller)
    this.buildingData = {}; // player -> [{ time, building }]

    // Attack tracking (for storyteller)
    this.attackData = []; // [{ time, attacker, target, units }]

    // Training tracking (for storyteller milestones)
    this.trainingData = {}; // player -> { unitType: [times] }

    // Storyteller
    this.storyteller = null;
    this.captionsContainer = document.getElementById("captions-container");

    // Track if controls have been set up
    this.controlsInitialized = false;

    // Match browsing state
    this.currentPlayer = { name: "ddk220", profileId: null };
    this.matches = [];
    this.selectedMatch = null;
    // The player chosen from the search step. Used to highlight their row in
    // each match and to pick the download perspective when loading a replay.
    this.selectedPlayer = null;
  }

  async init() {
    // Setup event listeners for match browsing
    this.setupMatchBrowsing();
    this.setupFileUpload();

    // Deep-link: /?match=<aoe2MatchId>&profile=<profileId> auto-loads a replay.
    // This is what NammaPUBobot posts as the "Watch replay" link after a match.
    const params = new URLSearchParams(window.location.search);
    // Optional ?t=<seconds> or ?t=<mm:ss> jumps to that moment on load and
    // starts playing (e.g. to share a specific trebuchet barrage).
    this.startAtTime = this.parseTimeParam(params.get("t"));
    const linkedMatch = params.get("match");
    if (linkedMatch) {
      const linkedProfile = params.get("profile") || "612690";
      await this.loadMatchById(linkedMatch, linkedProfile);
      return;
    }

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

    // Player search (step 1)
    this.playerSearchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      this.searchPlayers();
    });

    // Back from a player's matches (step 2) to the search results (step 1)
    this.backToPlayerSearchBtn.addEventListener("click", () => {
      this.showPlayerSearchStep();
    });

    // Close buttons
    this.closeMatchListBtn.addEventListener("click", () => {
      this.hideMatchListPanel();
    });

    this.closeMatchDetailBtn.addEventListener("click", () => {
      this.hideMatchDetailPanel();
    });

    // Back to the chosen player's match list (not the player search step)
    this.backToListBtn.addEventListener("click", () => {
      this.hideMatchDetailPanel();
      document.querySelector(".loading")?.remove();
      this.matchListOverlay.classList.remove("hidden");
      this.showPlayerMatchesStep();
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

  showMatchListPanel() {
    document.querySelector(".loading")?.remove();
    this.matchListOverlay.classList.remove("hidden");
    // Always open on the player-search step.
    this.showPlayerSearchStep();
    // Focus the search box for quick typing.
    setTimeout(() => this.playerSearchInput?.focus(), 0);
  }

  hideMatchListPanel() {
    this.matchListOverlay.classList.add("hidden");
  }

  // Step 1 ⇄ Step 2 toggling within the panel.
  showPlayerSearchStep() {
    this.playerSearchStep.classList.remove("hidden");
    this.playerMatchesStep.classList.add("hidden");
    if (this.matchListTitle) this.matchListTitle.textContent = "Find a Player";
  }

  showPlayerMatchesStep() {
    this.playerSearchStep.classList.add("hidden");
    this.playerMatchesStep.classList.remove("hidden");
    if (this.matchListTitle) this.matchListTitle.textContent = "Recent Matches";
  }

  // ---- Step 1: search players by name ----

  async searchPlayers() {
    const query = (this.playerSearchInput.value || "").trim();
    if (!query) {
      this.playerSearchInput.focus();
      return;
    }

    this.playerSearchLoading.classList.remove("hidden");
    this.playerResults.innerHTML = "";

    try {
      const response = await fetch(
        `/api/players?search=${encodeURIComponent(query)}`,
      );
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || "Failed to search players");
      }
      const data = await response.json();
      this.renderPlayerResults(data.players || []);
    } catch (error) {
      console.error("Failed to search players:", error);
      this.playerResults.innerHTML = `<div class="error-message">${error.message}</div>`;
    }

    this.playerSearchLoading.classList.add("hidden");
  }

  renderPlayerResults(players) {
    this.playerResults.innerHTML = "";

    if (!players.length) {
      this.playerResults.innerHTML =
        '<div class="no-matches">No players found. Try a different name.</div>';
      return;
    }

    for (const player of players) {
      const item = document.createElement("div");
      item.className = "player-result";
      item.addEventListener("click", () => this.selectPlayer(player));

      const country = player.country
        ? `<span class="player-result-country">${player.country.toUpperCase()}</span>`
        : "";
      const clan = player.clan
        ? `<span class="player-result-clan">[${player.clan}]</span>`
        : "";
      const games =
        typeof player.games === "number" && player.games > 0
          ? `<span class="player-result-games">${player.games.toLocaleString()} games</span>`
          : "";
      const verified = player.verified
        ? '<span class="player-result-verified" title="Verified profile">✓</span>'
        : "";

      item.innerHTML = `
        <div class="player-result-main">
          ${clan}
          <span class="player-result-name">${player.name || "Unknown"}</span>
          ${verified}
          ${country}
        </div>
        <div class="player-result-meta">${games}</div>
      `;

      this.playerResults.appendChild(item);
    }
  }

  // ---- Step 2: a chosen player's recent games ----

  async selectPlayer(player) {
    this.selectedPlayer = player;
    // The match renderers highlight "tracked" players and pick the download
    // perspective from this list — make it the player we just chose.
    this.players = [{ name: player.name, profileId: player.profileId }];

    this.showPlayerMatchesStep();
    this.selectedPlayerHeader.innerHTML = `
      <span class="selected-player-label">Last 10 games for</span>
      <span class="selected-player-name">${player.name || "player"}</span>
    `;
    this.matchListLoading.classList.remove("hidden");
    this.matchList.innerHTML = "";

    try {
      await this.fetchMatchesForPlayer(player.profileId);
      this.renderMatchList();
    } catch (error) {
      console.error("Failed to fetch matches:", error);
      this.matchList.innerHTML = `<div class="error-message">Failed to load matches: ${error.message}</div>`;
    }

    this.matchListLoading.classList.add("hidden");
  }

  async fetchMatchesForPlayer(profileId) {
    const response = await fetch(
      `/api/player/${profileId}/matches?limit=10`,
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || "Failed to fetch matches");
    }
    const data = await response.json();
    this.matches = data.matches || [];
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
            ${match.matchId ? `<span class="match-id" title="Match ID (click to copy)">ID: ${match.matchId}</span>` : ""}
            ${targetWon !== null ? `<span class="match-result-indicator ${targetWon ? "win" : "loss"}">${targetWon ? "WIN" : "LOSS"}</span>` : ""}
          </div>
        </div>
      `;

      // Clicking the ID copies it (instead of opening the match).
      const idEl = item.querySelector(".match-id");
      if (idEl) {
        idEl.addEventListener("click", (e) => {
          e.stopPropagation();
          const id = String(match.matchId);
          const done = () => {
            const prev = idEl.textContent;
            idEl.textContent = "Copied!";
            setTimeout(() => (idEl.textContent = prev), 1000);
          };
          if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(id).then(done, done);
          } else {
            done();
          }
        });
      }

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

    // Find a tracked player in this match to use for download perspective.
    // Default to the player chosen from search (whose game this is).
    const playerIds = new Set((this.players || []).map((p) => p.profileId));
    let profileIdForDownload =
      this.selectedPlayer?.profileId || 612690; // Fallback: ddk220
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
      this.currentMatchId = match.matchId;
      this.currentProfileId = profileIdForDownload;

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

  // Load a replay directly from an aoe2 match id + profile id (deep-link entry).
  // Unlike loadMatch(), we don't have a full match object — just the two ids.
  async loadMatchById(matchId, profileId) {
    document.querySelector(".loading")?.remove();
    this.showLoadingOverlay("Downloading replay...");
    try {
      const response = await fetch("/api/load-match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matchId, profileId }),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${response.status}`);
      }
      this.showLoadingOverlay("Processing replay...");
      this.data = await response.json();
      this.currentMatchId = matchId;
      this.currentProfileId = profileId;
      if (this.renderLoopId) {
        cancelAnimationFrame(this.renderLoopId);
      }
      this.initializeWithData();
      this.hideLoadingOverlay();
    } catch (error) {
      console.error("Deep-link load failed:", error);
      this.hideLoadingOverlay();
      this.matchInfo.textContent = `Couldn't load match ${matchId}: ${error.message}`;
      // Fall back to the normal match browser so the page is still usable.
      this.showMatchListPanel();
    }
  }

  initializeWithData() {
    // Fully tear down any previous session so a new load can't leave the old
    // one running. The old Playback drives its own requestAnimationFrame loop
    // (separate from the render loop), so without pausing it + detaching its
    // callback it keeps advancing time and fighting the new match.
    if (this.renderLoopId) {
      cancelAnimationFrame(this.renderLoopId);
      this.renderLoopId = null;
    }
    if (this.playback) {
      this.playback.pause();
      this.playback.onTimeUpdate = null;
    }
    this.isScrubbing = false;
    this._wasPlayingBeforeScrub = false;
    this._btnPlayState = null;

    // Initialize renderer
    this.renderer = new Renderer(this.canvas, this.data.match.map_size);
    this.renderer.setPlayerColors(this.data.players);
    // Starting-map backdrop (terrain + resources), if the server provided it.
    this.renderer.setMapData(
      this.data.terrain,
      this.data.map_objects,
      this.data.animals,
    );

    // Initialize playback
    this.playback = new Playback(this.data);
    this.playback.onTimeUpdate = (time) => this.onTimeUpdate(time);

    // Preprocess production data from DE_QUEUE actions
    this.preprocessProductionData();

    // Preprocess research data for technology tracker
    this.preprocessResearchData();

    // Setup UI (this sets up this.teams)
    this.setupUI();
    this.setupKeyboardShortcuts();

    // Preprocess building, attack, and training data (used elsewhere too)
    this.preprocessBuildingData();
    this.preprocessAttackData();
    this.preprocessTrainingData();

    // Storyteller narration ("Castle Age", "building a Castle", ...) disabled.
    // this.initializeStoryteller();

    // Share-clip button is only usable for replays loaded by aoe2 match id
    // (browser / deep-link) — server-side clip export re-downloads by id.
    if (this.shareClipBtn) {
      this.shareClipBtn.disabled = !this.currentMatchId;
      this.shareClipBtn.title = this.currentMatchId
        ? "Generate a short shareable WebM highlight clip of this match"
        : "Load a match from Browse Matches to generate a shareable clip";
    }

    // Initial render
    this.startRenderLoop();

    // Deep-link timestamp: jump to the requested moment and start playing so a
    // shared link lands right on the action (e.g. a trebuchet firing).
    if (this.startAtTime != null && this.playback) {
      this.playback.seekTo(this.startAtTime);
      if (!this.playback.isPlaying) this.togglePlay();
      this.startAtTime = null; // only on first load, not on later match swaps
    }

    // Remove loading state
    document.querySelector(".loading")?.remove();
  }

  // Parse a ?t= value: plain seconds ("2600") or mm:ss / hh:mm:ss ("43:20").
  parseTimeParam(s) {
    if (!s) return null;
    if (s.includes(":")) {
      const parts = s.split(":").map(Number);
      if (parts.some((n) => Number.isNaN(n))) return null;
      return parts.reduce((acc, n) => acc * 60 + n, 0);
    }
    const v = parseFloat(s);
    return Number.isNaN(v) ? null : v;
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

  preprocessResearchData() {
    // Reset research data
    this.researchData = {};
    this.playerAges = {};

    // Age research names (various formats that might appear)
    const ageMap = {
      "feudal age": "Feudal",
      feudalage: "Feudal",
      "castle age": "Castle",
      castleage: "Castle",
      "imperial age": "Imperial",
      imperialage: "Imperial",
    };

    for (const player of this.data.players) {
      this.researchData[player.name] = [];
      this.playerAges[player.name] = [{ time: 0, age: "Dark" }]; // Everyone starts in Dark Age
    }

    // Process all RESEARCH actions
    for (const action of this.data.actions) {
      if (action.type === "RESEARCH" && action.target && action.player) {
        const techName = action.target;
        const playerData = this.researchData[action.player];

        if (playerData) {
          // Check for duplicate (same tech at same time)
          const isDupe = playerData.some(
            (r) => r.tech === techName && Math.abs(r.time - action.time) < 1,
          );
          if (!isDupe) {
            playerData.push({ time: action.time, tech: techName });

            // Check if this is an age upgrade
            const normalizedTech = techName.toLowerCase().replace(/\s+/g, "");
            for (const [key, ageName] of Object.entries(ageMap)) {
              if (normalizedTech === key.replace(/\s+/g, "")) {
                this.playerAges[action.player].push({
                  time: action.time,
                  age: ageName,
                });
                break;
              }
            }
          }
        }
      }
    }

    // Sort research by time
    for (const player of Object.keys(this.researchData)) {
      this.researchData[player].sort((a, b) => a.time - b.time);
      this.playerAges[player].sort((a, b) => a.time - b.time);
    }
  }

  preprocessBuildingData() {
    // Reset building data
    this.buildingData = {};

    for (const player of this.data.players) {
      this.buildingData[player.name] = [];
    }

    // Process BUILD actions
    for (const action of this.data.actions) {
      if (action.type === "BUILD" && action.target && action.player) {
        const playerData = this.buildingData[action.player];
        if (playerData) {
          playerData.push({
            time: action.time,
            building: action.target,
          });
        }
      }
    }

    // Sort by time
    for (const player of Object.keys(this.buildingData)) {
      this.buildingData[player].sort((a, b) => a.time - b.time);
    }
  }

  preprocessAttackData() {
    // Reset attack data
    this.attackData = [];

    // Track unit ownership for attack detection
    const unitOwner = {}; // unit_id -> player_name

    // Build unit ownership from actions
    for (const action of this.data.actions) {
      if (action.subjects && action.player) {
        for (const subject of action.subjects) {
          if (!unitOwner[subject]) {
            unitOwner[subject] = action.player;
          }
        }
      }
    }

    // Process ORDER actions (attacks)
    // Group attacks by time window to count units
    const attackWindows = {}; // "attacker_target_timeWindow" -> { time, attacker, target, units: Set }

    for (const action of this.data.actions) {
      if (
        action.type === "ORDER" &&
        action.target_id &&
        action.player &&
        action.subjects
      ) {
        // Check if target belongs to a different player
        const targetOwner = unitOwner[action.target_id];
        if (targetOwner && targetOwner !== action.player) {
          // This is an attack on an enemy
          const timeWindow = Math.floor(action.time / 5) * 5; // 5-second windows
          const key = `${action.player}_${targetOwner}_${timeWindow}`;

          if (!attackWindows[key]) {
            attackWindows[key] = {
              time: action.time,
              attacker: action.player,
              target: targetOwner,
              unitSet: new Set(),
            };
          }

          // Add attacking units
          for (const subject of action.subjects) {
            attackWindows[key].unitSet.add(subject);
          }
        }
      }
    }

    // Convert to array
    for (const attack of Object.values(attackWindows)) {
      this.attackData.push({
        time: attack.time,
        attacker: attack.attacker,
        target: attack.target,
        units: attack.unitSet.size,
      });
    }

    // Sort by time
    this.attackData.sort((a, b) => a.time - b.time);
  }

  preprocessTrainingData() {
    // Reset training data
    this.trainingData = {};

    for (const player of this.data.players) {
      this.trainingData[player.name] = {};
    }

    // Process DE_QUEUE actions for specific unit types
    for (const action of this.data.actions) {
      if (action.type === "DE_QUEUE" && action.target && action.player) {
        const unitType = action.target.toLowerCase().replace(/[\s-_]/g, "");
        const playerData = this.trainingData[action.player];

        if (playerData) {
          if (!playerData[unitType]) {
            playerData[unitType] = [];
          }
          playerData[unitType].push(action.time);
        }
      }
    }

    // Sort by time
    for (const player of Object.keys(this.trainingData)) {
      for (const unit of Object.keys(this.trainingData[player])) {
        this.trainingData[player][unit].sort((a, b) => a - b);
      }
    }
  }

  async initializeStoryteller() {
    if (!this.captionsContainer) return;

    this.storyteller = new Storyteller(this.captionsContainer);
    await this.storyteller.loadStories();

    // Set game data
    this.storyteller.setGameData({
      players: this.data.players,
      teams: this.teams,
      researchData: this.researchData,
      buildingData: this.buildingData,
      productionData: this.productionData,
      attackData: this.attackData,
    });

    // Also pass training data
    this.storyteller.trainingData = this.trainingData;
  }

  getPlayerAge(playerName, currentTime) {
    const ages = this.playerAges[playerName] || [{ time: 0, age: "Dark" }];
    let currentAge = "Dark";
    for (const entry of ages) {
      if (entry.time <= currentTime) {
        currentAge = entry.age;
      } else {
        break;
      }
    }
    return currentAge;
  }

  getRecentTechs(playerName, currentTime, limit = 5) {
    const techs = this.researchData[playerName] || [];
    // Get techs researched up to current time
    const researched = techs.filter((t) => t.time <= currentTime);
    // Return the most recent ones
    return researched.slice(-limit);
  }

  formatTechName(tech) {
    // Convert lowercase tech names to readable format
    // e.g., "feudalage" -> "Feudal Age", "doublebitaxe" -> "Double Bit Axe"
    const techNames = {
      loom: "Loom",
      feudalage: "Feudal Age",
      castleage: "Castle Age",
      imperialage: "Imperial Age",
      doublebitaxe: "Double-Bit Axe",
      bowsaw: "Bow Saw",
      twomansaw: "Two-Man Saw",
      horsecollar: "Horse Collar",
      heavyplow: "Heavy Plow",
      croprotation: "Crop Rotation",
      goldmining: "Gold Mining",
      goldshaftmining: "Gold Shaft Mining",
      stonemining: "Stone Mining",
      stoneshaftmining: "Stone Shaft Mining",
      wheelbarrow: "Wheelbarrow",
      handcart: "Hand Cart",
      townwatch: "Town Watch",
      townpatrol: "Town Patrol",
      fletching: "Fletching",
      bodkinarrow: "Bodkin Arrow",
      bracer: "Bracer",
      forging: "Forging",
      ironcasting: "Iron Casting",
      blastfurnace: "Blast Furnace",
      scalemailarmor: "Scale Mail Armor",
      chainmailarmor: "Chain Mail Armor",
      platemailarmor: "Plate Mail Armor",
      scalebardingarmor: "Scale Barding Armor",
      chainbardingarmor: "Chain Barding Armor",
      platebardingarmor: "Plate Barding Armor",
      paddedarcherarmor: "Padded Archer Armor",
      leatherarcherarmor: "Leather Archer Armor",
      ringarcherarmor: "Ring Archer Armor",
      bloodlines: "Bloodlines",
      husbandry: "Husbandry",
      crossbowman: "Crossbowman",
      arbalester: "Arbalester",
      eliteskirmisher: "Elite Skirmisher",
      pikeman: "Pikeman",
      halberdier: "Halberdier",
      longswordsman: "Long Swordsman",
      twohanded: "Two-Handed Swordsman",
      champion: "Champion",
      lightcavalry: "Light Cavalry",
      hussar: "Hussar",
      cavalier: "Cavalier",
      paladin: "Paladin",
      heavycamelarcher: "Heavy Camel Archer",
      heavycamelrider: "Heavy Camel Rider",
      thumbring: "Thumb Ring",
      parthiantactics: "Parthian Tactics",
      ballistics: "Ballistics",
      chemistry: "Chemistry",
      siegeengineers: "Siege Engineers",
      murder_holes: "Murder Holes",
      masonry: "Masonry",
      architecture: "Architecture",
      heatedshot: "Heated Shot",
      arrowslits: "Arrowslits",
      redemption: "Redemption",
      atonement: "Atonement",
      herbalMedicine: "Herbal Medicine",
      heresy: "Heresy",
      sanctity: "Sanctity",
      fervor: "Fervor",
      illumination: "Illumination",
      blockprinting: "Block Printing",
      theocracy: "Theocracy",
      faith: "Faith",
      careening: "Careening",
      drydock: "Dry Dock",
      shipwright: "Shipwright",
      gillnets: "Gillnets",
      conscription: "Conscription",
      spies: "Spies/Treason",
    };

    const normalized = tech.toLowerCase().replace(/[\s-_]/g, "");
    return techNames[normalized] || tech;
  }

  updateTechTracker(currentTime) {
    if (!this.techTracker || !this.teams.length) return;

    let html = "";

    for (let i = 0; i < this.teams.length; i++) {
      const teamMembers = this.teams[i];

      html += `<div class="tech-team-section">`;
      html += `<div class="tech-team-label">Team ${i + 1}</div>`;

      for (const player of teamMembers) {
        const age = this.getPlayerAge(player.name, currentTime);
        const ageClass = age.toLowerCase();
        const recentTechs = this.getRecentTechs(player.name, currentTime, 5);

        html += `<div class="tech-player-row">`;
        html += `<div class="tech-player-name" style="color: ${player.color_hex}">`;
        html += `${player.name}`;
        html += `<span class="tech-player-age ${ageClass}">${age}</span>`;
        html += `</div>`;

        html += `<div class="tech-list">`;
        for (const tech of recentTechs) {
          const mins = Math.floor(tech.time / 60);
          const secs = Math.floor(tech.time % 60);
          const timeStr = `${mins}:${secs.toString().padStart(2, "0")}`;
          html += `<div class="tech-item">`;
          html += `<span class="tech-name">${this.formatTechName(tech.tech)}</span>`;
          html += `<span class="tech-time">${timeStr}</span>`;
          html += `</div>`;
        }
        html += `</div>`;

        html += `</div>`;
      }

      html += `</div>`;
    }

    this.techTracker.innerHTML = html;
  }

  setupFileUpload() {
    this.fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (
        file.name.endsWith(".json") ||
        file.name.endsWith(".aoe2ddkrecord")
      ) {
        // Pre-processed snapshot (our own .aoe2ddkrecord is just this JSON):
        // load directly, no server parse needed.
        await this.loadJsonFile(file);
      } else if (file.name.endsWith(".aoe2record")) {
        // Raw replay — upload to the server to be parsed.
        await this.uploadReplay(file);
      } else {
        alert("Please select a .aoe2record, .aoe2ddkrecord, or .json file");
      }
    });
  }

  async loadJsonFile(file) {
    this.matchInfo.textContent = `Loading ${file.name}...`;

    try {
      const text = await file.text();
      this.data = JSON.parse(text);
      // Local file: no aoe2 match id, so server-side clip export isn't available.
      this.currentMatchId = null;
      this.currentProfileId = null;

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

  // Save the fully-processed match data as a <matchid>.aoe2ddkrecord file. This
  // is exactly the JSON the visualizer runs on, so it can be reloaded later to
  // keep watching without re-downloading / re-parsing the raw .aoe2record.
  saveRecord() {
    if (!this.data) {
      alert("Load a match first, then save.");
      return;
    }
    const matchId = this.data.source && this.data.source.matchId;
    const mapName = (this.data.match && this.data.match.map_name) || "replay";
    const dur = Math.round(
      (this.data.match && this.data.match.duration_seconds) || 0,
    );
    const base = matchId
      ? String(matchId)
      : `${mapName.replace(/[^\w]+/g, "_")}_${dur}s`;

    const blob = new Blob([JSON.stringify(this.data)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${base}.aoe2ddkrecord`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // ==================== Share Clip ====================

  // Open the clip modal, populating the focus-player dropdown from the loaded
  // match. Defaults the selection to the tracked player we downloaded from.
  openClipPanel() {
    if (!this.currentMatchId) {
      alert("Load a match from Browse Matches first to generate a clip.");
      return;
    }
    // (Re)populate the player dropdown.
    this.clipPlayerSelect.innerHTML = "";
    const players = (this.data && this.data.players) || [];
    for (const p of players) {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = p.name;
      this.clipPlayerSelect.appendChild(opt);
    }
    // Default to the perspective player if it's in the match.
    const myName = (this.currentPlayer && this.currentPlayer.name) || "";
    if (players.some((p) => p.name === myName)) {
      this.clipPlayerSelect.value = myName;
    }

    // Reset transient UI state.
    this.clipResult.classList.add("hidden");
    this.clipStatus.classList.add("hidden");
    this.clipGenerateBtn.disabled = false;
    if (this.clipVideo) this.clipVideo.removeAttribute("src");

    this.clipOverlay.classList.remove("hidden");
  }

  hideClipPanel() {
    this.clipOverlay.classList.add("hidden");
    // Stop the preview so it isn't playing behind the scenes.
    if (this.clipVideo) {
      this.clipVideo.pause();
      this.clipVideo.removeAttribute("src");
      this.clipVideo.load();
    }
  }

  // Call the server-side clip exporter and show the resulting WebM + links.
  async generateClip() {
    if (!this.currentMatchId) {
      alert("Load a match from Browse Matches first to generate a clip.");
      return;
    }
    const player = this.clipPlayerSelect.value || "";
    this.clipGenerateBtn.disabled = true;
    this.clipResult.classList.add("hidden");
    this.clipStatus.classList.remove("hidden");
    this.clipStatus.textContent =
      "Rendering highlight clip… this can take up to a minute.";

    try {
      const params = new URLSearchParams({
        matchId: String(this.currentMatchId),
        profileId: String(this.currentProfileId || ""),
      });
      if (player) params.set("player", player);
      const resp = await fetch(`/api/clip?${params.toString()}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${resp.status}`);
      }
      const out = await resp.json();
      // Cache-bust so a regenerated clip for the same player refreshes.
      const bust = `?v=${Date.now()}`;
      this.clipVideo.src = out.clip_url + bust;
      this.clipVideo.load();
      this.clipUrlInput.value = out.clip_url;
      this.clipViewInput.value = out.view_url || "";
      this.clipStatus.classList.add("hidden");
      this.clipResult.classList.remove("hidden");
    } catch (error) {
      console.error("Clip generation failed:", error);
      this.clipStatus.textContent = `Failed to generate clip: ${error.message}`;
    } finally {
      this.clipGenerateBtn.disabled = false;
    }
  }

  async copyToClipboard(input, btn) {
    if (!input || !input.value) return;
    try {
      await navigator.clipboard.writeText(input.value);
    } catch (e) {
      // Fallback for older browsers / insecure contexts.
      input.select();
      document.execCommand("copy");
    }
    const prev = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => {
      btn.textContent = prev;
    }, 1500);
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
      // Uploaded raw replay: no aoe2 match id for server-side clip export.
      this.currentMatchId = null;
      this.currentProfileId = null;

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

      // Timeline scrubbing. While dragging we pause the engine (so the play
      // loop doesn't fight the thumb) and seek live to wherever the marker is,
      // then resume if it was playing. This makes the marker land exactly where
      // you point it instead of jumping.
      const startScrub = () => {
        if (this.isScrubbing) return;
        this.isScrubbing = true;
        this._wasPlayingBeforeScrub = this.playback.isPlaying;
        this.playback.pause();
      };
      const endScrub = () => {
        if (!this.isScrubbing) return;
        this.isScrubbing = false;
        if (this._wasPlayingBeforeScrub) this.playback.play();
        this._wasPlayingBeforeScrub = false;
      };
      this.timeline.addEventListener("pointerdown", startScrub);
      this.timeline.addEventListener("pointerup", endScrub);
      this.timeline.addEventListener("pointercancel", endScrub);
      this.timeline.addEventListener("input", (e) => {
        // Keyboard nudges (focus + arrows) fire input without a pointerdown;
        // treat those as an instantaneous seek too.
        this.playback.seekTo(parseFloat(e.target.value));
      });
      this.timeline.addEventListener("change", endScrub);

      // Save the processed match as a .aoe2ddkrecord file.
      if (this.saveRecordBtn) {
        this.saveRecordBtn.addEventListener("click", () => this.saveRecord());
      }

      // Share-clip modal wiring.
      if (this.shareClipBtn) {
        this.shareClipBtn.addEventListener("click", () => this.openClipPanel());
      }
      if (this.closeClipBtn) {
        this.closeClipBtn.addEventListener("click", () => this.hideClipPanel());
      }
      if (this.clipOverlay) {
        this.clipOverlay.addEventListener("click", (e) => {
          if (e.target === this.clipOverlay) this.hideClipPanel();
        });
      }
      if (this.clipGenerateBtn) {
        this.clipGenerateBtn.addEventListener("click", () =>
          this.generateClip(),
        );
      }
      if (this.copyClipUrlBtn) {
        this.copyClipUrlBtn.addEventListener("click", () =>
          this.copyToClipboard(this.clipUrlInput, this.copyClipUrlBtn),
        );
      }
      if (this.copyClipViewBtn) {
        this.copyClipViewBtn.addEventListener("click", () =>
          this.copyToClipboard(this.clipViewInput, this.copyClipViewBtn),
        );
      }

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

    // Group players by team using their team array (list of teammate names)
    this.teams = [];
    const assignedPlayers = new Set();

    for (const player of this.data.players) {
      if (assignedPlayers.has(player.name)) continue;

      // Find all players on this team
      const teamMembers = [player];
      assignedPlayers.add(player.name);

      // player.team contains names of teammates
      if (player.team && player.team.length > 0) {
        for (const teammateName of player.team) {
          if (!assignedPlayers.has(teammateName)) {
            const teammate = this.data.players.find(
              (p) => p.name === teammateName,
            );
            if (teammate) {
              teamMembers.push(teammate);
              assignedPlayers.add(teammateName);
            }
          }
        }
      }

      this.teams.push(teamMembers);
    }

    // Render each team
    this.teams.forEach((teamMembers, teamIndex) => {
      // Add team divider if more than one team
      if (this.teams.length > 1 && teamIndex > 0) {
        const divider = document.createElement("div");
        divider.className = "team-divider";
        this.playerLegend.appendChild(divider);
      }

      // Add team label if more than one team
      if (this.teams.length > 1) {
        const teamLabel = document.createElement("div");
        teamLabel.className = "team-label";
        teamLabel.textContent = `Team ${teamIndex + 1}`;
        this.playerLegend.appendChild(teamLabel);
      }

      for (const player of teamMembers) {
        this.playerVisibility[player.name] = true;

        const civ = player.civilization ? ` (${player.civilization})` : "";
        const item = document.createElement("div");
        item.className = "player-item";
        item.innerHTML = `
          <input type="checkbox" id="player-${player.color_id}" checked>
          <div class="player-color" style="background-color: ${player.color_hex}"></div>
          <label for="player-${player.color_id}">${player.name}${civ}<span class="player-age-badge dark" data-player="${player.name}">Dark</span></label>
        `;

        const checkbox = item.querySelector("input");
        checkbox.addEventListener("change", (e) => {
          this.playerVisibility[player.name] = e.target.checked;
        });

        this.playerLegend.appendChild(item);
      }
    });
  }

  updatePlayerAgesInLegend(currentTime) {
    for (const player of this.data.players) {
      const badge = this.playerLegend.querySelector(
        `.player-age-badge[data-player="${player.name}"]`,
      );
      if (badge) {
        const age = this.getPlayerAge(player.name, currentTime);
        badge.textContent = age;
        badge.className = `player-age-badge ${age.toLowerCase()}`;
      }
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
        case "KeyP":
          // Toggle the player list / production-rates overlay (hidden by default)
          document.querySelector(".info-panel")?.classList.toggle("hidden");
          break;
        case "KeyT":
          // Toggle the research / Recent Technologies overlay (hidden by default)
          document.getElementById("tech-panel")?.classList.toggle("hidden");
          break;
      }
    });
  }

  togglePlay() {
    // Just flip the engine; the render loop keeps the button label in sync with
    // the real play state (so it's correct even when playback auto-pauses at the
    // end, or when a new match is loaded).
    this.playback.togglePlayPause();
    this.syncPlayButton();
  }

  // Reflect the engine's actual play state on the button. Cheap to call every
  // frame: it only touches the DOM when the state flips.
  syncPlayButton() {
    const playing = !!(this.playback && this.playback.isPlaying);
    if (this._btnPlayState === playing) return;
    this._btnPlayState = playing;
    this.btnPlay.textContent = playing ? "Pause" : "Play";
    this.btnPlay.classList.toggle("playing", playing);
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
    // Don't move the thumb out from under the user while they're dragging it.
    if (!this.isScrubbing) this.timeline.value = time;

    // Update player tracker every second (avoid excessive updates)
    if (Math.abs(time - this.lastTrackerUpdate) >= 1) {
      this.lastTrackerUpdate = time;
      this.updatePlayerTracker(time);
      this.updateTechTracker(time);
      this.updatePlayerAgesInLegend(time);
    }

    // Update storyteller (runs every frame for accurate timing)
    if (this.storyteller) {
      this.storyteller.update(time);
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
        // Trebuchet shots are keyed by player too — carry them through (they
        // were being dropped, so they never rendered). Generic attack arrows
        // are intentionally left out (visually noisy).
        trebProjectiles: (state.trebProjectiles || []).filter(
          (tp) => this.playerVisibility[tp.player] !== false,
        ),
        // Needed by renderer.drawAnimals() to hide animals past their gone_at.
        currentTime: state.currentTime,
      };

      this.renderer.render(filteredState);
      // Keep the play/pause button label honest regardless of how the state
      // changed (click, spacebar, end-of-game auto-pause, scrub).
      this.syncPlayButton();
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
