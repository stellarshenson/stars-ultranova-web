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
            'stargates': this._stargates
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
                stars within. Spectacular, and entirely harmless: they
                impose no drag on ships and no penalty on scanners.</p>
                <ul>
                    <li><b>No gameplay effect</b> - travel and scanning
                        proceed at full capability.</li>
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
                    <li><b>Shelter</b> - starbases are immune, sheltered
                        in their planet's magnetosphere.</li>
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
                <p>Starbase-mounted jump gates. Order warp 10 between
                two of your own gated starbases and the fleet arrives
                the same year, spending no fuel at all - provided it
                fits through the gate.</p>
                <ul>
                    <li><b>Requirements</b> - both the origin and the
                        destination star need your own starbase with a
                        stargate fitted.</li>
                    <li><b>Limits</b> - every gate model has a safe
                        hull mass (kT) and a safe range (ly); the
                        tighter limit of the two gates applies. Models:
                        100/250, any/300, 150/600, 100/any, any/800
                        and any/any (mass/range, "any" =
                        unlimited).</li>
                    <li><b>Over the limits</b> - each over-limit ship
                        has a 25% chance of being torn apart in
                        transit; survivors arrive with 50% extra
                        damage.</li>
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
