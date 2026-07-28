/**
 * Stars Nova Web - photoreal orbital station renderer
 *
 * A LARGE detail view (256 px and up) for the starbase in orbit. This is
 * not the star panel sprite: planet-art.js still draws that at eight to
 * eleven pixels and nothing here touches it. The split is exactly what
 * makes the look possible, because photorealism needs pixels to live in.
 *
 * Technique: signed distance field sphere tracing, per pixel, into an
 * ImageData buffer - the same per-pixel pattern planet-art.js proves out
 * on this canvas. Every primitive is an exact analytic distance function,
 * so unions, cuts and smooth-union fairings come out with real curvature,
 * and the march itself pays for the three cues that read as photographed:
 * soft shadows from the closest-approach ratio, ambient occlusion sampled
 * along the normal, and true occlusion between parts.
 *
 * Deterministic: Math.random is never used. Per-class jitter is drawn
 * from one mulberry32 seeded on the hull name, in a fixed order, so a
 * class renders byte for byte identically on every visit.
 *
 * Reference art: references/original-game/Graphics/High_Resolution/Base/
 * establishes the class ladder - Orbital Fort two armoured nodes, Space
 * Dock three, Space Station four, Ultra Station six, Death Star a sphere
 * inside a strut cage. The ladder and the silhouettes are canon. The
 * 1990s purple plastic finish is not.
 *
 * No class carries an external gun. A hull this size mounts its
 * emplacements internally, behind recessed ports, and the Shipyard
 * mounts none at all.
 */
