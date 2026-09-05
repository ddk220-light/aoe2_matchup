import { buildSelectionPreviewUnits, createMapRenderer } from "/v3-runtime/viewer/map-renderer.js";
import { WorkerSession } from "./worker-session.js";

export function createPlaybackController({updateStats, syncPlayerControls, updateBattleWinner}) {
function deepFreeze(value, visited = new Set()) {
    if (!value || typeof value !== "object" || visited.has(value)) return value;
    visited.add(value);
    for (const child of Object.values(value)) deepFreeze(child, visited);
    return Object.freeze(value);
}

class PageSim {
    constructor(canvas) {
        this.canvas = canvas;
        this.renderer = null;
        this.previewPlacementByOwner = null;
        this.session = new WorkerSession();
        this.config = null;
        this.unitIndex = new Map();
        this.snapshots = [];
        this.cursor = 0;
        this.latestSnapshot = null;
        this.result = null;
        this.complete = false;
        this.playheadTick = 0;
        this.animationFrame = null;
        this.speedMultiplier = 1.0;
        this.state = "selecting";
        this.lastTimestamp = 0;
        this.resizeObserver = new ResizeObserver(() => this.renderer?.resize());
        this.resizeObserver.observe(canvas);
    }

    get running() { return this.state === "playing" || this.state === "paused"; }
    get paused() { return this.state === "paused"; }
    get winner() {
        return this.result?.winnerOwner ?? null;
    }

    setStatus(message, isError = false) {
        const element = document.getElementById("v3MapStatus");
        if (!element) return;
        element.textContent = message;
        element.classList.toggle("error", isError);
    }

    ensureRenderer(map) {
        if (this.renderer) return;
        this.renderer = createMapRenderer(
            this.canvas,
            map,
            {
                presentation: "production",
                unitScale: 0.9,
            },
        );
    }

    initializeArena({ map, placementByOwner }) {
        this.ensureRenderer(map);
        this.previewPlacementByOwner = placementByOwner;
        this.renderer.setUnits([]);
        this.renderer.resize();
    }

    showSelectionPreview(selections, images) {
        if (!this.renderer || !this.previewPlacementByOwner || this.running) return;
        const previewCounts = {
            1: Math.min(27, Math.max(1,
                parseInt(document.getElementById("team1Count")?.value, 10) || 27)),
            2: Math.min(27, Math.max(1,
                parseInt(document.getElementById("team2Count")?.value, 10) || 27)),
        };
        for (const teamNumber of [1, 2]) {
            this.renderer.setUnitAssets(teamNumber === 1 ? 2 : 3, {
                img: images[teamNumber],
                sheet: null,
            });
        }
        this.renderer.setUnits(buildSelectionPreviewUnits(
            selections,
            this.previewPlacementByOwner,
            previewCounts,
        ));
    }

    buildUnitIndex(config) {
        const index = new Map();
        const addArmy = (owner, team, count) => {
            const base = owner === 2 ? 9000 : owner === 3 ? 9500 : 10000;
            for (let offset = 0; offset < count; offset += 1) {
                index.set(base + offset, {
                    owner,
                    slug: team.mechanics.unit_slug,
                    label: team.unit_name,
                    master: team.mechanics.unit_master,
                    mechanics: team.mechanics,
                });
            }
        };
        addArmy(2, config.teams[0], config.teams[0].count);
        addArmy(3, config.teams[1], config.teams[1].count);
        const auxiliary = config.scenario.auxiliaryArmiesByOwner || {};
        for (const [ownerText, army] of Object.entries(auxiliary)) {
            const owner = Number(ownerText);
            addArmy(owner, {
                unit_name: army.unit_name || "Scout Cavalry",
                mechanics: army.mechanics,
            }, army.cells.length);
        }
        return index;
    }

    rendererSnapshot(snapshot) {
        const units = snapshot.units.map((row) => {
            const [referenceId, x, y, facing, hp, alive, action,
                pursuitTargetId, engagedTargetId, attackTargetId] = row;
            const meta = this.unitIndex.get(referenceId);
            if (!meta) throw new Error(`Missing unit metadata for ${referenceId}`);
            return {
                referenceId,
                x,
                y,
                facing,
                hp,
                alive: alive === 1,
                action,
                pursuitTargetId,
                engagedTargetId,
                attackTargetId,
                owner: meta.owner,
                slug: meta.slug,
                label: meta.label,
                unitMaster: meta.master,
                mechanics: meta.mechanics,
            };
        });
        return deepFreeze({
            tick: snapshot.tick,
            units,
            events: snapshot.events,
            ...(snapshot.navigation ? { navigation: snapshot.navigation } : {}),
        });
    }

    setup({ config, assets }) {
        this.stop();
        this.config = deepFreeze(config);
        this.unitIndex = this.buildUnitIndex(this.config);
        this.snapshots = [];
        this.cursor = 0;
        this.latestSnapshot = null;
        this.result = null;
        this.complete = false;
        this.playheadTick = 0;
        this.state = "loading";
        this.ensureRenderer(this.config.scenario.mapFixture.map);
        this.renderer.showFormation();
        this.renderer.setUnitAssets(2, assets[2]);
        this.renderer.setUnitAssets(3, assets[3]);
        if (assets[4]) this.renderer.setUnitAssets(4, assets[4]);
        this.renderer.resize();

        this.session.start(this.config, (data) => {
            if (data.type === "started") this.setStatus("Battle in progress");
            if (data.type === "snapshots") this.snapshots.push(...data.snapshots);
            if (data.type === "complete") {
                this.result = data.result;
                this.complete = true;
            }
            if (data.type === "error") {
                this.complete = true;
                this.state = "failed";
                this.setStatus(`Simulation error: ${data.error}`, true);
                syncPlayerControls();
            }
        });
        this.setStatus("Preparing battle…");
    }

    start() {
        if (!this.config) {
            alert("Please configure both teams");
            return;
        }
        this.state = "playing";
        this.lastTimestamp = performance.now();
        updateStats(null, this.unitIndex);
        syncPlayerControls();
        this.loop();
    }

    pause() {
        if (!this.running) return;
        this.state = this.paused ? "playing" : "paused";
        if (this.animationFrame !== null) cancelAnimationFrame(this.animationFrame);
        this.animationFrame = null;
        if (!this.paused) {
            this.lastTimestamp = performance.now();
            this.loop();
        }
        syncPlayerControls();
    }

    stop() {
        if (this.animationFrame !== null) cancelAnimationFrame(this.animationFrame);
        this.animationFrame = null;
        this.session.cancel();
        this.state = "selecting";
    }

    reset() {
        this.stop();
        this.config = null;
        this.snapshots = [];
        this.cursor = 0;
        this.latestSnapshot = null;
        this.result = null;
        this.complete = false;
        this.playheadTick = 0;
        updateStats(null);
        this.renderer?.showFormation();
        this.setStatus("Golden Arena ready");
        syncPlayerControls();
    }

    loop() {
        if (!this.running || this.paused) return;
        const now = performance.now();
        const elapsed = Math.min((now - this.lastTimestamp) / 1000, 0.25);
        this.lastTimestamp = now;
        if (this.cursor < this.snapshots.length || this.complete) {
            this.playheadTick += elapsed * this.speedMultiplier * 60;
        }
        while (
            this.cursor < this.snapshots.length
            && this.snapshots[this.cursor].tick <= this.playheadTick
        ) {
            this.latestSnapshot = this.snapshots[this.cursor];
            this.cursor += 1;
        }
        if (this.latestSnapshot) {
            const snapshot = this.rendererSnapshot(this.latestSnapshot);
            this.renderer.setSimulationSnapshot(snapshot);
            updateStats(snapshot, this.unitIndex);
        }
        if (this.complete && this.cursor >= this.snapshots.length && this.result) {
            this.state = "completed";
            updateBattleWinner(this.result.winnerOwner);
            const winningTeam = this.result.winnerOwner === 2 ? 1 : 2;
            const winner = this.config.teams[winningTeam - 1];
            const remaining = Math.round(this.result.winnerHp);
            this.setStatus(`${winner.civ} ${winner.unit_name} wins · ${remaining} HP remaining`);
            syncPlayerControls();
        } else {
            this.animationFrame = requestAnimationFrame(() => this.loop());
        }
    }

    render() {
        this.renderer?.resize();
    }
}


return PageSim;
}
