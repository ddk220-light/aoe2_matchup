import {LatestRequest, requestJson} from './api.js';

export function createPageData() {
    const request = new LatestRequest();
    const cache = new Map();
    return {
        async select(url, bootstrap) {
            const ticket = request.begin();
            const data = bootstrap || cache.get(url) || await requestJson(url, {signal:ticket.signal});
            if (!ticket.isCurrent()) return null;
            cache.set(url, data);
            return data;
        },
        cancel: () => request.cancel(),
        detail: url => requestJson(url),
    };
}
