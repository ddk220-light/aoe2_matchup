/**
 * Playback engine - handles game state and action processing
 * Units move smoothly between command positions based on timing
 */

class Playback {
  constructor(data) {
    this.data = data;
    this.duration = data.match.duration_seconds;

    // Playback state
    this.currentTime = 0;
    this.isPlaying = false;
    this.playbackSpeed = 1;

    // Game state
    this.units = new Map(); // unit_name -> {x, y, player, type, alive, dying, movements: [...]}
    this.buildings = new Map(); // building_key -> {x, y, player, type}

    // Callbacks
    this.onTimeUpdate = null;
    this.onActionProcessed = null;

    // Animation
    this.lastFrameTime = 0;
    this.animationId = null;

    // Track which actions have been logged
    this.lastLoggedActionIndex = -1;

    // Build unit ownership map from starting units
    this.unitOwners = new Map();
    for (const unit of this.data.starting_units) {
      this.unitOwners.set(unit.id, unit.player);
    }

    // Pre-process all unit movements
    this.preprocessMovements();

    // Initialize state
    this.initializeUnits();
  }

  // Extract owner from unit name (format: type_player_number)
  getOwnerFromUnitName(unitName) {
    // First check if we already know the owner
    if (this.unitOwners.has(unitName)) {
      return this.unitOwners.get(unitName);
    }

    // Parse from name: villager_Shadeslayer II_1 -> Shadeslayer II
    const parts = unitName.split("_");
    if (parts.length >= 3) {
      // Join all parts except first (type) and last (number)
      return parts.slice(1, -1).join("_");
    }
    return null;
  }

  // Pre-process all actions to build movement timelines for each unit
  preprocessMovements() {
    this.unitMovements = new Map(); // unit_name -> [{time, x, y}, ...]
    this.buildingEvents = []; // [{time, player, type, x, y}, ...]
    this.unitDeletions = new Map(); // unit_name -> deletion_time
    this.buildingDeletions = []; // [{time, x, y}, ...]

    const actions = this.data.actions;

    for (const action of actions) {
      const { type, player, subjects, target, x, y, time } = action;

      // Track DELETE actions
      if (type === "DELETE") {
        // Handle unit deletions
        if (subjects && subjects.length > 0) {
          for (const unitName of subjects) {
            const owner = this.getOwnerFromUnitName(unitName);

            // Only process deletions from the owner
            if (owner && owner !== player) {
              continue;
            }

            // Record deletion time for this unit
            if (!this.unitDeletions.has(unitName)) {
              this.unitDeletions.set(unitName, time);
            }
          }
        }

        // Handle building deletions (by position)
        if (x !== null && y !== null) {
          this.buildingDeletions.push({
            time: time,
            x: Math.round(x),
            y: Math.round(y),
            player: player,
          });
        }
      }

      // Track position-based actions for units
      // ONLY include actions where the commanding player owns the unit
      if (subjects && subjects.length > 0 && x !== null && y !== null) {
        for (const unitName of subjects) {
          const owner = this.getOwnerFromUnitName(unitName);

          // Skip if the action player doesn't match the unit owner
          if (owner && owner !== player) {
            continue;
          }

          // Store owner if we don't have it yet
          if (!this.unitOwners.has(unitName)) {
            this.unitOwners.set(unitName, player);
          }

          if (!this.unitMovements.has(unitName)) {
            this.unitMovements.set(unitName, []);
          }
          this.unitMovements.get(unitName).push({
            time: time,
            x: x,
            y: y,
            actionType: type,
          });
        }
      }

      // Track building placements
      if (type === "BUILD" && x !== null && y !== null && target) {
        this.buildingEvents.push({
          time: time,
          player: player,
          type: target,
          x: x,
          y: y,
        });
      }
    }

    // Sort movements by time for each unit
    for (const [unitName, movements] of this.unitMovements) {
      movements.sort((a, b) => a.time - b.time);
    }

    // Sort building events by time
    this.buildingEvents.sort((a, b) => a.time - b.time);
  }

