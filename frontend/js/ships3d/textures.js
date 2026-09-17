// Canvas texture baker for the ship model compiler. Bakes a PBR texture set
// (albedo, normal-from-height, combined occlusion-roughness-metalness,
// emissives) from the seeded rng, so the compiled glb carries its full
// surface detail with it. Browser-only (needs 2d canvas); the compiler
// skips this module entirely when textures are disabled.

import * as THREE from '../../vendor/three/build/three.module.js';

function makeCanvas(size) {
    const c = document.createElement('canvas');
    c.width = size; c.height = size;
    return c;
}

function tex(canvas, srgb) {
    const t = new THREE.CanvasTexture(canvas);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.flipY = false; // glTF convention, keeps compile preview and reload identical
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.needsUpdate = true;
    return t;
}

// Recursive panel split: returns list of {x, y, w, h} rects covering the canvas.
function splitPanels(rng, x, y, w, h, minSize, out) {
    if (w < minSize || h < minSize || (w < minSize * 1.8 && h < minSize * 1.8 && rng.chance(0.55))) {
        out.push({ x, y, w, h });
        return out;
    }
    const vertical = w > h ? true : (h > w ? false : rng.chance(0.5));
    const t = rng.range(0.35, 0.65);
    if (vertical) {
        const wa = Math.floor(w * t);
        splitPanels(rng, x, y, wa, h, minSize, out);
        splitPanels(rng, x + wa, y, w - wa, h, minSize, out);
    } else {
        const ha = Math.floor(h * t);
        splitPanels(rng, x, y, w, ha, minSize, out);
        splitPanels(rng, x, y + ha, w, h - ha, minSize, out);
    }
    return out;
}

// Sobel a grayscale height canvas into a tangent-space normal map.
function normalFromHeight(heightCanvas, strength) {
    const S = heightCanvas.width;
    const src = heightCanvas.getContext('2d').getImageData(0, 0, S, S);
    const out = makeCanvas(S);
    const ctx = out.getContext('2d');
    const dst = ctx.createImageData(S, S);
    const h = (x, y) => src.data[(((y + S) % S) * S + ((x + S) % S)) * 4];
    for (let y = 0; y < S; y++) {
        for (let x = 0; x < S; x++) {
            const dx = (h(x - 1, y - 1) + 2 * h(x - 1, y) + h(x - 1, y + 1)
                - h(x + 1, y - 1) - 2 * h(x + 1, y) - h(x + 1, y + 1)) / 1020;
            const dy = (h(x - 1, y - 1) + 2 * h(x, y - 1) + h(x + 1, y - 1)
                - h(x - 1, y + 1) - 2 * h(x, y + 1) - h(x + 1, y + 1)) / 1020;
            const nx = dx * strength, ny = dy * strength, nz = 1;
            const inv = 1 / Math.sqrt(nx * nx + ny * ny + nz * nz);
            const i = (y * S + x) * 4;
            dst.data[i] = Math.round((nx * inv * 0.5 + 0.5) * 255);
            dst.data[i + 1] = Math.round((ny * inv * 0.5 + 0.5) * 255);
            dst.data[i + 2] = Math.round((nz * inv * 0.5 + 0.5) * 255);
            dst.data[i + 3] = 255;
        }
    }
    ctx.putImageData(dst, 0, 0);
    return out;
}

// --- armour set -------------------------------------------------------------

const ARMOR_DEFAULTS = {
    armorBase: [59, 64, 70],
    paint: ['rgba(96,58,48,0.5)', 'rgba(70,76,56,0.5)', 'rgba(46,50,60,0.55)'],
    paintChance: 0.09, rustChance: 0.35, grimeMul: 1.0,
};

