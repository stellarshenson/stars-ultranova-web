/**
 * Stars Nova Web - shared SDF raymarch engine
 *
 * The sphere-tracing renderer factored out of station-detail.js so the
 * ship renderer (ship-detail.js) and the station renderer share one
 * marcher, one shading pipeline and one material vocabulary instead of
 * two divergent copies. Nothing about the technique changed in the
 * move: exact analytic distance functions, soft shadows from the
 * closest-approach ratio, ambient occlusion walked along the normal,
 * Blinn-Phong under a Schlick Fresnel, triplanar plating seams, filmic
 * tonemap. Deterministic throughout - Math.random is never used.
 *
 * Consumers provide a design spec {scene, bound, yaw, pitch, roll,
 * fill, winRows, winDens|winCols, point, cool} plus a material table,
 * and get back a raw RGBA buffer. `makeRenderer` wraps that in the
 * cache/canvas plumbing both views need.
 */
(function () {
    'use strict';

    // ---------------------------------------------------------------
    // March tunables. These are the whole performance story: cost is
    // (pixels) x (MARCH_STEPS + 4 normal taps + SHADOW_STEPS + AO_TAPS)
    // scene evaluations. Raising MARCH_STEPS buys grazing-angle
    // accuracy, SHADOW_STEPS buys penumbra length, AO_TAPS buys recess
    // depth. The bounding-sphere entry test in paint() is what keeps
    // the empty half of the frame free.
    // ---------------------------------------------------------------

    /** Sphere-trace iterations per primary ray. */
    const MARCH_STEPS = 78;
    /** Give up on a primary ray past this distance from the camera. */
    const MAX_DIST = 8.5;
    /** Surface hit threshold, scaled by distance so far rays cost less. */
    const SURF_EPS = 0.0013;
    /** Iterations for the soft shadow march toward the key light. */
    const SHADOW_STEPS = 26;
    /** Penumbra hardness: larger is a tighter shadow edge. */
    const SHADOW_K = 11.0;
    /** How far a shadow ray travels before it is declared unoccluded. */
    const SHADOW_MAX = 3.4;
    /** Ambient occlusion taps walked out along the surface normal. */
    const AO_TAPS = 5;
    /** Reach of the AO cone, in scene units. */
    const AO_SPAN = 0.17;
    /** Central-difference offset for the normal (tetrahedron, 4 taps). */
    const NORMAL_EPS = 0.0016;

    // ---------------------------------------------------------------
    // Exact analytic distance functions. Each takes coordinates already
    // translated into the primitive's own frame. Axis-permuted variants
    // are handled by the caller passing arguments in a different order,
    // which costs nothing and keeps the primitive count honest.
    // ---------------------------------------------------------------

    function clamp01(t) {
        return t < 0 ? 0 : (t > 1 ? 1 : t);
    }

    /** Sphere of radius r at the origin. */
    function sdSphere(px, py, pz, r) {
        return Math.sqrt(px * px + py * py + pz * pz) - r;
    }

    /** Axis-aligned box of half extents b. */
    function sdBox(px, py, pz, bx, by, bz) {
        const qx = Math.abs(px) - bx;
        const qy = Math.abs(py) - by;
        const qz = Math.abs(pz) - bz;
        const mx = qx > 0 ? qx : 0;
        const my = qy > 0 ? qy : 0;
        const mz = qz > 0 ? qz : 0;
        const inner = Math.max(qx, Math.max(qy, qz));
        return Math.sqrt(mx * mx + my * my + mz * mz) + (inner < 0 ? inner : 0);
    }

    /** Box with its edges rounded off by radius r. */
    function sdRoundBox(px, py, pz, bx, by, bz, r) {
        return sdBox(px, py, pz, bx - r, by - r, bz - r) - r;
    }

    /**
     * Capped cylinder. `ax` is the axial coordinate, (rb, rc) the two
     * radial ones, `h` the half length and `r` the radius.
     */
    function sdCyl(ax, rb, rc, h, r) {
        const dr = Math.sqrt(rb * rb + rc * rc) - r;
        const da = Math.abs(ax) - h;
        const ox = dr > 0 ? dr : 0;
        const oy = da > 0 ? da : 0;
        const inner = Math.max(dr, da);
        return Math.sqrt(ox * ox + oy * oy) + (inner < 0 ? inner : 0);
    }

    /** Infinite cylinder about the axis whose radial coords are (rb, rc). */
    function sdCylInf(rb, rc, r) {
        return Math.sqrt(rb * rb + rc * rc) - r;
    }

    /** Capped cylinder with its rims filleted by rr. */
    function sdRoundCyl(ax, rb, rc, h, r, rr) {
        return sdCyl(ax, rb, rc, h - rr, r - rr) - rr;
    }

    /** Torus of major radius R and tube radius r, about the `ax` axis. */
    function sdTorus(ax, rb, rc, R, r) {
        const q = Math.sqrt(rb * rb + rc * rc) - R;
        return Math.sqrt(q * q + ax * ax) - r;
    }

    /**
     * Arc: a capped torus about the `ax` axis, spanning `an` radians
     * either side of the +rb direction. Exact. The buttress and intake
     * handle primitive the ship catalogue needs.
     */
    function sdArc(ax, rb, rc, R, r, an) {
        const s = Math.sin(an), c = Math.cos(an);
        const x = Math.abs(rc);
        const k = (c * x > s * rb) ? (x * s + rb * c)
            : Math.sqrt(x * x + rb * rb);
        return Math.sqrt(x * x + rb * rb + ax * ax + R * R - 2 * R * k) - r;
    }

    /** Capsule between two points, radius r. */
    function sdCapsule(px, py, pz, ax, ay, az, bx, by, bz, r) {
        const pax = px - ax, pay = py - ay, paz = pz - az;
        const bax = bx - ax, bay = by - ay, baz = bz - az;
        const bb = bax * bax + bay * bay + baz * baz;
        let h = (pax * bax + pay * bay + paz * baz) / bb;
        h = h < 0 ? 0 : (h > 1 ? 1 : h);
        const dx = pax - bax * h, dy = pay - bay * h, dz = paz - baz * h;
        return Math.sqrt(dx * dx + dy * dy + dz * dz) - r;
    }

    /**
     * Ellipsoid. Not an exact distance - it is the standard bounded
     * approximation - so callers must not step by more than it returns.
     */
    function sdEllipsoid(px, py, pz, rx, ry, rz) {
        const ax = px / rx, ay = py / ry, az = pz / rz;
        const k0 = Math.sqrt(ax * ax + ay * ay + az * az);
        if (k0 === 0) return -Math.min(rx, Math.min(ry, rz));
        const bx = ax / rx, by = ay / ry, bz = az / rz;
        const k1 = Math.sqrt(bx * bx + by * by + bz * bz);
        return k0 * (k0 - 1) / k1;
    }

    // ---------------------------------------------------------------
    // Operators. Every one carries the material of whichever surface it
    // hands back, so shading gets the right albedo without a second
    // pass over the scene.
    // ---------------------------------------------------------------

    /** Material of the surface the current scene evaluation settled on. */
    let MAT = 0;

    /** Union: nearer wins. */
    function opU(d, e, m) {
        if (e < d) { MAT = m; return e; }
        return d;
    }

    /** Polynomial smooth union - the fairing that removes hard joints. */
    function opSU(d, e, k, m) {
        const h = clamp01(0.5 + 0.5 * (d - e) / k);
        if (h > 0.5) MAT = m;
        return d * (1 - h) + e * h - k * h * (1 - h);
    }

    /** Subtraction: cut `e` out of `d`; `m` dresses the cut face. */
    function opSub(d, e, m) {
        if (-e > d) { MAT = m; return -e; }
        return d;
    }

    /** Smooth subtraction, so a bay mouth gets a filleted lip. */
    function opSSub(d, e, k, m) {
        const h = clamp01(0.5 + 0.5 * (d + e) / k);
        if (h < 0.5) MAT = m;
        return (-e) * (1 - h) + d * h + k * h * (1 - h);
    }

    /** Intersection: both must be inside. */
    function opI(d, e, m) {
        if (e > d) { MAT = m; return e; }
        return d;
    }

    // ---------------------------------------------------------------
    // Domain folding. Radial repetition is how a six-node rim costs one
    // primitive instead of six, and it is the only place in the hot
    // loop that spends a transcendental.
    // ---------------------------------------------------------------

    /** Folded radial coordinates, written into FOLD as [radial, tangent]. */
    const FOLD = [0, 0];

    function foldRadial(x, z, sectors) {
        const rr = Math.sqrt(x * x + z * z);
        const sect = (Math.PI * 2) / sectors;
        let a = Math.atan2(z, x);
        a -= sect * Math.round(a / sect);
        FOLD[0] = rr * Math.cos(a);
        FOLD[1] = rr * Math.sin(a);
    }

    /** Repeat along one axis, limited to +/- lim copies. */
    function repLimit(v, period, lim) {
        let i = Math.round(v / period);
        if (i < -lim) i = -lim;
        if (i > lim) i = lim;
        return v - period * i;
    }

    // ---------------------------------------------------------------
    // Materials. `e` is emissive radiance added after shadow and AO, so
    // window rows and running lights survive on the dark side, which is
    // how a lit hull reads as inhabited rather than as a lamp.
    // ---------------------------------------------------------------

    // `seam` is the panel grid frequency, `greeble` how strongly panels
    // step in and out of the plane, `s`/`sh` the specular strength and
    // Blinn-Phong exponent. Plating is warm off-white and structure is
    // cold and dark, which is what a real hull photographs like: the
    // value gap between plate and truss carries the whole read.
    const MATERIALS = [
        // 0 armour plate
        { a: [0.66, 0.65, 0.62], s: 0.85, sh: 190, seam: 5.5, greeble: 1.0,
          win: 0 },
        // 1 structural truss, dark and rough
        { a: [0.17, 0.18, 0.21], s: 0.30, sh: 34, seam: 11.0, greeble: 0.5,
          win: 0 },
        // 2 pressurised hull, the surface that carries window rows
        { a: [0.63, 0.63, 0.61], s: 0.95, sh: 240, seam: 4.5, greeble: 1.0,
          win: 1 },
        // 3 window glass, warm and emissive
        { a: [0.08, 0.08, 0.09], s: 0.60, sh: 260, seam: 0, greeble: 0,
          e: [1.00, 0.74, 0.42] },
        // 4 work light / bay interior floodlight. A floodlit wall is a
        // LIT surface, not a lamp: most of its brightness has to come
        // from albedo and the warm point light, or it reads as a flat
        // yellow decal pasted into the recess
        { a: [0.56, 0.46, 0.32], s: 0.30, sh: 40, seam: 3.0, greeble: 0.6,
          e: [0.40, 0.23, 0.09], vol: 1 },
        // 5 cut interior: deep, unlit, rough
        { a: [0.10, 0.10, 0.12], s: 0.14, sh: 20, seam: 13.0, greeble: 1.4,
          win: 0 },
        // 6 radiator and solar array, near-black and glossy
        { a: [0.045, 0.06, 0.11], s: 1.00, sh: 380, seam: 19.0, greeble: 0.3,
          win: 0 },
        // 7 bare ship hull in the slip, warmer and brighter metal
        { a: [0.72, 0.69, 0.62], s: 0.95, sh: 230, seam: 7.0, greeble: 1.1,
          win: 0 },
        // 8 death star core, the only self-lit volume. `vol` makes the
        // emissive fall off toward grazing angles, so the core reads as
        // a glowing sphere seen through a gap rather than a flat decal
        { a: [0.26, 0.12, 0.04], s: 0.25, sh: 26, seam: 0, greeble: 0,
          e: [1.05, 0.36, 0.07], vol: 1, plasma: 1 },
        // 9 death star cage strut, canon greenish grey
        { a: [0.30, 0.34, 0.28], s: 0.55, sh: 90, seam: 8.5, greeble: 0.9,
          win: 0 },
        // 10 port beacon, red
        { a: [0.20, 0.04, 0.04], s: 0.30, sh: 40, seam: 0, greeble: 0,
          e: [1.00, 0.16, 0.10] },
        // 11 starboard beacon, green
        { a: [0.04, 0.20, 0.06], s: 0.30, sh: 40, seam: 0, greeble: 0,
          e: [0.24, 1.00, 0.34] }
    ];

    // ---------------------------------------------------------------
    // Surface variation. Evaluated once per shaded pixel, never in the
    // march, so it is allowed to be expensive. Seeded deterministically
    // from integer cell indices, so a panel keeps its shade forever.
    // ---------------------------------------------------------------

    function hash2i(i, j) {
        let h = Math.imul(i | 0, 374761393) + Math.imul(j | 0, 668265263);
        h = Math.imul(h ^ h >>> 13, 1274126177);
        return ((h ^ h >>> 16) >>> 0) / 4294967296;
    }

    /**
     * Signed bevel slope across a panel cell. Zero through the middle of
     * a panel, rising to a peak at the cell edge with the sign that
     * tilts the shading normal back into the panel - so a plate looks
     * like a plate, with its edges catching the key light separately
     * from its face. `t` is the offset from the cell centre in [-0.5,
     * 0.5]; the profile is the derivative of a smoothstep, so it is
     * continuous and bounded rather than a hard crease.
     */
    function bevel(t) {
        const a = t < 0 ? -t : t;
        if (a < 0.40) return 0;
        const u = (a - 0.40) * 10;
        const s = 6 * u * (1 - u);
        return t < 0 ? s : -s;
    }

    /** Smooth 1D value noise, used for brushed-metal streaking. */
    function noise1(t) {
        const i = Math.floor(t);
        const f = t - i;
        const u = f * f * (3 - 2 * f);
        const a = hash2i(i, 7717);
        const b = hash2i(i + 1, 7717);
        return a + (b - a) * u;
    }

    /** mulberry32 over FNV-1a, the same pair planet-art.js seeds with. */
    function makeRng(key) {
        let h = 2166136261;
        for (let i = 0; i < key.length; i++) {
            h ^= key.charCodeAt(i);
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

    // ---------------------------------------------------------------
    // The march and its lighting queries
    // ---------------------------------------------------------------

    /** Closest-approach ratio of the last missed primary ray. */
    let MISS = 1e9;

    /**
     * The march. Returns the hit distance or -1, and leaves the
     * closest approach ratio in MISS so a ray that just grazes the
     * silhouette can be turned into partial coverage. That is where
     * the edge antialiasing comes from, and it costs nothing.
     */
    function march(scene, ox, oy, oz, dx, dy, dz, tStart, tEnd) {
        let t = tStart;
        let closest = 1e9;
        for (let i = 0; i < MARCH_STEPS; i++) {
            const h = scene(ox + dx * t, oy + dy * t, oz + dz * t);
            const eps = SURF_EPS * (1 + t * 0.6);
            if (h < eps) { MISS = 0; return t; }
            const ratio = h / t;
            if (ratio < closest) closest = ratio;
            t += h * 0.92;
            if (t > tEnd) break;
        }
        MISS = closest;
        return -1;
    }

    /** Tetrahedral central differences: four taps instead of six. */
    function surfaceNormal(scene, x, y, z, out) {
        const h = NORMAL_EPS;
        const a = scene(x + h, y - h, z - h);
        const b = scene(x - h, y - h, z + h);
        const c = scene(x - h, y + h, z - h);
        const d = scene(x + h, y + h, z + h);
        let nx = a - b - c + d;
        let ny = -a - b + c + d;
        let nz = -a + b - c + d;
        const l = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
        out[0] = nx / l; out[1] = ny / l; out[2] = nz / l;
    }

    /**
     * Soft shadow by closest approach. The penumbra falls out of the
     * ratio of clearance to distance travelled, which is why a ring
     * throws a believable graduated shadow across its own core
     * instead of a hard stencil.
     */
    function softShadow(scene, x, y, z, lx, ly, lz) {
        let res = 1;
        let t = 0.022;
        for (let i = 0; i < SHADOW_STEPS; i++) {
            const h = scene(x + lx * t, y + ly * t, z + lz * t);
            if (h < 0.0009) return 0;
            const s = SHADOW_K * h / t;
            if (s < res) res = s;
            if (res < 0.004) return 0;
            t += h < 0.014 ? 0.014 : (h > 0.22 ? 0.22 : h);
            if (t > SHADOW_MAX) break;
        }
        return res < 0 ? 0 : (res > 1 ? 1 : res);
    }

    /**
     * Ambient occlusion by walking the field out along the normal.
     * Where the field falls short of the step, something is nearby,
     * so recesses darken. This is what makes a docking bay read as
     * a hole rather than as a dark rectangle.
     */
    function ambient(scene, x, y, z, nx, ny, nz) {
        let occ = 0, sca = 1;
        for (let i = 1; i <= AO_TAPS; i++) {
            const hr = AO_SPAN * i / AO_TAPS;
            const d = scene(x + nx * hr, y + ny * hr, z + nz * hr);
            occ += (hr - d) * sca;
            sca *= 0.72;
        }
        const a = 1 - 2.6 * occ;
        return a < 0 ? 0 : (a > 1 ? 1 : a);
    }

    // ---------------------------------------------------------------
    // The full frame: camera, lights, shading, tonemap
    // ---------------------------------------------------------------

    /**
     * Render one design to a raw RGBA buffer. `spec` carries the scene
     * function and the camera/lighting record {bound, yaw, pitch, roll,
     * fill, winRows, winDens|winCols, point, cool}; `seedKey` feeds the
     * deterministic per-design jitter; `materials` is the table the
     * scene's material indices resolve against. No DOM is touched.
     */
    function paint(spec, seedKey, size, materials) {
        const P = spec;
        const scene = P.scene;
        const winDens = P.winDens != null ? P.winDens : (P.winCols || 0);
        const rng = makeRng(seedKey);
        // per-design jitter, drawn in a fixed order
        const jYaw = (rng() - 0.5) * 0.10;
        const jPitch = (rng() - 0.5) * 0.06;
        const seamPhase = rng() * 8;
        const winSeed = Math.floor(rng() * 4096);
        const grain = 0.010 + rng() * 0.008;

        const half = 0.42;                       // half the vertical fov
        const bound = P.bound;
        const dist = bound / (Math.tan(half) * P.fill);

        const yaw = P.yaw + jYaw;
        const pitch = P.pitch + jPitch;
        const cy2 = Math.cos(yaw), sy2 = Math.sin(yaw);
        const cp = Math.cos(pitch), sp = Math.sin(pitch);

        // camera basis: forward toward the origin, right, then up
        const ox = dist * sy2 * cp;
        const oy = dist * sp;
        const oz = dist * cy2 * cp;
        const fx = -ox / dist, fy = -oy / dist, fz = -oz / dist;
        // right = normalize(cross(worldUp, forward)) with a roll applied
        let rx = -fz, ry = 0, rz = fx;
        let rl = Math.sqrt(rx * rx + rz * rz) || 1;
        rx /= rl; rz /= rl;
        let ux = ry * fz - rz * fy;
        let uy = rz * fx - rx * fz;
        let uz = rx * fy - ry * fx;
        const cr = Math.cos(P.roll), sr = Math.sin(P.roll);
        const rx2 = rx * cr + ux * sr, ry2 = ry * cr + uy * sr;
        const rz2 = rz * cr + uz * sr;
        const ux2 = ux * cr - rx * sr, uy2 = uy * cr - ry * sr;
        const uz2 = uz * cr - rz * sr;

        const tanHalf = Math.tan(half);

        // key light, warm white, from the upper left and in front
        let kx = -0.62, ky = 0.66, kz = 0.42;
        let kl = Math.sqrt(kx * kx + ky * ky + kz * kz);
        kx /= kl; ky /= kl; kz /= kl;
        // cool fill from the opposite side: reflected planetlight, dim,
        // unshadowed, and the reason the dark side is not black
        let ax = 0.55, ay2 = -0.50, az = -0.42;
        const al = Math.sqrt(ax * ax + ay2 * ay2 + az * az);
        ax /= al; ay2 /= al; az /= al;

        const KEY = [1.30, 1.24, 1.14];
        const FILL = [0.34, 0.44, 0.62];
        const SKY = [0.16, 0.20, 0.30];
        const RIM = [0.62, 0.76, 1.00];
        const cool = P.cool ? 1 : 0;
        const pt = P.point || null;

        const out = new Uint8ClampedArray(size * size * 4);
        const n = [0, 0, 0];
        const b2 = bound * 1.04;
        const b2sq = b2 * b2;
        // the ray origin never moves, so the bounding-sphere quadratic
        // shares these two terms across every pixel
        const oo = ox * ox + oy * oy + oz * oz;
        const cTerm = oo - b2sq;

        for (let py = 0; py < size; py++) {
            const sv = -((py + 0.5) / size * 2 - 1) * tanHalf;
            const row = py * size * 4;
            for (let pxi = 0; pxi < size; pxi++) {
                const su = ((pxi + 0.5) / size * 2 - 1) * tanHalf;
                let dx = fx + rx2 * su + ux2 * sv;
                let dy = fy + ry2 * su + uy2 * sv;
                let dz = fz + rz2 * su + uz2 * sv;
                const dl = Math.sqrt(dx * dx + dy * dy + dz * dz);
                dx /= dl; dy /= dl; dz /= dl;

                // reject rays that miss the bounding sphere outright,
                // and start the rest at the sphere rather than at the
                // camera - this is most of the performance budget
                const bq = ox * dx + oy * dy + oz * dz;
                const disc = bq * bq - cTerm;
                if (disc <= 0) continue;
                const sq = Math.sqrt(disc);
                const tNear = -bq - sq;
                const tFar = -bq + sq;
                if (tFar <= 0) continue;

                const t = march(scene, ox, oy, oz, dx, dy, dz,
                    tNear > 0.01 ? tNear : 0.01,
                    tFar < MAX_DIST ? tFar : MAX_DIST);
                const i = row + pxi * 4;

                if (t < 0) {
                    // silhouette coverage from the closest approach:
                    // a ray that nearly grazed the hull is a partly
                    // covered pixel, which antialiases the outline
                    const cov = 1 - clamp01(MISS / 0.0075);
                    if (cov <= 0.02) continue;
                    // shade the near-miss as the dimmest hull value so
                    // the feather does not tint the edge
                    out[i] = 26 * cov;
                    out[i + 1] = 30 * cov;
                    out[i + 2] = 38 * cov;
                    out[i + 3] = 255 * cov * 0.55;
                    continue;
                }

                const mat = MAT;
                const hx = ox + dx * t, hy = oy + dy * t, hz = oz + dz * t;
                surfaceNormal(scene, hx, hy, hz, n);
                const nx = n[0], ny = n[1], nz = n[2];

                const M = materials[mat] || materials[0];
                let ar = M.a[0], ag = M.a[1], ab = M.a[2];
                let sx = nx, sy = ny, sz = nz;

                // ---- surface variation -------------------------
                // Panels are bump mapped, not just tinted. Tilting the
                // shading normal along a seam is what makes plating
                // read as bolted-on sheet rather than as paint: the
                // specular breaks at every panel edge, and that break
                // is the single strongest manufactured cue there is.
                if (M.seam > 0) {
                    // triplanar frame: pick the two world axes that lie
                    // in the surface, so seams wrap the hull correctly
                    const anx = Math.abs(nx), any = Math.abs(ny);
                    const anz = Math.abs(nz);
                    let pu, pv, tux, tuy, tuz, tvx, tvy, tvz;
                    if (anx >= any && anx >= anz) {
                        pu = hz; pv = hy;
                        tux = 0; tuy = 0; tuz = 1;
                        tvx = 0; tvy = 1; tvz = 0;
                    } else if (any >= anz) {
                        pu = hx; pv = hz;
                        tux = 1; tuy = 0; tuz = 0;
                        tvx = 0; tvy = 0; tvz = 1;
                    } else {
                        pu = hx; pv = hy;
                        tux = 1; tuy = 0; tuz = 0;
                        tvx = 0; tvy = 1; tvz = 0;
                    }

                    let bu = 0, bv = 0;
                    // coarse plating grid
                    const gu = pu * M.seam + seamPhase;
                    const gv = pv * M.seam + seamPhase;
                    const cu = Math.floor(gu), cv = Math.floor(gv);
                    const du = gu - cu - 0.5, dv = gv - cv - 0.5;
                    // a panel either stands proud or is let in, chosen
                    // once per cell and kept forever
                    const pk = hash2i(cu + winSeed, cv);
                    const step = (pk > 0.62 ? 1 : (pk < 0.20 ? -1 : 0))
                        * M.greeble;
                    const k = 1 + (pk - 0.5) * 0.22 + step * 0.05;
                    ar *= k; ag *= k; ab *= k;
                    // Panel families. A real hull is not one grey: it
                    // is plate, charcoal composite and gold thermal
                    // blanket in patches, and that hue variation does
                    // more for the photographed read than any amount
                    // of extra geometry.
                    // The family grid is deliberately COARSER than the
                    // panel grid: a treatment covers a run of plates,
                    // the way a real blanket or radiator section does.
                    // Hashing per panel instead turns the hull into a
                    // camouflage quilt.
                    if (M.greeble > 0.4) {
                        const fam = hash2i(
                            (cu >= 0 ? cu / 4 : (cu - 3) / 4) | 0,
                            ((cv >= 0 ? cv / 3 : (cv - 2) / 3) | 0)
                                + winSeed);
                        if (fam > 0.93) {
                            // thermal blanket, warm and dull
                            ar *= 1.14; ag *= 0.95; ab *= 0.60;
                        } else if (fam > 0.80) {
                            // charcoal composite
                            ar *= 0.55; ag *= 0.57; ab *= 0.61;
                        } else if (fam < 0.08) {
                            // cold white radiative plate
                            ar *= 1.10; ag *= 1.12; ab *= 1.16;
                        }
                    }
                    bu += bevel(du) * (0.30 + 0.22 * step);
                    bv += bevel(dv) * (0.30 + 0.22 * step);
                    // seam line itself darkens: a shadowed hairline
                    const edge = Math.max(Math.abs(du), Math.abs(dv));
                    if (edge > 0.462) {
                        const s = 1 - (edge - 0.462) / 0.038 * 0.55;
                        ar *= s; ag *= s; ab *= s;
                    }

                    // fine sub-panel grid: rivet lines and access hatches
                    const fu = gu * 3.7, fv = gv * 3.7;
                    bu += bevel(fu - Math.floor(fu) - 0.5) * 0.11;
                    bv += bevel(fv - Math.floor(fv) - 0.5) * 0.11;

                    // brushed-metal streaking along the panel grain
                    const st = 0.95 + noise1(pv * 130 + seamPhase) * 0.10;
                    ar *= st; ag *= st; ab *= st;
                    bu += (noise1(pv * 130 + seamPhase) - 0.5) * 0.05;

                    // low-frequency weathering: scorch and thruster
                    // wash, uneven across the whole hull
                    const wg = 0.80 + 0.24 * noise1(pu * 1.7 + 40)
                        * noise1(pv * 2.3 + 90) * 2;
                    ar *= wg; ag *= wg * 0.995; ab *= wg * 0.985;

                    sx = nx + tux * bu + tvx * bv;
                    sy = ny + tuy * bu + tvy * bv;
                    sz = nz + tuz * bu + tvz * bv;
                    const sl = Math.sqrt(sx * sx + sy * sy + sz * sz) || 1;
                    sx /= sl; sy /= sl; sz /= sl;
                }

                // ---- emissive windows --------------------------
                let er = 0, eg = 0, eb = 0, emAO = 0;
                if (M.e) {
                    let ek = 1;
                    if (M.vol) {
                        const f = -(nx * dx + ny * dy + nz * dz);
                        ek = 0.22 + 0.78 * clamp01(f) * clamp01(f);
                    }
                    if (M.plasma) {
                        // Churn, so the core is not a flat orange disc.
                        // A uniform emitter really is uniform across
                        // its disc, which is exactly why an untextured
                        // one reads as a decal rather than a volume.
                        ek *= 0.40 + 1.10 * noise1(hx * 8.5 + hz * 3.1)
                            * noise1(hy * 7.3 - hx * 2.7 + 11);
                        ek *= 0.72 + 0.50 * noise1(hy * 21 + hx * 9 + 3);
                        emAO = 1;
                    }
                    er = M.e[0] * ek; eg = M.e[1] * ek; eb = M.e[2] * ek;
                } else if (M.win && P.winRows > 0) {
                    // rows in y, cells around the axis: a habitat
                    // hull with the lights on
                    const wv = hy * P.winRows;
                    const rw = Math.abs(wv - Math.round(wv));
                    if (rw < 0.115) {
                        // Columns are spaced by ARC LENGTH, not by
                        // angle. Dividing the angle evenly gives a
                        // narrow command drum the same window count as
                        // a 1.2 radius habitat ring, which comes out as
                        // a bead necklace rather than as windows.
                        const rr = Math.sqrt(hx * hx + hz * hz) || 1e-6;
                        const wa = Math.atan2(hz, hx);
                        const wu = wa * rr * winDens;
                        const wc = Math.floor(wu);
                        const cw = Math.abs(wu - wc - 0.5);
                        if (cw < 0.30) {
                            const lit = hash2i(wc + winSeed,
                                Math.round(wv) * 31);
                            if (lit > 0.34) {
                                // face the window outward only
                                const facing = (nx * hx + nz * hz) / rr;
                                if (facing > 0.35) {
                                    const g = (0.45 + lit * 0.85) * facing;
                                    er = 1.00 * g;
                                    eg = 0.72 * g;
                                    eb = 0.40 * g;
                                    ar *= 0.35; ag *= 0.35; ab *= 0.35;
                                }
                            }
                        }
                    }
                }

                // ---- lighting ----------------------------------
                // The geometric normal aims the shadow and AO rays,
                // because those march the real field; the perturbed
                // normal does the shading.
                const ndl = sx * kx + sy * ky + sz * kz;
                let sh = 0;
                if (nx * kx + ny * ky + nz * kz > -0.12) {
                    sh = softShadow(scene, hx + nx * 0.006,
                        hy + ny * 0.006, hz + nz * 0.006, kx, ky, kz);
                }
                const ao = ambient(scene, hx, hy, hz, nx, ny, nz);
                const dif = (ndl > 0 ? ndl : 0) * sh;

                // Blinn-Phong specular with a Schlick Fresnel factor,
                // which is what gives metal its tight bright highlight
                let spc = 0;
                if (dif > 0) {
                    let bx2 = kx - dx, by2 = ky - dy, bz2 = kz - dz;
                    const bl = Math.sqrt(bx2 * bx2 + by2 * by2 + bz2 * bz2)
                        || 1;
                    bx2 /= bl; by2 /= bl; bz2 /= bl;
                    const ndh = sx * bx2 + sy * by2 + sz * bz2;
                    if (ndh > 0) {
                        const vdh = -(dx * bx2 + dy * by2 + dz * bz2);
                        const f = 0.04 + 0.96
                            * Math.pow(1 - clamp01(vdh), 5);
                        spc = Math.pow(ndh, M.sh) * M.s * sh * (0.26 + f);
                    }
                }

                // Cool fill, unshadowed, standing in for planetlight.
                // Deliberately weak: fill and ambient together have to
                // stay well under the key or the shadow side comes up
                // to meet the lit side and the whole render goes flat
                // grey, which is the first thing that stops a picture
                // reading as a photograph.
                const ndf = sx * ax + sy * ay2 + sz * az;
                const fil = (ndf > 0 ? ndf : 0) * 0.26 * ao;

                // hemispheric ambient, gated hard by occlusion
                const amb = (0.25 + 0.75 * (sy * 0.5 + 0.5)) * 0.15 * ao;

                let r = ar * (KEY[0] * dif + FILL[0] * fil + SKY[0] * amb);
                let g = ag * (KEY[1] * dif + FILL[1] * fil + SKY[1] * amb);
                let b = ab * (KEY[2] * dif + FILL[2] * fil + SKY[2] * amb);

                // a warm interior point light: a shipyard slip, a
                // reactor core or a drive plume bouncing onto the hull
                if (pt) {
                    let lx2 = pt[0] - hx, ly2 = pt[1] - hy, lz2 = pt[2] - hz;
                    const ll = Math.sqrt(lx2 * lx2 + ly2 * ly2 + lz2 * lz2)
                        || 1;
                    lx2 /= ll; ly2 /= ll; lz2 /= ll;
                    const nd = sx * lx2 + sy * ly2 + sz * lz2;
                    if (nd > 0) {
                        const at = pt[6] / (1 + ll * ll * 2.2) * nd * ao;
                        r += ar * pt[3] * at;
                        g += ag * pt[4] * at;
                        b += ab * pt[5] * at;
                    }
                }

                // specular is white for the key, tinted cool if the
                // design is lit cold from outside
                r += spc * (cool ? 0.86 : 1.00);
                g += spc * (cool ? 0.92 : 0.98);
                b += spc * (cool ? 1.00 : 0.94);

                // Fresnel rim: grazing angles brighten, which is what
                // separates a curved hull from a flat painted disc
                const vdn = -(nx * dx + ny * dy + nz * dz);
                const fr = Math.pow(1 - clamp01(vdn), 5) * 0.42 * ao;
                r += RIM[0] * fr; g += RIM[1] * fr; b += RIM[2] * fr;

                // Emissive last, untouched by shadow: window rows and
                // running lights have to survive on the dark side.
                // A reactor core down a well is the exception - the
                // walls of the well genuinely block its own light, so
                // that one term is allowed to see the occlusion.
                const ek2 = emAO ? (0.42 + 0.58 * ao) : 1;
                r += er * ek2; g += eg * ek2; b += eb * ek2;

                // fine grain: sensor noise, deterministic per pixel
                const gz = (hash2i(pxi + winSeed, py) - 0.5) * grain;
                r += gz; g += gz; b += gz;

                // filmic-ish tonemap then gamma, so highlights roll
                // off instead of clipping to flat white
                r = r / (1 + r); g = g / (1 + g); b = b / (1 + b);
                out[i] = 255 * Math.pow(r * 1.42, 0.4545);
                out[i + 1] = 255 * Math.pow(g * 1.42, 0.4545);
                out[i + 2] = 255 * Math.pow(b * 1.42, 0.4545);
                out[i + 3] = 255;
            }
        }
        return out;
    }

    // ---------------------------------------------------------------
    // Renderer plumbing shared by both views: bitmap cache keyed by
    // design name and pixel size, canvas blit, cold-render timing.
    // ---------------------------------------------------------------

    function makeRenderer(opts) {
        return {
            CACHE_MAX: opts.cacheMax || 24,
            cache: new Map(),
            lastRenderMs: 0,
            classify: opts.classify,

            /**
             * Draw the design onto `canvas`, scaling if the canvas is
             * not the rendered size. Cached per design and size, so
             * reopening the view is a single drawImage.
             */
            render(canvas, hull, size) {
                const ctx = canvas.getContext('2d');
                const W = canvas.width, H = canvas.height;
                ctx.clearRect(0, 0, W, H);
                if (!W || !H) return;
                const n = size || Math.min(W, H);
                const px = this.renderPixels(hull, n);
                const img = ctx.createImageData(n, n);
                img.data.set(px);
                if (n === W && n === H) {
                    ctx.putImageData(img, 0, 0);
                    return;
                }
                const tmp = document.createElement('canvas');
                tmp.width = tmp.height = n;
                tmp.getContext('2d').putImageData(img, 0, 0);
                ctx.drawImage(tmp, 0, 0, n, n, 0, 0, W, H);
            },

            /**
             * Render one design to a raw RGBA buffer. No DOM is
             * touched, which is what lets the tests exercise the real
             * renderer in node rather than a port of it.
             */
            renderPixels(hull, size) {
                const cls = this.classify(hull);
                const key = cls + '|' + size;
                let px = this.cache.get(key);
                if (px) {
                    this.cache.delete(key);
                    this.cache.set(key, px);
                    return px;
                }
                const t0 = (typeof performance !== 'undefined')
                    ? performance.now() : Date.now();
                px = paint(opts.designs[cls], cls, size, opts.materials);
                this.lastRenderMs = ((typeof performance !== 'undefined')
                    ? performance.now() : Date.now()) - t0;
                this.cache.set(key, px);
                while (this.cache.size > this.CACHE_MAX) {
                    this.cache.delete(this.cache.keys().next().value);
                }
                return px;
            }
        };
    }

    const SDFEngine = {
        TUNE: {
            MARCH_STEPS: MARCH_STEPS, MAX_DIST: MAX_DIST,
            SURF_EPS: SURF_EPS, SHADOW_STEPS: SHADOW_STEPS,
            AO_TAPS: AO_TAPS, NORMAL_EPS: NORMAL_EPS
        },
        MATERIALS: MATERIALS,
        sdf: {
            sphere: sdSphere, box: sdBox, roundBox: sdRoundBox,
            cyl: sdCyl, cylInf: sdCylInf, roundCyl: sdRoundCyl,
            torus: sdTorus, arc: sdArc, capsule: sdCapsule,
            ellipsoid: sdEllipsoid,
            union: opU, smoothUnion: opSU, subtract: opSub,
            smoothSubtract: opSSub, intersect: opI
        },
        clamp01: clamp01,
        FOLD: FOLD,
        foldRadial: foldRadial,
        repLimit: repLimit,
        hash2i: hash2i,
        bevel: bevel,
        noise1: noise1,
        makeRng: makeRng,
        getMat: function () { return MAT; },
        setMat: function (m) { MAT = m; },
        march: march,
        surfaceNormal: surfaceNormal,
        softShadow: softShadow,
        ambient: ambient,
        paint: paint,
        makeRenderer: makeRenderer
    };

    if (typeof window !== 'undefined') window.SDFEngine = SDFEngine;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = SDFEngine;
    }
})();
