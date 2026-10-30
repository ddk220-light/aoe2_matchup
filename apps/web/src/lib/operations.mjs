// Measurements contain stage and duration only; never unit choices, URLs or error text.
export function operation(stage, durationMs = 0) {
    if (typeof window === 'undefined') return;
    window.dispatchEvent(new CustomEvent('aoe2-operation', {detail:{
        stage, duration_ms: Math.max(0, Math.round(durationMs)),
    }}));
}
