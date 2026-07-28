/**
 * Stars Nova Web - procedural planet art
 *
 * Per-pixel sphere renderer for the star panel planet graphic, built to
 * the specification in docs/research-planet-rendering.md. Sibling of
 * EncyclopediaArt (encyclopedia.js) and reuses its seeded primitives:
 * _hash (FNV-1a), _rng (mulberry32), _cloud, _grain and _vignette.
 *
 * Structure, not recolouring, is what makes worlds differ: nine classes
 * pick different generators (warped fBm continents, ridged canyons,
 * Worley craters, Worley ice fractures, emissive lava fissures, warped
 * latitude bands with storm ovals), and colour is a two-axis
 * (elevation, moisture) palette lookup rather than a temperature ramp.
 *
 * Deterministic: every per-world parameter is drawn from one mulberry32
 * generator seeded on the star id, in a fixed order. Math.random is
 * never used. Rendered bitmaps are cached per star id and environment.
 */
const PlanetArt = {

    CACHE_MAX: 60,
    cache: new Map(),
    lastRenderMs: 0,

    /**
     * Class table. Each entry carries the lighting constants and the
     * (elevation, moisture) palette; `d` is the dry stop colour, `w` the
     * wet one, and `cold` is what the palette blends toward past the
     * world's ice latitude.
     */
    CLASSES: {
        terran: {
            gen: 'rocky', sea: true, ridge: 'mountain', clouds: true,
            caps: 1, redistScale: 1,
            k: 0.70, penumbra: 0.13, wrap: true, specPower: 150,
            rim: '130,180,255', rimAlpha: 0.32, haze: 0,
            cold: [234, 241, 250],
            stops: [
                { e: 0.00, d: [14, 34, 78], w: [7, 23, 64] },
                { e: 0.22, d: [30, 82, 132], w: [20, 64, 118] },
                { e: 0.30, d: [214, 198, 146], w: [186, 180, 132] },
                { e: 0.44, d: [152, 150, 92], w: [54, 108, 52] },
                { e: 0.62, d: [122, 106, 66], w: [40, 86, 46] },
                { e: 0.80, d: [124, 112, 98], w: [96, 104, 88] },
                { e: 1.00, d: [188, 184, 178], w: [220, 226, 230] }
            ]
        },
        tundra: {
            gen: 'rocky', sea: true, ridge: 'mountain', clouds: true,
            caps: 1, redistScale: 1,
            k: 0.72, penumbra: 0.11, wrap: true, specPower: 170,
            rim: '150,190,235', rimAlpha: 0.26, haze: 0,
            cold: [228, 236, 244],
            stops: [
                { e: 0.00, d: [24, 46, 68], w: [15, 36, 58] },
                { e: 0.24, d: [48, 76, 96], w: [34, 64, 88] },
                { e: 0.30, d: [140, 136, 118], w: [118, 122, 110] },
                { e: 0.46, d: [106, 114, 88], w: [58, 84, 64] },
                { e: 0.64, d: [92, 96, 84], w: [46, 70, 56] },
                { e: 0.82, d: [142, 142, 138], w: [152, 160, 160] },
                { e: 1.00, d: [218, 224, 230], w: [230, 236, 242] }
            ]
        },
        desert: {
            gen: 'rocky', sea: false, ridge: 'canyon', clouds: false,
            caps: 0.8, redistScale: 0.6,
            k: 0.66, penumbra: 0.10, wrap: true, specPower: 0,
            rim: '230,180,120', rimAlpha: 0.22, haze: 0.20,
            hazeColor: [206, 168, 118],
            cold: [236, 228, 214],
            stops: [
                { e: 0.00, d: [96, 56, 34], w: [116, 80, 50] },
                { e: 0.25, d: [146, 92, 50], w: [154, 114, 72] },
                { e: 0.45, d: [186, 130, 76], w: [174, 138, 94] },
                { e: 0.66, d: [208, 164, 104], w: [190, 158, 116] },
                { e: 0.86, d: [224, 194, 148], w: [206, 182, 148] },
                { e: 1.00, d: [240, 222, 190], w: [224, 208, 184] }
            ]
        },
        ice: {
            gen: 'rocky', sea: false, ridge: 'none', clouds: true,
            crack: true, caps: 0.35, redistScale: 0.5,
            k: 0.78, penumbra: 0.09, wrap: false, specPower: 200,
            rim: '180,215,255', rimAlpha: 0.30, haze: 0,
            cold: [255, 255, 255],
            stops: [
                { e: 0.00, d: [140, 168, 196], w: [124, 156, 188] },
                { e: 0.30, d: [190, 210, 230], w: [176, 202, 226] },
                { e: 0.60, d: [222, 236, 248], w: [210, 228, 244] },
                { e: 0.85, d: [240, 248, 255], w: [230, 242, 252] },
                { e: 1.00, d: [252, 254, 255], w: [246, 250, 255] }
            ]
        },
        volcanic: {
            gen: 'rocky', sea: false, ridge: 'fissure', clouds: false,
            lava: true, caps: 0.25, redistScale: 0.7,
            k: 0.70, penumbra: 0.07, wrap: false, specPower: 0,
            rim: '255,140,70', rimAlpha: 0.26, haze: 0,
            cold: [96, 88, 82],
            stops: [
                { e: 0.00, d: [26, 20, 20], w: [38, 30, 26] },
                { e: 0.30, d: [48, 38, 34], w: [60, 48, 38] },
                { e: 0.56, d: [74, 58, 44], w: [98, 76, 44] },
                { e: 0.78, d: [130, 98, 44], w: [160, 126, 54] },
                { e: 1.00, d: [188, 160, 74], w: [208, 184, 98] }
            ]
        },
        barren: {
            gen: 'rocky', sea: false, ridge: 'none', clouds: false,
            craters: true, caps: 0, redistScale: 0.25,
            k: 0.82, penumbra: 0.03, wrap: false, specPower: 0,
            rim: '0,0,0', rimAlpha: 0, haze: 0,
            cold: [206, 206, 206],
            stops: [
                { e: 0.00, d: [56, 54, 52], w: [46, 45, 45] },
                { e: 0.35, d: [92, 90, 88], w: [80, 80, 80] },
                { e: 0.60, d: [126, 124, 120], w: [112, 112, 110] },
                { e: 0.85, d: [158, 156, 152], w: [144, 144, 142] },
                { e: 1.00, d: [188, 186, 182], w: [172, 172, 170] }
            ]
        },
        radiated: {
            gen: 'rocky', sea: false, ridge: 'none', clouds: false,
            craters: true, caps: 0, redistScale: 0.25,
            k: 0.80, penumbra: 0.04, wrap: false, specPower: 0,
            rim: '235,110,235', rimAlpha: 0.20, haze: 0,
            cold: [216, 198, 216],
            stops: [
                { e: 0.00, d: [52, 34, 56], w: [44, 29, 49] },
                { e: 0.35, d: [96, 58, 96], w: [84, 52, 88] },
                { e: 0.60, d: [132, 84, 128], w: [118, 74, 116] },
                { e: 0.85, d: [168, 120, 158], w: [150, 108, 146] },
                { e: 1.00, d: [198, 162, 188], w: [182, 150, 176] }
            ]
        },
        toxic: {
            gen: 'rocky', sea: false, ridge: 'none', clouds: true,
            shear: true, caps: 0, redistScale: 0.4,
            k: 0.35, penumbra: 0.28, wrap: true, specPower: 0,
            rim: '245,225,150', rimAlpha: 0.40, haze: 0.45,
            hazeColor: [236, 226, 168],
            cold: [238, 236, 220],
            stops: [
                { e: 0.00, d: [166, 144, 72], w: [178, 158, 90] },
                { e: 0.35, d: [196, 178, 104], w: [206, 190, 120] },
                { e: 0.60, d: [216, 202, 138], w: [224, 212, 152] },
                { e: 0.85, d: [232, 222, 170], w: [236, 228, 184] },
                { e: 1.00, d: [242, 236, 200], w: [244, 240, 210] }
            ]
        },
        gas: {
            gen: 'gas', sea: false, ridge: 'none', clouds: false,
            k: 0.55, penumbra: 0.24, wrap: true, specPower: 0,
            rim: '210,200,180', rimAlpha: 0.34, haze: 0,
            cold: [222, 228, 236],
            // warm (Jovian) and cold (Uranian) band ramps; the world's
            // temperature picks which one drives the latitude lookup
            bandsWarm: [
                [206, 176, 130], [150, 108, 70], [232, 216, 190],
                [186, 132, 78], [240, 228, 206], [166, 122, 88],
                [214, 190, 148], [128, 92, 62]
            ],
            bandsCold: [
                [148, 178, 200], [96, 128, 160], [206, 224, 236],
                [122, 156, 186], [226, 238, 246], [110, 140, 172],
                [176, 202, 220], [86, 116, 150]
            ],
            stops: []
        }
    },

    // ---------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------

    /**
     * Draw the planet for `star` onto `canvas`. Cached per star id and
     * environment, so terraforming or colonisation re-renders and
     * everything else is a single drawImage.
     */
    render(canvas, star) {
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);
        if (!W || !H) return;

        const key = this._cacheKey(star, W, H);
        let bitmap = this.cache.get(key);
        if (bitmap) {
            // refresh LRU position
            this.cache.delete(key);
            this.cache.set(key, bitmap);
        } else {
            bitmap = document.createElement('canvas');
            bitmap.width = W;
            bitmap.height = H;
            this._paint(bitmap, star);
            this.cache.set(key, bitmap);
            while (this.cache.size > this.CACHE_MAX) {
                this.cache.delete(this.cache.keys().next().value);
            }
        }
        ctx.drawImage(bitmap, 0, 0);
    },

    /**
     * Pick the planet class from the world's environment. Thresholds
     * follow the class table in docs/research-planet-rendering.md.
     */
    classify(star) {
        const env = this._env(star);
        const t = env.temperature, r = env.radiation, g = env.gravity;
        if (g >= 88) return 'gas';
        if (r > 80 && t >= 78) return 'toxic';
        if (t >= 72) return 'volcanic';
        if (r > 80 && t < 40) return 'radiated';
        if (r > 70) return 'toxic';
        if (t < 22) return 'ice';
        if (g < 30) return 'barren';
        if (t >= 58) return 'desert';
        if (t < 42) return 'tundra';
        if (env.habitability >= 40) return 'terran';
        return 'desert';
    },

    // ---------------------------------------------------------------
    // Environment, seeding and per-world parameters
    // ---------------------------------------------------------------

    _env(star) {
        const gravity = star.gravity != null ? star.gravity : 50;
        const temperature = star.temperature != null ? star.temperature : 50;
        const radiation = star.radiation != null ? star.radiation : 50;
        let hab = star.habitability;
        if (hab == null) {
            const penalty = (Math.abs(gravity - 50) + Math.abs(temperature - 50)
                + Math.abs(radiation - 50)) / 3;
            hab = Math.max(-45, Math.min(100, 100 - penalty * 2));
        }
        return {
            gravity, temperature, radiation,
            habitability: hab,
            spectral: star.spectral_class || 'G',
            colonized: (star.colonists || 0) > 0
        };
    },

    _seedKey(star) {
        return String(star.id != null ? star.id : (star.name || 'world'));
    },

    _cacheKey(star, W, H) {
        const env = this._env(star);
        // the starbase belongs in the key: build or lose a station and the
        // cached bitmap must be discarded, or the orbit never changes
        const base = star ? (star.starbase_hull || star.starbase_name || '') : '';
        return `${this._seedKey(star)}|${W}x${H}|${env.gravity}|`
            + `${env.temperature}|${env.radiation}|${env.colonized ? 1 : 0}`
            + `|${base}`;
    },

    /**
     * The fifteen per-world parameters, drawn in a FIXED order so a star
     * always looks identical. Three of them are then correlated with the
     * environment (ice latitude with temperature, cloud cover with
     * habitability, hue jitter with the host star's spectral class).
     */
    _params(env, cls, spec, rng) {
        const p = {};
        p.rotationPhase = rng() * Math.PI * 2;
        p.axialTilt = (rng() - 0.5) * 1.22;
        p.lightAngle = (200 + rng() * 140) * Math.PI / 180;
        p.hurstH = 0.6 + rng() * 0.4;
        p.warpAmount = 0.4 + rng() * 2.6;
        p.noiseScale = 1.6 + rng() * 2.4;
        p.seaLevel = 0.32 + rng() * 0.30;
        p.redistExponent = 1.0 + rng() * 2.5;
        p.cloudCover = rng() * 0.75;
        p.iceLatitude = 0.45 + rng() * 0.50;
        p.mountainStrength = rng() * 0.5;
        p.hueJitter = (rng() - 0.5) * 24;
        p.bandCount = 6 + Math.floor(rng() * 11);
        p.stormCount = Math.floor(rng() * 7);
        p.craterDensity = 0.3 + rng() * 0.7;

        // correlate three of them with the game state
        p.iceLatitude = Math.max(0.06, Math.min(1.30,
            0.08 + env.temperature / 100 * 1.05 + (p.iceLatitude - 0.70) * 0.35));
        p.cloudCover = spec.clouds
            ? Math.max(0, Math.min(0.80,
                Math.max(0, env.habitability) / 100 * 0.55 + p.cloudCover * 0.40))
            : 0;
        p.hueJitter += this.SPECTRAL_HUE[env.spectral] || 0;

        p.gain = Math.pow(2, -p.hurstH);
        p.octaves = 5;

        if (cls === 'gas') {
            p.storms = [];
            for (let i = 0; i < p.stormCount; i++) {
                p.storms.push({
                    lon: (rng() * 2 - 1) * Math.PI,
                    lat: (rng() * 2 - 1) * 0.72,
                    rx: 0.22 + rng() * 0.45,
                    ry: 0.05 + rng() * 0.10,
                    spin: (rng() < 0.5 ? -1 : 1) * (1.4 + rng() * 2.6),
                    tint: rng()
                });
            }
        }
        return p;
    },

    // Warmer palettes around cool stars, cooler ones around hot stars.
    SPECTRAL_HUE: { O: -14, B: -10, A: -6, F: -2, G: 0, K: 6, M: 12 },

    // ---------------------------------------------------------------
    // Value noise, fBm, ridged fBm and Worley cells
    // ---------------------------------------------------------------

    /** 512-entry permutation table shuffled from the world's own rng. */
    _perm(rng) {
        const p = new Uint8Array(256);
        for (let i = 0; i < 256; i++) p[i] = i;
        for (let i = 255; i > 0; i--) {
            const j = Math.floor(rng() * (i + 1));
            const t = p[i]; p[i] = p[j]; p[j] = t;
        }
        const perm = new Uint8Array(512);
        for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
        return perm;
    },

    /** 3D value noise with Perlin's quintic fade, 0..1. */
    _noise3(perm, x, y, z) {
        const X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z);
        const fx = x - X, fy = y - Y, fz = z - Z;
        const xi = X & 255, yi = Y & 255, zi = Z & 255;
        const u = fx * fx * fx * (fx * (fx * 6 - 15) + 10);
        const v = fy * fy * fy * (fy * (fy * 6 - 15) + 10);
        const w = fz * fz * fz * (fz * (fz * 6 - 15) + 10);
        const a = perm[xi], b = perm[xi + 1];
        const aa = perm[a + yi], ab = perm[a + yi + 1];
        const ba = perm[b + yi], bb = perm[b + yi + 1];
        const c000 = perm[aa + zi], c001 = perm[aa + zi + 1];
        const c010 = perm[ab + zi], c011 = perm[ab + zi + 1];
        const c100 = perm[ba + zi], c101 = perm[ba + zi + 1];
        const c110 = perm[bb + zi], c111 = perm[bb + zi + 1];
        const x00 = c000 + (c100 - c000) * u;
        const x10 = c010 + (c110 - c010) * u;
        const x01 = c001 + (c101 - c001) * u;
        const x11 = c011 + (c111 - c011) * u;
        const y0 = x00 + (x10 - x00) * v;
        const y1 = x01 + (x11 - x01) * v;
        return (y0 + (y1 - y0) * w) / 255;
    },

    /** fBm with gain G = 2^-H, normalized to 0..1. */
    _fbm3(perm, x, y, z, octaves, gain) {
        let f = 1, a = 1, t = 0, norm = 0;
        for (let i = 0; i < octaves; i++) {
            t += a * this._noise3(perm, x * f, y * f, z * f);
            norm += a;
            f *= 2; a *= gain;
        }
        return t / norm;
    },

    /** Ridged multifractal - creases at the zero crossings, 0..1. */
    _ridged3(perm, x, y, z, octaves, gain) {
        let f = 1, a = 1, t = 0, norm = 0, prev = 1;
        for (let i = 0; i < octaves; i++) {
            let n = this._noise3(perm, x * f, y * f, z * f) * 2 - 1;
            n = 1 - Math.abs(n);
            n *= n;
            t += a * n * prev;
            norm += a;
            prev = Math.min(1, n * 1.5);
            f *= 2; a *= gain;
        }
        return t / norm;
    },

    /**
     * Worley F1 distance over the 27 neighbouring cells. The second
     * distance is left in _worleyF2 for cell-border (fracture) work,
     * which avoids allocating a result pair per pixel.
     */
    _worleyF2: 0,

    _worley3(x, y, z, seed) {
        const X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z);
        let f1 = 9, f2 = 9;
        for (let i = -1; i <= 1; i++) {
            for (let j = -1; j <= 1; j++) {
                for (let k = -1; k <= 1; k++) {
                    const cx = X + i, cy = Y + j, cz = Z + k;
                    let h = Math.imul(cx, 374761393) + Math.imul(cy, 668265263)
                        + Math.imul(cz, 1442695041) + seed;
                    h = Math.imul(h ^ h >>> 13, 1274126177);
                    h ^= h >>> 16;
                    // one hash, three 10-bit slices - the feature point
                    const r1 = (h & 1023) / 1024;
                    const r2 = (h >>> 10 & 1023) / 1024;
                    const r3 = (h >>> 20 & 1023) / 1024;
                    const dx = cx + r1 - x, dy = cy + r2 - y, dz = cz + r3 - z;
                    const d = dx * dx + dy * dy + dz * dz;
                    if (d < f1) { f2 = f1; f1 = d; }
                    else if (d < f2) { f2 = d; }
                }
            }
        }
        this._worleyF2 = Math.sqrt(f2);
        return Math.sqrt(f1);
    },

    /** Deterministic 0..1 from a lattice cell - band and city jitter. */
    _cellRand(i, seed) {
        let h = Math.imul(i, 374761393) + seed;
        h = Math.imul(h ^ h >>> 13, 1274126177);
        return ((h ^ h >>> 16) >>> 0) / 4294967296;
    },

    _lerp(a, b, t) { return a + (b - a) * t; },

    _smooth(e0, e1, x) {
        let t = (x - e0) / (e1 - e0);
        t = t < 0 ? 0 : (t > 1 ? 1 : t);
        return t * t * (3 - 2 * t);
    },

    // ---------------------------------------------------------------
    // Palette work
    // ---------------------------------------------------------------

    /** Hue-rotate one rgb triple by `deg`, preserving saturation. */
    _hueShift(rgb, deg) {
        const r = rgb[0] / 255, g = rgb[1] / 255, b = rgb[2] / 255;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        const l = (max + min) / 2;
        if (max === min) return [rgb[0], rgb[1], rgb[2]];
        const d = max - min;
        const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        let h;
        if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
        else if (max === g) h = (b - r) / d + 2;
        else h = (r - g) / d + 4;
        h = (h / 6 + deg / 360 + 1) % 1;
        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        const hue = (t) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1 / 6) return p + (q - p) * 6 * t;
            if (t < 1 / 2) return q;
            if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
            return p;
        };
        return [
            Math.round(hue(h + 1 / 3) * 255),
            Math.round(hue(h) * 255),
            Math.round(hue(h - 1 / 3) * 255)
        ];
    },

    _mixRgb(a, b, t) {
        return [
            Math.round(a[0] + (b[0] - a[0]) * t),
            Math.round(a[1] + (b[1] - a[1]) * t),
            Math.round(a[2] + (b[2] - a[2]) * t)
        ];
    },

    /**
     * Per-world copy of the class palette: hue-jittered once here rather
     * than per pixel, plus the class-specific environment tints.
     */
    _worldPalette(cls, spec, P, env) {
        const deg = P.hueJitter;
        const pal = { cold: this._hueShift(spec.cold, deg), stops: [] };
        let tint = null, tintAmount = 0;
        if (cls === 'toxic') {
            if (env.temperature >= 78) {
                // a runaway greenhouse burns amber rather than sickly green
                tint = [236, 158, 78];
                tintAmount = 0.30 + this._smooth(78, 100, env.temperature) * 0.25;
            } else if (env.radiation > 70) {
                tint = [126, 196, 68];
                tintAmount = Math.min(1, (env.radiation - 70) / 30) * 0.70;
            }
        }
        for (const s of spec.stops) {
            let d = this._hueShift(s.d, deg);
            let w = this._hueShift(s.w, deg);
            if (tint) {
                d = this._mixRgb(d, tint, tintAmount);
                w = this._mixRgb(w, tint, tintAmount);
            }
            pal.stops.push({ e: s.e, d, w });
        }
        if (cls === 'gas') {
            const warm = this._smooth(30, 70, env.temperature);
            const src = spec.bandsWarm.map((c, i) =>
                this._mixRgb(spec.bandsCold[i], c, warm));
            pal.bands = src.map(c => this._hueShift(c, deg));
            pal.storm = this._hueShift(
                this._mixRgb([200, 210, 220], [206, 106, 74], warm), deg);
        }
        return pal;
    },

    /** Two-axis lookup: elevation picks the stop pair, moisture blends. */
    _ramp(stops, e, m, out) {
        let i = 1;
        while (i < stops.length - 1 && e > stops[i].e) i++;
        const a = stops[i - 1], b = stops[i];
        let t = (e - a.e) / (b.e - a.e);
        t = t < 0 ? 0 : (t > 1 ? 1 : t);
        const ad = a.d, aw = a.w, bd = b.d, bw = b.w;
        for (let k = 0; k < 3; k++) {
            const dry = ad[k] + (bd[k] - ad[k]) * t;
            const wet = aw[k] + (bw[k] - aw[k]) * t;
            out[k] = dry + (wet - dry) * m;
        }
    },

    // ---------------------------------------------------------------
    // Surface evaluators
    // ---------------------------------------------------------------

    // scratch: [r, g, b, waterMask, emissive, landMask]
    _px: [0, 0, 0, 0, 0, 0],

    /**
     * Rocky surface: one-level domain-warped fBm, redistribution, a
     * ridged term above sea level, class-specific craters or fractures,
     * a decorrelated moisture field, then the (elevation, moisture)
     * palette blended toward the cold colour past the ice latitude.
     */
    _rocky(perm, P, spec, pal, qx, qy, qz, out) {
        const s = P.noiseScale;
        const X = qx * s, Y = qy * s, Z = qz * s;
        const g = P.gain, w = P.warpAmount;

        // one level of domain warping - fbm(p + w * h(p))
        const q1 = this._fbm3(perm, X + 5.2, Y + 1.3, Z + 2.7, 2, g) * 2 - 1;
        const q2 = this._fbm3(perm, X + 1.7, Y + 9.2, Z + 4.1, 2, g) * 2 - 1;
        let e = this._fbm3(perm, X + w * q1, Y + w * q2, Z + w * q1 * 0.6,
            P.octaves, g);

        // redistribution - broad plains with isolated highlands
        const rex = 1 + (P.redistExponent - 1) * spec.redistScale;
        e = Math.pow(Math.min(1, e * 1.15), rex);

        let water = 0, land = 1;
        if (spec.sea) {
            // the sea level runs through the same redistribution, so the
            // land fraction stays what the parameter asked for
            const sl = Math.pow(Math.min(1, P.seaLevel * 1.15), rex);
            if (e < sl) {
                water = 1;
                e = (e / sl) * 0.30;
                land = 0;
            } else {
                e = 0.30 + (e - sl) / (1 - sl) * 0.70;
            }
        }

        let emissive = 0;
        if (spec.ridge === 'mountain' && P.mountainStrength > 0) {
            const r = this._ridged3(perm, X * 1.7 + 11.3, Y * 1.7 + 2.9,
                Z * 1.7 + 7.1, 4, g);
            e += r * P.mountainStrength * this._smooth(0.30, 0.58, e);
        } else if (spec.ridge === 'canyon') {
            const r = this._ridged3(perm, X * 1.9 + 4.3, Y * 1.9 + 12.7,
                Z * 1.9 + 1.1, 5, g);
            e = e * 0.62 + r * (0.30 + P.mountainStrength * 0.7);
        } else if (spec.ridge === 'fissure') {
            const r = this._ridged3(perm, X * 1.5 + 3.7, Y * 1.5 + 8.1,
                Z * 1.5 + 5.3, 5, g);
            e = e * 0.70 + r * 0.35;
            // the valleys of the ridged field are the glowing cracks
            emissive = this._smooth(0.30, 0.04, r) * (0.55 + 0.45 * (1 - e));
        }

        if (spec.craters) {
            const cs = 2.1 + P.noiseScale * 0.3;
            const d1 = this._worley3(X * cs, Y * cs, Z * cs, 17);
            e += this._crater(d1) * P.craterDensity;
            const d2 = this._worley3(X * cs * 2.9 + 5, Y * cs * 2.9,
                Z * cs * 2.9 + 9, 71);
            e += this._crater(d2) * P.craterDensity * 0.55;
        }

        if (e < 0) e = 0; else if (e > 1) e = 1;

        // decorrelated moisture field, sharpened so biomes read
        const m = this._smooth(0.36, 0.64,
            this._fbm3(perm, X * 0.75 + 31.7, Y * 0.75 + 17.3,
                Z * 0.75 + 23.9, 3, g));

        this._ramp(pal.stops, e, m, out);

        if (spec.crack) {
            // Worley cell borders as fracture lineae (Europa's brown lines)
            const cs = 1.2 + P.noiseScale * 0.9;
            const f1 = this._worley3(X * cs + 3.1, Y * cs, Z * cs + 7.7, 131);
            const edge = 1 - this._smooth(0.0, 0.06 + P.mountainStrength * 0.14,
                this._worleyF2 - f1);
            if (edge > 0) {
                const stain = 0.85 * edge;
                out[0] += (146 - out[0]) * stain;
                out[1] += (98 - out[1]) * stain;
                out[2] += (68 - out[2]) * stain;
            }
        }

        if (spec.shear) {
            // Venusian super-rotation streaks over a featureless deck
            const sh = this._fbm3(perm, X * 0.9, Y * 3.4, Z * 0.9, 4, g);
            const k = (sh - 0.5) * 0.22;
            out[0] *= 1 + k; out[1] *= 1 + k * 0.9; out[2] *= 1 + k * 0.5;
        }

        // polar caps: blend toward the class cold colour past ice latitude
        const ice = spec.caps
            ? this._smooth(P.iceLatitude, P.iceLatitude + 0.12, Math.abs(qy))
                * spec.caps
            : 0;
        if (ice > 0) {
            const t = ice * (water ? 0.85 : 1);
            const c = pal.cold;
            out[0] += (c[0] - out[0]) * t;
            out[1] += (c[1] - out[1]) * t;
            out[2] += (c[2] - out[2]) * t;
        }

        if (emissive > 0) {
            out[0] += (255 - out[0]) * emissive * 0.75;
            out[1] += (120 - out[1]) * emissive * 0.55;
            out[2] += (30 - out[2]) * emissive * 0.45;
        }

        out[3] = water ? 1 : (ice > 0.5 ? 0.7 : 0);
        out[4] = emissive;
        out[5] = land * (1 - ice);
    },

    /** Classic crater profile - a floor, a raised rim, smooth outside. */
    _crater(d) {
        const rim = 0.40;
        const floor = -0.24 * (1 - this._smooth(rim * 0.55, rim, d));
        const wall = 0.20 * Math.exp(-((d - rim) * (d - rim)) / 0.005);
        return floor + wall;
    },

    /**
     * Gas giant: warped latitude bands, per-band variation, fine shear
     * streaks along the flow, then analytic storm ovals with swirled
     * interiors. Bands live in latitude, so this path keeps it.
     */
    _gas(perm, P, spec, pal, qx, qy, qz, out) {
        const s = P.noiseScale;
        const g = P.gain;
        // stretch in latitude, squash in longitude - zonal flow
        const wx = qx * s * 0.32, wy = qy * s * 1.7, wz = qz * s * 0.32;
        const t1 = this._fbm3(perm, wx + 5.2, wy + 1.3, wz + 8.4, 2, g) * 2 - 1;
        const t2 = this._fbm3(perm, wx + 1.7, wy + 9.2, wz + 2.8, 2, g) * 2 - 1;
        const turb = this._fbm3(perm, wx + P.warpAmount * t1,
            wy + P.warpAmount * t2 * 0.35, wz + P.warpAmount * t1 * 0.5,
            4, g);

        const lat = qy;
        const latW = lat + (turb * 2 - 1) * 0.085 * (1 - lat * lat);
        const bands = pal.bands;
        const n = bands.length;
        const idx = (latW * 0.5 + 0.5) * P.bandCount;
        const bi = Math.floor(idx);
        const f = this._smooth(0.22, 0.78, idx - bi);
        const c0 = bands[((bi % n) + n) % n];
        const c1 = bands[(((bi + 1) % n) + n) % n];
        const bright = 0.86 + 0.28 * this._cellRand(bi, 9173);
        for (let k = 0; k < 3; k++) {
            out[k] = (c0[k] + (c1[k] - c0[k]) * f) * bright;
        }

        // fine streaks following the flow
        const shear = this._fbm3(perm, qx * s * 2.2, latW * 18, qz * s * 2.2,
            2, g);
        const sm = 0.88 + 0.26 * shear;
        out[0] *= sm; out[1] *= sm; out[2] *= sm;

        if (P.storms && P.storms.length) {
            const lon = Math.atan2(qx, qz);
            for (let i = 0; i < P.storms.length; i++) {
                const st = P.storms[i];
                let dlon = lon - st.lon;
                while (dlon > Math.PI) dlon -= Math.PI * 2;
                while (dlon < -Math.PI) dlon += Math.PI * 2;
                const dlat = latW - st.lat;
                const ux = dlon / st.rx, uy = dlat / st.ry;
                const rr = Math.sqrt(ux * ux + uy * uy);
                if (rr >= 0.98) continue;
                // swirl the interior - rotation falls off with radius
                const ang = st.spin * (1 - rr) * (1 - rr);
                const ca = Math.cos(ang), sa = Math.sin(ang);
                const vx = ux * ca - uy * sa, vy = ux * sa + uy * ca;
                const sw = this._fbm3(perm, vx * 2.6 + 40, vy * 2.6 + 12,
                    rr * 2.2, 3, g);
                const k = this._smooth(1.0, 0.45, rr) * (0.55 + 0.7 * sw);
                const t = k > 1 ? 1 : k;
                const sc = pal.storm;
                const shade = 0.75 + 0.5 * sw;
                out[0] += (sc[0] * shade - out[0]) * t;
                out[1] += (sc[1] * shade - out[1]) * t;
                out[2] += (sc[2] * shade - out[2]) * t;
            }
        }

        out[3] = 0;
        out[4] = 0;
        out[5] = 0;
    },

    // ---------------------------------------------------------------
    // Painting
    // ---------------------------------------------------------------

    _paint(canvas, star) {
        const t0 = (typeof performance !== 'undefined')
            ? performance.now() : Date.now();
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        const env = this._env(star);
        const cls = this.classify(star);
        const spec = this.CLASSES[cls];
        const art = (typeof EncyclopediaArt !== 'undefined')
            ? EncyclopediaArt : null;
        const rng = art
            ? art._rng(art._hash(this._seedKey(star)))
            : this._fallbackRng(this._seedKey(star));
        const P = this._params(env, cls, spec, rng);
        const pal = this._worldPalette(cls, spec, P, env);
        const perm = this._perm(rng);

        // planet radius follows gravity, as the original panel did
        const R = Math.min(W, H) * (0.3125 + ((env.gravity - 50) / 50) * 0.1);
        const cx = W / 2, cy = H / 2;

        // light direction and the half vector for the specular term
        const la = P.lightAngle;
        let Lx = Math.cos(la), Ly = Math.sin(la) * 0.6, Lz = 0.78;
        const ll = Math.sqrt(Lx * Lx + Ly * Ly + Lz * Lz);
        Lx /= ll; Ly /= ll; Lz /= ll;
        let Hx = Lx, Hy = Ly, Hz = Lz + 1;
        const hl = Math.sqrt(Hx * Hx + Hy * Hy + Hz * Hz);
        Hx /= hl; Hy /= hl; Hz /= hl;

        const ct = Math.cos(P.axialTilt), st = Math.sin(P.axialTilt);
        const cp = Math.cos(P.rotationPhase), sp = Math.sin(P.rotationPhase);

        const isGas = spec.gen === 'gas';
        const out = this._px;
        const img = ctx.createImageData(W, H);
        const data = img.data;
        const haze = spec.haze || 0;
        const hz = spec.hazeColor || [255, 255, 255];
        const cityScale = 26;
        const cityDensity = env.colonized
            ? Math.min(0.35, 0.12 + Math.log10(
                Math.max(10, star.colonists || 0)) * 0.03)
            : 0;

        for (let y = 0; y < H; y++) {
            const dy = (y + 0.5 - cy) / R;
            const row = y * W * 4;
            for (let x = 0; x < W; x++) {
                const dx = (x + 0.5 - cx) / R;
                const d2 = dx * dx + dy * dy;
                if (d2 > 1) continue;
                const nz = Math.sqrt(1 - d2);
                const nx = dx, ny = -dy;

                // tilt the pole axis, then spin the world on it
                const px = nx * ct + ny * st;
                const py = -nx * st + ny * ct;
                const qx = px * cp + nz * sp;
                const qz = -px * sp + nz * cp;
                const qy = py;

                if (isGas) this._gas(perm, P, spec, pal, qx, qy, qz, out);
                else this._rocky(perm, P, spec, pal, qx, qy, qz, out);

                // Minnaert limb darkening plus a soft terminator
                const dotNL = nx * Lx + ny * Ly + nz * Lz;
                let lit = this._smooth(-spec.penumbra, spec.penumbra, dotNL);
                if (spec.wrap) {
                    lit = Math.max(lit, this._smooth(-spec.penumbra * 2.6,
                        spec.penumbra, dotNL) * 0.30);
                }
                const mu = nz < 0.05 ? 0.05 : nz;
                const mu0 = dotNL < 0 ? 0 : dotNL;
                let mn = Math.pow(mu0, spec.k) * Math.pow(mu, spec.k - 1);
                if (mn > 1.7) mn = 1.7;
                // Ambient floor rises toward the limb. A flat 6% floor left
                // the night limb of a dark world at ~4/255 - indistinguishable
                // from the background, so the silhouette disappeared on the
                // unlit side and the planet read as two mismatched circles.
                // Grazing angles scatter more starlight, so lifting the floor
                // as nz falls is both physical and exactly what keeps the
                // sphere's outline readable all the way round.
                const ambient = 0.05 + 0.06 * (1 - nz) * (1 - nz);
                const shade = ambient + lit * mn;

                let r = out[0] * shade;
                let gch = out[1] * shade;
                let b = out[2] * shade;

                // emissive terms survive on the night side
                if (out[4] > 0) {
                    const glow = out[4] * (0.30 + 0.70 * (1 - lit));
                    r += 235 * glow; gch += 92 * glow; b += 24 * glow;
                }
                if (spec.specPower && out[3] > 0) {
                    const dh = nx * Hx + ny * Hy + nz * Hz;
                    if (dh > 0) {
                        const sp2 = Math.pow(dh, spec.specPower) * out[3] * lit;
                        r += 235 * sp2; gch += 242 * sp2; b += 255 * sp2;
                    }
                }
                if (cityDensity > 0 && lit < 0.35 && out[5] > 0.4) {
                    const c = this._city(qx, qy, qz, cityScale, cityDensity);
                    if (c > 0) {
                        const k = c * (1 - lit) * out[5];
                        r += 255 * k; gch += 196 * k; b += 110 * k;
                    }
                }
                if (haze > 0) {
                    const t = (1 - nz) * (1 - nz) * haze;
                    r += (hz[0] * (0.25 + shade) - r) * t;
                    gch += (hz[1] * (0.25 + shade) - gch) * t;
                    b += (hz[2] * (0.25 + shade) - b) * t;
                }

                // one-pixel coverage feather at the limb
                const edge = (1 - Math.sqrt(d2)) * R * 1.4;
                const i = row + x * 4;
                data[i] = r;
                data[i + 1] = gch;
                data[i + 2] = b;
                data[i + 3] = edge >= 1 ? 255 : edge * 255;
            }
        }
        ctx.putImageData(img, 0, 0);

        this._composite(ctx, W, H, cx, cy, R, P, spec, pal, env, rng,
            Lx, Ly, perm);

        const station = this.stationSpec(star);
        if (station) {
            this._drawStation(ctx, W, H, cx, cy, R, station, P, Lx, Ly);
        }

        this.lastRenderMs = ((typeof performance !== 'undefined')
            ? performance.now() : Date.now()) - t0;
    },

    /** Sparse warm points on a jittered lattice - Black Marble style. */
    _city(qx, qy, qz, scale, density) {
        const x = qx * scale, y = qy * scale, z = qz * scale;
        const X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z);
        let h = Math.imul(X, 374761393) + Math.imul(Y, 668265263)
            + Math.imul(Z, 1442695041);
        h = Math.imul(h ^ h >>> 13, 1274126177);
        const r1 = ((h ^ h >>> 16) >>> 0) / 4294967296;
        if (r1 > density) return 0;
        let h2 = Math.imul(h ^ 0x9E3779B9, 2654435761);
        const r2 = ((h2 ^ h2 >>> 15) >>> 0) / 4294967296;
        let h3 = Math.imul(h2 ^ 0x85EBCA6B, 2246822519);
        const r3 = ((h3 ^ h3 >>> 13) >>> 0) / 4294967296;
        const dx = x - X - r2, dy = y - Y - r3, dz = z - Z - r1;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        return 1 - this._smooth(0.0, 0.42, d);
    },

    /**
     * Composite finishers - draw calls only: cloud deck, atmospheric rim,
     * radiation ring, then the shared grain and vignette clipped to the
     * disc so the canvas stays transparent outside the planet.
     */
    _composite(ctx, W, H, cx, cy, R, P, spec, pal, env, rng, Lx, Ly, perm) {
        const art = (typeof EncyclopediaArt !== 'undefined')
            ? EncyclopediaArt : null;

        if (P.cloudCover > 0 && art) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, R, 0, Math.PI * 2);
            ctx.clip();
            const billows = 30 + Math.floor(P.cloudCover * 90);
            for (let i = 0; i < billows; i++) {
                // a point on the visible hemisphere, foreshortened
                const u = rng() * 2 - 1, v = rng() * 2 - 1;
                const d2 = u * u + v * v;
                if (d2 > 0.94) continue;
                const nz = Math.sqrt(1 - d2);
                const lit = 0.35 + 0.65 * Math.max(0,
                    u * Lx - v * Ly + nz * 0.7);
                const rad = R * (0.05 + rng() * 0.11) * (0.35 + nz * 0.65);
                art._cloud(ctx, cx + u * R, cy + v * R, rad,
                    '245,248,255',
                    (0.12 + P.cloudCover * 0.38) * lit * (0.4 + rng() * 0.7));
            }
            ctx.restore();
        }

        if (spec.rimAlpha > 0) {
            // Atmospheric limb scattering. Two constraints fight here and
            // both must hold, or the disc stops reading as a sphere:
            //   1. CONCENTRIC with the disc. An offset gradient centre makes
            //      the bright band an off-centre circle whose curvature
            //      disagrees with the planet's edge - the eye reads that as a
            //      lumpy, potato-shaped world.
            //   2. NO hard inner boundary. Clipping to an annulus, or fading
            //      the gradient back to zero before the limb, draws a second
            //      visible circle inside the first.
            // So the profile peaks AT the limb and decays smoothly inward
            // (the disc's own alpha feather finishes the outer edge), and the
            // day/night crescent is applied afterwards by masking the ring
            // offscreen - which changes its brightness without touching its
            // geometry.
            const ring = this._scratch(W, H);
            const rc = ring.getContext('2d');
            rc.clearRect(0, 0, W, H);
            const g = rc.createRadialGradient(cx, cy, R * 0.55, cx, cy, R);
            g.addColorStop(0, `rgba(${spec.rim},0)`);
            g.addColorStop(0.72, `rgba(${spec.rim},${spec.rimAlpha * 0.28})`);
            g.addColorStop(1, `rgba(${spec.rim},${spec.rimAlpha})`);
            rc.fillStyle = g;
            rc.beginPath();
            rc.arc(cx, cy, R, 0, Math.PI * 2);
            rc.fill();

            // fade the ring toward the night limb, geometry untouched
            rc.globalCompositeOperation = 'destination-in';
            const lg = rc.createLinearGradient(
                cx - Lx * R, cy + Ly * R, cx + Lx * R, cy - Ly * R);
            lg.addColorStop(0, 'rgba(0,0,0,0.18)');
            lg.addColorStop(0.5, 'rgba(0,0,0,0.6)');
            lg.addColorStop(1, 'rgba(0,0,0,1)');
            rc.fillStyle = lg;
            rc.fillRect(0, 0, W, H);
            rc.globalCompositeOperation = 'source-over';

            ctx.save();
            ctx.globalCompositeOperation = 'lighter';
            ctx.drawImage(ring, 0, 0);
            ctx.restore();
            if (art) {
                // the outer halo goes around the disc, never over it
                ctx.save();
                this._clipOutsideDisc(ctx, W, H, cx, cy, R);
                ctx.globalCompositeOperation = 'lighter';
                // concentric: an offset halo brightens the space on one side
                // only, which reads as a second circle disagreeing with the
                // disc - the crescent belongs on the ring, not the halo
                art._cloud(ctx, cx, cy, R * 1.28,
                    spec.rim, spec.rimAlpha * 0.34);
                ctx.restore();
            }
        }

        if (env.radiation > 60 && art) {
            const t = (env.radiation - 60) / 40;
            ctx.save();
            this._clipOutsideDisc(ctx, W, H, cx, cy, R);
            ctx.globalCompositeOperation = 'lighter';
            art._cloud(ctx, cx, cy, R * (1.18 + t * 0.22),
                '226,96,226', 0.14 + t * 0.30);
            ctx.restore();
        }

        if (art) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, R, 0, Math.PI * 2);
            ctx.clip();
            ctx.translate(cx - R, cy - R);
            art._grain(ctx, R * 2, R * 2, rng);
            ctx.restore();

            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, R, 0, Math.PI * 2);
            ctx.clip();
            ctx.translate(cx - R * 1.6, cy - R * 1.6);
            art._vignette(ctx, R * 3.2, R * 3.2);
            ctx.restore();
        }
    },

    /**
     * Orbital station classes. `len` is the station's LONGEST dimension as
     * a fraction of the planet radius - the whole footprint, keyline and
     * all, fits inside a box of that side. `kind` picks the builder in
     * _stationParts. Hull names come from components.xml; anything
     * unrecognised falls back to the fort.
     *
     * Classes differ by topology and feature count, never by scale alone:
     * six sizes of one shape is one shape. See
     * docs/research-station-rendering.md.
     *
     * The architecture is Deep Space 9 and Privateer's Perry Station: a
     * core with a habitat ring on pylons for the large classes, a
     * pressurised drum on an axle for the small ones. Radial symmetry is
     * allowed here BECAUSE the parts are solid volumes - the first attempt
     * failed as an emblem because it was radial *wire*, thin spars with no
     * mass. No class hangs guns outside its hull: a station this size
     * carries internal emplacements.
     *
     * `min` is the smallest box the class's topology survives in - a twin
     * spine needs eight pixels, a slip needs seven - and it only binds on
     * the 80 px star panel, where R is 25 and the fractions would round
     * every class down to the same illegible stub.
     */
    STATIONS: {
        'Orbital Fort':  { len: 0.10, min: 6, kind: 'fort' },
        'Space Dock':    { len: 0.12, min: 7, kind: 'dock' },
        'Space Station': { len: 0.13, min: 7, kind: 'station' },
        'Ultra Station': { len: 0.14, min: 8, kind: 'ultra' },
        'Death Star':    { len: 0.11, min: 6, kind: 'sphere' },
        'Shipyard':      { len: 0.13, min: 7, kind: 'yard' },
    },

    /**
     * Three luminance steps plus warm accents. Value contrast is what
     * survives at five pixels; hue does not. Every one of these is
     * OPAQUE - lighting lives in RGB, never in alpha, or a bright desert
     * bleeds through the hull.
     */
    STATION_COLORS: {
        key:        'rgb(4,6,10)',
        bodyDark:   'rgb(84,96,116)',
        bodyLight:  'rgb(186,198,214)',
        hilite:     'rgb(240,246,254)',
        panelDark:  'rgb(46,58,84)',
        panelLight: 'rgb(96,120,158)',
        hull:       'rgb(208,216,228)',
        cut:        'rgb(8,11,16)',
        warm:       'rgb(255,206,128)',
        work:       'rgb(255,172,64)',
        discDark:   'rgb(88,92,102)',
        discLight:  'rgb(178,178,188)',
        core:       'rgb(255,150,60)',
    },

    /** Draw a dim arc where the station's orbit runs. Off by default. */
    STATION_ORBIT_ARC: false,

    stationSpec(star) {
        const hull = star && (star.starbase_hull || star.starbase_name);
        if (!hull) return null;
        if (this.STATIONS[hull]) return this.STATIONS[hull];
        // a shipyard is named rather than hulled until the class ships
        if (/yard|dock/i.test(hull)) return this.STATIONS['Shipyard'];
        return this.STATIONS['Orbital Fort'];
    },

    /**
     * Lay the station out as axis-aligned integer rectangles in a local
     * frame: spine along +X, the planet toward +Y, the sun toward -Y. The
     * whole footprint fits in an L x L box, which is what keeps the ink
     * under one percent of the planet disc.
     *
     * Returns rectangle lists by role:
     *   body   - hull structure, two-toned about the spine axis
     *   panels - flat plates, darker and bluer, edge-on to the spine
     *   hull   - the shipyard's part-built ship: bright, not two-toned
     *   struts - gantries, drawn over the hull
     *   cuts   - dock apertures and trenches, punched out near-black
     *   lights - one warm running light
     *   work   - amber work lights inside a slip
     */
    _stationParts(kind, L) {
        const xa = -Math.floor(L / 2);
        // the L rows are top..top+L-1, straddling the terminator at row 0
        // with the sunward half never the smaller of the two
        const top = -Math.ceil(L / 2);
        const bot = top + L - 1;
        // a feature `w` wide placed at fraction `f` along the spine, held
        // clear of the far edge so it never lands as a 1 px sliver
        const at = (f, w = 2) =>
            Math.min(xa + Math.round(f * L), xa + L - w);
        const body = [], panels = [], hull = [], struts = [],
            cuts = [], lights = [], work = [];
        // every rectangle is clipped into the L x L box on the way in, so
        // the footprint cannot outgrow the class budget at any planet size
        const r = (list, x, y, w, h) => {
            const y0 = Math.max(y, top), y1 = Math.min(y + h, bot + 1);
            const x0 = Math.max(x, xa), x1 = Math.min(x + w, xa + L);
            if (y1 > y0 && x1 > x0) {
                list.push({ x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
            }
        };

        if (kind === 'fort') {
            // A short pressurised drum on an axle. Dock capacity 0 - it
            // services nothing, so no bay is cut. Its weapons are internal
            // emplacements, not barrels: a station this size does not hang
            // guns off the outside.
            // the drum must dominate the axle, or the pair reads as a bar
            const dh = Math.max(4, L - 2);
            r(body, xa + 1, -Math.floor(dh / 2), L - 2, dh);   // drum
            r(body, xa, -1, L, 2);                             // axle
            r(cuts, xa + 2, -1, L - 5, 1);                     // window band
            r(lights, xa + L - 1, -2, 1, 1);                   // running light
        } else if (kind === 'dock') {
            // A larger drum with a docking bay cut into the forward face.
            // Dock capacity 200 kT, so the bay is a notch, not an aperture
            // a capital ship could enter.
            const dh = Math.max(4, L - 3);
            const t0 = -Math.floor(dh / 2);
            r(body, xa + 1, t0, L - 2, dh);                    // drum
            r(body, xa, -1, L, 2);                             // axle
            r(cuts, xa + L - 3, -2, 2, 4);                     // docking bay
            r(cuts, xa + 2, t0 + 1, L - 6, 1);                 // window band
            r(lights, xa + 1, t0, 1, 1);                       // running light
        } else if (kind === 'station') {
            // A truss station: spine, two modules, one panel pair and a
            // dock aperture punched through the larger module.
            //
            // NOT the Deep Space 9 ring the detail view uses. A ring was
            // tried here and failed: at ten pixels the rim leaves a six
            // pixel interior, and once a core and its pylons sit in it
            // there is no annulus left to see - it reads as a solid block
            // with two slots. The ring architecture lives in
            // station-detail.js, which has the pixels to carry it.
            const pl = Math.max(2, Math.floor((L - 2) / 2));
            r(body, xa, -1, L, 2);                  // spine
            r(body, xa, -2, 2, 4);                  // module, aft
            r(body, xa + L - 4, -2, 4, 4);          // module, dock
            r(cuts, xa + L - 3, -1, 2, 2);          // dock aperture
            r(panels, at(0.30), -1 - pl, 2, pl);    // panel, sunward
            r(panels, at(0.30), 1, 2, pl);          // panel, shadow
            r(lights, xa + L - 1, -2, 1, 1);        // running light
        } else if (kind === 'ultra') {
            // Twice the structure, not twice the length: two parallel
            // spines cross-tied into an H-truss, three modules stacked
            // asymmetrically along it.
            const ta = top + 1, tb = bot - 2;       // the two spine rows
            r(body, xa, ta, L, 2);                  // spine, sunward
            r(body, xa, tb, L, 2);                  // spine, planetward
            r(body, at(0.10), ta, 2, tb - ta + 2);  // cross-tie
            r(body, at(0.75), ta, 2, tb - ta + 2);  // cross-tie
            r(body, xa, ta - 1, 2, 4);              // module, aft
            r(body, at(0.60), tb - 1, 2, 4);        // module, lower
            r(body, at(0.80), ta - 1, 2, 4);        // module, forward
            r(panels, at(0.34, 2), ta - 3, 2, 2);   // array, sunward
            r(lights, xa + L - 1, ta - 1, 1, 1);    // running light
        } else if (kind === 'yard') {
            // An open frame with a part-built ship cradled in it. The gap
            // in the outward long bar is what makes it a slip and not a
            // box; the absence of guns is half the read. Three rows
            // either side of the slip - two of frame, one of interior -
            // or the ship has nowhere to sit.
            const hh = Math.max(3, Math.floor((L - 2) / 2) - 1);
            const seg = Math.max(2, Math.round(L * 0.38));
            r(body, xa, -hh, 2, hh * 2);            // frame, aft
            r(body, xa + L - 2, -hh, 2, hh * 2);    // frame, forward
            r(body, xa, hh - 2, L, 2);              // frame, planetward
            r(body, xa, -hh, seg, 2);               // frame, sunward, part
            r(body, xa + L - seg, -hh, seg, 2);     // frame, sunward, part
            r(hull, xa + 2, -1, L - 5, 2);          // part-built ship
            // uneven on purpose: evenly spaced gantries read as decoration.
            // 0.25 and 0.50 keep the PAIR off-centre in the slip, which
            // survives the integer grid at these sizes where prettier
            // fractions round back into symmetry.
            r(struts, at(0.25, 1), -hh, 1, hh * 2); // gantry
            r(struts, at(0.50, 1), -hh, 1, hh * 2); // gantry
            r(work, xa + 2, -1, 1, 1);              // work light
            r(work, xa + 4, 0, 1, 1);               // work light
        }
        return { body, panels, hull, struts, cuts, lights, work };
    },

    /**
     * Draw the starbase in orbit.
     *
     * Small, but plainly there. Legibility at five to ten pixels comes
     * from three cheap things, none of them bulk:
     *   1. an opaque high-value body inside a near-black keyline laid down
     *      by DILATION - inflating every rectangle 1 px - because stroking
     *      a 2 px bar leaves no interior
     *   2. placement off the limb on the sunward side, so a lit object
     *      sits against black sky instead of over a bright surface
     *   3. elongation - the eye detects oriented edges before it detects
     *      area, so a bar reads larger than a blob of the same ink
     * Lit from the same direction as the surface, with a hard terminator
     * on the spine axis, or the station reads as a decal.
     */
    _drawStation(ctx, W, H, cx, cy, R, spec, P, Lx, Ly) {
        const C = this.STATION_COLORS;
        const L = Math.max(spec.min, Math.round(R * spec.len));

        // the surface shader lights with (Lx, -Ly) in screen space
        let ux = Lx, uy = -Ly;
        const ul = Math.sqrt(ux * ux + uy * uy) || 1;
        ux /= ul; uy /= ul;

        // sunward side of the limb, jittered per world so the six classes
        // do not all sit at the same clock position on a review sheet
        const jitter = (P.rotationPhase / (Math.PI * 2) - 0.5) * 0.85;
        const phi = Math.atan2(uy, ux) + jitter;
        const room = Math.min(W, H) / 2 - (L * 0.75 + 2);
        const dist = Math.min(R * 1.18, room);
        const sx = Math.round(cx + Math.cos(phi) * dist);
        const sy = Math.round(cy + Math.sin(phi) * dist);

        // Spine follows the orbit tangent, but QUANTIZED to a right angle.
        // An arbitrary rotation anti-aliases every fillRect, which at 5-9 px
        // turns a 1 px keyline into grey haze and loses the hard terminator -
        // the "too soft" complaint that got the previous version rejected.
        // Snapping to a multiple of 90 degrees keeps every edge on a pixel
        // boundary, so the sprite stays crisp; the tangent is still followed
        // to within 45 degrees, which is enough to read as travelling.
        const tangent = phi + Math.PI / 2 + P.axialTilt * 0.28;
        const ang = Math.round(tangent / (Math.PI / 2)) * (Math.PI / 2);

        if (this.STATION_ORBIT_ARC) {
            ctx.save();
            this._clipOutsideDisc(ctx, W, H, cx, cy, R);
            ctx.strokeStyle = 'rgba(160,185,225,0.12)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, dist, phi - 0.26, phi + 0.26);
            ctx.stroke();
            ctx.restore();
        }

        ctx.save();
        ctx.translate(sx, sy);
        ctx.rotate(ang);

        if (spec.kind === 'sphere') {
            this._drawDeathStar(ctx, L, ang, ux, uy);
            ctx.restore();
            return;
        }

        const parts = this._stationParts(spec.kind, L);
        // the sun in the local frame: the rotation puts it near -Y, so the
        // spine axis is the terminator and the split is a single hard line
        const sly = -ux * Math.sin(ang) + uy * Math.cos(ang);
        const litUp = sly <= 0;

        // 1 - keyline, by dilation
        ctx.fillStyle = C.key;
        const outline = [...parts.panels, ...parts.body, ...parts.hull];
        for (const q of outline) {
            ctx.fillRect(q.x - 1, q.y - 1, q.w + 2, q.h + 2);
        }

        // 2 - panels behind the structure, hard two-tone
        this._stationTone(ctx, parts.panels, litUp, C.panelDark, C.panelLight);
        // 3 - hull structure
        this._stationTone(ctx, parts.body, litUp, C.bodyDark, C.bodyLight);
        // 4 - the part-built ship: bright and flat, so it reads smoother
        //     than the frame around it
        ctx.fillStyle = C.hull;
        for (const q of parts.hull) ctx.fillRect(q.x, q.y, q.w, q.h);
        // 5 - gantries over the slip
        this._stationTone(ctx, parts.struts, litUp, C.bodyDark, C.bodyLight);
        // 6 - apertures and trenches punched back out
        ctx.fillStyle = C.cut;
        for (const q of parts.cuts) ctx.fillRect(q.x, q.y, q.w, q.h);

        // 7 - one-pixel sunward highlight on the spine
        if (parts.body.length) {
            const s = parts.body[0];
            ctx.fillStyle = C.hilite;
            ctx.fillRect(s.x, litUp ? s.y : s.y + s.h - 1, s.w, 1);
        }
        // 8 - specular flip on the panel whose face is within about thirty
        //     degrees of the light: a bright blade against a black one
        if (parts.panels.length && Math.abs(sly) > 0.866) {
            const p = litUp ? parts.panels[0] : parts.panels[1];
            ctx.fillStyle = C.hilite;
            ctx.fillRect(p.x, litUp ? p.y : p.y + p.h - 1, p.w, 1);
        }

        // 9 - running and work lights
        ctx.fillStyle = C.warm;
        for (const q of parts.lights) ctx.fillRect(q.x, q.y, q.w, q.h);
        ctx.fillStyle = C.work;
        for (const q of parts.work) ctx.fillRect(q.x, q.y, q.w, q.h);

        ctx.restore();
    },

    /**
     * Fill rectangles in the shadow value, then repaint the sunward half
     * in the light value. The boundary is the spine axis and it is hard -
     * a gradient across a six-pixel body is two grey pixels and blur.
     */
    _stationTone(ctx, rects, litUp, dark, light) {
        if (!rects.length) return;
        ctx.fillStyle = dark;
        for (const q of rects) ctx.fillRect(q.x, q.y, q.w, q.h);
        ctx.fillStyle = light;
        for (const q of rects) {
            if (litUp) {
                const h = Math.min(q.y + q.h, 0) - q.y;
                if (h > 0) ctx.fillRect(q.x, q.y, q.w, h);
            } else {
                const y = Math.max(q.y, 0);
                const h = q.y + q.h - y;
                if (h > 0) ctx.fillRect(q.x, y, q.w, h);
            }
        }
    },

    /**
     * The Death Star is the only compact class - a filled sphere rather
     * than a truss, which is how the reference art distinguishes it too.
     * Disc, hard terminator, one offset meridian trench, one warm core.
     */
    _drawDeathStar(ctx, L, ang, ux, uy) {
        const C = this.STATION_COLORS;
        const rad = L / 2;
        const sly = -ux * Math.sin(ang) + uy * Math.cos(ang);
        const litUp = sly <= 0;

        ctx.fillStyle = C.key;
        ctx.beginPath();
        ctx.arc(0, 0, rad + 1, 0, Math.PI * 2);
        ctx.fill();

        ctx.save();
        ctx.beginPath();
        ctx.arc(0, 0, rad, 0, Math.PI * 2);
        ctx.clip();
        ctx.fillStyle = C.discDark;
        ctx.fillRect(-rad - 1, -rad - 1, L + 2, L + 2);
        ctx.fillStyle = C.discLight;
        if (litUp) ctx.fillRect(-rad - 1, -rad - 1, L + 2, rad + 1);
        else ctx.fillRect(-rad - 1, 0, L + 2, rad + 1);
        // meridian trench, offset from centre so the sphere has a pole
        ctx.fillStyle = C.cut;
        ctx.fillRect(-Math.max(1, Math.round(rad * 0.35)), -rad - 1, 1, L + 2);
        ctx.restore();

        ctx.fillStyle = C.core;
        ctx.fillRect(0, litUp ? 1 : -2, 1, 1);
    },

    /**
     * A reusable offscreen canvas, so masking a layer costs no allocation
     * per world. Grown on demand, never shrunk.
     */
    _scratch(W, H) {
        let c = this._scratchCanvas;
        if (!c) {
            c = this._scratchCanvas = document.createElement('canvas');
            c.width = 0; c.height = 0;
        }
        if (c.width < W) c.width = W;
        if (c.height < H) c.height = H;
        return c;
    },

    /** Clip to everything except the planet disc - halos and glow rings. */
    _clipOutsideDisc(ctx, W, H, cx, cy, R) {
        ctx.beginPath();
        ctx.rect(0, 0, W, H);
        ctx.arc(cx, cy, R, 0, Math.PI * 2, true);
        ctx.clip();
    },

    /** mulberry32 over FNV-1a, used only when encyclopedia.js is absent. */
    _fallbackRng(key) {
        let h = 2166136261;
        for (const c of key) {
            h ^= c.charCodeAt(0);
            h = Math.imul(h, 16777619);
        }
        let a = h >>> 0;
        return () => {
            a |= 0; a = a + 0x6D2B79F5 | 0;
            let t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    }
};

// Export
window.PlanetArt = PlanetArt;