export function bakeArmorSet(rng, size = 1024, palette = {}) {
    const pal = { ...ARMOR_DEFAULTS, ...palette };
    const [br, bg, bb] = pal.armorBase;
    const S = size;
    const panels = splitPanels(rng, 0, 0, S, S, Math.floor(S / 13), []);

    const albedo = makeCanvas(S), height = makeCanvas(S), mr = makeCanvas(S);
    const a = albedo.getContext('2d'), hc = height.getContext('2d'), m = mr.getContext('2d');

    a.fillStyle = `rgb(${br},${bg},${bb})`; a.fillRect(0, 0, S, S);
    hc.fillStyle = 'rgb(128,128,128)'; hc.fillRect(0, 0, S, S);
    // ORM: R occlusion (255 = none), G roughness, B metalness
    m.fillStyle = 'rgb(255,150,215)'; m.fillRect(0, 0, S, S);

    for (const p of panels) {
        const j = rng.int(-9, 9);
        a.fillStyle = `rgb(${br + j},${bg + j},${bb + j})`;
        a.fillRect(p.x, p.y, p.w, p.h);
        const hv = 128 + rng.int(-7, 7);
        hc.fillStyle = `rgb(${hv},${hv},${hv})`;
        hc.fillRect(p.x, p.y, p.w, p.h);
        m.fillStyle = `rgb(255,${150 + rng.int(-18, 18)},${215 + rng.int(-12, 8)})`;
        m.fillRect(p.x, p.y, p.w, p.h);
        // occasional painted panel: rougher, less metallic
        if (rng.chance(pal.paintChance)) {
            const col = rng.pick(pal.paint);
            a.fillStyle = col; a.fillRect(p.x, p.y, p.w, p.h);
            m.fillStyle = 'rgba(255,195,120,0.6)'; m.fillRect(p.x, p.y, p.w, p.h);
        }
        // worn bright edge on two sides of some panels
        if (rng.chance(0.5)) {
            a.strokeStyle = 'rgba(168,176,186,0.35)'; a.lineWidth = 1.2;
            a.beginPath(); a.moveTo(p.x + 1, p.y + p.h - 1); a.lineTo(p.x + 1, p.y + 1); a.lineTo(p.x + p.w - 1, p.y + 1); a.stroke();
            m.strokeStyle = 'rgba(255,90,255,0.5)'; m.lineWidth = 1.2;
            m.beginPath(); m.moveTo(p.x + 1, p.y + p.h - 1); m.lineTo(p.x + 1, p.y + 1); m.lineTo(p.x + p.w - 1, p.y + 1); m.stroke();
        }
    }
    // seams: dark grooves in albedo and height
    for (const p of panels) {
        a.strokeStyle = 'rgba(14,16,18,0.85)'; a.lineWidth = 2;
        a.strokeRect(p.x + 1, p.y + 1, p.w - 2, p.h - 2);
        hc.strokeStyle = 'rgb(58,58,58)'; hc.lineWidth = 3;
        hc.strokeRect(p.x + 1, p.y + 1, p.w - 2, p.h - 2);
        hc.strokeStyle = 'rgb(158,158,158)'; hc.lineWidth = 1;
        hc.strokeRect(p.x + 3, p.y + 3, p.w - 6, p.h - 6);
    }
    // rivet rows along some panel edges
    for (const p of panels) {
        if (!rng.chance(0.55)) continue;
        const n = Math.max(2, Math.floor(p.w / 26));
        for (let i = 0; i < n; i++) {
            const x = p.x + 10 + (i * (p.w - 20)) / Math.max(1, n - 1);
            for (const y of [p.y + 8, p.y + p.h - 8]) {
                hc.fillStyle = 'rgb(176,176,176)';
                hc.beginPath(); hc.arc(x, y, 2.2, 0, Math.PI * 2); hc.fill();
                a.fillStyle = 'rgba(20,22,25,0.6)';
                a.beginPath(); a.arc(x, y, 1.6, 0, Math.PI * 2); a.fill();
            }
        }
    }
    // grime streaks
    for (let i = 0; i < Math.floor((S / 12) * pal.grimeMul); i++) {
        const x = rng.range(0, S), y = rng.range(0, S * 0.8);
        const len = rng.range(S * 0.05, S * 0.3), w = rng.range(2, 9);
        const grad = a.createLinearGradient(0, y, 0, y + len);
        const col = rng.chance(pal.rustChance) ? '106,66,40' : '18,20,24';
        grad.addColorStop(0, `rgba(${col},${rng.range(0.1, 0.3)})`);
        grad.addColorStop(1, `rgba(${col},0)`);
        a.fillStyle = grad; a.fillRect(x, y, w, len);
        m.fillStyle = 'rgba(255,220,140,0.18)'; m.fillRect(x, y, w, len);
    }
    // scratches
    for (let i = 0; i < Math.floor(S / 14); i++) {
        const x = rng.range(0, S), y = rng.range(0, S);
        const dx = rng.range(-40, 40), dy = rng.range(-14, 14);
        a.strokeStyle = `rgba(178,186,196,${rng.range(0.1, 0.3)})`;
        a.lineWidth = 0.8;
        a.beginPath(); a.moveTo(x, y); a.lineTo(x + dx, y + dy); a.stroke();
    }
    // hazard chevrons in one region, heavily worn
    if (true) {
        const p = panels[rng.int(0, panels.length - 1)];
        a.save();
        a.beginPath(); a.rect(p.x, p.y, p.w, p.h); a.clip();
        a.globalAlpha = 0.30;
        for (let x = p.x - p.h; x < p.x + p.w + p.h; x += 22) {
            a.fillStyle = '#b09a3a';
            a.beginPath();
            a.moveTo(x, p.y + p.h); a.lineTo(x + 11, p.y + p.h);
            a.lineTo(x + 11 + p.h, p.y); a.lineTo(x + p.h, p.y);
            a.closePath(); a.fill();
        }
        a.restore();
    }
    // stencil markings
    a.font = `${Math.floor(S / 42)}px monospace`;
    for (let i = 0; i < 7; i++) {
        const code = `${rng.pick(['DV', 'BK', 'AX', 'MK'])}-${rng.int(10, 99)}${rng.int(0, 9)}`;
        a.fillStyle = `rgba(190,198,206,${rng.range(0.25, 0.5)})`;
        a.fillText(code, rng.range(0, S * 0.9), rng.range(20, S));
    }

    return {
        map: tex(albedo, true),
        normalMap: tex(normalFromHeight(height, 2.2), false),
        mrMap: tex(mr, false),
    };
}

