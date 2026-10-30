/** Shared HTTP boundary. No page globals; callers own cancellation. */
export async function requestJson(url, {method = "GET", body, signal, timeoutMs = 10000} = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort(signal?.reason);
    if (signal?.aborted) abort();
    else signal?.addEventListener("abort", abort, {once:true});
    const timeout = setTimeout(() => controller.abort(new Error("Request timed out")), timeoutMs);
    try {
        const response = await fetch(url, {
            method, signal:controller.signal,
            ...(body === undefined ? {} : {headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)}),
        });
        const data = await response.json();
        if (!response.ok || data?.error) throw new Error(data?.detail || data?.error || `HTTP ${response.status}`);
        return data;
    } finally {
        clearTimeout(timeout);
        signal?.removeEventListener("abort", abort);
    }
}

/** Only the latest request may publish, even if an abort races its response. */
export class LatestRequest {
    sequence = 0;
    controller = null;
    cancel() { this.sequence += 1; this.controller?.abort(); this.controller = null; }
    begin() {
        this.cancel();
        const sequence = this.sequence;
        this.controller = new AbortController();
        return {signal:this.controller.signal, isCurrent:() => sequence === this.sequence};
    }
}
