// Team A (team 1) is drawn in blue player colour, Team B (team 2) in red.
// Idle sprites ship as both red (`url`) and blue (`url_blue`) renders, but the
// attack sprite-sheets only exist in red. Without a blue sheet a Team A unit
// would flash red every time its attack animation plays, so the sheet is
// recoloured client-side: saturated red player-colour pixels get the hue of
// the blue renders (~232deg), keeping their saturation and brightness.
// Presentation only: nothing here touches the simulation.

const BLUE_HUE = 232 / 360;

/** Recolour red player-colour pixels in RGBA `data` (Uint8ClampedArray) in place. */
export function recolourRedToBlue(data) {
    for (let i = 0; i < data.length; i += 4) {
        if (data[i + 3] === 0) continue;
        const r = data[i] / 255, g = data[i + 1] / 255, b = data[i + 2] / 255;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        if (max !== r || max < 0.12) continue;
        const delta = max - min;
        const s = delta / max;
        if (s < 0.5) continue;
        // Hue of a red-dominant pixel, in degrees (-60..60).
        const hue = 60 * (g - b) / delta;
        if (hue > 18 || hue < -20) continue;
        const [nr, ng, nb] = hsvToRgb(BLUE_HUE, s, max);
        data[i] = nr; data[i + 1] = ng; data[i + 2] = nb;
    }
    return data;
}

function hsvToRgb(h, s, v) {
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
    const [r, g, b] = [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i % 6];
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

/**
 * Returns an <img> that will hold a blue-player-colour copy of the red sheet at
 * `url`. Until the copy is ready (or if it cannot be made) the image stays
 * empty, and the arena keeps drawing the blue idle sprite instead.
 */
export function blueSheetImage(url) {
    const out = new Image();
    const raw = new Image();
    raw.crossOrigin = 'anonymous';
    raw.addEventListener('load', () => {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = raw.naturalWidth;
            canvas.height = raw.naturalHeight;
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            ctx.drawImage(raw, 0, 0);
            const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
            recolourRedToBlue(pixels.data);
            ctx.putImageData(pixels, 0, 0);
            canvas.toBlob(blob => { if (blob) out.src = URL.createObjectURL(blob); }, 'image/png');
        } catch {
            // Cross-origin or decode failure: no attack animation for this team.
        }
    }, { once: true });
    raw.src = url;
    return out;
}
