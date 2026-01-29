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
    this.unitMovements = new Map(); // unit_name -> [{time, x, y, actionType}, ...]
    this.buildingEvents = []; // [{time, player, type, x, y}, ...]
    this.unitDeletions = new Map(); // unit_name -> deletion_time
    this.buildingDeletions = []; // [{time, x, y}, ...]
    this.attackActions = []; // [{time, attackerNames, targetX, targetY, player}, ...]
    this.targetPositions = new Map(); // target_id -> {x, y} for tracking attack targets

    const actions = this.data.actions;

    for (const action of actions) {
      const { type, player, subjects, target, target_id, x, y, time } = action;

      // Track ORDER (attack) actions with target positions
      if (type === "ORDER" && target_id && x !== null && y !== null) {
        // Store target position for this target_id
        this.targetPositions.set(target_id, { x, y, time });

        // Record attack action
        if (subjects && subjects.length > 0) {
          this.attackActions.push({
            time: time,
            attackerNames: subjects,
            targetX: x,
            targetY: y,
            targetId: target_id,
            player: player,
          });
        }
      }

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

          // For ORDER (attack) actions, check if this is a ranged unit
          // Ranged units don't move all the way to the target
          const isAttack = type === "ORDER" && target_id;

          this.unitMovements.get(unitName).push({
            time: time,
            x: x,
            y: y,
            actionType: type,
            isAttack: isAttack,
            targetId: isAttack ? target_id : null,
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

    // Ranged unit types that should stay at distance when attacking
    const RANGED_TYPES = new Set(["archer", "siege"]);
    const RANGED_ATTACK_DISTANCE = 5; // Tiles - ranged units stop this far from target
    const isRangedUnit = RANGED_TYPES.has(unit.type);

    for (let i = 0; i <= commandIndex; i++) {
      const command = movements[i];
      let destX = command.x;
      let destY = command.y;

      // For ranged units attacking, stop at a distance from the target
      if (isRangedUnit && command.isAttack) {
        const dx = destX - currentX;
        const dy = destY - currentY;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > RANGED_ATTACK_DISTANCE) {
          // Move to attack range, not all the way to target
          const stopDistance = distance - RANGED_ATTACK_DISTANCE;
          const ratio = stopDistance / distance;
          destX = currentX + dx * ratio;
          destY = currentY + dy * ratio;
        } else {
          // Already in range, don't move
          destX = currentX;
          destY = currentY;
        }
      }

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

    // Constants for idle/death detection
    const VILLAGER_IDLE_THRESHOLD = 30; // 30 seconds for villager idle detection
    const END_GAME_BUFFER = 3 * 60; // Last 3 minutes of game - don't mark units as dead
    const isEndGame = this.currentTime >= this.duration - END_GAME_BUFFER;

    for (const [name, unit] of this.units) {
      // Check if unit should be alive
      let alive = unit.alive;
      const isVillager = unit.type === "villager";

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

      // Track last command time and idle state
      const movements = unit.movements || [];
      let lastCommandTime = null;
      let lastCommandInGame = null; // Last command ever for this unit

      if (movements.length > 0) {
        // Find the last command ever (for non-villager death detection)
        lastCommandInGame = movements[movements.length - 1].time;

        // Find the last command before or at current time
        for (const movement of movements) {
          if (movement.time <= this.currentTime) {
            lastCommandTime = movement.time;
          }
        }
      }

      // For non-villagers: if they have no more actions after current time, they're dead
      // Exception: don't apply this in the last 3 minutes of game
      let idleVillager = false;

      if (!isVillager && alive && lastCommandInGame !== null) {
        // Check if unit has no future commands (last command is in the past)
        if (lastCommandTime !== null && lastCommandTime === lastCommandInGame) {
          // This unit has no more commands after this point
          // Don't mark dead in end game (units may still be alive)
          if (!isEndGame) {
            alive = false;
          }
        }
      }

      // For villagers: check 30-second idle threshold for opacity reduction
      let villagerIdleTime = 0;
      if (isVillager && alive && lastCommandTime !== null) {
        const timeSinceLastCommand = this.currentTime - lastCommandTime;
        if (timeSinceLastCommand > VILLAGER_IDLE_THRESHOLD) {
          idleVillager = true;
          villagerIdleTime = timeSinceLastCommand;
        }
      }

      // Legacy 5-minute inactivity check for villagers only (keep them visible but faded)
      const INACTIVITY_THRESHOLD = 5 * 60; // 5 minutes in seconds
      if (isVillager && movements.length > 0 && lastCommandTime !== null) {
        const timeSinceLastCommand = this.currentTime - lastCommandTime;
        if (timeSinceLastCommand > INACTIVITY_THRESHOLD) {
          // Villager hasn't been commanded in 5+ minutes, consider it dead
          alive = false;
          // Mark as dying if within 30 seconds of the threshold
          if (timeSinceLastCommand <= INACTIVITY_THRESHOLD + 30) {
            dying = true;
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
        idleVillager: idleVillager, // New flag for idle villagers
        idleTime: villagerIdleTime, // Time since last command (for opacity fade)
      });
    }

    // Update buildings based on time, tracking age for opacity
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
          const buildingAge = this.currentTime - event.time;
          currentBuildings.set(key, {
            x: event.x,
            y: event.y,
            player: event.player,
            type: event.type,
            age: buildingAge, // Time since building was placed
          });
        }
      }
    }

    // Get active attack actions (within last 3 seconds)
    const ATTACK_DISPLAY_DURATION = 3; // Show attack arrows for 3 seconds
    const activeAttacks = [];
    for (const attack of this.attackActions) {
      const timeSinceAttack = this.currentTime - attack.time;
      if (timeSinceAttack >= 0 && timeSinceAttack <= ATTACK_DISPLAY_DURATION) {
        // Get attacker positions
        for (const attackerName of attack.attackerNames) {
          const attackerUnit = interpolatedUnits.get(attackerName);
          if (attackerUnit && attackerUnit.alive) {
            activeAttacks.push({
              fromX: attackerUnit.x,
              fromY: attackerUnit.y,
              toX: attack.targetX,
              toY: attack.targetY,
              player: attack.player,
              opacity: 1 - timeSinceAttack / ATTACK_DISPLAY_DURATION, // Fade out
            });
          }
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
      attacks: activeAttacks, // Attack arrows to draw
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