  initializeUnits() {
    this.units.clear();
    this.buildings.clear();
    this.lastLoggedActionIndex = -1;

    // Add starting units with their movement timelines
    for (const unit of this.data.starting_units) {
      const movements = this.unitMovements.get(unit.id) || [];

      // Determine starting position: use first movement if no initial position
      let startX = unit.x;
      let startY = unit.y;
      if ((startX === null || startY === null) && movements.length > 0) {
        startX = movements[0].x;
        startY = movements[0].y;
      }

      this.units.set(unit.id, {
        x: startX,
        y: startY,
        player: unit.player,
        type: unit.type,
        alive: true,
        dying: false,
        movements: movements,
        instanceId: unit.instance_id,
      });
    }

    // Create units that appear later (not in starting units)
    for (const [unitName, movements] of this.unitMovements) {
      if (!this.units.has(unitName) && movements.length > 0) {
        const player = this.unitOwners.get(unitName) || "unknown";

        // Determine type from name
        const type = this.classifyUnitType(unitName);

        this.units.set(unitName, {
          x: null, // Will be set when unit first appears
          y: null,
          player: player,
          type: type,
          alive: false, // Not alive until first seen
          dying: false,
          movements: movements,
          spawnTime: movements[0].time, // When unit first appears
        });
      }
    }
  }

  // Classify unit type from unit name
  classifyUnitType(unitName) {
    const name = unitName.toLowerCase();

    if (name.includes("villager")) return "villager";
    if (name.includes("scout")) return "cavalry";
    if (
      name.includes("knight") ||
      name.includes("cavalier") ||
      name.includes("paladin") ||
      name.includes("hussar") ||
      name.includes("camel") ||
      name.includes("elephant") ||
      name.includes("cavalry") ||
      name.includes("tarkan") ||
      name.includes("boyar") ||
      name.includes("konnik") ||
      name.includes("leitis") ||
      name.includes("keshik") ||
      name.includes("cataphract") ||
      name.includes("mameluke")
    )
      return "cavalry";
    if (
      name.includes("archer") ||
      name.includes("crossbow") ||
      name.includes("arbalest") ||
      name.includes("skirmisher") ||
      name.includes("longbow") ||
      name.includes("mangudai") ||
      name.includes("handcannoneer") ||
      name.includes("janissary") ||
      name.includes("conquistador") ||
      name.includes("chukonou") ||
      name.includes("plumed") ||
      name.includes("genitour") ||
      name.includes("kipchak") ||
      name.includes("arambai") ||
      name.includes("rattan")
    )
      return "archer";
    if (
      name.includes("militia") ||
      name.includes("swordsman") ||
      name.includes("champion") ||
      name.includes("spearman") ||
      name.includes("pikeman") ||
      name.includes("halberdier") ||
      name.includes("eagle") ||
      name.includes("huskarl") ||
      name.includes("berserk") ||
      name.includes("samurai") ||
      name.includes("jaguar") ||
      name.includes("woad") ||
      name.includes("teutonic") ||
      name.includes("throwing") ||
      name.includes("gbeto") ||
      name.includes("kamayuk") ||
      name.includes("shotel") ||
      name.includes("serjeant") ||
      name.includes("obuch") ||
      name.includes("urumi")
    )
      return "infantry";
    if (
      name.includes("ram") ||
      name.includes("mangonel") ||
      name.includes("onager") ||
      name.includes("scorpion") ||
      name.includes("trebuchet") ||
      name.includes("bombard") ||
      name.includes("siege")
    )
      return "siege";
    if (name.includes("monk") || name.includes("missionary")) return "monk";
    if (
      name.includes("galley") ||
      name.includes("ship") ||
      name.includes("boat") ||
      name.includes("caravel") ||
      name.includes("longboat") ||
      name.includes("turtle") ||
      name.includes("cannon galleon") ||
      name.includes("dromon")
    )
      return "ship";
    if (name.includes("king")) return "king";

    return "military";
  }

