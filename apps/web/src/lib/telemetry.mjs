import {isPublicHost} from './site-policy.mjs';
import {operation} from './operations.mjs';

const id = 'G-MYNEW08LBR';
const publicPage = () => isPublicHost(location.hostname)
    && !location.pathname.startsWith('/migration-review/')
    && window[`ga-disable-${id}`] !== true;
const stages = new Set(['configuration_ready', 'configuration_error', 'worker_ready',
    'first_frame', 'simulation_error', 'media_error']);

if (publicPage()) {
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    const url = new URL(location.origin + location.pathname);
    // Retain campaign attribution without ever transmitting protection credentials
    // or arbitrary query values. The existing Analytics property stays unchanged.
    for (const key of ['utm_source','utm_medium','utm_campaign','utm_content','utm_term']) {
        if (new URL(location.href).searchParams.has(key))
            url.searchParams.set(key, new URL(location.href).searchParams.get(key).slice(0, 100));
    }
    window.gtag('js', new Date());
    window.gtag('config', id, {page_location:url.href,
        page_referrer:document.referrer ? new URL(document.referrer).origin : ''});
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
    document.head.append(script);
}

let sent = 0;
window.addEventListener('aoe2-operation', ({detail}) => {
    if (!publicPage() || !stages.has(detail?.stage) || sent >= 20
        || !Number.isFinite(detail.duration_ms) || typeof window.gtag !== 'function') return;
    sent += 1;
    // Recheck exclusion at send time, including a test flag set after initialization.
    window.gtag('event', 'aoe2_operation', {stage:detail.stage,
        duration_ms:detail.duration_ms, non_interaction:true});
});
document.addEventListener('error', event => {
    if (event.target instanceof HTMLImageElement) operation('media_error');
}, true);
