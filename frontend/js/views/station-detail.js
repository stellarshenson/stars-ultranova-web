/**
 * Stars Nova Web - photoreal orbital station renderer
 *
 * A LARGE detail view (256 px and up) for the starbase in orbit. This is
 * not the star panel sprite: planet-art.js still draws that at eight to
 * eleven pixels and nothing here touches it. The split is exactly what
 * makes the look possible, because photorealism needs pixels to live in.
 *
 * Technique: signed distance field sphere tracing, per pixel, into an
 * ImageData buffer. The marcher, the shading pipeline and the material
 * vocabulary live in sdf-engine.js and are shared with the ship
 * renderer (ship-detail.js); this file carries only what is station:
 * the six scene functions and the class table.
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
    const sdCapsule = S.capsule, sdEllipsoid = S.ellipsoid;
    const opU = S.union, opSU = S.smoothUnion, opSub = S.subtract;
    const opSSub = S.smoothSubtract;
    const foldRadial = E.foldRadial, FOLD = E.FOLD, repLimit = E.repLimit;
    const clamp01 = E.clamp01, setMat = E.setMat;

    // ---------------------------------------------------------------
    // Scenes. One function per class, each returning the distance to
    // the whole station and leaving its material in the engine's MAT.
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
        setMat(1);
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
        setMat(1);
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
        setMat(2);
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
        setMat(2);
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

        setMat(0);
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
        if (core < hull) { d = core; setMat(8); } else { d = hull; }

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
        setMat(1);
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
    // Renderer: the shared cache/canvas plumbing wrapped around this
    // file's class table and fallback rules.
    // ---------------------------------------------------------------

    /**
     * Resolve a hull name to a class. Anything unrecognised falls
     * back the same way the star panel sprite does, so the two
     * views never disagree about what is in orbit.
     */
    function classify(hull) {
        if (hull && CLASSES[hull]) return hull;
        if (hull && /yard|slip/i.test(hull)) return 'Shipyard';
        if (hull && /dock/i.test(hull)) return 'Space Dock';
        return 'Orbital Fort';
    }

    const StationDetail = Object.assign(
        E.makeRenderer({
            designs: CLASSES,
            materials: E.MATERIALS,
            classify: classify,
            cacheMax: 24
        }),
        {
            CLASSES: CLASSES,
            MATERIALS: E.MATERIALS,
            /** Exposed for tests: the primitive and operator library. */
            sdf: E.sdf,
            TUNE: E.TUNE
        });

    if (typeof window !== 'undefined') window.StationDetail = StationDetail;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = StationDetail;
    }
})();
