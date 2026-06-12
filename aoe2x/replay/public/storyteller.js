/**
 * Storyteller - Narrates interesting moments during replay playback
 */

class Storyteller {
  constructor(container) {
    this.container = container;
    this.stories = [];
    this.config = {
      max_visible_captions: 3,
      caption_duration_ms: 5000,
      fade_duration_ms: 500,
    };

    // Game data (set via setGameData)
    this.players = [];
    this.teams = [];
    this.researchData = {}; // player -> [{ time, tech }]
    this.buildingData = {}; // player -> [{ time, building }]
    this.productionData = {}; // player -> { villagers: [], military: [] }
    this.attackData = []; // [{ time, attacker, target, units }]

    // Tracking state
    this.triggeredStories = new Set(); // Story IDs that have fired (one-time)
    this.lastTriggerTime = {}; // Story ID -> last trigger game time (for cooldowns)
    this.lastCheckTime = {}; // Story ID -> last check time (for interval checks)
    this.activeCaptions = []; // { id, text, addedAt, element }

    // For "last player" detection
    this.pendingLastPlayer = {}; // target -> { players: Set, deadline }

    this.lastGameTime = 0;
  }

  async loadStories(url = "/stories/stories.json") {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Failed to load stories");
      const data = await response.json();

      this.config = { ...this.config, ...data.config };
      this.stories = data.stories.filter((s) => s.enabled !== false);
      console.log(`Storyteller: Loaded ${this.stories.length} stories`);
    } catch (error) {
      console.error("Storyteller: Failed to load stories", error);
    }
  }

  setGameData({
    players,
    teams,
    researchData,
    buildingData,
    productionData,
    attackData,
  }) {
    this.players = players || [];
    this.teams = teams || [];
    this.researchData = researchData || {};
    this.buildingData = buildingData || {};
    this.productionData = productionData || {};
    this.attackData = attackData || [];

    // Reset tracking state
    this.triggeredStories.clear();
    this.lastTriggerTime = {};
    this.lastCheckTime = {};
    this.pendingLastPlayer = {};
    this.activeCaptions = [];
    this.container.innerHTML = "";
  }

  update(gameTime) {
    // Only process forward in time (skip if rewinding)
    if (gameTime < this.lastGameTime - 1) {
      // Reset if we've gone back significantly
      this.triggeredStories.clear();
      this.lastTriggerTime = {};
      this.lastCheckTime = {};
      this.pendingLastPlayer = {};
    }
    this.lastGameTime = gameTime;

    // Evaluate each story
    for (const story of this.stories) {
      this.evaluateStory(story, gameTime);
    }

    // Check for pending "last player" stories
    this.checkPendingLastPlayer(gameTime);

    // Remove expired captions
    this.updateCaptions();
  }

  evaluateStory(story, gameTime) {
    const trigger = story.trigger;
    if (!trigger) return;

    // Skip if already triggered (one-time stories)
    if (
      !story.cooldown_seconds &&
      this.triggeredStories.has(story.id)
    ) {
      return;
    }

    // Check cooldown
    if (story.cooldown_seconds) {
      const lastTime = this.lastTriggerTime[story.id] || 0;
      if (gameTime - lastTime < story.cooldown_seconds) {
        return;
      }
    }

    switch (trigger.type) {
      case "first_player":
        this.checkFirstPlayer(story, gameTime);
        break;
      case "last_player":
        this.checkLastPlayer(story, gameTime);
        break;
      case "player_event":
        this.checkPlayerEvent(story, gameTime);
        break;
      case "absence":
        this.checkAbsence(story, gameTime);
        break;
      case "milestone":
        this.checkMilestone(story, gameTime);
        break;
      case "comparison":
        this.checkComparison(story, gameTime);
        break;
      case "attack_event":
        this.checkAttackEvent(story, gameTime);
        break;
    }
  }

  checkFirstPlayer(story, gameTime) {
    const { event, target } = story.trigger;
    const events = this.getEvents(event, target);

    // Find the first event across all players
    let firstEvent = null;
    let firstPlayer = null;

    for (const player of this.players) {
      const playerEvents = events[player.name] || [];
      for (const evt of playerEvents) {
        if (evt.time <= gameTime) {
          if (!firstEvent || evt.time < firstEvent.time) {
            firstEvent = evt;
            firstPlayer = player;
          }
          break; // Only check first event per player
        }
      }
    }

    if (firstEvent && !this.triggeredStories.has(story.id)) {
      // Check if we just passed this time
      if (
        firstEvent.time <= gameTime &&
        firstEvent.time > gameTime - 1
      ) {
        this.triggerStory(story, {
          player: firstPlayer,
          time: firstEvent.time,
          target: firstEvent.target || target,
        });
      }
    }
  }

  checkLastPlayer(story, gameTime) {
    const { event, target } = story.trigger;
    const events = this.getEvents(event, target);
    const key = `${story.id}_${target}`;

    // Initialize tracking if needed
    if (!this.pendingLastPlayer[key]) {
      this.pendingLastPlayer[key] = {
        players: new Set(this.players.map((p) => p.name)),
        triggered: false,
      };
    }

    const pending = this.pendingLastPlayer[key];
    if (pending.triggered) return;

    // Remove players who have done the action
    for (const player of this.players) {
      const playerEvents = events[player.name] || [];
      for (const evt of playerEvents) {
        if (evt.time <= gameTime) {
          pending.players.delete(player.name);
          break;
        }
      }
    }

    // When only one player remains and they do it, that's the last
    if (pending.players.size === 1) {
      const lastPlayerName = [...pending.players][0];
      const lastPlayer = this.players.find((p) => p.name === lastPlayerName);
      const playerEvents = events[lastPlayerName] || [];

      for (const evt of playerEvents) {
        if (evt.time <= gameTime && evt.time > gameTime - 1) {
          this.triggerStory(story, {
            player: lastPlayer,
            time: evt.time,
            target: evt.target || target,
          });
          pending.triggered = true;
          break;
        }
      }
    }
  }

  checkPendingLastPlayer(gameTime) {
    // This is handled in checkLastPlayer now
  }

  checkPlayerEvent(story, gameTime) {
    const { event, target } = story.trigger;
    const events = this.getEvents(event, target);
    const triggeredKey = `${story.id}_triggered`;

    if (!this[triggeredKey]) {
      this[triggeredKey] = new Set();
    }

    for (const player of this.players) {
      const playerEvents = events[player.name] || [];
      for (const evt of playerEvents) {
        const eventKey = `${player.name}_${evt.time}`;
        if (
          evt.time <= gameTime &&
          evt.time > gameTime - 1 &&
          !this[triggeredKey].has(eventKey)
        ) {
          this.triggerStory(story, {
            player: player,
            time: evt.time,
            target: evt.target || target,
          });
          this[triggeredKey].add(eventKey);
        }
      }
    }
  }

  checkAbsence(story, gameTime) {
    const { event, target, deadline, check_at } = story.trigger;
    const checkTime = check_at || deadline;

    // Only check at the specific time
    if (gameTime < checkTime || gameTime > checkTime + 1) return;
    if (this.triggeredStories.has(story.id)) return;

    const events = this.getEvents(event, target);

    for (const player of this.players) {
      const playerEvents = events[player.name] || [];
      const hasResearched = playerEvents.some((e) => e.time <= deadline);

      if (!hasResearched) {
        this.triggerStory(story, {
          player: player,
          time: gameTime,
          target: target,
        });
        // Only trigger once per story for absence
        return;
      }
    }
  }

  checkMilestone(story, gameTime) {
    const { event, target, threshold, before_time } = story.trigger;

    // Check time constraint
    if (before_time && gameTime > before_time) return;

    const triggeredKey = `${story.id}_milestone_triggered`;
    if (!this[triggeredKey]) {
      this[triggeredKey] = new Set();
    }

    for (const player of this.players) {
      if (this[triggeredKey].has(player.name)) continue;

      let count = 0;
      const targets = Array.isArray(target) ? target : [target];

      if (event === "train" || event === "train_cumulative") {
        // Count from production data
        const prodData = this.productionData[player.name];
        if (prodData) {
          for (const t of targets) {
            const unitEvents = prodData[t] || [];
            count += unitEvents.filter((time) => time <= gameTime).length;
          }
          // Also check military array for general units
          if (targets.includes("knight")) {
            // Knights are in military, need to check training events
          }
        }
        // Also check from training events in actions
        count = this.countTrainedUnits(player.name, targets, gameTime);
      }

      if (count >= threshold) {
        this.triggerStory(story, {
          player: player,
          time: gameTime,
          value: count,
          target: targets.join("/"),
        });
        this[triggeredKey].add(player.name);
      }
    }
  }

  checkComparison(story, gameTime) {
    const { metric, condition, threshold, check_interval } = story.trigger;

    // Check interval
    const lastCheck = this.lastCheckTime[story.id] || 0;
    if (gameTime - lastCheck < check_interval) return;
    this.lastCheckTime[story.id] = gameTime;

    if (this.teams.length < 2) return;

    // Calculate metric for each team
    const teamValues = this.teams.map((team, idx) => {
      let value = 0;
      for (const player of team) {
        value += this.getMetricValue(player.name, metric, gameTime);
      }
      return { team: idx + 1, value };
    });

    // Compare teams
    if (condition === "team_difference_exceeds") {
      const sorted = [...teamValues].sort((a, b) => b.value - a.value);
      const diff = sorted[0].value - sorted[1].value;

      if (diff >= threshold) {
        this.triggerStory(story, {
          team: sorted[0].team,
          value: diff,
          time: gameTime,
        });
      }
    }
  }

  checkAttackEvent(story, gameTime) {
    const { condition, min_units } = story.trigger;

    if (condition === "first_attack") {
      if (this.triggeredStories.has(story.id)) return;

      for (const attack of this.attackData) {
        if (
          attack.time <= gameTime &&
          attack.time > gameTime - 1 &&
          attack.units >= (min_units || 1)
        ) {
          const attacker = this.players.find(
            (p) => p.name === attack.attacker
          );
          const target = this.players.find((p) => p.name === attack.target);

          if (attacker && target && !this.sameTeam(attacker, target)) {
            this.triggerStory(story, {
              player: attacker,
              player2: target,
              time: attack.time,
            });
            return;
          }
        }
      }
    }
  }

  sameTeam(player1, player2) {
    for (const team of this.teams) {
      const names = team.map((p) => p.name);
      if (names.includes(player1.name) && names.includes(player2.name)) {
        return true;
      }
    }
    return false;
  }

  getEvents(event, target) {
    const result = {};
    const targets = Array.isArray(target) ? target : [target];
    const normalizedTargets = targets.map((t) =>
      t.toLowerCase().replace(/[\s-_]/g, "")
    );

    for (const player of this.players) {
      result[player.name] = [];

      if (event === "research") {
        const researches = this.researchData[player.name] || [];
        for (const r of researches) {
          const normalizedTech = r.tech.toLowerCase().replace(/[\s-_]/g, "");
          if (normalizedTargets.some((t) => normalizedTech.includes(t))) {
            result[player.name].push({ time: r.time, target: r.tech });
          }
        }
      } else if (event === "build") {
        const buildings = this.buildingData[player.name] || [];
        for (const b of buildings) {
          const normalizedBuilding = b.building
            .toLowerCase()
            .replace(/[\s-_]/g, "");
          if (normalizedTargets.some((t) => normalizedBuilding.includes(t))) {
            result[player.name].push({ time: b.time, target: b.building });
          }
        }
      }
    }

    return result;
  }

  countTrainedUnits(playerName, targets, gameTime) {
    // This would need training event data
    // For now, return 0 - will be populated from app.js
    const trainData = this.trainingData?.[playerName] || {};
    let count = 0;
    for (const target of targets) {
      const events = trainData[target.toLowerCase()] || [];
      count += events.filter((t) => t <= gameTime).length;
    }
    return count;
  }

  getMetricValue(playerName, metric, gameTime) {
    const prodData = this.productionData[playerName];
    if (!prodData) return 0;

    if (metric === "military_count") {
      return prodData.military.filter((t) => t <= gameTime).length;
    } else if (metric === "villager_count") {
      return prodData.villagers.filter((t) => t <= gameTime).length;
    }
    return 0;
  }

  triggerStory(story, data) {
    // Mark as triggered
    this.triggeredStories.add(story.id);
    this.lastTriggerTime[story.id] = data.time;

    // Select random template
    const template =
      story.templates[Math.floor(Math.random() * story.templates.length)];

    // Format the caption text
    const text = this.formatTemplate(template, data);

    // Add caption
    this.addCaption(story.id, text, story.priority || 2);

    console.log(`Story triggered: ${story.id} - ${text}`);
  }

  formatTemplate(template, data) {
    let text = template;

    // Format time
    if (data.time !== undefined) {
      const mins = Math.floor(data.time / 60);
      const secs = Math.floor(data.time % 60);
      const timeStr = `${mins}:${secs.toString().padStart(2, "0")}`;
      text = text.replace(/\{time\}/g, timeStr);
    }

    // Format player with color
    if (data.player) {
      const playerHtml = `<span class="player-name" style="color: ${data.player.color_hex}">${data.player.name}</span>`;
      text = text.replace(/\{player\}/g, playerHtml);
    }

    // Format player2
    if (data.player2) {
      const player2Html = `<span class="player-name" style="color: ${data.player2.color_hex}">${data.player2.name}</span>`;
      text = text.replace(/\{player2\}/g, player2Html);
    }

    // Format team
    if (data.team !== undefined) {
      text = text.replace(/\{team\}/g, data.team);
    }

    // Format value
    if (data.value !== undefined) {
      text = text.replace(/\{value\}/g, data.value);
    }

    // Format target
    if (data.target) {
      text = text.replace(/\{target\}/g, data.target);
    }

    // Format civ
    if (data.player?.civilization) {
      text = text.replace(/\{civ\}/g, data.player.civilization);
    }

    return text;
  }

  addCaption(id, text, priority) {
    // Remove oldest if at max
    while (this.activeCaptions.length >= this.config.max_visible_captions) {
      const oldest = this.activeCaptions.shift();
      if (oldest.element) {
        oldest.element.classList.add("fading");
        setTimeout(() => oldest.element.remove(), this.config.fade_duration_ms);
      }
    }

    // Create caption element
    const element = document.createElement("div");
    element.className = "caption";
    element.innerHTML = text;
    this.container.appendChild(element);

    // Track caption
    this.activeCaptions.push({
      id,
      text,
      priority,
      addedAt: Date.now(),
      element,
    });
  }

  updateCaptions() {
    const now = Date.now();
    const expireTime = this.config.caption_duration_ms;
    const fadeTime = this.config.fade_duration_ms;

    for (let i = this.activeCaptions.length - 1; i >= 0; i--) {
      const caption = this.activeCaptions[i];
      const age = now - caption.addedAt;

      // Start fading
      if (age > expireTime - fadeTime && !caption.fading) {
        caption.fading = true;
        caption.element.classList.add("fading");
      }

      // Remove after fade
      if (age > expireTime) {
        caption.element.remove();
        this.activeCaptions.splice(i, 1);
      }
    }
  }

  // Clear all captions (for reset)
  clear() {
    for (const caption of this.activeCaptions) {
      caption.element.remove();
    }
    this.activeCaptions = [];
  }
}