(function () {
    'use strict';

    // ---------------------------------------------------------------
    // March tunables. These are the whole performance story: cost is
    // (pixels) x (MARCH_STEPS + 4 normal taps + SHADOW_STEPS + AO_TAPS)
    // scene evaluations. Raising MARCH_STEPS buys grazing-angle
    // accuracy, SHADOW_STEPS buys penumbra length, AO_TAPS buys recess
    // depth. The bounding-sphere entry test below is what keeps the
    // empty half of the frame free.
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
    // Scenes. One function per class, each returning the distance to
    // the whole station and leaving its material in MAT.
    //
    // Every class is built from solid volumes faired together, never
    // from thin spars: mass is what survives lighting. The ladder from
    // the reference art is carried in the node count, not in scale.
    // ---------------------------------------------------------------

    /**
     * Orbital Fort. A short pressurised drum on an axle with one
     * armoured node capping each end - the canon pair. Dock capacity is
     * zero, so there is no bay anywhere on it. The ring of recessed
     * ports around the drum equator is the internal emplacement battery.
     */
    function sceneFort(x, y, z) {
        MAT = 1;
        // axle running the full length, node to node
        let d = sdCyl(y, x, z, 1.00, 0.105);

        // two armoured nodes, folded onto the axle ends. Hard fillets,
        // not soft ones: armour is faceted, and a big smoothing radius
        // is what made the first pass read as inflated plastic.
        const ay = Math.abs(y) - 0.78;
        d = opSU(d, sdRoundBox(x, ay, z, 0.31, 0.23, 0.31, 0.045), 0.05, 0);
        // collar tying each node down to the drum
        d = opSU(d, sdCyl(ay + 0.20, x, z, 0.09, 0.36), 0.05, 1);

        // pressurised drum amidships, taller and narrower than the nodes
        // are wide, so the silhouette steps rather than bulges
        d = opSU(d, sdRoundCyl(y, x, z, 0.36, 0.62, 0.06), 0.06, 2);
        // rib bands around the drum
        const by = Math.abs(y) - 0.24;
        d = opU(d, sdTorus(by, x, z, 0.62, 0.035), 0);

        // equatorial trench: the groove is what gives the drum a waist
        d = opSub(d, sdTorus(y, x, z, 0.63, 0.05), 5);

        // six recessed emplacement ports around the trench, folded
        foldRadial(x, z, 6);
        d = opSub(d, sdCyl(FOLD[0] - 0.66, y, FOLD[1], 0.13, 0.085), 5);

        // running lights on the node caps
        d = opU(d, sdSphere(x, y - 1.02, z, 0.042), 10);
        d = opU(d, sdSphere(x, y + 1.02, z, 0.042), 11);
        return d;
    }

    /**
     * Space Dock. The fort architecture one step up: a larger drum,
     * three armoured nodes on the rim rather than two on the axle, and
     * a real docking bay let into the forward face. Two hundred kT of
     * capacity buys a notch, not a cavern, so the recess is shallow and
     * the warm slab at the back of it is what sells the depth.
     */
    function sceneDock(x, y, z) {
        MAT = 1;
        let d = sdCyl(y, x, z, 1.00, 0.11);

        // axle caps
        const ay = Math.abs(y) - 0.94;
        d = opSU(d, sdRoundBox(x, ay, z, 0.23, 0.14, 0.23, 0.04), 0.05, 0);

        // main drum
        d = opSU(d, sdRoundCyl(y, x, z, 0.42, 0.78, 0.07), 0.06, 2);

        // three armoured nodes bolted to the rim
        foldRadial(x, z, 3);
        d = opSU(d, sdRoundBox(FOLD[0] - 0.82, y, FOLD[1],
            0.20, 0.26, 0.22, 0.05), 0.07, 0);

        // twin equatorial trenches
        const ty = Math.abs(y) - 0.22;
        d = opSub(d, sdTorus(ty, x, z, 0.79, 0.04), 5);

        // emplacement ports, six around the rim
        foldRadial(x, z, 6);
        d = opSub(d, sdCyl(FOLD[0] - 0.80, y - 0.32, FOLD[1], 0.12, 0.07), 5);

        // Docking bay recessed into the forward face. Two hundred kT of
        // capacity is a notch, not a cavern, so the mouth is modest and
        // it is the occlusion inside that carries the depth.
        d = opSSub(d, sdRoundBox(x, y + 0.02, z - 0.90, 0.30, 0.19, 0.28, 0.05),
            0.04, 5);
        // floodlit back wall of the bay
        d = opU(d, sdRoundBox(x, y + 0.02, z - 0.58, 0.26, 0.15, 0.02, 0.01), 4);
        // approach guides either side of the mouth
        d = opU(d, sdSphere(Math.abs(x) - 0.32, y + 0.02, z - 0.66, 0.032), 3);

        d = opU(d, sdSphere(x, y - 1.06, z, 0.042), 10);
        d = opU(d, sdSphere(x, y + 1.06, z, 0.042), 11);
        return d;
    }

    /**
     * Space Station. Deep Space 9: a habitat ring carried around a
     * central core on curved pylons, four habitat pods on the ring, and
     * the docking bay let into the core itself. The pylons are bent by
     * offsetting the axial coordinate as a function of radius, which is
     * a domain warp rather than a real curved primitive - the distance
     * is scaled down afterwards to keep the march from overstepping.
     */
    function sceneStation(x, y, z) {
        MAT = 2;
        // core spindle: an ellipsoid with a command drum top and bottom
        let d = sdEllipsoid(x, y, z, 0.40, 0.56, 0.40);
        const cy = Math.abs(y) - 0.62;
        d = opSU(d, sdRoundCyl(cy, x, z, 0.12, 0.28, 0.04), 0.10, 2);
        // waist collar where the pylons root
        d = opSU(d, sdRoundCyl(y, x, z, 0.10, 0.46, 0.04), 0.06, 0);

        // habitat ring: a flattened torus, wider than it is deep, so it
        // reads as a deck rather than as a pipe
        const ring = sdTorus(y * 1.5, x, z, 1.14, 0.135) / 1.5;
        d = opU(d, ring, 2);
        // guard rails top and bottom of the ring
        const gy = Math.abs(y) - 0.10;
        d = opU(d, sdTorus(gy, x, z, 1.13, 0.028), 0);

        foldRadial(x, z, 4);
        const fx = FOLD[0], fz = FOLD[1];

        // habitat pods sitting on the ring
        d = opSU(d, sdRoundBox(fx - 1.14, y, fz, 0.19, 0.21, 0.17, 0.045),
            0.05, 2);

        // Curved pylons, upper and lower, core out to ring. The curve is
        // a domain warp - the axial coordinate is offset as a function of
        // radius - so the distance is no longer exact and the result is
        // scaled down to keep the march from stepping through it.
        const u = 1 - clamp01((fx - 0.36) / 0.78);
        const py = Math.abs(y) - 0.32 * u * u;
        const pylon = sdRoundBox(fx - 0.75, py, fz, 0.42, 0.052, 0.115, 0.035);
        d = opSU(d, pylon * 0.8, 0.05, 1);

        // docking bay let into the forward face of the core
        d = opSSub(d, sdRoundBox(x, y - 0.04, z - 0.48, 0.23, 0.15, 0.22, 0.05),
            0.035, 5);
        d = opU(d, sdRoundBox(x, y - 0.04, z - 0.25, 0.19, 0.11, 0.02, 0.01), 4);

        // recessed emplacement ports around the core waist
        foldRadial(x, z, 6);
        d = opSub(d, sdCyl(FOLD[0] - 0.42, y + 0.28, FOLD[1], 0.10, 0.062), 5);

        d = opU(d, sdSphere(x, y - 0.80, z, 0.042), 10);
        d = opU(d, sdSphere(x, y + 0.80, z, 0.042), 11);
        return d;
    }

    /**
     * Ultra Station. The same architecture a generation on: a heavier
     * rim, a bigger core, six habitat pods faired into the rim instead
     * of sitting on it, and radiator and solar arrays spread above and
     * below on short spars. The fairing radius is what carries the
     * generational difference - the pods melt into the rim rather than
     * bolting to it.
     */
    function sceneUltra(x, y, z) {
        MAT = 2;
        let d = sdEllipsoid(x, y, z, 0.48, 0.68, 0.48);
        const cy = Math.abs(y) - 0.74;
        d = opSU(d, sdRoundCyl(cy, x, z, 0.14, 0.33, 0.05), 0.11, 2);
        d = opSU(d, sdRoundCyl(y, x, z, 0.12, 0.56, 0.04), 0.07, 0);

        // heavy rim, flattened so it reads as a deck ring
        const rim = sdTorus(y * 1.35, x, z, 1.18, 0.19) / 1.35;
        d = opU(d, rim, 2);
        const gy = Math.abs(y) - 0.13;
        d = opU(d, sdTorus(gy, x, z, 1.17, 0.030), 0);

        foldRadial(x, z, 6);
        const fx = FOLD[0], fz = FOLD[1];

        // Six pods faired INTO the rim rather than perched on it - the
        // generational difference from the Space Station is carried by
        // the fairing radius, not by scale.
        d = opSU(d, sdRoundBox(fx - 1.18, y, fz, 0.20, 0.29, 0.19, 0.05),
            0.13, 2);

        // twin pylons per sector, arcing out from the core
        const u = 1 - clamp01((fx - 0.44) / 0.74);
        const py = Math.abs(y) - 0.36 * u * u;
        const pylon = sdRoundBox(fx - 0.81, py, fz, 0.40, 0.062, 0.135, 0.04);
        d = opSU(d, pylon * 0.8, 0.06, 1);

        // radiator and solar arrays on spars above and below the core
        const ay = Math.abs(y);
        d = opU(d, sdCyl(ay - 0.96, x, z, 0.24, 0.05), 1);
        d = opU(d, sdRoundBox(x, ay - 1.16, z, 0.90, 0.014, 0.32, 0.012), 6);
        d = opU(d, sdRoundBox(z, ay - 1.16, x, 0.90, 0.014, 0.32, 0.012), 6);
        // panel spines, so the arrays are not bare sheets
        d = opU(d, sdCyl(x, ay - 1.16, z, 0.90, 0.028), 1);
        d = opU(d, sdCyl(z, ay - 1.16, x, 0.90, 0.028), 1);

        // bay into the core, wider than the Space Station's
        d = opSSub(d, sdRoundBox(x, y - 0.04, z - 0.56, 0.29, 0.18, 0.24, 0.05),
            0.04, 5);
        d = opU(d, sdRoundBox(x, y - 0.04, z - 0.30, 0.25, 0.14, 0.02, 0.01), 4);

        // emplacement ports around the rim
        foldRadial(x, z, 12);
        d = opSub(d, sdCyl(FOLD[0] - 1.20, y, FOLD[1], 0.09, 0.058), 5);

        d = opU(d, sdSphere(x, y - 0.90, z, 0.045), 10);
        d = opU(d, sdSphere(x, y + 0.90, z, 0.045), 11);
        return d;
    }

    /**
     * Death Star. The odd one out and the only sphere in the ladder: an
     * armoured hull inside a cage of strut rings, with the focusing
     * well cut into the forward face and the glowing core sitting at
     * the bottom of it. The core is also a point light, so the well
     * walls take a real orange bounce - that bounce is what stops the
     * cut reading as a painted-on disc.
     */
    function sceneSphere(x, y, z) {
        // The core is a real lit volume sitting under the armour, so
        // every cut that goes deep enough exposes it. Nothing here is a
        // painted-on glow.
        const core = sdSphere(x, y, z, 0.80);

        MAT = 0;
        let hull = sdSphere(x, y, z, 0.92);

        // equatorial trench, deep enough to reach the core: the orange
        // band between plates is the canon read from the reference art
        hull = opSub(hull, sdTorus(y, x, z, 0.93, 0.145), 5);
        // two latitude trenches, panel detail only
        const ty = Math.abs(y) - 0.50;
        hull = opSub(hull, sdTorus(ty, x, z, 0.79, 0.05), 5);
        // meridian grooves, twelve of them, cut on great circles
        foldRadial(x, z, 12);
        hull = opSub(hull, sdTorus(FOLD[1], FOLD[0], y, 0.93, 0.055), 5);
        // recessed emplacement ports around the upper hemisphere
        foldRadial(x, z, 8);
        hull = opSub(hull, sdCyl(FOLD[0] - 0.93, y - 0.30, FOLD[1],
            0.11, 0.07), 5);

        // focusing well cut into the forward face, down to the core
        const well = sdCyl(z - 1.05, x, y - 0.12, 0.76, 0.27);
        hull = opSSub(hull, well, 0.04, 5);

        // combine by hand: the operators carry the material of the last
        // surface they resolved, and the armour chain has been writing
        // into MAT the whole way down
        let d;
        if (core < hull) { d = core; MAT = 8; } else { d = hull; }

        // strut cage over the whole thing: three great circles and a
        // pair of latitude rings, standing clear of the armour
        let cage = sdTorus(y, x, z, 1.02, 0.052);
        cage = Math.min(cage, sdTorus(x, y, z, 1.02, 0.052));
        cage = Math.min(cage, sdTorus(z, x, y, 1.02, 0.052));
        const cy = Math.abs(y) - 0.60;
        cage = Math.min(cage, sdTorus(cy, x, z, 0.86, 0.042));
        d = opU(d, cage, 9);

        d = opU(d, sdSphere(x - 0.60, y + 0.72, z, 0.05), 10);
        d = opU(d, sdSphere(x + 0.60, y + 0.72, z, 0.05), 11);
        return d;
    }

    /**
     * Shipyard. An open scaffold with a part-built hull cradled inside
     * it - four longerons, a stack of square ribs, and gantries. The
     * hull's plating stops partway up and the frame ribs carry on bare,
     * which is the whole read: this is a ship being built, not a ship.
     *
     * The only class lit warm from inside and cool from outside, and
     * the only one with no emplacement anywhere. The absence of weapons
     * is half of what identifies it.
     */
    function sceneYard(x, y, z) {
        MAT = 1;
        // four corner longerons, folded by mirror rather than by angle
        const mx = Math.abs(x) - 0.62, mz = Math.abs(z) - 0.62;
        let d = sdRoundBox(mx, y, mz, 0.055, 1.06, 0.055, 0.02);

        // open square ribs repeated up the slip: thin bands, so the
        // cradled hull stays visible through the scaffold
        const ry = repLimit(y, 0.44, 2);
        const rib = Math.max(
            sdRoundBox(x, ry, z, 0.66, 0.032, 0.66, 0.016),
            -sdBox(x, ry, z, 0.57, 0.5, 0.57));
        d = opU(d, rib, 1);
        // One diagonal brace per bay per face. Folded four ways about the
        // axis so it costs a single primitive; the fold puts the folded
        // radial coordinate through the middle of a face, which is
        // exactly where a brace between two corner longerons belongs.
        foldRadial(x, z, 4);
        d = opU(d, sdCapsule(FOLD[0], repLimit(y, 0.44, 2), FOLD[1],
            0.62, -0.20, -0.56, 0.62, 0.20, 0.56, 0.026), 1);

        // end caps: heavier frames top and bottom
        const ey = Math.abs(y) - 1.06;
        const cap = Math.max(
            sdRoundBox(x, ey, z, 0.70, 0.055, 0.70, 0.025),
            -sdBox(x, ey, z, 0.54, 0.5, 0.54));
        d = opU(d, cap, 0);

        // gantry arms reaching in toward the hull
        d = opU(d, sdCapsule(x, y - 0.36, z, 0.60, 0, 0.60, 0.26, 0, 0.26,
            0.045), 1);
        d = opU(d, sdCapsule(x, y + 0.40, z, -0.60, 0, -0.60, -0.26, 0, -0.26,
            0.045), 1);

        // the hull in the cradle
        const ship = sdEllipsoid(x, y - 0.02, z, 0.36, 0.86, 0.36);
        // plating stops here; everything above the cut is bare frame
        const openBox = sdBox(x, y - 1.02, z, 1.4, 0.58, 1.4);
        const plated = ship > -openBox ? ship : -openBox;
        const platedMat = (-openBox > ship) ? 5 : 7;

        // Ribs of the unplated bow: a hollow shell of the same hull
        // sliced by repeated slabs, so the frames follow the real curve
        // of the ship instead of being drawn on. This is the whole read
        // of the class - a ship being built, not a ship.
        const shell = Math.abs(ship) - 0.024;
        const slab = Math.abs(repLimit(y - 0.02, 0.17, 8)) - 0.032;
        const frame = Math.max(Math.max(shell, slab), openBox);
        // and four stringers running the length of the bare section,
        // reusing the fold already computed for the scaffold bracing
        const stringer = Math.max(Math.max(shell, Math.abs(FOLD[1]) - 0.030),
            openBox);

        d = opU(d, plated, platedMat);
        d = opU(d, frame, 7);
        d = opU(d, stringer, 7);

        // warm work lights on the inside faces of the scaffold
        d = opU(d, sdSphere(mx, repLimit(y, 0.44, 2), mz, 0.045), 4);

        // and the floodlit deck plate at the foot of the slip
        d = opU(d, sdRoundCyl(y + 1.00, x, z, 0.025, 0.46, 0.015), 4);
        return d;
    }

    // ---------------------------------------------------------------
    // Class table. `bound` is the radius of the sphere the class fits
    // in, which drives both the camera framing and the ray rejection
    // test, so it has to be a true bound or silhouettes get clipped.
    // ---------------------------------------------------------------

    const CLASSES = {
        'Orbital Fort': {
            kind: 'fort', scene: sceneFort, bound: 1.32,
            yaw: 0.62, pitch: 0.28, roll: 0.10, fill: 0.86,
            winRows: 7, winDens: 5.2
        },
        'Space Dock': {
            kind: 'dock', scene: sceneDock, bound: 1.36,
            yaw: -0.34, pitch: 0.24, roll: 0.08, fill: 0.88,
            winRows: 6, winDens: 5.0
        },
        'Space Station': {
            kind: 'station', scene: sceneStation, bound: 1.42,
            yaw: 0.48, pitch: 0.36, roll: 0.05, fill: 0.90,
            winRows: 9, winDens: 5.4
        },
        'Ultra Station': {
            kind: 'ultra', scene: sceneUltra, bound: 1.52,
            yaw: -0.55, pitch: 0.40, roll: 0.04, fill: 0.92,
            winRows: 10, winDens: 5.6
        },
        'Death Star': {
            kind: 'sphere', scene: sceneSphere, bound: 1.10,
            yaw: 0.30, pitch: 0.22, roll: 0, fill: 0.88,
            // the point light sits at the mouth of the focusing well, not
            // at the sphere centre: a light buried inside its own hull
            // faces away from every surface and contributes nothing
            winRows: 0, winDens: 0, point: [0, -0.08, 0.62, 1.00, 0.42, 0.12, 2.4]
        },
        'Shipyard': {
            // a box needs a looser bounding sphere than a drum does: the
            // scaffold's top corners sit at 1.49, and a bound short of
            // that clips them out of the silhouette entirely
            kind: 'yard', scene: sceneYard, bound: 1.52,
            yaw: 0.72, pitch: 0.30, roll: 0.06, fill: 0.98,
            // work light inside the slip, offset off the ship's own axis
            // so it actually falls on the hull instead of inside it
            winRows: 0, winDens: 0,
            point: [0.50, -0.15, 0.50, 1.00, 0.58, 0.24, 3.4], cool: 1
        }
    };

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

    // ---------------------------------------------------------------
    // Renderer
    // ---------------------------------------------------------------

    const StationDetail = {

        /** Bitmap cache, keyed by hull name and pixel size. */
        CACHE_MAX: 24,
        cache: new Map(),
        lastRenderMs: 0,

        CLASSES: CLASSES,
        MATERIALS: MATERIALS,

        /** Exposed for tests: the primitive and operator library. */
        sdf: {
            sphere: sdSphere, box: sdBox, roundBox: sdRoundBox,
            cyl: sdCyl, cylInf: sdCylInf, roundCyl: sdRoundCyl,
            torus: sdTorus, capsule: sdCapsule, ellipsoid: sdEllipsoid,
            union: opU, smoothUnion: opSU, subtract: opSub,
            smoothSubtract: opSSub, intersect: opI
        },

        TUNE: {
            MARCH_STEPS: MARCH_STEPS, MAX_DIST: MAX_DIST,
            SURF_EPS: SURF_EPS, SHADOW_STEPS: SHADOW_STEPS,
            AO_TAPS: AO_TAPS, NORMAL_EPS: NORMAL_EPS
        },

        /**
         * Resolve a hull name to a class. Anything unrecognised falls
         * back the same way the star panel sprite does, so the two
         * views never disagree about what is in orbit.
         */
        classify(hull) {
            if (hull && CLASSES[hull]) return hull;
            if (hull && /yard|slip/i.test(hull)) return 'Shipyard';
            if (hull && /dock/i.test(hull)) return 'Space Dock';
            return 'Orbital Fort';
        },

        /**
         * Draw the station onto `canvas`, scaling if the canvas is not
         * the rendered size. Cached per class and size, so reopening
         * the view is a single drawImage.
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
         * Render one station to a raw RGBA buffer. No DOM is touched,
         * which is what lets the tests exercise the real renderer in
         * node rather than a port of it.
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
            px = this._paint(cls, size);
            this.lastRenderMs = ((typeof performance !== 'undefined')
                ? performance.now() : Date.now()) - t0;
            this.cache.set(key, px);
            while (this.cache.size > this.CACHE_MAX) {
                this.cache.delete(this.cache.keys().next().value);
            }
            return px;
        },

        /** mulberry32 over FNV-1a, the same pair planet-art.js seeds with. */
        _rng(key) {
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
        },

        /**
         * The march. Returns the hit distance or -1, and leaves the
         * closest approach ratio in _miss so a ray that just grazes the
         * silhouette can be turned into partial coverage. That is where
         * the edge antialiasing comes from, and it costs nothing.
         */
        _march(scene, ox, oy, oz, dx, dy, dz, tStart, tEnd) {
            let t = tStart;
            let closest = 1e9;
            for (let i = 0; i < MARCH_STEPS; i++) {
                const h = scene(ox + dx * t, oy + dy * t, oz + dz * t);
                const eps = SURF_EPS * (1 + t * 0.6);
                if (h < eps) { this._miss = 0; return t; }
                const ratio = h / t;
                if (ratio < closest) closest = ratio;
                t += h * 0.92;
                if (t > tEnd) break;
            }
            this._miss = closest;
            return -1;
        },

        /** Tetrahedral central differences: four taps instead of six. */
        _normal(scene, x, y, z, out) {
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
        },

        /**
         * Soft shadow by closest approach. The penumbra falls out of the
         * ratio of clearance to distance travelled, which is why a ring
         * throws a believable graduated shadow across its own core
         * instead of a hard stencil.
         */
        _shadow(scene, x, y, z, lx, ly, lz) {
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
        },

        /**
         * Ambient occlusion by walking the field out along the normal.
         * Where the field falls short of the step, something is nearby,
         * so recesses darken. This is what makes a docking bay read as
         * a hole rather than as a dark rectangle.
         */
        _ao(scene, x, y, z, nx, ny, nz) {
            let occ = 0, sca = 1;
            for (let i = 1; i <= AO_TAPS; i++) {
                const hr = AO_SPAN * i / AO_TAPS;
                const d = scene(x + nx * hr, y + ny * hr, z + nz * hr);
                occ += (hr - d) * sca;
                sca *= 0.72;
            }
            const a = 1 - 2.6 * occ;
            return a < 0 ? 0 : (a > 1 ? 1 : a);
        },

        _paint(cls, size) {
            const P = CLASSES[cls];
            const scene = P.scene;
            const rng = this._rng(cls);
            // per-class jitter, drawn in a fixed order
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

                    const t = this._march(scene, ox, oy, oz, dx, dy, dz,
                        tNear > 0.01 ? tNear : 0.01,
                        tFar < MAX_DIST ? tFar : MAX_DIST);
                    const i = row + pxi * 4;

                    if (t < 0) {
                        // silhouette coverage from the closest approach:
                        // a ray that nearly grazed the hull is a partly
                        // covered pixel, which antialiases the outline
                        const cov = 1 - clamp01(this._miss / 0.0075);
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
                    this._normal(scene, hx, hy, hz, n);
                    const nx = n[0], ny = n[1], nz = n[2];

                    const M = MATERIALS[mat] || MATERIALS[0];
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
                            const wu = wa * rr * P.winDens;
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
                        sh = this._shadow(scene, hx + nx * 0.006,
                            hy + ny * 0.006, hz + nz * 0.006, kx, ky, kz);
                    }
                    const ao = this._ao(scene, hx, hy, hz, nx, ny, nz);
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

                    // a warm interior point light: the shipyard slip and
                    // the death star core both bounce onto their own walls
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
                    // class is lit cold from outside
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
        },

        _miss: 1e9
    };

    if (typeof window !== 'undefined') window.StationDetail = StationDetail;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = StationDetail;
    }
})();