// --- trim set (engraved bronze) --------------------------------------------

export function bakeTrimSet(rng, size = 512, palette = {}) {
    const S = size;
    const albedo = makeCanvas(S), height = makeCanvas(S), mr = makeCanvas(S);
    const a = albedo.getContext('2d'), hc = height.getContext('2d'), m = mr.getContext('2d');
    a.fillStyle = palette.trimBase || '#78633c'; a.fillRect(0, 0, S, S);
    hc.fillStyle = 'rgb(128,128,128)'; hc.fillRect(0, 0, S, S);
    m.fillStyle = 'rgb(255,95,255)'; m.fillRect(0, 0, S, S);
    // banded engraving: rows of notches and studs
    const band = S / 8;
    for (let by = 0; by < 8; by++) {
        const y0 = by * band;
        const motif = by % 2 === 0;
        for (let x = 0; x < S; x += 32) {
            if (motif) {
                // engraved rectangle
                hc.fillStyle = 'rgb(78,78,78)';
                hc.fillRect(x + 6, y0 + band * 0.22, 20, band * 0.56);
                a.fillStyle = 'rgba(40,32,16,0.55)';
                a.fillRect(x + 6, y0 + band * 0.22, 20, band * 0.56);
                m.fillStyle = 'rgba(255,170,255,0.7)';
                m.fillRect(x + 6, y0 + band * 0.22, 20, band * 0.56);
            } else {
                // raised stud
                hc.fillStyle = 'rgb(198,198,198)';
                hc.beginPath(); hc.arc(x + 16, y0 + band / 2, band * 0.18, 0, Math.PI * 2); hc.fill();
                a.fillStyle = 'rgba(160,140,90,0.8)';
                a.beginPath(); a.arc(x + 16, y0 + band / 2, band * 0.18, 0, Math.PI * 2); a.fill();
            }
        }
        hc.fillStyle = 'rgb(96,96,96)'; hc.fillRect(0, y0, S, 2);
        a.fillStyle = 'rgba(30,24,12,0.6)'; a.fillRect(0, y0, S, 2);
    }
    // tarnish
    for (let i = 0; i < 220; i++) {
        a.fillStyle = `rgba(52,40,22,${rng.range(0.04, 0.16)})`;
        a.fillRect(rng.range(0, S), rng.range(0, S), rng.range(4, 40), rng.range(3, 14));
    }
    return {
        map: tex(albedo, true),
        normalMap: tex(normalFromHeight(height, 2.0), false),
        mrMap: tex(mr, false),
    };
}

// --- emissives --------------------------------------------------------------

export function bakeWindowEmissive(rng, size = 512) {
    const S = size;
    const c = makeCanvas(S);
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, S, S);
    const rows = 16, wh = 14, ww = 7, gap = 5;
    for (let r = 0; r < rows; r++) {
        const y = (r + 0.5) * (S / rows) - wh / 2;
        for (let x = 4; x < S - ww; x += ww + gap) {
            if (rng.chance(0.28)) continue; // dark cabin
            const warm = rng.chance(0.75);
            ctx.fillStyle = warm
                ? `rgba(255,${rng.int(200, 224)},${rng.int(140, 170)},1)`
                : `rgba(${rng.int(190, 215)},${rng.int(220, 235)},255,1)`;
            ctx.fillRect(x, y, ww, wh);
        }
    }
    return tex(c, true);
}

export function bakeEngineGlow(size = 128, pal = {}) {
    const S = size;
    const stops = pal.glowStops || ['#ffffff', '#cfeaff', '#5aa8e8', '#02040a'];
    const c = makeCanvas(S);
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, S, S);
    const g = ctx.createRadialGradient(S / 2, S / 2, 2, S / 2, S / 2, S / 2);
    g.addColorStop(0, stops[0]);
    g.addColorStop(0.25, stops[1]);
    g.addColorStop(0.6, stops[2]);
    g.addColorStop(1, stops[3]);
    ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
    return tex(c, true);
}

export function bakeRadiatorEmissive(size = 256) {
    const S = size;
    const c = makeCanvas(S);
    const ctx = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, S, 0);
    g.addColorStop(0, '#ff9440');
    g.addColorStop(0.5, '#c33d10');
    g.addColorStop(1, '#1a0602');
    ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
    // fin shadow lines
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    for (let y = 0; y < S; y += 9) ctx.fillRect(0, y, S, 3);
    return tex(c, true);
}