  // Get interpolated position for a unit at current time
  // Uses speed-based movement: units move at a fixed speed toward their destination
  // If interrupted by a new command, the new starting position is where they actually were
  getUnitPosition(unit) {
    const movements = unit.movements;
    if (!movements || movements.length === 0) {
      return { x: unit.x, y: unit.y };
    }

    // Unit movement speeds (tiles per second) - approximate AoE2 speeds
    const UNIT_SPEEDS = {
      villager: 0.8,
      infantry: 0.9,
      archer: 0.96,
      cavalry: 1.35,
      siege: 0.6,
      monk: 0.7,
      ship: 1.5,
      king: 0.9,
      military: 0.9,
    };

    const speed = UNIT_SPEEDS[unit.type] || 0.9;

    // Find the movement command that applies at currentTime
    let commandIndex = -1;
    for (let i = 0; i < movements.length; i++) {
      if (movements[i].time <= this.currentTime) {
        commandIndex = i;
      } else {
        break;
      }
    }

    // Before first movement - use starting position
    if (commandIndex < 0) {
      if (unit.x !== null && unit.y !== null) {
        return { x: unit.x, y: unit.y };
      }
      if (movements.length > 0) {
        return { x: movements[0].x, y: movements[0].y };
      }
      return { x: unit.x, y: unit.y };
    }

    // Calculate position by simulating movement through all commands up to now
    let currentX = unit.x !== null ? unit.x : movements[0].x;
    let currentY = unit.y !== null ? unit.y : movements[0].y;

    // If no starting position, use first command destination
    if (currentX === null || currentY === null) {
      currentX = movements[0].x;
      currentY = movements[0].y;
    }

    for (let i = 0; i <= commandIndex; i++) {
      const command = movements[i];
      const destX = command.x;
      const destY = command.y;

      // Time available for this movement
      const startTime = i === 0 ? movements[0].time - 10 : movements[i].time; // Assume unit existed 10s before first command
      const endTime =
        i < commandIndex ? movements[i + 1].time : this.currentTime;
      const availableTime = endTime - startTime;

      // Distance to destination
      const dx = destX - currentX;
      const dy = destY - currentY;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance > 0) {
        // Time needed to reach destination
        const timeNeeded = distance / speed;

        if (availableTime >= timeNeeded) {
          // Unit reaches destination
          currentX = destX;
          currentY = destY;
        } else {
          // Unit is interrupted - calculate how far it got
          const progress = (availableTime * speed) / distance;
          currentX = currentX + dx * progress;
          currentY = currentY + dy * progress;
        }
      }
    }

