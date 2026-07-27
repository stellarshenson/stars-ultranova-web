/**
 * Stars Nova Web - Encyclopedia
 * In-game encyclopedia dialog: spatial phenomena entries with the
 * actual gameplay numbers (user directive 2026-07-13). Numbers mirror
 * backend/core/globals.py, turn_generator.py MINE_STATS, the Wormhole
 * drift model in server_data.py and the stargate catalog in
 * components.xml - update this text when those constants change.
 */

/**
 * Painterly artwork for encyclopedia entries (user directive 2026-07-13:
 * every phenomenon carries beautiful, hand-painted-feel imagery).
 * Deterministic procedural painting - seeded per entry id, no external
 * assets. Layered translucent brush strokes, gradient billows, grain
 * and vignette give the hand-painted look.
 */
const EncyclopediaArt = {
    paint(entryId, canvas) {
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        const rng = this._rng(this._hash(entryId));
        const painters = {
            'dust-nebulae': this._dustNebulae,
            'emission-nebulae': this._emissionNebulae,
            'storms': this._storms,
            'wormholes': this._wormholes,
            'minefields': this._minefields,
            'stargates': this._stargates,
            'mystery-trader': this._mysteryTrader,
            'mineral-packets': this._mineralPackets
        };
        (painters[entryId] || this._deepSpace).call(this, ctx, W, H, rng);
        this._grain(ctx, W, H, rng);
        this._vignette(ctx, W, H);
    },

    _hash(s) {
        let h = 2166136261;
        for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
        return h >>> 0;
    },

    _rng(seed) {
        let a = seed || 1;
        return () => {
            a |= 0; a = a + 0x6D2B79F5 | 0;
            let t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    },

    _wash(ctx, W, H, top, bottom) {
        const g = ctx.createLinearGradient(0, 0, 0, H);
        g.addColorStop(0, top);
        g.addColorStop(1, bottom);
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
    },

    _stars(ctx, W, H, rng, n, bright) {
        for (let i = 0; i < n; i++) {
            const x = rng() * W, y = rng() * H, r = rng() * 1.4 + 0.3;
            const a = rng() * 0.7 + 0.15;
            ctx.fillStyle = `rgba(220,228,255,${a})`;
            ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
            if (bright && rng() < 0.08) {
                ctx.strokeStyle = `rgba(230,238,255,${a * 0.5})`;
                ctx.lineWidth = 0.6;
                const s = r * 6;
                ctx.beginPath();
                ctx.moveTo(x - s, y); ctx.lineTo(x + s, y);
                ctx.moveTo(x, y - s); ctx.lineTo(x, y + s);
                ctx.stroke();
            }
        }
    },

    _cloud(ctx, x, y, r, rgb, alpha) {
        const g = ctx.createRadialGradient(x, y, 0, x, y, r);
        g.addColorStop(0, `rgba(${rgb},${alpha})`);
        g.addColorStop(1, `rgba(${rgb},0)`);
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    },

    // Chain of soft blobs along a wandering path - one billow bank.
    _billow(ctx, W, H, rng, palette, cx, cy, span, r, alpha) {
        let x = cx, y = cy, ang = rng() * 6.28;
        const steps = 14 + Math.floor(rng() * 10);
        for (let i = 0; i < steps; i++) {
            const rgb = palette[Math.floor(rng() * palette.length)];
            this._cloud(ctx, x, y, r * (0.6 + rng() * 0.8), rgb, alpha * (0.5 + rng() * 0.5));
            ang += (rng() - 0.5) * 1.2;
            x += Math.cos(ang) * span / steps;
            y += Math.sin(ang) * span / steps * 0.5;
        }
    },

    // Short curved brush strokes following a flow field - painterly texture.
    _strokes(ctx, W, H, rng, n, flow, colorFn, len, width) {
        for (let i = 0; i < n; i++) {
            let x = rng() * W, y = rng() * H;
            ctx.strokeStyle = colorFn(x, y, rng);
            ctx.lineWidth = width * (0.4 + rng());
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(x, y);
            const steps = 3 + Math.floor(rng() * 3);
            for (let s = 0; s < steps; s++) {
                const a = flow(x, y) + (rng() - 0.5) * 0.4;
                x += Math.cos(a) * len; y += Math.sin(a) * len;
                ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
    },

    _grain(ctx, W, H, rng) {
        for (let i = 0; i < 1600; i++) {
            const v = rng() < 0.5 ? '255,255,255' : '0,0,0';
            ctx.fillStyle = `rgba(${v},${rng() * 0.04})`;
            ctx.fillRect(rng() * W, rng() * H, 1.5, 1.5);
        }
    },

    _vignette(ctx, W, H) {
        const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.5, W / 2, H / 2, W * 0.75);
        g.addColorStop(0, 'rgba(0,0,0,0)');
        g.addColorStop(1, 'rgba(0,0,10,0.55)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
    },

    _deepSpace(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#070a18', '#0b0714');
        this._stars(ctx, W, H, rng, 220, true);
    },

    _dustNebulae(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#0a0d1e', '#120c14');
        this._stars(ctx, W, H, rng, 260, true);
        // Dark occluding banks with faint warm rim light
        const dark = ['26,20,34', '18,14,26', '34,24,28'];
        for (let i = 0; i < 7; i++) {
            this._billow(ctx, W, H, rng, dark,
                rng() * W, H * (0.45 + rng() * 0.5), W * 0.5, 70 + rng() * 60, 0.5);
        }
        const warm = ['120,82,52', '90,60,44'];
        for (let i = 0; i < 3; i++) {
            this._billow(ctx, W, H, rng, warm,
                rng() * W, H * (0.35 + rng() * 0.3), W * 0.3, 34 + rng() * 26, 0.10);
        }
        this._strokes(ctx, W, H, rng, 260, () => 0.05, (x, y, r) =>
            `rgba(30,24,40,${0.05 + r() * 0.09})`, 26, 5);
    },

    _emissionNebulae(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#0a0716', '#140a1c');
        this._stars(ctx, W, H, rng, 160, false);
        ctx.globalCompositeOperation = 'lighter';
        const glow = ['176,58,120', '42,138,138', '106,58,160', '192,96,48'];
        for (let i = 0; i < 9; i++) {
            this._billow(ctx, W, H, rng, glow,
                W * (0.15 + rng() * 0.7), H * (0.25 + rng() * 0.55),
                W * 0.35, 55 + rng() * 55, 0.16);
        }
        this._strokes(ctx, W, H, rng, 300, (x, y) =>
            Math.sin(x / 140) * 0.8, (x, y, r) =>
            `rgba(${glow[Math.floor(r() * glow.length)]},${0.05 + r() * 0.08})`, 22, 4);
        ctx.globalCompositeOperation = 'source-over';
        this._stars(ctx, W, H, rng, 60, true);
    },

    _storms(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#0d0514', '#1c0a18');
        this._stars(ctx, W, H, rng, 120, false);
        const cx = W * 0.52, cy = H * 0.5;
        ctx.globalCompositeOperation = 'lighter';
        // Swirling vortex strokes around the core
        const swirl = (x, y) => Math.atan2(y - cy, x - cx) + Math.PI / 2 + 0.35;
        const storm = ['106,42,74', '160,48,80', '70,28,60', '200,90,70'];
        this._strokes(ctx, W, H, rng, 420, swirl, (x, y, r) => {
            const d = Math.hypot(x - cx, y - cy) / (H * 0.9);
            const a = Math.max(0, 0.16 - d * 0.12) + r() * 0.05;
            return `rgba(${storm[Math.floor(r() * storm.length)]},${a})`;
        }, 30, 5);
        this._cloud(ctx, cx, cy, H * 0.42, '255,128,96', 0.30);
        this._cloud(ctx, cx, cy, H * 0.18, '255,190,150', 0.5);
        // Red lightning forks
        ctx.globalCompositeOperation = 'source-over';
        for (let b = 0; b < 3; b++) {
            let x = cx + (rng() - 0.5) * H * 0.5, y = cy + (rng() - 0.5) * H * 0.4;
            ctx.strokeStyle = `rgba(255,66,66,${0.5 + rng() * 0.3})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath(); ctx.moveTo(x, y);
            for (let s = 0; s < 6; s++) {
                x += (rng() - 0.4) * 44; y += (rng() - 0.45) * 34;
                ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
        // Dashed red boundary hint - the storm's map signature
        ctx.strokeStyle = 'rgba(255,64,64,0.5)';
        ctx.lineWidth = 1.6;
        ctx.setLineDash([7, 6]);
        ctx.beginPath();
        for (let i = 0; i <= 40; i++) {
            const a = i / 40 * Math.PI * 2;
            const r = H * 0.62 * (1 + 0.16 * Math.sin(a * 3 + 1.7) + 0.10 * Math.sin(a * 5));
            const px = cx + Math.cos(a) * r * 1.25, py = cy + Math.sin(a) * r * 0.8;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.stroke();
        ctx.setLineDash([]);
    },

    _wormholes(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#060a1c', '#0a0616');
        this._stars(ctx, W, H, rng, 200, true);
        const cx = W * 0.5, cy = H * 0.52;
        ctx.globalCompositeOperation = 'lighter';
        // Spiral tunnel strokes drawn inward to a bright throat
        const spiral = (x, y) => Math.atan2(y - cy, x - cx) + Math.PI / 2 + 0.55;
        const hole = ['58,90,192', '122,154,255', '42,58,128', '150,120,220'];
        this._strokes(ctx, W, H, rng, 480, spiral, (x, y, r) => {
            const d = Math.hypot((x - cx) * 0.8, (y - cy) * 1.3) / (H * 0.8);
            const a = Math.max(0, 0.18 - d * 0.13) + r() * 0.04;
            return `rgba(${hole[Math.floor(r() * hole.length)]},${a})`;
        }, 26, 4);
        for (let ring = 6; ring >= 1; ring--) {
            ctx.strokeStyle = `rgba(122,154,255,${0.05 + (6 - ring) * 0.02})`;
            ctx.lineWidth = 5;
            ctx.beginPath();
            ctx.ellipse(cx, cy, ring * H * 0.075 * 1.5, ring * H * 0.075, 0.15, 0, 7);
            ctx.stroke();
        }
        this._cloud(ctx, cx, cy, H * 0.16, '210,225,255', 0.85);
        this._cloud(ctx, cx, cy, H * 0.34, '122,154,255', 0.30);
        ctx.globalCompositeOperation = 'source-over';
    },

    _minefields(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#04100e', '#071410');
        this._stars(ctx, W, H, rng, 150, false);
        const cx = W * 0.5, cy = H * 0.52, R = H * 0.72;
        this._cloud(ctx, cx, cy, R, '20,60,50', 0.22);
        // The sown field - hundreds of glinting mines in a disc
        for (let i = 0; i < 240; i++) {
            const a = rng() * Math.PI * 2, d = Math.sqrt(rng()) * R;
            const x = cx + Math.cos(a) * d * 1.55, y = cy + Math.sin(a) * d * 0.72;
            if (x < 0 || x > W || y < 0 || y > H) continue;
            const hostile = rng() < 0.12;
            const c = hostile ? '255,90,80' : '140,230,190';
            const al = 0.35 + rng() * 0.6, s = 1 + rng() * 2.2;
            ctx.fillStyle = `rgba(${c},${al})`;
            ctx.beginPath(); ctx.arc(x, y, s * 0.55, 0, 7); ctx.fill();
            ctx.strokeStyle = `rgba(${c},${al * 0.5})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(x - s * 2, y); ctx.lineTo(x + s * 2, y);
            ctx.moveTo(x, y - s * 2); ctx.lineTo(x, y + s * 2);
            ctx.stroke();
        }
        ctx.strokeStyle = 'rgba(140,230,190,0.28)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([4, 8]);
        ctx.beginPath(); ctx.ellipse(cx, cy, R * 1.55, R * 0.72, 0, 0, 7); ctx.stroke();
        ctx.setLineDash([]);
    },

    _stargates(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#080a1a', '#100a14');
        this._stars(ctx, W, H, rng, 220, true);
        const cx = W * 0.5, cy = H * 0.52, rx = H * 0.58, ry = H * 0.42, tilt = -0.28;
        ctx.globalCompositeOperation = 'lighter';
        // Event horizon inside the ring - gradient built in the
        // transformed space so it fills the tilted ellipse correctly
        ctx.save();
        ctx.translate(cx, cy); ctx.rotate(tilt); ctx.scale(1, ry / rx);
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx * 0.92);
        g.addColorStop(0, 'rgba(150,225,255,0.7)');
        g.addColorStop(0.5, 'rgba(80,140,225,0.3)');
        g.addColorStop(1, 'rgba(30,50,120,0)');
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(0, 0, rx * 0.92, 0, 7); ctx.fill();
        // Rippled surface strokes across the horizon
        for (let i = 0; i < 60; i++) {
            const rr = rng() * rx * 0.85, aa = rng() * Math.PI * 2;
            ctx.strokeStyle = `rgba(140,200,255,${0.05 + rng() * 0.10})`;
            ctx.lineWidth = 1 + rng() * 2;
            ctx.beginPath();
            ctx.arc(0, 0, rr, aa, aa + 0.5 + rng());
            ctx.stroke();
        }
        ctx.restore();
        // The golden ring, layered strokes for a burnished feel
        for (const [w, a] of [[9, 0.25], [5, 0.5], [2.2, 0.9]]) {
            ctx.strokeStyle = `rgba(235,190,90,${a})`;
            ctx.lineWidth = w;
            ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, tilt, 0, 7); ctx.stroke();
        }
        // Structural chevrons around the ring, each with a warm glow
        ctx.globalCompositeOperation = 'source-over';
        for (let i = 0; i < 9; i++) {
            const a = i / 9 * Math.PI * 2 + 0.3;
            const px = cx + Math.cos(a) * rx * Math.cos(tilt) - Math.sin(a) * ry * Math.sin(tilt);
            const py = cy + Math.cos(a) * rx * Math.sin(tilt) + Math.sin(a) * ry * Math.cos(tilt);
            this._cloud(ctx, px, py, 14, '255,190,90', 0.55);
            ctx.fillStyle = 'rgba(255,224,150,1)';
            ctx.beginPath(); ctx.arc(px, py, 5, 0, 7); ctx.fill();
        }
        this._cloud(ctx, cx, cy, H * 0.16, '190,235,255', 0.6);
    },

    _mysteryTrader(ctx, W, H, rng) {
        // An enigmatic lone ship, warm running lights against deep
        // space - a long dark hull trailing a curved golden wake
        this._wash(ctx, W, H, '#04061a', '#0e0a16');
        this._stars(ctx, W, H, rng, 260, true);
        // Cold deep-space billows below, one warm distant bank above
        this._billow(ctx, W, H, rng, ['26,34,72', '36,28,64'],
                     W * 0.22, H * 0.78, W * 0.5, H * 0.20, 0.10);
        this._billow(ctx, W, H, rng, ['110,74,44', '96,52,52'],
                     W * 0.80, H * 0.18, W * 0.34, H * 0.15, 0.07);

        // Ship position and heading (upper right, climbing gently)
        const sx = W * 0.66, sy = H * 0.42, ang = -0.16;
        const cosA = Math.cos(ang), sinA = Math.sin(ang);

        // Curved golden wake: warm strokes along a quadratic arc from
        // the lower left up to the hull, brightening toward the ship
        const ax = W * 0.04, ay = H * 0.80;
        const cxq = W * 0.38, cyq = H * 0.72;
        const q = (t, a, c, b) =>
            (1 - t) * (1 - t) * a + 2 * (1 - t) * t * c + t * t * b;
        const warm = ['255,214,120', '255,178,84', '214,128,60',
                      '255,236,190'];
        ctx.globalCompositeOperation = 'lighter';
        for (let i = 0; i < 150; i++) {
            const t = Math.min(1, rng() * 1.04);
            const x = q(t, ax, cxq, sx) + (rng() - 0.5) * 18 * (1 - t);
            const y = q(t, ay, cyq, sy) + (rng() - 0.5) * 18 * (1 - t);
            const dx = 2 * (1 - t) * (cxq - ax) + 2 * t * (sx - cxq);
            const dy = 2 * (1 - t) * (cyq - ay) + 2 * t * (sy - cyq);
            const len = Math.hypot(dx, dy) || 1;
            const step = (5 + rng() * 14) * (0.4 + t);
            const rgb = warm[Math.floor(rng() * warm.length)];
            ctx.strokeStyle = `rgba(${rgb},${0.05 + rng() * 0.14 + t * 0.22})`;
            ctx.lineWidth = 0.6 + rng() * 1.8 + t * 1.4;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(x - dx / len * step, y - dy / len * step);
            ctx.lineTo(x, y);
            ctx.stroke();
        }
        // Soft golden halo announcing the ship
        this._cloud(ctx, sx, sy, H * 0.26, '255,206,120', 0.22);
        this._cloud(ctx, sx, sy, H * 0.12, '255,224,160', 0.30);

        // The hull: a long dark silhouette over the glow
        ctx.globalCompositeOperation = 'source-over';
        const hullL = W * 0.16, hullH = H * 0.045;
        ctx.save();
        ctx.translate(sx, sy);
        ctx.rotate(ang);
        const hg = ctx.createLinearGradient(0, -hullH, 0, hullH);
        hg.addColorStop(0, 'rgba(34,30,44,0.98)');
        hg.addColorStop(0.55, 'rgba(18,16,26,0.98)');
        hg.addColorStop(1, 'rgba(8,8,14,0.98)');
        ctx.fillStyle = hg;
        ctx.beginPath();
        ctx.moveTo(-hullL * 0.55, 0);
        ctx.quadraticCurveTo(-hullL * 0.2, -hullH * 1.4, hullL * 0.45, -hullH * 0.5);
        ctx.quadraticCurveTo(hullL * 0.62, 0, hullL * 0.45, hullH * 0.5);
        ctx.quadraticCurveTo(-hullL * 0.2, hullH * 1.4, -hullL * 0.55, 0);
        ctx.closePath();
        ctx.fill();
        // Warm rim light along the upper edge
        ctx.strokeStyle = 'rgba(255,206,130,0.55)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(-hullL * 0.5, -hullH * 0.15);
        ctx.quadraticCurveTo(-hullL * 0.2, -hullH * 1.25, hullL * 0.45, -hullH * 0.45);
        ctx.stroke();
        ctx.restore();

        // Warm running lights: a line of glowing gold dots along the
        // hull, each with its own soft bloom
        ctx.globalCompositeOperation = 'lighter';
        for (let i = 0; i < 7; i++) {
            const t = i / 6 - 0.5;
            const lx = sx + cosA * hullL * 0.9 * t;
            const ly = sy + sinA * hullL * 0.9 * t + hullH * 0.15;
            this._cloud(ctx, lx, ly, 7 + rng() * 4, '255,214,130',
                        0.5 + rng() * 0.3);
            ctx.fillStyle = 'rgba(255,244,210,0.95)';
            ctx.beginPath(); ctx.arc(lx, ly, 1.4 + rng() * 0.8, 0, 7);
            ctx.fill();
        }
        // The stern drive: a brighter ember where the wake meets the hull
        this._cloud(ctx, sx - cosA * hullL * 0.55,
                    sy - sinA * hullL * 0.55, H * 0.05,
                    '255,190,100', 0.9);
        ctx.globalCompositeOperation = 'source-over';
    },

    _mineralPackets(ctx, W, H, rng) {
        this._wash(ctx, W, H, '#060812', '#140b06');
        this._stars(ctx, W, H, rng, 210, true);
        // Destination planet disc, lower right, lit from the packet's
        // side
        const px = W * 0.84, py = H * 0.62, pr = H * 0.30;
        const pg = ctx.createRadialGradient(
            px - pr * 0.5, py - pr * 0.5, pr * 0.1, px, py, pr);
        pg.addColorStop(0, 'rgba(150,170,205,0.95)');
        pg.addColorStop(0.6, 'rgba(70,90,130,0.9)');
        pg.addColorStop(1, 'rgba(20,28,50,0.9)');
        ctx.fillStyle = pg;
        ctx.beginPath(); ctx.arc(px, py, pr, 0, 7); ctx.fill();
        this._cloud(ctx, px, py, pr * 1.5, '90,120,180', 0.18);
        // The mineral slug: a molten streak arcing from the upper
        // left toward the planet - layered warm strokes along a
        // quadratic path with seeded jitter
        const sx = W * 0.06, sy = H * 0.30;
        const cxq = W * 0.45, cyq = H * 0.02;
        const hx = px - pr * 0.85, hy = py - pr * 0.75;
        const q = (t, a, c, b) =>
            (1 - t) * (1 - t) * a + 2 * (1 - t) * t * c + t * t * b;
        const warm = ['255,214,120', '255,160,60', '230,100,35',
                      '255,235,190'];
        ctx.globalCompositeOperation = 'lighter';
        for (let i = 0; i < 130; i++) {
            const t = Math.min(1, rng() * 1.04);
            const x = q(t, sx, cxq, hx) + (rng() - 0.5) * 14 * (1 - t);
            const y = q(t, sy, cyq, hy) + (rng() - 0.5) * 14 * (1 - t);
            // Tangent of the arc at t drives the stroke direction
            const dx = 2 * (1 - t) * (cxq - sx) + 2 * t * (hx - cxq);
            const dy = 2 * (1 - t) * (cyq - sy) + 2 * t * (hy - cyq);
            const len = Math.hypot(dx, dy) || 1;
            const step = (6 + rng() * 18) * (0.5 + t);
            const rgb = warm[Math.floor(rng() * warm.length)];
            ctx.strokeStyle = `rgba(${rgb},${0.08 + rng() * 0.25 + t * 0.25})`;
            ctx.lineWidth = 0.8 + rng() * 2.6 + t * 2.2;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(x - dx / len * step, y - dy / len * step);
            ctx.lineTo(x, y);
            ctx.stroke();
        }
        // Sparks shed along the tail
        for (let i = 0; i < 40; i++) {
            const t = rng();
            const x = q(t, sx, cxq, hx) + (rng() - 0.5) * 30;
            const y = q(t, sy, cyq, hy) + (rng() - 0.5) * 30;
            ctx.fillStyle = `rgba(255,220,150,${0.15 + rng() * 0.5})`;
            ctx.beginPath(); ctx.arc(x, y, 0.5 + rng() * 1.6, 0, 7);
            ctx.fill();
        }
        // White-hot head bearing down on the planet
        this._cloud(ctx, hx, hy, H * 0.13, '255,190,110', 0.75);
        this._cloud(ctx, hx, hy, H * 0.06, '255,245,220', 0.95);
        ctx.globalCompositeOperation = 'source-over';
    }
};

const Encyclopedia = {
    /**
     * Static entry catalog. Each entry: id, title, html content.
     */
    ENTRIES: [
        {
            id: 'dust-nebulae',
            title: 'Dust Nebulae',
            html: `
                <p>Cold, lightless banks of interstellar dust. Beautiful
                on the charts - miserable to fly through. Dust drag
                fouls engine intakes and its haze blinds sensors; the
                thicker the dust, the worse both get.</p>
                <ul>
                    <li><b>Ship speed</b> - reduced by up to 40% in the
                        densest dust, scaled by the average dust density
                        (0 to 1) along the flight path. Speed never
                        drops below 60% of the ordered warp.</li>
                    <li><b>Scanners</b> - range cut by up to 50%, scaled
                        by the dust density at the scanner's
                        position.</li>
                    <li>Only dark dust nebulae have these effects -
                        glowing emission nebulae are harmless.</li>
                </ul>`
        },
        {
            id: 'emission-nebulae',
            title: 'Emission Nebulae',
            html: `
                <p>Vast clouds of luminous gas set aglow by the young
                stars within. Spectacular - and not quite harmless:
                all that glow washes out your sensors.</p>
                <ul>
                    <li><b>Sensor glare</b> - scanner range cut by up
                        to 15%, scaled by the emission density at the
                        scanner's position. Far milder than dust, but
                        it compounds with any dust or storm
                        penalty.</li>
                    <li><b>No drag</b> - ship speed is unaffected;
                        only dark dust nebulae slow travel.</li>
                    <li><b>Storm nurseries</b> - galactic storms
                        preferentially brew inside nebulae (about 70%
                        of storms spawn there). Treat a glowing sky as
                        a weather warning.</li>
                </ul>`
        },
        {
            id: 'storms',
            title: 'Galactic Storms',
            html: `
                <p>Roaming electromagnetic tempests, drifting a little
                further across the charts every year. A storm is an
                irregular blob with a calm rim and a murderous core:
                the local intensity is zero at the boundary and ramps
                smoothly up to the storm's full strength at the center.
                Every effect below scales with the local intensity at
                your fleet's position.</p>
                <ul>
                    <li><b>Hull damage</b> - 20% armor damage per year
                        at full local intensity. Ships reaching 100%
                        damage are destroyed.</li>
                    <li><b>Warp risk</b> - warp 6 is safe. Each warp
                        above adds a 10% mishap chance (times local
                        intensity), capped at 75%. A mishap deals 25%
                        extra damage (times local intensity) and stops
                        the fleet dead in the storm.</li>
                    <li><b>Scanners</b> - up to 70% range loss at a
                        storm core - stronger than dust, and it
                        compounds with any dust penalty.</li>
                    <li><b>Colonists</b> - passengers in cargo holds
                        suffer 10% attrition per year at full local
                        intensity (always at least 100 colonists).</li>
                    <li><b>Safe harbor</b> - storms never touch planets,
                        nor any fleet or starbase in orbit of one: a
                        planet's magnetosphere shelters everything
                        parked there. Only fleets in open space suffer
                        storm effects.</li>
                </ul>
                <p><b>Protection.</b> Ships can be hardened against
                storms; the sources below add up and cap at 100% (total
                immunity). A fleet is only as protected as its weakest
                ship, and protection scales down hull damage, warp
                mishap chance and damage, and colonist attrition alike.
                It does not clear the sensor static: a scanner inside a
                storm always scans worse.</p>
                <ul>
                    <li><b>Storm shields</b> - dedicated components in
                        shield slots: Storm Deflector 40% (Propulsion 6,
                        Energy 6), Storm Barrier 70% (Prop 12, Energy
                        12), Storm Bulwark 100% (Prop 18, Energy 18) -
                        the top tier alone grants total immunity. Only
                        the best tier aboard counts.</li>
                    <li><b>Conventional shields</b> - any regular
                        shields aboard add 35%.</li>
                    <li><b>Armor plates</b> - fitted armor components
                        add 15% (a bare hull does not count).</li>
                    <li><b>Radiation-hardened races</b> - races immune
                        to radiation, or with a radiation optimum in
                        the extreme band (85+), add 25% fleet-wide.</li>
                </ul>`
        },
        {
            id: 'wormholes',
            title: 'Wormholes',
            html: `
                <p>Twin tears in spacetime, joined at the hip. Fly into
                one end and you are spat out of the other - however
                many hundred light years away that happens to be.</p>
                <ul>
                    <li><b>Discovery</b> - an endpoint is charted the
                        moment it comes within range of any of your
                        scanners, and stays on your charts forever
                        after.</li>
                    <li><b>Drift</b> - endpoints wander every year, up
                        to 1-4 ly per axis: the less stable the
                        wormhole, the further it drifts (drift = 1 + 3
                        x (1 - stability)).</li>
                    <li><b>Transit</b> - set a waypoint on an endpoint
                        and fly into it (within 5 ly). The fleet is
                        pulled through instantly and emerges at the far
                        end - no fuel spent, regardless of
                        distance.</li>
                </ul>`
        },
        {
            id: 'minefields',
            title: 'Minefields',
            html: `
                <p>Sown by minelaying ships and lethal to anyone in a
                hurry. Creep through at the field's safe warp and the
                mines ignore you; run faster and every light year is a
                dice roll.</p>
                <ul>
                    <li><b>Standard mines</b> - safe warp 4. Above it,
                        0.3% strike chance per light year travelled in
                        the field, per warp over safe. A strike deals
                        100 damage per ship (minimum 500 to the
                        fleet).</li>
                    <li><b>Heavy mines</b> - safe warp 6; 1.0% per
                        light year per warp over; 50 damage per ship
                        (minimum 2,000 to the fleet).</li>
                    <li><b>Speed trap mines</b> - safe warp 5; 3.5% per
                        light year per warp over; no damage - the fleet
                        is simply stopped.</li>
                    <li>Your own fields never trigger. Any strike stops
                        the fleet dead; at most one strike per fleet
                        per year.</li>
                </ul>`
        },
        {
            id: 'stargates',
            title: 'Stargates',
            html: `
                <p>Starbase-mounted jump gates, powered by the star
                they orbit. Order warp 10 between two of your own
                gated starbases and the fleet arrives the same year,
                spending no fuel at all - provided the gate will take
                it.</p>
                <ul>
                    <li><b>Requirements</b> - both the origin and the
                        destination star need your own starbase with a
                        stargate fitted.</li>
                    <li><b>Hull size</b> - only small and medium hulls
                        may gate. Small: Scout, Frigate, Destroyer,
                        Colony Ships, Small Freighter, Fuel Transport,
                        Mini Mine Layer, Midget Miner, Mini Bomber.
                        Medium: Cruiser, Privateer, Rogue, Medium
                        Freighter, Super-Fuel Transport, Mini Miner,
                        Miner, Super Mine Layer, Stealth and B-17
                        Bombers, Meta Morph. Everything larger - Battle
                        Cruiser, Battleship, Dreadnought, Nubian,
                        Galleon, Large and Super Freighters, B-52
                        Bomber, Maxi and Ultra Miners - is refused
                        outright: no gamble, the heavies fly
                        conventionally.</li>
                    <li><b>Star-fuelled range</b> - a gate's reach is
                        its model's safe range times the host star's
                        spectral factor: O x2.0, B x1.6, A x1.3,
                        F x1.1, G x1.0, K x0.8, M x0.6. "Any"-range
                        models cap at 800 ly before the factor - no
                        gate is unlimited. The tighter limit of the
                        two gates applies (safe mass likewise).</li>
                    <li><b>Cargo</b> - mineral cargo never gates:
                        unload it or ship it by freighter or mass
                        driver. Colonists aboard gate only for
                        Interstellar Traveler races; fuel always
                        travels free.</li>
                    <li><b>Over the limits</b> - a small or medium
                        ship over the safe mass, or jumping beyond the
                        range, has a 25% chance of being torn apart in
                        transit; survivors arrive with 50% extra
                        damage.</li>
                </ul>`
        },
        {
            id: 'mystery-trader',
            title: 'The Mystery Trader',
            html: `
                <p>An enigmatic vessel that answers no hail and fears
                no weapon. From mid-game on it enters at a galaxy edge,
                crosses in a straight line at impossible speed, and
                leaves the far side. Meet it with a generous gift and
                it may part with technology no laboratory will ever
                reproduce.</p>
                <ul>
                    <li><b>Schedule</b> - may appear from year 2140
                        (40 years in); a 1-in-16 chance each year while
                        none is present. From year 2200 up to three
                        traders may cross at once.</li>
                    <li><b>Course</b> - enters on a random edge, exits
                        the opposite edge, straight line at warp 7-13
                        (warp&sup2; ly per year - often faster than
                        anything you can build).</li>
                    <li><b>Universal visibility</b> - every empire sees
                        the trader and its projected course from the
                        moment it spawns, no scanners needed; arrival
                        and departure are announced to all.</li>
                    <li><b>Untouchable</b> - it cannot be attacked,
                        mined, or harmed by storms, and it never
                        initiates hostilities.</li>
                    <li><b>Intercept</b> - set the trader itself as a
                        waypoint target; the intercept course is
                        recomputed every year as it moves. At its
                        position, use the fleet Gift action.</li>
                    <li><b>Gifts</b> - minerals or colonists only, one
                        way; the trader always keeps the cargo. Your
                        running total per trader must reach 1000 kT
                        for any reward; below that you get a courteous
                        nod and nothing else. Each empire's gifts are
                        tracked separately - simultaneous intercepts
                        resolve independently.</li>
                    <li><b>Rewards by total gift G</b> -
                        1000-1999 kT: 40% trader component, 30%
                        research boost (+1 level in 2 fields), 30%
                        mineral bounty (2 x G kT loaded onto your
                        fleet, fuel topped to full).
                        2000-3999 kT: 50% component, 25% research
                        (+1 in 4 fields), 15% minerals (3 x G), 10%
                        gifted warship.
                        4000+ kT: 55% component, 20% research (+2 in
                        3 fields), 25% gifted warship (a Trader
                        Marauder - armor 2000, shields 800, four
                        Anti-Matter Torpedo batteries).</li>
                    <li><b>Hidden technology</b> - trader items can
                        never be researched (tech requirement zero,
                        catalog-hidden until granted): Multi-Function
                        Pod (Electrical, 2 kT - 30 cloak, 10% jamming,
                        +&frac14; battle movement), Anti-Matter
                        Torpedo (8 kT - power 60, range 6, accuracy
                        85%), Mega Poly Shell (20 kT - 100 shield, 400
                        armor, 20 cloak, 80/40 ly scanner), Genesis
                        Device (10 kT - a legendary artifact; its
                        world-remaking power still sleeps). Once
                        granted, the item appears in your component
                        catalog and your shipyards may build it; each
                        item is granted at most once.</li>
                    <li><b>Game setting</b> - the "Mystery Trader"
                        toggle at game creation turns the visitor off
                        entirely (default on).</li>
                </ul>`
        },
        {
            id: 'mineral-packets',
            title: 'Mineral Packets and Mass Drivers',
            html: `
                <p>Interstellar freight without the freighter. A
                starbase-mounted mass driver hurls a slug of raw
                minerals straight at another star at relativistic
                speed. A matching driver at the far end catches it
                gently; anything less, and the packet arrives as a
                weapon.</p>
                <ul>
                    <li><b>Drivers</b> - Orbital components for
                        starbase slots: Mass Driver 5/6 (Energy 4/7),
                        Super Driver 7/8/9 (Energy 7/11/13), Ultra
                        Driver 10/11/12/13 (Energy 15/17/20/24). The
                        number is the driver's warp rating; two equal
                        drivers operate one warp higher.</li>
                    <li><b>Flinging</b> - pick a mineral mix (kT) from
                        the planet's surface, a target star and a
                        warp from the driver's rating up to 3 over
                        (never above warp 13). The packet flies in a
                        straight line at warp&sup2; ly per year, needs
                        no fuel and cannot change course.</li>
                    <li><b>Overfling decay</b> - 1/2/3 warp over the
                        rating loses 10%/25%/50% of each mineral per
                        year in flight (at least 10 kT per mineral).
                        At the rated warp packets fly forever
                        undiminished.</li>
                    <li><b>Catch</b> - a receiving driver at or above
                        the packet's warp lands every kT on the
                        surface, harmlessly.</li>
                    <li><b>Impact</b> - otherwise the caught fraction
                        is receiverWarp&sup2;/packetWarp&sup2;, one
                        third of the rest is still recovered, and the
                        planet takes damage = (packetWarp&sup2; -
                        receiverWarp&sup2;) x kT / 160, reduced by
                        defense coverage. Colonists killed = max(dmg x
                        pop / 1000, dmg x 100); defenses destroyed =
                        max(defenses x dmg / 1000, dmg / 20).
                        Uninhabited targets just collect the recovered
                        minerals.</li>
                    <li><b>In flight</b> - packets are visible,
                        scannable objects. Any fleet that reaches one
                        may load (steal) minerals straight out of it;
                        an emptied packet vanishes.</li>
                </ul>`
        }
    ],

    /**
     * Open the encyclopedia dialog, optionally at a specific entry.
     * @param {string} entryId - Entry to show (defaults to the first)
     */
    open(entryId) {
        if (!window.Dialogs) return;

        const listHtml = this.ENTRIES.map(entry => `
            <li class="encyclopedia-entry" data-entry="${entry.id}">
                ${entry.title}
            </li>
        `).join('');

        const html = `
            <div class="dialog-header">
                <h2>Encyclopedia</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>
            <div class="dialog-body encyclopedia-layout">
                <ul class="encyclopedia-list">${listHtml}</ul>
                <div class="encyclopedia-content" id="encyclopedia-content"></div>
            </div>
            <div class="dialog-footer">
                <button class="btn-primary" onclick="Dialogs.close()">Close</button>
            </div>
        `;

        Dialogs.show(html);

        // Widen the standard dialog for the two-pane layout
        document.querySelector('#dialog-overlay .dialog-content')
            ?.classList.add('encyclopedia-dialog');

        document.querySelectorAll('.encyclopedia-entry').forEach(item => {
            item.addEventListener('click', () => {
                this.select(item.dataset.entry);
            });
        });

        this.select(entryId || this.ENTRIES[0].id);
    },

    /**
     * Show an entry in the content pane and highlight it in the list.
     * @param {string} entryId - Entry identifier
     */
    select(entryId) {
        const entry = this.ENTRIES.find(e => e.id === entryId)
            || this.ENTRIES[0];

        document.querySelectorAll('.encyclopedia-entry').forEach(item => {
            item.classList.toggle('active', item.dataset.entry === entry.id);
        });

        const content = document.getElementById('encyclopedia-content');
        if (content) {
            content.innerHTML = `<h3>${entry.title}</h3>` +
                `<canvas class="encyclopedia-art" id="encyclopedia-art"` +
                ` width="1200" height="360"></canvas>${entry.html}`;
            const art = document.getElementById('encyclopedia-art');
            if (art) EncyclopediaArt.paint(entry.id, art);
        }
    }
};

// Export
window.Encyclopedia = Encyclopedia;
