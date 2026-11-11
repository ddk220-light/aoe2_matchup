/** Owns exactly one worker. Cancellation invalidates already queued events. */
export class WorkerSession {
    constructor(createWorker = () => new Worker("/static/js/v3_sim_worker.js", {type:"module"})) {
        this.createWorker = createWorker;
        this.worker = null;
        this.generation = 0;
    }
    cancel() {
        this.generation += 1;
        this.worker?.terminate();
        this.worker = null;
    }
    start(config, onMessage) {
        this.cancel();
        const runId = this.generation;
        const worker = this.createWorker();
        this.worker = worker;
        const deliver = data => {
            if (runId !== this.generation || worker !== this.worker || data?.runId !== runId) return;
            if (data.type === "complete" || data.type === "error") {
                worker.terminate();
                this.worker = null;
            }
            onMessage(data);
        };
        worker.onmessage = ({data}) => deliver(data);
        worker.onerror = event => deliver({type:"error", runId, error:event.message || "Worker failed to load"});
        worker.postMessage({runId, config});
    }
}
