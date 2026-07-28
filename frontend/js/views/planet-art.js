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
        return `${this._seedKey(star)}|${W}x${H}|${env.gravity}|`
            + `${env.temperature}|${env.radiation}|${env.colonized ? 1 : 0}`;
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
                const shade = 0.06 + lit * mn;

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
            // Fresnel-style crescent: the gradient centre sits toward the
            // light, so the ring fades out on the night limb
            ctx.save();
            ctx.globalCompositeOperation = 'lighter';
            const gx = cx + Lx * R * 0.14, gy = cy - Ly * R * 0.14;
            const g = ctx.createRadialGradient(gx, gy, R * 0.70, gx, gy, R);
            g.addColorStop(0, `rgba(${spec.rim},0)`);
            g.addColorStop(0.86, `rgba(${spec.rim},${spec.rimAlpha})`);
            g.addColorStop(1, `rgba(${spec.rim},0)`);
            ctx.fillStyle = g;
            ctx.beginPath();
            ctx.arc(cx, cy, R, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
            if (art) {
                // the outer halo goes around the disc, never over it
                ctx.save();
                this._clipOutsideDisc(ctx, W, H, cx, cy, R);
                ctx.globalCompositeOperation = 'lighter';
                art._cloud(ctx, cx + Lx * R * 0.1, cy - Ly * R * 0.1, R * 1.28,
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
