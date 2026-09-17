/**
 * Stars Nova Web - photoreal ship hull renderer
 *
 * The detail view for the thirty ship hull classes, rendered by the
 * same SDF sphere-tracing engine as the stations (sdf-engine.js): soft
 * shadows, ambient occlusion, Fresnel rim, Blinn-Phong under Schlick,
 * triplanar plating seams, filmic tonemap. Deterministic throughout.
 *
 * Unlike station-detail.js, every hull here is a DATA RECORD, not a
 * hand-written scene function: {bound, yaw, pitch, roll, fill, winRows,
 * winCols, point, cool, parts[]}. Each part is a declarative record
 * {p, m, op, k, axis, at, fold, cut, rep, clip, scale, squash, d}
 * compiled once into a flat numeric form that one generic evaluator
 * walks per scene sample. This is the foundation the 200-300 hull
 * generator needs: a new hull is a new record, never new marcher code.
 *
 * Part schema (all fields optional except p and d):
 *   p      primitive: sphere|box|rbox|cyl|rcyl|torus|arc|ell|capsule|ribs
 *   d      dimensions, per primitive (half extents / radii / [R,r,...])
 *   m      material index into MATERIALS (default 0, armour plate)
 *   op     combine: u|su|sub|ssub|i (default u); k = fairing radius
 *   axis   x|y|z axis for axial primitives (default z, the thrust axis)
 *   at     [x,y,z] translation of the part
 *   cut    mirror axes, e.g. 'x' places the part on both flanks
 *   fold   N (or [N,axis]) radial repetition about an axis (default z)
 *   rep    [axis, period, lim] limited linear repetition
 *   clip   [bx,by,bz] intersect with a box in the part frame
 *   scale  uniform scale; squash [fx,fy,fz] flattens (distance stays safe)
 *
 * Transform order per part: cut -> fold -> rep -> at -> squash -> scale.
 * Parts evaluate strictly in order, so a subtraction cuts everything
 * before it and a later union can restore what the cut removed.
 *
 * Ship frame: +z is the bow, -z the drives, +y dorsal, x the beam.
 * Design language per docs/ART_DIRECTION.md - The Expanse crossed with
 * W40k: functional greebled hulls, drive cones, gothic mass for the
 * capitals, container spines for the freighters, industrial gantries
 * for the miners. No smooth sci-fi blobs.
 */