    return { x: currentX, y: currentY };
  }

  // Get current game state for rendering
  getState() {
    // Update unit positions based on interpolation
    const interpolatedUnits = new Map();

    for (const [name, unit] of this.units) {
      // Check if unit should be alive
      let alive = unit.alive;

      // Unit spawns when first movement occurs
      if (unit.spawnTime !== undefined) {
        if (this.currentTime < unit.spawnTime) {
          alive = false;
        } else {
          alive = true;
        }
      }

      // Check for death
      const deathTime = this.data.unit_deaths[name];
      let dying = false;
      if (deathTime !== undefined) {
        if (this.currentTime >= deathTime) {
          alive = false;
        } else if (this.currentTime >= deathTime - 30) {
          dying = true;
        }
      }

      // Check for deletion by player
      const deletionTime = this.unitDeletions.get(name);
      if (deletionTime !== undefined && this.currentTime >= deletionTime) {
        alive = false;
      }

      // Check for 5-minute inactivity (unit disappears if no commands for 5 min)
      const INACTIVITY_THRESHOLD = 5 * 60; // 5 minutes in seconds
      const movements = unit.movements || [];
      if (movements.length > 0) {
        // Find the last command before or at current time
        let lastCommandTime = null;
        for (const movement of movements) {
          if (movement.time <= this.currentTime) {
            lastCommandTime = movement.time;
          }
        }

        if (lastCommandTime !== null) {
          const timeSinceLastCommand = this.currentTime - lastCommandTime;
          if (timeSinceLastCommand > INACTIVITY_THRESHOLD) {
            // Unit hasn't been commanded in 5+ minutes, consider it dead
            alive = false;
            // Mark as dying if within 30 seconds of the threshold
            if (timeSinceLastCommand <= INACTIVITY_THRESHOLD + 30) {
              dying = true;
            }
          }
        }
      }

      // Get interpolated position
      const pos = this.getUnitPosition(unit);

      // Skip units with no valid position
      if (pos.x === null || pos.y === null) {
        continue;
      }

      interpolatedUnits.set(name, {
        x: pos.x,
        y: pos.y,
        player: unit.player,
        type: unit.type,
        alive: alive,
        dying: dying,
      });
    }

    // Update buildings based on time
    const currentBuildings = new Map();
    for (const event of this.buildingEvents) {
      if (event.time <= this.currentTime) {
        const roundedX = Math.round(event.x);
        const roundedY = Math.round(event.y);

        // Check if this building was deleted (after it was placed)
        let deleted = false;
        for (const deletion of this.buildingDeletions) {
          // Deletion must happen after the building was placed and before current time
          if (
            deletion.time > event.time &&
            deletion.time <= this.currentTime &&
            Math.abs(deletion.x - roundedX) <= 2 &&
            Math.abs(deletion.y - roundedY) <= 2
          ) {
            deleted = true;
            break;
          }
        }

        if (!deleted) {
          const key = `${event.type}_${event.player}_${roundedX}_${roundedY}`;
          currentBuildings.set(key, {
            x: event.x,
            y: event.y,
            player: event.player,
            type: event.type,
          });
        }
      }
    }

    // Update walls based on time
    const currentWalls = [];
    const walls = this.data.walls || [];
    for (const wall of walls) {
      if (wall.time <= this.currentTime) {
        currentWalls.push({
          x_start: wall.x_start,
          y_start: wall.y_start,
          x_end: wall.x_end,
          y_end: wall.y_end,
          player: wall.player,
          type: wall.type,
        });
      }
    }

    return {
      units: interpolatedUnits,
      buildings: currentBuildings,
      walls: currentWalls,
      actionLines: [], // No more action lines
      currentTime: this.currentTime,
    };
  }

  // Format time as MM:SS
  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  // Process actions for logging purposes
  processActionsForLog() {
    const actions = this.data.actions;

    // Find actions that should be logged
    while (
      this.lastLoggedActionIndex + 1 < actions.length &&
      actions[this.lastLoggedActionIndex + 1].time <= this.currentTime
    ) {
      this.lastLoggedActionIndex++;
      const action = actions[this.lastLoggedActionIndex];

      if (this.onActionProcessed) {
        this.onActionProcessed(action);
      }
    }
  }

  // Seek to a specific time
  seekTo(time) {
    time = Math.max(0, Math.min(this.duration, time));

    // If going backwards, reset log index
    if (time < this.currentTime) {
      this.lastLoggedActionIndex = -1;
    }

    this.currentTime = time;
    this.processActionsForLog();

    if (this.onTimeUpdate) {
      this.onTimeUpdate(this.currentTime);
    }
  }

  // Step forward/backward by one action
  stepForward() {
    const actions = this.data.actions;
    const nextIndex = this.lastLoggedActionIndex + 1;
    if (nextIndex < actions.length) {
      this.seekTo(actions[nextIndex].time + 0.001);
    }
  }

  stepBackward() {
    const actions = this.data.actions;
    if (this.lastLoggedActionIndex > 0) {
      const targetIndex = this.lastLoggedActionIndex - 1;
      // Reset and seek to just after that action
      this.lastLoggedActionIndex = -1;
      this.seekTo(actions[targetIndex].time + 0.001);
    } else {
      this.seekTo(0);
    }
  }

  // Animation loop
  animate(timestamp) {
    if (!this.isPlaying) return;

    if (this.lastFrameTime === 0) {
      this.lastFrameTime = timestamp;
    }

    const deltaTime = (timestamp - this.lastFrameTime) / 1000; // Convert to seconds
    this.lastFrameTime = timestamp;

    // Advance time
    this.currentTime += deltaTime * this.playbackSpeed;

    // Check if we've reached the end
    if (this.currentTime >= this.duration) {
      this.currentTime = this.duration;
      this.pause();
    }

    // Process actions for logging
    this.processActionsForLog();

    // Update UI
    if (this.onTimeUpdate) {
      this.onTimeUpdate(this.currentTime);
    }

    // Continue animation
    if (this.isPlaying) {
      this.animationId = requestAnimationFrame((t) => this.animate(t));
    }
  }

  // Playback controls
  play() {
    if (this.isPlaying) return;

    this.isPlaying = true;
    this.lastFrameTime = 0;
    this.animationId = requestAnimationFrame((t) => this.animate(t));
  }

  pause() {
    this.isPlaying = false;
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
  }

  togglePlayPause() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
    return this.isPlaying;
  }

  setSpeed(speed) {
    this.playbackSpeed = speed;
  }

  goToStart() {
    this.pause();
    this.lastLoggedActionIndex = -1;
    this.seekTo(0);
  }

  goToEnd() {
    this.pause();
    this.seekTo(this.duration);
  }
}

// Export for use in other modules
window.Playback = Playback;
