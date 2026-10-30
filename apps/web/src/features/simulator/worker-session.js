/** Owns exactly one worker. Cancellation invalidates already queued events. */
import {catalog} from './catalog.mjs';
import {operation} from '../../lib/operations.mjs';
export class WorkerSession {
    constructor(createWorker = () => new Worker(catalog.engine_worker_url, {type:"module"})) {
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
        const started = performance.now();
        const worker = this.createWorker();
        this.worker = worker;
        const deliver = data => {
            if (runId !== this.generation || worker !== this.worker || data?.runId !== runId) return;
            if (data.type === 'started') {
                performance.mark('aoe2-worker-ready');
                operation('worker_ready', performance.now() - started);
            }
            if (data.type === 'error') operation('simulation_error', performance.now() - started);
            if (data.type === 'complete') performance.mark('aoe2-compute-complete');
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