(function () {
    'use strict';

    // The shared engine: window.SDFEngine when the page loaded
    // sdf-engine.js first, a require fallback when the file is eval'd
    // bare in node by the test harness (which runs from the repo root).
    const E = (typeof window !== 'undefined' && window.SDFEngine)
        || (function () {
            if (typeof require !== 'function') {
                throw new Error('SDFEngine not loaded');
            }
            const paths = ['./sdf-engine.js',
                './frontend/js/views/sdf-engine.js'];
            for (let i = 0; i < paths.length; i++) {
                try { return require(paths[i]); } catch (err) { }
            }
            throw new Error('SDFEngine not found');
        })();

    const S = E.sdf;
    const sdSphere = S.sphere, sdBox = S.box, sdRoundBox = S.roundBox;
    const sdCyl = S.cyl, sdRoundCyl = S.roundCyl, sdTorus = S.torus;
    const sdArc = S.arc, sdCapsule = S.capsule, sdEllipsoid = S.ellipsoid;
    const opU = S.union, opSU = S.smoothUnion, opSub = S.subtract;
    const opSSub = S.smoothSubtract, opI = S.intersect;
    const foldRadial = E.foldRadial, FOLD = E.FOLD, repLimit = E.repLimit;

    // ---------------------------------------------------------------
    // Materials: the shared station vocabulary plus what only ships
    // need - drive plasma, weapon-port glow, stealth composite and
    // industrial hazard paint.
    // ---------------------------------------------------------------

    const MATERIALS = E.MATERIALS.concat([
        // 12 drive exhaust plasma, blue-white, falls off at grazing
        { a: [0.06, 0.08, 0.16], s: 0.40, sh: 80, seam: 0, greeble: 0,
          e: [0.62, 0.84, 1.35], vol: 1 },
        // 13 weapon port / dispenser glow, warm
        { a: [0.10, 0.08, 0.07], s: 0.50, sh: 120, seam: 0, greeble: 0,
          e: [1.05, 0.50, 0.18] },
        // 14 stealth composite, near-black and glossy, faceted panels
        { a: [0.09, 0.10, 0.13], s: 1.00, sh: 320, seam: 6.5, greeble: 0.6,
          win: 0 },
        // 15 industrial hazard paint, dull ochre
        { a: [0.55, 0.42, 0.18], s: 0.35, sh: 50, seam: 7.0, greeble: 0.8,
          win: 0 }
    ]);

    // ---------------------------------------------------------------
    // Part compiler and the generic evaluator. compileParts turns the
    // declarative records into flat numeric ones with a uniform shape,
    // so the hot loop stays monomorphic; compileScene closes over the
    // flat list and is what the engine marches.
    // ---------------------------------------------------------------

    const PRIM = { sphere: 0, box: 1, rbox: 2, cyl: 3, rcyl: 4, torus: 5,
                   arc: 6, ell: 7, capsule: 8, ribs: 9 };
    const OPS = { u: 0, su: 1, sub: 2, ssub: 3, i: 4 };
    const AXIS = { x: 0, y: 1, z: 2 };

    function compilePart(p) {
        if (!(p.p in PRIM)) throw new Error('unknown primitive ' + p.p);
        if (p.op && !(p.op in OPS)) throw new Error('unknown op ' + p.op);
        const cut = p.cut || '';
        const foldN = p.fold
            ? (Array.isArray(p.fold) ? p.fold[0] : p.fold) : 0;
        const foldAx = (p.fold && Array.isArray(p.fold))
            ? AXIS[p.fold[1]] : 2;
        const sq = p.squash || null;
        return {
            pc: PRIM[p.p],
            op: OPS[p.op || 'u'],
            m: p.m || 0,
            k: p.k || 0,
            ax: AXIS[p.axis || 'z'],
            atx: p.at ? p.at[0] : 0,
            aty: p.at ? p.at[1] : 0,
            atz: p.at ? p.at[2] : 0,
            mx: cut.indexOf('x') >= 0,
            my: cut.indexOf('y') >= 0,
            mz: cut.indexOf('z') >= 0,
            fold: foldN,
            fax: foldAx,
            rep: p.rep ? [AXIS[p.rep[0]], p.rep[1], p.rep[2]] : null,
            sq: sq,
            sqm: sq ? Math.max(sq[0], sq[1], sq[2]) : 1,
            sc: p.scale || 1,
            clip: p.clip || null,
            d: p.d
        };
    }

    function compileScene(parts) {
        const rs = parts.map(compilePart);
        const n = rs.length;
        return function (x, y, z) {
            let d = 1e9;
            for (let i = 0; i < n; i++) {
                const r = rs[i];
                let px = x, py = y, pz = z;
                if (r.mx) px = px < 0 ? -px : px;
                if (r.my) py = py < 0 ? -py : py;
                if (r.mz) pz = pz < 0 ? -pz : pz;
                if (r.fold) {
                    if (r.fax === 2) {
                        foldRadial(px, py, r.fold);
                        px = FOLD[0]; py = FOLD[1];
                    } else if (r.fax === 1) {
                        foldRadial(px, pz, r.fold);
                        px = FOLD[0]; pz = FOLD[1];
                    } else {
                        foldRadial(py, pz, r.fold);
                        py = FOLD[0]; pz = FOLD[1];
                    }
                }
                if (r.rep) {
                    const q = r.rep;
                    if (q[0] === 0) px = repLimit(px, q[1], q[2]);
                    else if (q[0] === 1) py = repLimit(py, q[1], q[2]);
                    else pz = repLimit(pz, q[1], q[2]);
                }
                px -= r.atx; py -= r.aty; pz -= r.atz;
                if (r.sq) {
                    px *= r.sq[0]; py *= r.sq[1]; pz *= r.sq[2];
                }
                if (r.sc !== 1) {
                    px /= r.sc; py /= r.sc; pz /= r.sc;
                }
                const D = r.d;
                let e;
                switch (r.pc) {
                    case 0: e = sdSphere(px, py, pz, D[0]); break;
                    case 1: e = sdBox(px, py, pz, D[0], D[1], D[2]); break;
                    case 2: e = sdRoundBox(px, py, pz,
                        D[0], D[1], D[2], D[3]); break;
                    case 3:
                        e = r.ax === 0 ? sdCyl(px, py, pz, D[0], D[1])
                            : r.ax === 1 ? sdCyl(py, px, pz, D[0], D[1])
                            : sdCyl(pz, px, py, D[0], D[1]);
                        break;
                    case 4:
                        e = r.ax === 0
                            ? sdRoundCyl(px, py, pz, D[0], D[1], D[2])
                            : r.ax === 1
                            ? sdRoundCyl(py, px, pz, D[0], D[1], D[2])
                            : sdRoundCyl(pz, px, py, D[0], D[1], D[2]);
                        break;
                    case 5:
                        e = r.ax === 0 ? sdTorus(px, py, pz, D[0], D[1])
                            : r.ax === 1 ? sdTorus(py, px, pz, D[0], D[1])
                            : sdTorus(pz, px, py, D[0], D[1]);
                        break;
                    case 6:
                        e = r.ax === 0 ? sdArc(px, py, pz, D[0], D[1], D[2])
                            : r.ax === 1 ? sdArc(py, px, pz, D[0], D[1], D[2])
                            : sdArc(pz, px, py, D[0], D[1], D[2]);
                        break;
                    case 7: e = sdEllipsoid(px, py, pz,
                        D[0], D[1], D[2]); break;
                    case 8: e = sdCapsule(px, py, pz, D[0], D[1], D[2],
                        D[3], D[4], D[5], D[6]); break;
                    default: {
                        // ribs: a torus ring repeated along the axis -
                        // armour bands, dispenser rings, tank hoops
                        let a2;
                        if (r.ax === 0) {
                            a2 = repLimit(px, D[2], D[3]);
                            e = sdTorus(a2, py, pz, D[0], D[1]);
                        } else if (r.ax === 1) {
                            a2 = repLimit(py, D[2], D[3]);
                            e = sdTorus(a2, px, pz, D[0], D[1]);
                        } else {
                            a2 = repLimit(pz, D[2], D[3]);
                            e = sdTorus(a2, px, py, D[0], D[1]);
                        }
                        break;
                    }
                }
                if (r.sc !== 1) e *= r.sc;
                if (r.sqm !== 1) e /= r.sqm;
                if (r.clip) {
                    e = Math.max(e, sdBox(px, py, pz,
                        r.clip[0], r.clip[1], r.clip[2]));
                }
                switch (r.op) {
                    case 0: d = opU(d, e, r.m); break;
                    case 1: d = opSU(d, e, r.k, r.m); break;
                    case 2: d = opSub(d, e, r.m); break;
                    case 3: d = opSSub(d, e, r.k, r.m); break;
                    default: d = opI(d, e, r.m); break;
                }
            }
            return d;
        };
    }

    // ---------------------------------------------------------------
    // Shared part-group vocabulary. These are data helpers, not scene
    // code: each returns plain part records for a fitting the whole
    // catalogue reuses, which is exactly what the future generator
    // will call with sampled parameters.
    // ---------------------------------------------------------------

    /** Drive cluster: engine bells aft plus the exhaust glow discs. */
    function drives(n, r, zAft, ringR) {
        const bell = { p: 'rcyl', axis: 'z', d: [0.10, r, 0.02], m: 1 };
        const glow = { p: 'cyl', axis: 'z', d: [0.02, r * 0.70], m: 12 };
        if (n === 1) {
            return [
                Object.assign({}, bell, { at: [0, 0, zAft] }),
                Object.assign({}, glow, { at: [0, 0, zAft - 0.085] })
            ];
        }
        if (n === 2) {
            return [
                Object.assign({}, bell, { at: [ringR, 0, zAft], cut: 'x' }),
                Object.assign({}, glow,
                    { at: [ringR, 0, zAft - 0.085], cut: 'x' })
            ];
        }
        return [
            Object.assign({}, bell, { at: [ringR, 0, zAft], fold: n }),
            Object.assign({}, glow,
                { at: [ringR, 0, zAft - 0.085], fold: n })
        ];
    }

    /** A row of recessed weapon ports down both flanks, warm emitters. */
    function gunRow(x, y, zc, period, lim) {
        return [{ p: 'box', d: [0.020, 0.022, 0.030], at: [x, y, zc],
                  cut: 'x', rep: ['z', period, lim], m: 13 }];
    }

    /** Armour band frames standing proud of the hull, dark structure. */
    function bands(w, hgt, zc, period, lim) {
        return [{ p: 'rbox', d: [w, hgt, 0.030, 0.012], at: [0, 0, zc],
                  rep: ['z', period, lim], m: 1 }];
    }

    /** Dorsal command tower with a bridge slab on top. */
    function tower(y, zc, w, hgt, dep) {
        return [
            { p: 'rbox', d: [w, hgt, dep, 0.02], at: [0, y, zc],
              op: 'su', k: 0.04, m: 2 },
            { p: 'rbox', d: [w * 1.5, 0.026, dep * 0.7, 0.012],
              at: [0, y + hgt + 0.02, zc], m: 2 }
        ];
    }

    /** Port (red) and starboard (green) running beacons. */
    function beacons(x, y, zc) {
        return [
            { p: 'sphere', d: [0.028], at: [-x, y, zc], m: 10 },
            { p: 'sphere', d: [0.028], at: [x, y, zc], m: 11 }
        ];
    }

    // ---------------------------------------------------------------
    // The catalogue. One record per hull class in components.xml.
    // Camera off-axis in yaw AND pitch for every design, yaw varied
    // across the sheet so thirty hulls do not read as clones.
    // ---------------------------------------------------------------

    const DESIGNS = {};

    function def(name, spec) {
        spec.scene = compileScene(spec.parts);
        DESIGNS[name] = spec;
    }

    // ---- warships: gothic mass scales up the ladder ---------------

    def('Scout', {
        bound: 1.22, yaw: 0.58, pitch: 0.30, roll: 0.06, fill: 0.90,
        winRows: 0, winCols: 0,
        parts: [
            // lean spindle hull with a dorsal sensor hump
            { p: 'ell', d: [0.09, 0.115, 0.85] },
            { p: 'ell', d: [0.055, 0.14, 0.30], at: [0, 0.03, -0.10],
              op: 'su', k: 0.06, m: 2 },
            // bow sensor boom
            { p: 'capsule', d: [0, 0.02, 0.82, 0, 0.02, 1.12, 0.022],
              m: 1 },
            { p: 'sphere', d: [0.045], at: [0, 0.02, 1.12], m: 1 },
            // radiator canards
            { p: 'rbox', d: [0.17, 0.012, 0.07, 0.008],
              at: [0.14, 0, 0.42], cut: 'x', op: 'su', k: 0.03, m: 6 },
            // dorsal fin aft
            { p: 'rbox', d: [0.016, 0.13, 0.10, 0.008],
              at: [0, 0.08, -0.70], op: 'su', k: 0.03, m: 1 }
        ].concat(
            drives(1, 0.075, -0.90, 0),
            beacons(0.30, 0, 0.42)
        )
    });

    def('Frigate', {
        bound: 1.08, yaw: -0.48, pitch: 0.26, roll: 0.05, fill: 0.90,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'rbox', d: [0.13, 0.16, 0.68, 0.045], at: [0, 0, -0.10] },
            { p: 'rbox', d: [0.095, 0.20, 0.34, 0.04], at: [0, 0.01, -0.15],
              op: 'su', k: 0.07, m: 2 },
            // stepped prow, first mass then blade
            { p: 'rbox', d: [0.08, 0.14, 0.16, 0.035], at: [0, 0.01, 0.66],
              op: 'su', k: 0.05 },
            { p: 'rbox', d: [0.042, 0.19, 0.09, 0.022], at: [0, 0.04, 0.82],
              op: 'su', k: 0.04 },
            // keel skid
            { p: 'rbox', d: [0.024, 0.07, 0.26, 0.012],
              at: [0, -0.20, -0.20], op: 'su', k: 0.04, m: 1 }
        ].concat(
            bands(0.145, 0.175, -0.14, 0.30, 1),
            tower(0.22, -0.42, 0.05, 0.07, 0.08),
            gunRow(0.13, 0.04, 0.12, 0.22, 1),
            drives(2, 0.075, -0.86, 0.10),
            beacons(0.15, 0.02, -0.45)
        )
    });

    def('Destroyer', {
        bound: 1.22, yaw: 0.52, pitch: 0.24, roll: 0.07, fill: 0.91,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'rbox', d: [0.15, 0.19, 0.80, 0.05], at: [0, 0, -0.08] },
            { p: 'rbox', d: [0.11, 0.235, 0.42, 0.05], at: [0, 0.01, -0.18],
              op: 'su', k: 0.08, m: 2 },
            { p: 'rbox', d: [0.10, 0.16, 0.18, 0.04], at: [0, 0.01, 0.80],
              op: 'su', k: 0.06 },
            { p: 'rbox', d: [0.052, 0.22, 0.10, 0.028], at: [0, 0.04, 0.96],
              op: 'su', k: 0.05 },
            // keel fin: the destroyer's one-glance cue
            { p: 'rbox', d: [0.028, 0.12, 0.32, 0.014],
              at: [0, -0.26, -0.30], op: 'su', k: 0.05, m: 1 }
        ].concat(
            bands(0.165, 0.205, -0.12, 0.30, 1),
            tower(0.27, -0.45, 0.055, 0.09, 0.10),
            gunRow(0.15, 0.05, 0.15, 0.22, 1),
            drives(2, 0.085, -0.97, 0.115),
            beacons(0.17, 0.03, -0.50)
        )
    });

    def('Cruiser', {
        bound: 1.34, yaw: -0.60, pitch: 0.30, roll: 0.04, fill: 0.92,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'rbox', d: [0.19, 0.22, 0.88, 0.06], at: [0, 0, -0.10] },
            { p: 'rbox', d: [0.14, 0.28, 0.48, 0.06], at: [0, 0.01, -0.20],
              op: 'su', k: 0.09, m: 2 },
            { p: 'rbox', d: [0.13, 0.18, 0.20, 0.05], at: [0, 0.01, 0.86],
              op: 'su', k: 0.07 },
            { p: 'rbox', d: [0.06, 0.26, 0.12, 0.03], at: [0, 0.05, 1.04],
              op: 'su', k: 0.05 },
            // flank gun sponsons
            { p: 'rbox', d: [0.06, 0.10, 0.42, 0.03], at: [0.22, -0.02, 0.05],
              cut: 'x', op: 'su', k: 0.05 },
            // keel fin
            { p: 'rbox', d: [0.03, 0.12, 0.36, 0.015],
              at: [0, -0.30, -0.25], op: 'su', k: 0.05, m: 1 }
        ].concat(
            bands(0.205, 0.24, -0.15, 0.28, 2),
            tower(0.31, -0.50, 0.065, 0.10, 0.12),
            gunRow(0.28, -0.02, 0.05, 0.24, 1),
            gunRow(0.19, 0.10, 0.20, 0.24, 1),
            drives(3, 0.09, -1.08, 0.13),
            beacons(0.21, 0.04, -0.55)
        )
    });

    def('Battle Cruiser', {
        bound: 1.52, yaw: 0.66, pitch: 0.22, roll: 0.06, fill: 0.93,
        winRows: 0, winCols: 0,
        parts: [
            // long lean hull: a battleship's guns on a runner's frame
            { p: 'rbox', d: [0.17, 0.20, 1.00, 0.055], at: [0, 0, -0.12] },
            { p: 'rbox', d: [0.125, 0.26, 0.52, 0.055], at: [0, 0.01, -0.25],
              op: 'su', k: 0.08, m: 2 },
            // oversized engine block: the class is its drives
            { p: 'rbox', d: [0.24, 0.24, 0.20, 0.05], at: [0, 0, -1.05],
              op: 'su', k: 0.08, m: 1 },
            // raked prow blade
            { p: 'rbox', d: [0.11, 0.17, 0.22, 0.045], at: [0, 0.01, 0.98],
              op: 'su', k: 0.06 },
            { p: 'rbox', d: [0.048, 0.27, 0.16, 0.028], at: [0, 0.05, 1.18],
              op: 'su', k: 0.05 },
            { p: 'rbox', d: [0.03, 0.14, 0.40, 0.015],
              at: [0, -0.28, -0.40], op: 'su', k: 0.05, m: 1 }
        ].concat(
            bands(0.185, 0.22, -0.20, 0.30, 2),
            tower(0.29, -0.58, 0.06, 0.10, 0.11),
            gunRow(0.17, 0.06, 0.10, 0.26, 2),
            drives(4, 0.095, -1.28, 0.14),
            beacons(0.19, 0.03, -0.70)
        )
    });

    def('Battleship', {
        bound: 1.48, yaw: -0.55, pitch: 0.32, roll: 0.05, fill: 0.93,
        winRows: 12, winCols: 7,
        parts: [
            // massive central hull with a stepped armour belt
            { p: 'rbox', d: [0.24, 0.26, 0.92, 0.07], at: [0, 0, -0.08] },
            { p: 'rbox', d: [0.30, 0.16, 0.60, 0.05], at: [0, -0.04, -0.10],
              op: 'su', k: 0.07 },
            { p: 'rbox', d: [0.17, 0.34, 0.50, 0.07], at: [0, 0.02, -0.20],
              op: 'su', k: 0.10, m: 2 },
            // cathedral prow in three risers
            { p: 'rbox', d: [0.16, 0.20, 0.16, 0.05], at: [0, 0.01, 0.90],
              op: 'su', k: 0.07 },
            { p: 'rbox', d: [0.10, 0.28, 0.12, 0.04], at: [0, 0.04, 1.04],
              op: 'su', k: 0.06 },
            { p: 'rbox', d: [0.045, 0.37, 0.09, 0.025], at: [0, 0.08, 1.14],
              op: 'su', k: 0.05 },
            // buttress arcs over the dorsal shoulders
            { p: 'arc', axis: 'x', d: [0.34, 0.032, 1.05],
              at: [0.16, 0.06, -0.10], cut: 'x', rep: ['z', 0.38, 1],
              m: 1 },
            { p: 'rbox', d: [0.032, 0.13, 0.44, 0.016],
              at: [0, -0.34, -0.20], op: 'su', k: 0.05, m: 1 }
        ].concat(
            bands(0.255, 0.275, -0.10, 0.30, 2),
            tower(0.36, -0.50, 0.075, 0.12, 0.13),
            tower(0.30, 0.28, 0.055, 0.08, 0.09),
            gunRow(0.24, 0.02, 0.10, 0.20, 2),
            gunRow(0.30, -0.06, 0.00, 0.24, 1),
            drives(4, 0.10, -1.14, 0.15),
            beacons(0.26, 0.05, -0.60)
        )
    });

    def('Dreadnought', {
        bound: 1.66, yaw: 0.47, pitch: 0.28, roll: 0.06, fill: 0.94,
        winRows: 13, winCols: 7,
        point: [0, 0, -1.55, 0.55, 0.72, 1.30, 2.0],
        parts: [
            // cathedral mass: a main hull over an underslung second hull
            { p: 'rbox', d: [0.22, 0.24, 1.05, 0.06], at: [0, 0, -0.15] },
            { p: 'rbox', d: [0.16, 0.14, 0.82, 0.05], at: [0, -0.20, -0.22],
              op: 'su', k: 0.09 },
            { p: 'rbox', d: [0.16, 0.34, 0.55, 0.06], at: [0, 0.06, -0.35],
              op: 'su', k: 0.10, m: 2 },
            // the prow: three risers up to a gothic blade
            { p: 'rbox', d: [0.18, 0.22, 0.16, 0.05], at: [0, 0.01, 0.94],
              op: 'su', k: 0.07 },
            { p: 'rbox', d: [0.12, 0.30, 0.12, 0.04], at: [0, 0.05, 1.08],
              op: 'su', k: 0.06 },
            { p: 'rbox', d: [0.045, 0.42, 0.10, 0.025], at: [0, 0.10, 1.18],
              op: 'su', k: 0.05 },
            // thin prow vanes either side of the blade
            { p: 'rbox', d: [0.012, 0.30, 0.13, 0.008],
              at: [0.065, 0.06, 1.06], cut: 'x', m: 1 },
            // spine spires marching down the dorsal ridge
            { p: 'rbox', d: [0.028, 0.13, 0.030, 0.012], at: [0, 0.32, -0.20],
              rep: ['z', 0.30, 2], m: 1 },
            // buttress arcs, two stations of them
            { p: 'arc', axis: 'x', d: [0.32, 0.034, 1.10],
              at: [0.15, 0.08, -0.25], cut: 'x', rep: ['z', 0.44, 1],
              m: 1 },
            { p: 'rbox', d: [0.034, 0.15, 0.50, 0.016],
              at: [0, -0.40, -0.30], op: 'su', k: 0.05, m: 1 }
        ].concat(
            bands(0.235, 0.255, -0.18, 0.28, 2),
            tower(0.38, -0.62, 0.08, 0.13, 0.14),
            gunRow(0.22, 0.04, 0.05, 0.20, 2),
            gunRow(0.22, -0.08, 0.05, 0.20, 2),
            gunRow(0.16, 0.16, -0.10, 0.26, 1),
            drives(5, 0.095, -1.42, 0.16),
            beacons(0.24, 0.06, -0.75)
        )
    });

    // ---- modular hulls: visible socket frames ---------------------

    def('Nubian', {
        bound: 1.42, yaw: -0.70, pitch: 0.26, roll: 0.05, fill: 0.92,
        winRows: 0, winCols: 0,
        parts: [
            // open socket frames along the keel line
            { p: 'rbox', d: [0.30, 0.30, 0.045, 0.02], at: [0, 0, 0],
              rep: ['z', 0.42, 2], m: 1 },
            { p: 'box', d: [0.235, 0.235, 0.30], at: [0, 0, 0],
              rep: ['z', 0.42, 2], op: 'sub', m: 5 },
            // frame corner longerons tying the sockets together
            { p: 'rbox', d: [0.035, 0.035, 1.00, 0.015],
              at: [0.26, 0.26, 0], cut: 'xy', m: 1 },
            // the keel, restored after the socket cut
            { p: 'rbox', d: [0.07, 0.07, 1.02, 0.02], at: [0, 0, 0], m: 1 },
            // two sockets filled: a pressurised module and a tank
            { p: 'rbox', d: [0.19, 0.19, 0.15, 0.05], at: [0, 0, -0.42],
              m: 2 },
            { p: 'sphere', d: [0.175], at: [0, 0, 0.42], m: 0 },
            // bow sensor mast
            { p: 'capsule', d: [0, 0, 1.02, 0, 0, 1.24, 0.025], m: 1 },
            { p: 'sphere', d: [0.05], at: [0, 0, 1.24], m: 2 }
        ].concat(
            drives(2, 0.08, -1.16, 0.11),
            beacons(0.32, 0.32, 0.84)
        )
    });

    def('Meta Morph', {
        bound: 1.18, yaw: -0.58, pitch: 0.36, roll: 0.07, fill: 0.91,
        winRows: 0, winCols: 0,
        parts: [
            // a morphing chain: segments faired so heavily they read as
            // one body mid-change, collars marking the socket joints
            { p: 'ell', d: [0.20, 0.24, 0.32], at: [0, 0, -0.55],
              op: 'su', k: 0.12, m: 2 },
            { p: 'ell', d: [0.16, 0.19, 0.27], at: [0, 0.01, 0.02],
              op: 'su', k: 0.12, m: 2 },
            { p: 'ell', d: [0.13, 0.15, 0.22], at: [0, 0.02, 0.52],
              op: 'su', k: 0.12, m: 2 },
            { p: 'ell', d: [0.085, 0.105, 0.18], at: [0, 0.03, 0.90],
              op: 'su', k: 0.10, m: 2 },
            { p: 'torus', axis: 'z', d: [0.185, 0.032], at: [0, 0, -0.26],
              m: 1 },
            { p: 'torus', axis: 'z', d: [0.145, 0.028], at: [0, 0.015, 0.28],
              m: 1 },
            { p: 'torus', axis: 'z', d: [0.105, 0.024], at: [0, 0.025, 0.72],
              m: 1 },
            // dorsal socket studs waiting for modules
            { p: 'sphere', d: [0.045], at: [0, 0.245, -0.30],
              rep: ['z', 0.40, 1], m: 1 }
        ].concat(
            drives(3, 0.075, -0.98, 0.11),
            beacons(0.22, 0, -0.55)
        )
    });

    // ---- armed merchants ------------------------------------------

    def('Privateer', {
        bound: 1.10, yaw: 0.62, pitch: 0.34, roll: 0.05, fill: 0.91,
        winRows: 8, winCols: 5,
        parts: [
            // cargo drum with hoop frames - a merchant at heart
            { p: 'rcyl', axis: 'z', d: [0.60, 0.26, 0.05],
              at: [0, 0, -0.05] },
            { p: 'ribs', axis: 'z', d: [0.265, 0.020, 0.36, 1],
              at: [0, 0, -0.05], m: 1 },
            // bow cap and boom
            { p: 'rcyl', axis: 'z', d: [0.07, 0.19, 0.04], at: [0, 0, 0.62],
              op: 'su', k: 0.05 },
            { p: 'capsule', d: [0, 0, 0.66, 0, 0, 0.88, 0.03], m: 1 },
            // the gun deck bolted on top is what arms the merchant
            { p: 'rbox', d: [0.07, 0.06, 0.24, 0.025], at: [0, 0.30, 0.10],
              op: 'su', k: 0.05 },
            { p: 'rbox', d: [0.05, 0.09, 0.08, 0.02], at: [0, 0.34, -0.28],
              op: 'su', k: 0.04, m: 2 },
            { p: 'box', d: [0.018, 0.02, 0.05], at: [0.06, 0.31, 0.30],
              cut: 'x', m: 13 },
            // keel skid
            { p: 'rbox', d: [0.05, 0.04, 0.34, 0.02], at: [0, -0.28, 0],
              op: 'su', k: 0.05, m: 1 }
        ].concat(
            drives(2, 0.085, -0.80, 0.12),
            beacons(0.28, 0, -0.30)
        )
    });

    def('Rogue', {
        bound: 1.06, yaw: -0.44, pitch: 0.20, roll: 0.08, fill: 0.91,
        winRows: 0, winCols: 0,
        parts: [
            // low flat blade of a hull, stealth composite
            { p: 'rbox', d: [0.20, 0.09, 0.72, 0.045],
              at: [0, 0, -0.05], m: 14 },
            { p: 'rbox', d: [0.30, 0.042, 0.40, 0.025], at: [0, -0.02, 0.05],
              op: 'su', k: 0.06, m: 14 },
            // wedge nose
            { p: 'rbox', d: [0.10, 0.055, 0.20, 0.03], at: [0, -0.01, 0.72],
              op: 'su', k: 0.06, m: 14 },
            // cockpit spine hump, the only pressurised read
            { p: 'ell', d: [0.06, 0.06, 0.16], at: [0, 0.09, 0.30],
              op: 'su', k: 0.05, m: 2 },
            // concealed ventral bay, cut and left dark
            { p: 'rbox', d: [0.11, 0.05, 0.20, 0.02], at: [0, -0.11, -0.15],
              op: 'ssub', k: 0.03, m: 5 },
            // twin tail fins
            { p: 'rbox', d: [0.014, 0.10, 0.11, 0.008],
              at: [0.15, 0.07, -0.60], cut: 'x', m: 14 }
        ].concat(
            drives(2, 0.065, -0.84, 0.11)
        )
    });

    def('Galleon', {
        bound: 1.38, yaw: 0.55, pitch: 0.30, roll: 0.04, fill: 0.92,
        winRows: 9, winCols: 6,
        parts: [
            // twin cargo drums on a central keel
            { p: 'rcyl', axis: 'z', d: [0.70, 0.21, 0.05],
              at: [0.25, 0, -0.05], cut: 'x' },
            { p: 'ribs', axis: 'z', d: [0.215, 0.018, 0.35, 1],
              at: [0.25, 0, -0.05], cut: 'x', m: 1 },
            { p: 'rbox', d: [0.07, 0.09, 0.85, 0.025], at: [0, 0, 0],
              m: 1 },
            // cross ties clamping the drums to the keel
            { p: 'rbox', d: [0.44, 0.028, 0.06, 0.012], at: [0, 0.12, 0],
              rep: ['z', 0.42, 1], m: 1 },
            // stern castle: the tall windowed tower is the galleon read
            { p: 'rbox', d: [0.13, 0.26, 0.15, 0.04], at: [0, 0.18, -0.72],
              op: 'su', k: 0.06, m: 2 },
            { p: 'rbox', d: [0.18, 0.03, 0.11, 0.012], at: [0, 0.46, -0.72],
              m: 2 },
            // prow blade
            { p: 'rbox', d: [0.03, 0.17, 0.13, 0.015], at: [0, 0.05, 0.88],
              op: 'su', k: 0.05 }
        ].concat(
            drives(2, 0.095, -0.92, 0.25),
            drives(1, 0.08, -0.98, 0),
            beacons(0.47, 0, -0.05)
        )
    });

    // ---- freighters: container spines -----------------------------

    def('Small Freighter', {
        bound: 0.95, yaw: 0.64, pitch: 0.30, roll: 0.05, fill: 0.90,
        winRows: 6, winCols: 5,
        parts: [
            { p: 'rbox', d: [0.05, 0.05, 0.55, 0.02], at: [0, 0, 0], m: 1 },
            // one container amidships
            { p: 'rbox', d: [0.16, 0.15, 0.24, 0.03], at: [0, 0.01, 0.02] },
            { p: 'rbox', d: [0.175, 0.165, 0.028, 0.012], at: [0, 0.01, 0.02],
              rep: ['z', 0.22, 1], m: 1 },
            // engine block aft, crew cab forward
            { p: 'rbox', d: [0.12, 0.12, 0.12, 0.03], at: [0, 0, -0.58],
              m: 1 },
            { p: 'rbox', d: [0.07, 0.10, 0.09, 0.025], at: [0, 0.09, 0.52],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(1, 0.075, -0.76, 0),
            beacons(0.18, 0.01, 0.02)
        )
    });

    def('Medium Freighter', {
        bound: 1.10, yaw: -0.50, pitch: 0.28, roll: 0.04, fill: 0.91,
        winRows: 7, winCols: 5,
        parts: [
            { p: 'rbox', d: [0.055, 0.055, 0.72, 0.02], at: [0, 0, 0],
              m: 1 },
            // two containers on the spine
            { p: 'rbox', d: [0.17, 0.16, 0.20, 0.03], at: [0, 0.01, 0.24],
              cut: 'z', m: 0 },
            { p: 'rbox', d: [0.185, 0.175, 0.026, 0.012], at: [0, 0.01, 0],
              rep: ['z', 0.23, 2], m: 1 },
            { p: 'rbox', d: [0.14, 0.14, 0.13, 0.03], at: [0, 0, -0.76],
              m: 1 },
            { p: 'rbox', d: [0.075, 0.12, 0.10, 0.025], at: [0, 0.10, 0.70],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(2, 0.075, -0.94, 0.10),
            beacons(0.19, 0.01, -0.23)
        )
    });

    def('Large Freighter', {
        bound: 1.28, yaw: 0.44, pitch: 0.32, roll: 0.05, fill: 0.92,
        winRows: 8, winCols: 5,
        parts: [
            { p: 'rbox', d: [0.06, 0.06, 0.90, 0.02], at: [0, 0, 0], m: 1 },
            // three containers, paired wide
            { p: 'rbox', d: [0.11, 0.17, 0.22, 0.03], at: [0.12, 0.01, 0],
              cut: 'x', rep: ['z', 0.50, 1] },
            { p: 'rbox', d: [0.25, 0.19, 0.024, 0.012], at: [0, 0.01, 0],
              rep: ['z', 0.25, 3], m: 1 },
            { p: 'rbox', d: [0.16, 0.15, 0.15, 0.035], at: [0, 0, -0.95],
              m: 1 },
            { p: 'rbox', d: [0.08, 0.13, 0.11, 0.025], at: [0, 0.11, 0.88],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(2, 0.085, -1.14, 0.11),
            beacons(0.25, 0.01, -0.25)
        )
    });

    def('Super Freighter', {
        bound: 1.45, yaw: -0.66, pitch: 0.24, roll: 0.04, fill: 0.93,
        winRows: 9, winCols: 6,
        parts: [
            { p: 'rbox', d: [0.065, 0.065, 1.02, 0.02], at: [0, 0, 0],
              m: 1 },
            // double-wide, double-length container stacks
            { p: 'rbox', d: [0.12, 0.18, 0.13, 0.03], at: [0.13, 0.01, 0.02],
              cut: 'x', rep: ['z', 0.30, 2] },
            { p: 'rbox', d: [0.27, 0.20, 0.024, 0.012], at: [0, 0.01, 0.02],
              rep: ['z', 0.30, 2], m: 1 },
            // heavy engine block with an intercooler collar
            { p: 'rbox', d: [0.18, 0.17, 0.17, 0.04], at: [0, 0, -1.06],
              m: 1 },
            { p: 'ribs', axis: 'z', d: [0.20, 0.018, 0.10, 1],
              at: [0, 0, -1.06], m: 6 },
            { p: 'rbox', d: [0.09, 0.15, 0.12, 0.03], at: [0, 0.12, 1.00],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(3, 0.09, -1.28, 0.13),
            beacons(0.27, 0.01, 0.02)
        )
    });

    // ---- colony ships: freighter keel plus habitat ----------------

    def('Colony Ship', {
        bound: 1.18, yaw: 0.50, pitch: 0.36, roll: 0.05, fill: 0.91,
        winRows: 7, winCols: 5,
        parts: [
            { p: 'rbox', d: [0.06, 0.06, 0.88, 0.02], at: [0, 0, 0], m: 1 },
            // the habitat ring amidships is the class
            { p: 'torus', axis: 'z', d: [0.50, 0.135], at: [0, 0, 0.12],
              squash: [1, 1, 1.4], m: 2 },
            { p: 'box', d: [0.24, 0.035, 0.05], at: [0.26, 0, 0.12],
              fold: 4, m: 1 },
            // stores aft, command sphere forward
            { p: 'rbox', d: [0.15, 0.14, 0.20, 0.03], at: [0, 0.01, -0.48] },
            { p: 'sphere', d: [0.16], at: [0, 0.02, 0.74], op: 'su',
              k: 0.06, m: 2 }
        ].concat(
            drives(2, 0.08, -0.86, 0.11),
            beacons(0.66, 0, 0.12)
        )
    });

    def('Mini-Colony Ship', {
        bound: 0.86, yaw: -0.62, pitch: 0.30, roll: 0.06, fill: 0.89,
        winRows: 6, winCols: 5,
        parts: [
            // one drum, one dome: a village in a bottle
            { p: 'rcyl', axis: 'z', d: [0.30, 0.17, 0.04], at: [0, 0, 0] },
            { p: 'sphere', d: [0.19], at: [0, 0.16, 0.16], op: 'su',
              k: 0.08, m: 2 },
            { p: 'rbox', d: [0.10, 0.08, 0.10, 0.025], at: [0, 0, -0.38],
              m: 1 },
            // stub keel and clamp
            { p: 'rbox', d: [0.04, 0.035, 0.30, 0.015], at: [0, -0.18, 0],
              op: 'su', k: 0.04, m: 1 }
        ].concat(
            drives(1, 0.065, -0.52, 0),
            beacons(0.19, 0, 0)
        )
    });

    // ---- the boarding hull ----------------------------------------

    def('Assault Transport', {
        bound: 1.32, yaw: 0.70, pitch: 0.26, roll: 0.06, fill: 0.92,
        winRows: 0, winCols: 0,
        parts: [
            // armoured wedge in three narrowing steps
            { p: 'rbox', d: [0.20, 0.18, 0.34, 0.05], at: [0, 0, -0.55] },
            { p: 'rbox', d: [0.17, 0.155, 0.30, 0.045], at: [0, 0, 0.02],
              op: 'su', k: 0.06 },
            { p: 'rbox', d: [0.135, 0.125, 0.24, 0.04], at: [0, 0, 0.50],
              op: 'su', k: 0.06 },
            // breaching prow: collar, ram and cutting teeth
            { p: 'rcyl', axis: 'z', d: [0.14, 0.115, 0.03], at: [0, 0, 0.82],
              op: 'su', k: 0.05, m: 1 },
            { p: 'ell', d: [0.085, 0.085, 0.24], at: [0, 0, 1.00] },
            { p: 'box', d: [0.026, 0.02, 0.09], at: [0.10, 0, 0.94],
              fold: 4, m: 1 },
            // troop pods riding the flanks
            { p: 'rbox', d: [0.05, 0.09, 0.28, 0.03], at: [0.22, 0, -0.20],
              cut: 'x', op: 'su', k: 0.04, m: 2 },
            // dorsal point-defence blisters
            { p: 'sphere', d: [0.045], at: [0, 0.20, -0.15],
              rep: ['z', 0.36, 1], m: 1 }
        ].concat(
            bands(0.215, 0.195, -0.55, 0.24, 1),
            drives(2, 0.09, -1.00, 0.12),
            beacons(0.22, 0.04, -0.55)
        )
    });

    // ---- bombers: wings and ordnance racks ------------------------

    def('Mini Bomber', {
        bound: 0.92, yaw: -0.46, pitch: 0.34, roll: 0.07, fill: 0.90,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'ell', d: [0.08, 0.09, 0.55] },
            // one straight wing through the spine
            { p: 'rbox', d: [0.54, 0.018, 0.15, 0.01], at: [0, 0, -0.05] },
            { p: 'cyl', axis: 'z', d: [0.12, 0.035], at: [0.52, 0, -0.05],
              cut: 'x', m: 1 },
            // a pair of slung bombs
            { p: 'cyl', axis: 'z', d: [0.10, 0.030], at: [0.17, -0.07, 0],
              cut: 'x', m: 1 },
            { p: 'sphere', d: [0.032], at: [0.17, -0.07, 0.12], cut: 'x',
              m: 13 },
            { p: 'ell', d: [0.05, 0.05, 0.12], at: [0, 0.07, 0.28],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(1, 0.06, -0.62, 0)
        )
    });

    def('B-17 Bomber', {
        bound: 1.12, yaw: 0.56, pitch: 0.38, roll: 0.05, fill: 0.91,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'ell', d: [0.10, 0.12, 0.72] },
            { p: 'rbox', d: [0.84, 0.020, 0.19, 0.01], at: [0, 0.01, 0.05] },
            // four engine pods strung along the wing
            { p: 'cyl', axis: 'z', d: [0.14, 0.045], at: [0.32, -0.02, 0.05],
              cut: 'x', m: 1 },
            { p: 'cyl', axis: 'z', d: [0.13, 0.042], at: [0.60, -0.02, 0.05],
              cut: 'x', m: 1 },
            // the bomb row under the belly
            { p: 'cyl', axis: 'z', d: [0.12, 0.028], at: [0, -0.14, 0.02],
              rep: ['x', 0.085, 2], m: 1 },
            { p: 'sphere', d: [0.028], at: [0, -0.14, 0.16],
              rep: ['x', 0.085, 2], m: 13 },
            // tail group
            { p: 'rbox', d: [0.016, 0.14, 0.10, 0.008], at: [0, 0.10, -0.66],
              m: 1 },
            { p: 'rbox', d: [0.26, 0.014, 0.08, 0.008], at: [0, 0.05, -0.66],
              m: 1 },
            { p: 'ell', d: [0.06, 0.07, 0.14], at: [0, 0.08, 0.42],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(2, 0.06, -0.80, 0.09),
            beacons(0.86, 0.01, 0.05)
        )
    });

    def('Stealth Bomber', {
        bound: 0.95, yaw: -0.72, pitch: 0.32, roll: 0.06, fill: 0.90,
        winRows: 0, winCols: 0,
        parts: [
            // flying wedge, all facets, no mast, no beacon
            { p: 'rbox', d: [0.68, 0.038, 0.26, 0.02], at: [0, 0, -0.08],
              m: 14 },
            { p: 'rbox', d: [0.15, 0.072, 0.40, 0.03], at: [0, 0.01, 0.02],
              op: 'su', k: 0.06, m: 14 },
            { p: 'rbox', d: [0.42, 0.030, 0.16, 0.015], at: [0, -0.005, 0.26],
              op: 'su', k: 0.05, m: 14 },
            // dorsal intake slit, cut dark
            { p: 'box', d: [0.10, 0.02, 0.05], at: [0, 0.075, 0.10],
              op: 'ssub', k: 0.02, m: 5 },
            // cockpit slit glazing
            { p: 'box', d: [0.05, 0.012, 0.03], at: [0, 0.062, 0.32],
              m: 3 },
            // buried exhaust slots, dim
            { p: 'box', d: [0.09, 0.012, 0.02], at: [0.20, 0.015, -0.33],
              cut: 'x', m: 12 }
        ]
    });

    def('B-52 Bomber', {
        bound: 1.32, yaw: 0.48, pitch: 0.40, roll: 0.04, fill: 0.92,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'ell', d: [0.11, 0.13, 0.92] },
            // the span is the class: a wing wider than the hull is long
            { p: 'rbox', d: [1.02, 0.020, 0.17, 0.01], at: [0, 0.02, 0.10] },
            { p: 'cyl', axis: 'z', d: [0.15, 0.050], at: [0.38, -0.04, 0.10],
              cut: 'x', m: 1 },
            { p: 'cyl', axis: 'z', d: [0.14, 0.046], at: [0.72, -0.04, 0.10],
              cut: 'x', m: 1 },
            // two full ordnance rows
            { p: 'cyl', axis: 'z', d: [0.13, 0.030], at: [0, -0.15, 0.28],
              rep: ['x', 0.09, 2], m: 1 },
            { p: 'cyl', axis: 'z', d: [0.13, 0.030], at: [0, -0.15, -0.14],
              rep: ['x', 0.09, 2], m: 1 },
            { p: 'sphere', d: [0.030], at: [0, -0.15, 0.43],
              rep: ['x', 0.09, 2], m: 13 },
            // tall tail
            { p: 'rbox', d: [0.018, 0.19, 0.12, 0.008], at: [0, 0.13, -0.84],
              m: 1 },
            { p: 'rbox', d: [0.30, 0.014, 0.09, 0.008], at: [0, 0.04, -0.84],
              m: 1 },
            { p: 'ell', d: [0.065, 0.075, 0.16], at: [0, 0.09, 0.55],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(2, 0.07, -1.02, 0.10),
            beacons(1.04, 0.02, 0.10)
        )
    });

    // ---- miners: industrial gantries, maws and silos --------------

    def('Midget Miner', {
        bound: 0.72, yaw: -0.54, pitch: 0.28, roll: 0.07, fill: 0.88,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'rcyl', axis: 'z', d: [0.28, 0.16, 0.03], at: [0, 0, 0] },
            // the intake maw cut into the working face
            { p: 'cyl', axis: 'z', d: [0.12, 0.105], at: [0, 0, 0.30],
              op: 'ssub', k: 0.03, m: 5 },
            { p: 'cyl', axis: 'z', d: [0.012, 0.085], at: [0, 0, 0.19],
              m: 4 },
            // one gantry arm over the top
            { p: 'rbox', d: [0.028, 0.028, 0.30, 0.012], at: [0, 0.22, 0.02],
              m: 1 },
            { p: 'capsule', d: [0, 0.22, 0.30, 0, 0.06, 0.42, 0.025],
              m: 1 },
            // hazard block
            { p: 'rbox', d: [0.06, 0.035, 0.08, 0.015], at: [0, 0.19, -0.18],
              m: 15 }
        ].concat(
            drives(1, 0.06, -0.42, 0)
        )
    });

    def('Mini Miner', {
        bound: 0.86, yaw: 0.68, pitch: 0.24, roll: 0.05, fill: 0.89,
        winRows: 0, winCols: 0,
        parts: [
            // twin drums under a spine
            { p: 'rcyl', axis: 'z', d: [0.34, 0.135, 0.03],
              at: [0.15, -0.02, 0], cut: 'x' },
            { p: 'rbox', d: [0.20, 0.05, 0.30, 0.02], at: [0, 0.13, 0],
              m: 1 },
            // shared maw ahead of both drums
            { p: 'rcyl', axis: 'z', d: [0.10, 0.17, 0.03], at: [0, 0, 0.42],
              op: 'su', k: 0.05, m: 1 },
            { p: 'cyl', axis: 'z', d: [0.10, 0.13], at: [0, 0, 0.50],
              op: 'ssub', k: 0.03, m: 5 },
            { p: 'cyl', axis: 'z', d: [0.012, 0.10], at: [0, 0, 0.42],
              m: 4 },
            // gantry mast
            { p: 'rbox', d: [0.025, 0.11, 0.025, 0.012], at: [0, 0.24, -0.15],
              m: 1 },
            { p: 'rbox', d: [0.05, 0.03, 0.07, 0.012], at: [0, 0.20, -0.32],
              m: 15 }
        ].concat(
            drives(2, 0.06, -0.48, 0.15)
        )
    });

    def('Miner', {
        bound: 1.05, yaw: -0.42, pitch: 0.36, roll: 0.05, fill: 0.90,
        winRows: 0, winCols: 0,
        point: [0, 0, 0.60, 1.00, 0.55, 0.20, 2.2],
        parts: [
            // silo body with hoop frames
            { p: 'rcyl', axis: 'z', d: [0.46, 0.235, 0.04], at: [0, 0, -0.05] },
            { p: 'ribs', axis: 'z', d: [0.24, 0.020, 0.28, 1],
              at: [0, 0, -0.05], m: 1 },
            // the maw, with cutter teeth around the rim
            { p: 'cyl', axis: 'z', d: [0.16, 0.16], at: [0, 0, 0.44],
              op: 'ssub', k: 0.04, m: 5 },
            { p: 'cyl', axis: 'z', d: [0.014, 0.125], at: [0, 0, 0.30],
              m: 4 },
            { p: 'box', d: [0.032, 0.026, 0.06], at: [0.185, 0, 0.42],
              fold: 6, m: 15 },
            // dorsal crane
            { p: 'rbox', d: [0.03, 0.14, 0.03, 0.014], at: [0, 0.32, -0.20],
              m: 1 },
            { p: 'rbox', d: [0.028, 0.028, 0.24, 0.012], at: [0, 0.42, 0.0],
              m: 1 },
            // saddle tanks
            { p: 'rcyl', axis: 'z', d: [0.26, 0.08, 0.02],
              at: [0.28, -0.06, -0.15], cut: 'x', m: 0 }
        ].concat(
            drives(2, 0.08, -0.66, 0.11),
            beacons(0.26, 0.06, -0.40)
        )
    });

    def('Maxi Miner', {
        bound: 1.22, yaw: 0.60, pitch: 0.28, roll: 0.04, fill: 0.91,
        winRows: 0, winCols: 0,
        point: [0, 0, 0.70, 1.00, 0.55, 0.20, 2.4],
        parts: [
            // three silos around a core spine
            { p: 'rcyl', axis: 'z', d: [0.50, 0.145, 0.03],
              at: [0.235, 0, -0.10], fold: 3 },
            { p: 'cyl', axis: 'z', d: [0.55, 0.09], at: [0, 0, -0.05],
              m: 1 },
            // silo hoops
            { p: 'ribs', axis: 'z', d: [0.148, 0.016, 0.30, 1],
              at: [0.235, 0, -0.10], fold: 3, m: 15 },
            // big shared maw forward
            { p: 'rcyl', axis: 'z', d: [0.14, 0.28, 0.04], at: [0, 0, 0.52],
              op: 'su', k: 0.07, m: 1 },
            { p: 'cyl', axis: 'z', d: [0.16, 0.21], at: [0, 0, 0.64],
              op: 'ssub', k: 0.04, m: 5 },
            { p: 'cyl', axis: 'z', d: [0.016, 0.165], at: [0, 0, 0.50],
              m: 4 },
            { p: 'box', d: [0.04, 0.03, 0.07], at: [0.25, 0, 0.60],
              fold: 6, m: 15 },
            // gantry ring around the waist
            { p: 'torus', axis: 'z', d: [0.34, 0.028], at: [0, 0, 0.10],
              m: 1 }
        ].concat(
            drives(3, 0.085, -0.78, 0.14),
            beacons(0.30, 0.10, -0.45)
        )
    });

    def('Ultra Miner', {
        bound: 1.38, yaw: -0.56, pitch: 0.34, roll: 0.05, fill: 0.92,
        winRows: 0, winCols: 0,
        point: [0, 0, 0.80, 1.00, 0.52, 0.18, 2.8],
        parts: [
            // four silos, heavy gantry ring, a maw like a furnace door
            { p: 'rcyl', axis: 'z', d: [0.55, 0.16, 0.03],
              at: [0.285, 0, -0.12], fold: 4 },
            { p: 'cyl', axis: 'z', d: [0.62, 0.11], at: [0, 0, -0.08],
              m: 1 },
            { p: 'ribs', axis: 'z', d: [0.163, 0.016, 0.26, 2],
              at: [0.285, 0, -0.12], fold: 4, m: 15 },
            { p: 'rcyl', axis: 'z', d: [0.16, 0.34, 0.05], at: [0, 0, 0.62],
              op: 'su', k: 0.08, m: 1 },
            { p: 'cyl', axis: 'z', d: [0.18, 0.255], at: [0, 0, 0.76],
              op: 'ssub', k: 0.05, m: 5 },
            { p: 'cyl', axis: 'z', d: [0.018, 0.20], at: [0, 0, 0.58],
              m: 4 },
            { p: 'box', d: [0.045, 0.035, 0.08], at: [0.30, 0, 0.70],
              fold: 8, m: 15 },
            { p: 'torus', axis: 'z', d: [0.42, 0.040], at: [0, 0, 0.14],
              m: 1 },
            // crane tower
            { p: 'rbox', d: [0.035, 0.16, 0.035, 0.015], at: [0, 0.44, -0.30],
              m: 1 },
            { p: 'rbox', d: [0.03, 0.03, 0.30, 0.014], at: [0, 0.56, -0.10],
              m: 1 }
        ].concat(
            drives(4, 0.085, -0.92, 0.17),
            beacons(0.44, 0, 0.14)
        )
    });

    // ---- mine layers: tender hull plus dispenser drums ------------

    def('Mini Mine Layer', {
        bound: 0.95, yaw: 0.66, pitch: 0.32, roll: 0.06, fill: 0.90,
        winRows: 0, winCols: 0,
        parts: [
            { p: 'rbox', d: [0.115, 0.125, 0.42, 0.04], at: [0, 0.02, 0.20] },
            // twin dispenser drums slung aft
            { p: 'rcyl', axis: 'z', d: [0.36, 0.125, 0.03],
              at: [0.185, -0.03, -0.32], cut: 'x', m: 1 },
            { p: 'ribs', axis: 'z', d: [0.128, 0.014, 0.18, 1],
              at: [0.185, -0.03, -0.32], cut: 'x', m: 15 },
            // dispenser mouths, glowing warm
            { p: 'cyl', axis: 'z', d: [0.014, 0.085],
              at: [0.185, -0.03, -0.69], cut: 'x', m: 13 },
            // crew cab
            { p: 'rbox', d: [0.06, 0.09, 0.09, 0.025], at: [0, 0.14, 0.48],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(1, 0.07, -0.62, 0),
            beacons(0.13, 0.06, 0.20)
        )
    });

    def('Super Mine Layer', {
        bound: 1.22, yaw: -0.48, pitch: 0.26, roll: 0.05, fill: 0.92,
        winRows: 6, winCols: 5,
        parts: [
            { p: 'rbox', d: [0.15, 0.16, 0.55, 0.045], at: [0, 0, 0.28] },
            // four dispenser drums around the aft spine
            { p: 'rcyl', axis: 'z', d: [0.48, 0.135, 0.03],
              at: [0.24, 0, -0.42], fold: 4, m: 1 },
            { p: 'ribs', axis: 'z', d: [0.138, 0.015, 0.22, 1],
              at: [0.24, 0, -0.42], fold: 4, m: 15 },
            { p: 'cyl', axis: 'z', d: [0.016, 0.09],
              at: [0.24, 0, -0.91], fold: 4, m: 13 },
            // aft spine the drums hang from
            { p: 'cyl', axis: 'z', d: [0.50, 0.07], at: [0, 0, -0.40],
              m: 1 },
            { p: 'rbox', d: [0.075, 0.12, 0.11, 0.03], at: [0, 0.20, 0.55],
              op: 'su', k: 0.04, m: 2 }
        ].concat(
            drives(2, 0.08, -0.98, 0.11),
            beacons(0.17, 0.04, 0.28)
        )
    });

    // ---------------------------------------------------------------
    // Renderer: the shared cache/canvas plumbing wrapped around the
    // ship catalogue and its fallback rules.
    // ---------------------------------------------------------------

    /**
     * Resolve a hull name to a catalogue entry. Unrecognised names fall
     * back by family keyword so a modded hull still draws something of
     * roughly the right trade, then to Scout.
     */
    function classify(hull) {
        if (hull && DESIGNS[hull]) return hull;
        if (hull) {
            if (/freighter|transport|cargo/i.test(hull)) {
                return 'Medium Freighter';
            }
            if (/colon/i.test(hull)) return 'Colony Ship';
            if (/bomber/i.test(hull)) return 'B-17 Bomber';
            if (/miner|mining/i.test(hull)) return 'Miner';
            if (/mine/i.test(hull)) return 'Mini Mine Layer';
            if (/dread/i.test(hull)) return 'Dreadnought';
            if (/battle/i.test(hull)) return 'Battleship';
            if (/cruiser/i.test(hull)) return 'Cruiser';
            if (/destroyer/i.test(hull)) return 'Destroyer';
            if (/frigate|corvette/i.test(hull)) return 'Frigate';
        }
        return 'Scout';
    }

    const ShipDetail = Object.assign(
        E.makeRenderer({
            designs: DESIGNS,
            materials: MATERIALS,
            classify: classify,
            cacheMax: 40
        }),
        {
            DESIGNS: DESIGNS,
            MATERIALS: MATERIALS,
            /** Exposed for tests: the primitive and operator library. */
            sdf: E.sdf,
            TUNE: E.TUNE,
            compileScene: compileScene,
            compilePart: compilePart
        });

    if (typeof window !== 'undefined') window.ShipDetail = ShipDetail;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = ShipDetail;
    }
})();
