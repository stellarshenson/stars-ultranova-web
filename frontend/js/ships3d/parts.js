// Shared sub-assembly library for the ship model compiler. Every family
// builder composes hulls from these parts; each part is deterministic (all
// randomness flows through the passed rng) and adds geometry to a MeshBin.
//
// Axis convention: +Z bow, -Z stern, +Y dorsal. `frame.k` is the hull size
// factor (length / 10) used to scale structural cross-sections; greeble-scale
// detail stays absolute so large hulls read as LARGE (more, not bigger, bits).

import * as THREE from '../../vendor/three/build/three.module.js';
import { bevelPlate, loft, surfaceBasis, strut, tube, uvPatch, uvTransform } from './geometry.js';
import { greebleField } from './greebles.js';

// Warship cross-section: flat deck strip, armoured chamfers, vertical flank
// band, ventral chamfers, flat keel.
export const PROFILE = [
    [0.0, 1.0], [0.55, 0.94], [1.0, 0.42], [1.0, -0.32], [0.62, -0.84], [0.24, -1.0],
    [-0.24, -1.0], [-0.62, -0.84], [-1.0, -0.32], [-1.0, 0.42], [-0.55, 0.94],
];

// Chunky box section for freighters, assault wedges and utility hulls.
export const BOX_PROFILE = [
    [0.0, 1.0], [0.7, 0.96], [1.0, 0.6], [1.0, -0.6], [0.7, -0.96], [0.0, -1.0],
    [-0.7, -0.96], [-1.0, -0.6], [-1.0, 0.6], [-0.7, 0.96],
];

// Faceted low-signature chine section for the stealth slab.
export const CHINE_PROFILE = [
    [0.0, 1.0], [0.62, 0.5], [1.0, 0.0], [0.62, -0.55], [0.0, -0.85],
    [-0.62, -0.55], [-1.0, 0.0], [-0.62, 0.5],
];

export function lerpCurve(curve, z) {
    if (z >= curve[0][0]) return curve[0][1];
    for (let i = 0; i < curve.length - 1; i++) {
        const [z0, v0] = curve[i], [z1, v1] = curve[i + 1];
        if (z <= z0 && z >= z1) return v1 + (v0 - v1) * ((z - z1) / (z0 - z1));
    }
    return curve[curve.length - 1][1];
}

// Loft the hull skin from the record's width/height control curves and return
// the hull frame every other part works against.
//
// opts.flavour (0..1) is the human-to-alien knob: at 0 the section is the
// orthogonal armoured profile as recorded; rising flavour blends every
// profile point toward its organic (unit-circle) position and adds a gentle
// deterministic sheer warp along the length, so the same record reads as a
// grown hull rather than a built one while W/H placement queries stay
// consistent with the morphed skin.
export function hullFromCurves(bin, g, hull, opts = {}) {
    const fl = opts.flavour || 0;
    const baseProfile = opts.profile || PROFILE;
    const profile = baseProfile.map(([px, py]) => {
        const len = Math.hypot(px, py) || 1;
        const t = 0.55 * fl;
        return [px + (px / len - px) * t, py + (py / len - py) * t];
    });
    const k = hull.length / 10;
    const warpW = (z) => 1 + fl * 0.10 * Math.sin((z / k) * 1.1 + 0.7);
    const warpH = (z) => 1 + fl * 0.16 * Math.sin((z / k) * 1.6 + 1.9);
    const W = (z) => lerpCurve(hull.widthCurve, z) * warpW(z);
    const H = (z) => lerpCurve(hull.heightCurve, z) * warpH(z);
    const zBow = hull.widthCurve[0][0];
    const zStern = hull.widthCurve[hull.widthCurve.length - 1][0];
    const deckYAt = (z, x = 0) => H(z) * (1 - 0.06 * Math.min(1, Math.abs(x) / (0.55 * Math.max(W(z), 0.001))));
    const nSta = hull.stations;
    const stations = [];
    for (let i = 0; i < nSta; i++) {
        const z = zBow - 0.02 * k - ((zBow - 0.02 * k - zStern) * i) / (nSta - 1);
        stations.push({ z, pts: profile.map(([px, py]) => [px * W(z), py * H(z)]) });
    }
    const skin = loft(stations, { capStart: true, capEnd: true, uScale: 4, vScale: 0.4 / k });
    bin.add(opts.material || 'armor', skin, {});
    return { W, H, zBow, zStern, k, deckYAt, profile, nSta, stations, fl };
}

// Conformal bevelled armour plating: one plate per loft face, oriented to the
// face frame, so plate seams are geometric relief on top of the baked panels.
export function conformalPlating(bin, g, frame, opts = {}) {
    const { stations, nSta, k } = frame;
    const nPts = frame.profile.length;
    const missChance = opts.missChance ?? 0.12;
    const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3(), vD = new THREE.Vector3();
    const tU = new THREE.Vector3(), tV = new THREE.Vector3(), nrm = new THREE.Vector3(), ctr = new THREE.Vector3();
    for (let i = 0; i < nSta - 1; i++) {
        for (let j = 0; j < nPts; j++) {
            const s0 = stations[i], s1 = stations[i + 1];
            const p = (s, m) => [s.pts[m % nPts][0], s.pts[m % nPts][1], s.z];
            vA.fromArray(p(s0, j)); vB.fromArray(p(s0, j + 1)); vC.fromArray(p(s1, j + 1)); vD.fromArray(p(s1, j));
            const edge = vA.distanceTo(vB), span = vA.distanceTo(vD);
            if (edge < 0.11 * k || span < 0.1 * k) continue;
            if (g.chance(missChance)) continue; // missing plates read as battle wear
            ctr.copy(vA).add(vB).add(vC).add(vD).multiplyScalar(0.25);
            tU.copy(vB).sub(vA).normalize();
            nrm.copy(vB).sub(vA).cross(vC.clone().sub(vA)).normalize();
            tV.copy(tU).cross(nrm);
            const th = g.range(0.028, 0.055) * k;
            const plate = bevelPlate(edge * g.range(0.8, 0.9), th, span * g.range(0.8, 0.9), 0.02 * k);
            uvPatch(plate, g, 0.28);
            const m = new THREE.Matrix4().makeBasis(tU.clone(), nrm.clone(), tV.clone());
            m.setPosition(ctr.x + nrm.x * 0.004, ctr.y + nrm.y * 0.004, ctr.z + nrm.z * 0.004);
            bin.add('armor', plate, { basis: m });
            if (g.chance(opts.secondaryChance ?? 0.16)) {
                const p2 = bevelPlate(edge * g.range(0.3, 0.5), 0.03 * k, span * g.range(0.3, 0.5), 0.015 * k);
                uvPatch(p2, g, 0.2);
                const m2 = m.clone();
                m2.setPosition(ctr.x + nrm.x * th, ctr.y + nrm.y * th, ctr.z + nrm.z * th);
                bin.add(g.chance(0.15) ? 'trim' : 'armor', p2, { basis: m2, subPart: true });
            }
        }
    }
}

// Trireme ram prow: a deep V-wedge in both plan and profile whose leading
// edge is a reinforced vertical ram beam layered like a plough, extending
// well forward of the hull mass. Gothic under-beak on capitals. Optional
// beam-cannon apertures cut into the prow faces (FreeSpace capital language).
export function ramProw(bin, g, frame, opts = {}) {
    const { zBow, k } = frame;
    const fl = frame.fl || 0;
    // The prow IS the front fraction of the ship: an integral armoured wedge
    // anchored deep in the hull where the section carries real beam, flaring
    // from a tall ram blade at the tip to the full bow section at the root.
    // Only about a third of its run projects past the hull skin - closed
    // plated mass, never a boom.
    const total = (opts.lenFrac ?? 0.19) * frame.k * 10 * (1 + 0.12 * fl);
    const fwd = total * (opts.blunt ? 0.32 : 0.45);      // forward of the hull skin
    const zTip = zBow + fwd;
    const zA = zBow - (total - fwd);                     // root station, deep inside
    const w0 = frame.W(zA), h0 = frame.H(zA);
    // blunt rams (dreadnought: mass over reach) carry a wider tip blade
    const tipW = (opts.blunt ? 0.30 : 0.17) * w0;
    const tipH = (opts.blunt ? 0.66 : 0.52) * h0;
    // galley keel sweep: the tip rides high so the keel line rises to the ram
    // blade while the deck diagonal drops onto it - deep V read in profile.
    // Alien flavour droops it back down into an organic beak.
    const tipDy = 0.16 * h0 - fl * 0.44 * h0;
    // wedge loft: a massive armoured blade at the tip flaring to the bow
    // section. Mid stations ENVELOPE the hull skin (1.03x the section there)
    // so the wedge, not the lofted nose, owns the whole prow silhouette.
    const zM1 = zTip - (zTip - zA) * 0.35, zM2 = zTip - (zTip - zA) * 0.7;
    const P = [[0.0, 1.0], [0.75, 0.28], [0.85, -0.3], [0.0, -1.0], [-0.85, -0.3], [-0.75, 0.28]];
    const sta = [
        { z: zTip, w: tipW, h: tipH, dy: tipDy },
        { z: zM1, w: Math.max(0.56 * w0, 1.03 * frame.W(zM1)), h: Math.max(0.72 * h0, 1.03 * frame.H(zM1)), dy: tipDy * 0.5 },
        { z: zM2, w: Math.max(0.84 * w0, 1.03 * frame.W(zM2)), h: Math.max(0.93 * h0, 1.03 * frame.H(zM2)), dy: tipDy * 0.15 },
        { z: zA, w: 1.02 * w0, h: 1.03 * h0, dy: 0 },
    ].map((s) => ({ z: s.z, pts: P.map(([px, py]) => [px * s.w, py * s.h + (s.dy || 0)]) }));
    bin.add('armor', loft(sta, { capStart: true, capEnd: true, uScale: 2, vScale: 0.5 / k }), {});
    // half-width of the wedge skin at station z (linear approximation of the
    // loft) - used to keep plough layers and apertures ON the armour surface
    const wAt = (z) => {
        const t = Math.min(1, Math.max(0, (zTip - z) / (zTip - zA)));
        return tipW + (1.02 * w0 - tipW) * t;
    };
    // vertical ram beam on the leading edge, layered like a plough
    const hTip = tipH;
    strut(bin, 'armor', [0, tipDy - hTip * 1.05, zTip + 0.05 * k], [0, tipDy + hTip * 1.05, zTip + 0.05 * k], 0.09 * k, g);
    strut(bin, 'trim', [0, tipDy - hTip * 1.02, zTip + 0.1 * k], [0, tipDy + hTip * 1.02, zTip + 0.1 * k], 0.045 * k, g);
    for (let i = 0; i < 4; i++) {
        const t = i / 4;
        const z = zTip - t * fwd * 1.15, hh = hTip + t * (0.42 * h0);
        const layer = bevelPlate(0.2 * k + t * 0.3 * k, 0.08 * k, hh * 2, 0.025 * k);
        layer.rotateX(Math.PI / 2); // plate lies in the xz... rotate so depth spans y
        uvPatch(layer, g, 0.15);
        bin.add(i === 0 ? 'trim' : 'armor', layer, { pos: [0, tipDy * (1 - t * 0.6), z], subPart: i > 0 });
    }
    // armoured cheek plates layered down both wedge flanks (plough sides)
    for (const side of [1, -1]) {
        for (let i = 0; i < 3; i++) {
            const t = 0.22 + i * 0.24;
            const zc = zTip - t * (zTip - zA);
            const cheek = bevelPlate(0.05 * k, (0.4 + t * 0.35) * h0, (0.2 + 0.06 * i) * total, 0.02 * k);
            uvPatch(cheek, g, 0.2);
            const yawA = side * Math.atan2(0.98 * w0 - tipW, zTip - zA);
            const mB = new THREE.Matrix4().makeRotationY(yawA);
            mB.setPosition(side * wAt(zc) * 0.92, 0, zc);
            bin.add('armor', cheek, { basis: mB, subPart: true });
        }
    }
    // plough edges: trim rails from tip to the upper and lower chines
    for (const sy of [1, -1]) {
        strut(bin, 'trim', [0, tipDy + sy * hTip, zTip], [0, sy * 0.95 * h0, zA + 0.1 * k], 0.07 * k, g);
        for (const sx of [1, -1]) {
            strut(bin, 'trim', [0, tipDy + sy * hTip * 0.8, zTip - 0.05 * k], [sx * 0.8 * w0, sy * 0.29 * h0 * (sy > 0 ? 1 : 1.0), zA], 0.045 * k, g);
        }
    }
    // gothic under-beak on capitals
    if (opts.beak) {
        const beak = [
            { z: zTip - fwd * 0.3, w: 0.03 * k, h: 0.08 * h0 },
            { z: zTip - (zTip - zA) * 0.5, w: 0.08 * k, h: 0.3 * h0 },
            { z: zA, w: 0.14 * k, h: 0.44 * h0 },
        ].map((s) => ({ z: s.z, pts: [[0, 0], [s.w, -s.h * 0.4], [0, -s.h], [-s.w, -s.h * 0.4]] }));
        const geo = loft(beak, { capStart: true, capEnd: true, uScale: 1, vScale: 0.5 });
        geo.translate(0, -h0 * 0.62, 0);
        bin.add('armor', geo, {});
        strut(bin, 'trim', [0, -h0 * 0.62 - 0.06 * h0, zTip - fwd * 0.3], [0, -h0 * 0.62 - 0.42 * h0, zA], 0.04 * k, g);
    }
    // beam-cannon apertures: saturated slots recessed into the prow flanks,
    // riding the wedge skin so they read as cut into the armour
    if (opts.beamApertures) {
        for (const side of [1, -1]) {
            for (let i = 0; i < opts.beamApertures; i++) {
                const z = zTip - (zTip - zA) * (0.34 + 0.18 * i);
                const xs = side * wAt(z) * 0.84;
                const slot = new THREE.BoxGeometry(0.035 * k, 0.09 * h0, 0.3 * k);
                uvTransform(slot, 0.12, 0.12, 0.44, 0.44);
                bin.add('engine_glow', slot, { pos: [xs, 0.12 * h0, z] });
                strut(bin, 'trim', [xs, 0.19 * h0 + 0.08 * k, z - 0.16 * k],
                    [xs, 0.19 * h0 + 0.08 * k, z + 0.16 * k], 0.03 * k, g);
            }
        }
    }
    return { zTip, len: total };
}

// W40k armoured prow blade (class-identity round, corrected ruling): NO
// projecting ram beam, NO rostrum spar - the front IS the identity. One
// massive angled wedge face spans the full bow height like a cathedral door
// leaning forward. Profile per the user's exact spec: "wide at the bottom,
// and retracted + narrower to the top" - the KEEL of the blade juts furthest
// forward and carries the greatest width; rising, the face RAKES BACKWARD
// and NARROWS (the underbite blade). Layered armour facets band the face,
// trim-edged so the prow reads as its own gold-trimmed plate. Nothing
// projects ahead of the blade.
// Strengthened per the identity-sheet ruling ("must be stronger", every
// warship): more mass and forward dominance - broader keel slab thrown
// further ahead of the skin, deeper double-layered facet banding, and the
// face tiled in pale trim plates edged with trim rails so the prow reads
// as ONE distinct plated face, the single most massive element of the
// silhouette. lean (battle cruiser) now only deepens the rake - same
// authority, same keel beam and crest as the rest of the family.
export function prowBlade(bin, g, frame, opts = {}) {
    const { zBow, k } = frame;
    const fl = frame.fl || 0;
    const total = (opts.lenFrac ?? 0.22) * k * 10 * (1 + 0.1 * fl);
    // lean (battle cruiser): identical underbite mass, deeper rake only
    const lean = opts.lean ? 1 : 0;
    const fwd = total * (lean ? 0.58 : 0.53);   // keel tip well forward of the hull skin
    const zKeel = zBow + fwd;                   // bottom of the blade: furthest forward
    const zA = zBow - (total - fwd);            // root station, deep in armoured mass
    const w0 = frame.W(zA), h0 = frame.H(zA);
    const hCrest = (opts.crestRise ?? 1.12) * h0;  // blade tops the sheer
    const hKeel = 1.1 * h0;
    const keelDrop = 0.14 * h0;                 // chevron keel point under the bottom edge
    // crest sits well behind the keel: the raked face
    const zCrest = zKeel - fwd * (lean ? 1.36 : 1.2);
    // station parameterisation: t=0 keel tip -> t=1 root. Rising top edge
    // (the face has "passed" everything above the rake line), broad bottom
    // narrowing top, mid stations enveloping the hull skin so the blade,
    // not the loft nose, owns the whole bow silhouette.
    const wTop = 0.34 * w0;
    const sta = [];
    const mk = (z, yTop, wt, wb, tuck) => {
        const yMid = -hKeel + 0.34 * (yTop + hKeel);
        const wm = Math.max(wb, frame.W(Math.min(z, zBow)) * 1.05);
        sta.push({
            z,
            pts: [
                [0, yTop + 0.02 * h0], [wt, yTop], [wm, yMid], [wb * tuck, -hKeel],
                [0, -hKeel - keelDrop], [-wb * tuck, -hKeel], [-wm, yMid], [-wt, yTop],
            ],
        });
    };
    mk(zKeel, -hKeel + 0.26 * h0, 0.62 * w0, 0.78 * w0, 0.88);                // keel slab, broad and low
    mk(zKeel - (zKeel - zCrest) * 0.4, -hKeel + (hCrest + hKeel) * 0.4, 0.72 * wTop + 0.3 * w0, 0.95 * w0, 0.9);
    mk(zKeel - (zKeel - zCrest) * 0.75, -hKeel + (hCrest + hKeel) * 0.75, wTop * 1.1, 1.0 * w0, 0.91);
    mk(zCrest, hCrest, wTop, 1.04 * w0, 0.92);                                // crest: narrow top, full keel beam
    mk(zA, 1.04 * h0, 0.9 * w0, 1.05 * w0, 0.94);                             // blend into the hull section
    bin.add('armor', loft(sta, { capStart: true, capEnd: true, uScale: 2, vScale: 0.5 / k }), {});
    // layered armour facets banding the raked face - the "cathedral door"
    // plates, tilted to the face slope. Base bands are PALE trim plates that
    // tile the whole face; each carries a proud secondary armour facet so
    // the layering reads deep, and the face is a distinct trim-edged plate.
    const rake = Math.atan2(zKeel - zCrest, hCrest + hKeel);   // face pitch from vertical
    const nBands = opts.bands ?? 5;
    for (let i = 0; i < nBands; i++) {
        const t = (i + 0.5) / nBands;                          // 0 keel -> 1 crest
        const y = -hKeel + t * (hCrest + hKeel);
        const zf = zKeel - t * (zKeel - zCrest);
        const bw = (0.72 * w0) * (1 - t) + wTop * 1.5 * t;     // band narrows rising
        const bd = (0.36 - 0.025 * i) * total * 0.52;          // band depth down the face
        const plate = bevelPlate(bw * 2 * 0.98, 0.09 * k, bd, 0.025 * k);
        uvPatch(plate, g, 0.2);
        const mB = new THREE.Matrix4().makeRotationX(-(Math.PI / 2 - rake));
        mB.setPosition(0, y, zf + 0.03 * k);
        bin.add(i % 2 ? 'armor' : 'trim', plate, { basis: mB, subPart: i > 0 });
        // secondary facet proud of each band: the deep-layered face
        const p2 = bevelPlate(bw * 2 * 0.6, 0.05 * k, bd * 0.55, 0.02 * k);
        uvPatch(p2, g, 0.16);
        const m2 = mB.clone();
        m2.setPosition(0, y + 0.09 * k * Math.cos(rake), zf + 0.03 * k + 0.09 * k * Math.sin(rake));
        bin.add(i % 2 ? 'trim' : 'armor', p2, { basis: m2, subPart: true });
    }
    // chevron crease rails: keel point up the face centre to the crest, the
    // two raked leading edges, and a crest cross-rail framing the pale face -
    // all ON the blade, nothing ahead of it
    strut(bin, 'trim', [0, -hKeel - keelDrop, zKeel], [0, hCrest, zCrest], 0.07 * k, g);
    strut(bin, 'trim', [-wTop, hCrest, zCrest], [wTop, hCrest, zCrest], 0.05 * k, g);
    for (const side of [1, -1]) {
        strut(bin, 'trim', [side * 0.78 * w0 * 0.88, -hKeel, zKeel - 0.02 * k], [side * wTop, hCrest, zCrest], 0.06 * k, g);
        // bottom edge rail: the broad keel lip
        strut(bin, 'armor', [side * 0.78 * w0 * 0.88, -hKeel - 0.02 * h0, zKeel], [side * 1.02 * w0, -hKeel, zA + 0.1 * k], 0.075 * k, g);
    }
    // armoured cheek plates layered down the flanks (plough sides)
    for (const side of [1, -1]) {
        for (let i = 0; i < 4; i++) {
            const t = 0.2 + i * 0.2;
            const zc = zKeel - t * (zKeel - zA);
            const wm = Math.max((0.78 * w0) * (1 - t) + 1.02 * w0 * t, frame.W(Math.min(zc, zBow)) * 1.05);
            const cheek = bevelPlate(0.07 * k, (0.44 + t * 0.42) * h0, (0.2 + 0.05 * i) * total, 0.022 * k);
            uvPatch(cheek, g, 0.2);
            const yawA = side * Math.atan2(0.32 * w0, zKeel - zA);
            const mC = new THREE.Matrix4().makeRotationY(yawA);
            mC.setPosition(side * wm * 0.9, -0.25 * h0, zc);
            bin.add(i === 1 ? 'trim' : 'armor', cheek, { basis: mC, subPart: true });
        }
    }
    // beam-cannon apertures cut into the upper blade flanks
    if (opts.apertures) {
        for (const side of [1, -1]) {
            for (let i = 0; i < opts.apertures; i++) {
                const t = 0.55 + 0.18 * i;
                const z = zKeel - t * (zKeel - zA);
                const wm = Math.max((0.78 * w0) * (1 - t) + 1.02 * w0 * t, frame.W(Math.min(z, zBow)) * 1.05);
                const slot = new THREE.BoxGeometry(0.035 * k, 0.09 * h0, 0.3 * k);
                uvTransform(slot, 0.12, 0.12, 0.44, 0.44);
                bin.add('engine_glow', slot, { pos: [side * wm * 0.86, 0.16 * h0, z] });
                strut(bin, 'trim', [side * wm * 0.86, 0.23 * h0 + 0.08 * k, z - 0.16 * k],
                    [side * wm * 0.86, 0.23 * h0 + 0.08 * k, z + 0.16 * k], 0.03 * k, g);
            }
        }
    }
    return { zTip: zKeel, len: total };
}

// Twin forward mandible prongs (GTF Apollo lineage) for light combat hulls.
export function mandibleProws(bin, g, frame, opts = {}) {
    const { zBow, k } = frame;
    const w0 = frame.W(zBow - 0.4 * k), h0 = frame.H(zBow - 0.4 * k);
    const len = (opts.lenFrac ?? 0.16) * k * 10;
    const gap = opts.gap ?? 0.45 * w0;
    for (const side of [1, -1]) {
        const x = side * gap;
        const sta = [
            { z: zBow + len, w: 0.1 * k, h: 0.15 * k },
            { z: zBow + len * 0.45, w: 0.2 * k, h: 0.28 * k },
            { z: zBow - 0.5 * k, w: 0.3 * k, h: 0.42 * k },
        ].map((s) => ({ z: s.z, pts: [[s.w, s.h * 0.4], [s.w, -s.h * 0.6], [-s.w, -s.h * 0.6], [-s.w, s.h * 0.4], [0, s.h]] }));
        const geo = loft(sta, { capStart: true, capEnd: true, uScale: 1.5, vScale: 0.6 });
        geo.translate(x, -0.1 * h0, 0);
        bin.add('armor', geo, {});
        strut(bin, 'trim', [x, 0.14 * k - 0.1 * h0, zBow + len], [x, 0.3 * k - 0.1 * h0, zBow - 0.4 * k], 0.035 * k, g);
        // gun barrel in each mandible mouth
        const barrel = new THREE.CylinderGeometry(0.03 * k, 0.036 * k, len * 0.7, 8);
        barrel.rotateX(Math.PI / 2);
        uvPatch(barrel, g, 0.1);
        bin.add('mech', barrel, { pos: [x, -0.12 * h0, zBow + len * 0.65], subPart: true });
    }
}

// Gothic reinforcement bands ringing the hull at the given z stations.
export function gothicBands(bin, g, frame, zList) {
    const nPts = frame.profile.length;
    for (const z of zList) {
        const w = frame.W(z), h = frame.H(z);
        for (let j = 0; j < nPts; j++) {
            const p0 = frame.profile[j], p1 = frame.profile[(j + 1) % nPts];
            strut(bin, j % 2 === 0 ? 'trim' : 'armor',
                [p0[0] * w * 1.025, p0[1] * h * 1.025, z],
                [p1[0] * w * 1.025, p1[1] * h * 1.025, z], 0.07 * frame.k, g);
        }
    }
}

// Deck VLS missile field with trim kerb.
export function vlsField(bin, g, frame, vls) {
    const { z0, z1, cols, rows } = vls;
    const pitch = vls.pitch ?? 0.17;
    for (let r = 0; r < rows; r++) {
        const z = z0 + ((z1 - z0) * (r + 0.5)) / rows;
        for (let c = 0; c < cols; c++) {
            const x = (c - (cols - 1) / 2) * pitch;
            const cell = bevelPlate(pitch * 0.65, 0.035, pitch * 0.65, 0.02);
            uvPatch(cell, g, 0.1);
            bin.add('armor', cell, { pos: [x, frame.deckYAt(z, x), z] });
        }
    }
    const zm = (z0 + z1) / 2;
    const hw = (cols / 2) * pitch + 0.09;
    const y = frame.deckYAt(zm, hw) + 0.02;
    strut(bin, 'trim', [-hw + 0.02, y, z0 + 0.08], [hw - 0.02, y, z0 + 0.08], 0.035, g);
    strut(bin, 'trim', [-hw + 0.02, y, z1 - 0.08], [hw - 0.02, y, z1 - 0.08], 0.035, g);
    strut(bin, 'trim', [-hw, y, z0 + 0.08], [-hw, y, z1 - 0.08], 0.035, g);
    strut(bin, 'trim', [hw, y, z0 + 0.08], [hw, y, z1 - 0.08], 0.035, g);
}

// Twin-barrel naval turret; up = 1 dorsal, -1 ventral.
export function turret(bin, g, frame, z, up, s, opts = {}) {
    const y = up > 0 ? frame.deckYAt(z, 0) - 0.02 : -frame.H(z) * 0.985 + 0.02;
    const yaw = g.range(-0.16, 0.16);
    const yAxis = new THREE.Vector3(0, up, 0);
    const zAxis = new THREE.Vector3(0, 0, 1);
    const xAxis = new THREE.Vector3().crossVectors(yAxis, zAxis);
    const basis = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis);
    basis.setPosition(opts.x || 0, y, z);
    basis.multiply(new THREE.Matrix4().makeRotationY(yaw));
    const part = (name, geo, local, sub = true) => {
        uvPatch(geo, g, 0.18);
        const m = basis.clone().multiply(new THREE.Matrix4().makeTranslation(local[0], local[1], local[2]));
        bin.add(name, geo, { basis: m, subPart: sub });
    };
    part('armor', new THREE.CylinderGeometry(0.30 * s, 0.33 * s, 0.1 * s, 16), [0, 0.05 * s, 0], false);
    part('trim', new THREE.CylinderGeometry(0.31 * s, 0.31 * s, 0.03 * s, 16), [0, 0.11 * s, 0]);
    part('armor', bevelPlate(0.55 * s, 0.26 * s, 0.46 * s, 0.07 * s), [0, 0.12 * s, 0]);
    part('armor', new THREE.BoxGeometry(0.3 * s, 0.13 * s, 0.1 * s), [0, 0.24 * s, 0.22 * s]);
    const nb = opts.barrels ?? 2;
    const bxs = nb === 3 ? [-0.12 * s, 0, 0.12 * s] : nb === 1 ? [0] : [-0.09 * s, 0.09 * s];
    for (const bx of bxs) {
        const barrel = new THREE.CylinderGeometry(0.032 * s, 0.038 * s, 0.85 * s, 10);
        barrel.rotateX(Math.PI / 2);
        part('mech', barrel, [bx, 0.26 * s, 0.6 * s]);
        const muzzle = new THREE.CylinderGeometry(0.05 * s, 0.05 * s, 0.09 * s, 10);
        muzzle.rotateX(Math.PI / 2);
        part('mech', muzzle, [bx, 0.26 * s, 1.0 * s]);
        part('mech', new THREE.BoxGeometry(0.08 * s, 0.09 * s, 0.2 * s), [bx, 0.26 * s, 0.28 * s]);
    }
}

// Broadside gun decks: rows of casemate batteries arrayed down BOTH flanks,
// ship-of-the-line fashion. spec: { z0, z1, guns, tiers: [yFrac...], s }.
// Each tier is a continuous armoured deck strip with a trim rail and a row of
// casemates - sponson box, dark gun port, twin outward barrels with muzzles.
export function broadsideDeck(bin, g, frame, spec) {
    const { z0, z1 } = spec;
    const s = spec.s ?? Math.max(0.9, frame.k * 0.7);
    const guns = spec.guns ?? 6;
    const tiers = spec.tiers ?? [0.05];
    const skipZ = spec.skipZ || [];
    const bay = (z0 - z1) / guns;
    for (const side of [1, -1]) {
        for (const yf of tiers) {
            for (let i = 0; i < guns; i++) {
                const z = z0 + ((z1 - z0) * (i + 0.5)) / guns;
                if (skipZ.some((sz) => Math.abs(z - sz.z) < sz.dz)) continue;
                const w = frame.W(z), y = yf * frame.H(z);
                const x = side * (w + 0.07 * s);
                // deck pad segment: contiguous bays so the flank reads as one
                // continuous armoured gun deck line, not scattered blisters
                const pad = bevelPlate(0.1 * s, 0.4 * s, bay * 0.98, 0.02 * s);
                uvPatch(pad, g, 0.25);
                bin.add('armor', pad, { pos: [side * (w + 0.03 * s), y, z] });
                strut(bin, 'trim', [side * (w + 0.08 * s), y + 0.23 * s, z - bay * 0.5],
                    [side * (w + 0.08 * s), y + 0.23 * s, z + bay * 0.5], 0.03 * s, g);
                strut(bin, 'trim', [side * (w + 0.08 * s), y - 0.23 * s, z - bay * 0.5],
                    [side * (w + 0.08 * s), y - 0.23 * s, z + bay * 0.5], 0.026 * s, g);
                // casemate sponson
                const box = bevelPlate(0.22 * s, 0.3 * s, 0.38 * s, 0.04 * s);
                uvPatch(box, g, 0.15);
                bin.add('armor', box, { pos: [x, y, z] });
                // dark gun port on the outer face
                const port = new THREE.BoxGeometry(0.03 * s, 0.16 * s, 0.24 * s);
                uvTransform(port, 0.001, 0.001, 0.002, 0.002);
                bin.add('windows', port, { pos: [x + side * 0.1 * s, y, z], subPart: true });
                // twin barrels firing abeam
                for (const dz of [-0.065 * s, 0.065 * s]) {
                    const barrel = new THREE.CylinderGeometry(0.026 * s, 0.034 * s, 0.55 * s, 8);
                    barrel.rotateZ(Math.PI / 2);
                    uvPatch(barrel, g, 0.06);
                    bin.add('mech', barrel, { pos: [x + side * 0.36 * s, y + 0.02 * s, z + dz], subPart: true });
                    const muzzle = new THREE.CylinderGeometry(0.042 * s, 0.042 * s, 0.08 * s, 8);
                    muzzle.rotateZ(Math.PI / 2);
                    uvPatch(muzzle, g, 0.04);
                    bin.add('trim', muzzle, { pos: [x + side * 0.64 * s, y + 0.02 * s, z + dz], subPart: true });
                }
                // mantlet hood over the barrels
                const hood = new THREE.BoxGeometry(0.13 * s, 0.08 * s, 0.32 * s);
                uvPatch(hood, g, 0.08);
                bin.add('armor', hood, { pos: [x + side * 0.14 * s, y + 0.13 * s, z], subPart: true });
            }
        }
    }
}

// Ventral keel fin under the stern quarter (cruiser digest): a raked armoured
// blade dropping below the keel line, radiator surface on the trailing edge.
export function keelFin(bin, g, frame, z, s = 1.0) {
    const y0 = -frame.H(z) * 0.92;
    const sta = [
        { z: z + 1.0 * s, w: 0.05 * s, h: 0.12 * s },
        { z: z + 0.2 * s, w: 0.035 * s, h: 0.85 * s },
        { z: z - 0.7 * s, w: 0.045 * s, h: 0.55 * s },
    ].map((st) => ({ z: st.z, pts: [[st.w, 0], [st.w * 0.6, -st.h], [-st.w * 0.6, -st.h], [-st.w, 0]] }));
    const blade = loft(sta, { capStart: true, capEnd: true, uScale: 1, vScale: 0.5 });
    blade.translate(0, y0, 0);
    bin.add('armor', blade, {});
    const rad = new THREE.BoxGeometry(0.016 * s, 0.5 * s, 0.5 * s);
    bin.add('radiator', rad, { pos: [0, y0 - 0.45 * s, z - 0.5 * s], subPart: true });
    strut(bin, 'trim', [0, y0 - 0.02 * s, z + 1.0 * s], [0, y0 - 0.85 * s, z + 0.15 * s], 0.03 * s, g);
}

// Point-defence blister pair on the flank chamfers at z.
export function pdMounts(bin, g, frame, z, s = 1.0) {
    for (const side of [1, -1]) {
        const w = frame.W(z), h = frame.H(z);
        const px = side * 0.775 * w, py = 0.68 * h;
        const n2 = side > 0 ? [0.52, 0.45, 0] : [-0.52, 0.45, 0];
        const basis = surfaceBasis([px, py, z], n2, [0, 0, 1]);
        const part = (name, geo, local, sub = true) => {
            uvPatch(geo, g, 0.12);
            const m = basis.clone().multiply(new THREE.Matrix4().makeTranslation(local[0], local[1], local[2]));
            bin.add(name, geo, { basis: m, subPart: sub });
        };
        part('armor', new THREE.CylinderGeometry(0.07 * s, 0.085 * s, 0.05 * s, 12), [0, 0.025 * s, 0], false);
        part('mech', new THREE.SphereGeometry(0.075 * s, 12, 9), [0, 0.08 * s, 0]);
        const barrel = new THREE.CylinderGeometry(0.016 * s, 0.016 * s, 0.3 * s, 8);
        barrel.rotateX(Math.PI / 2);
        part('mech', barrel, [0, 0.1 * s, 0.17 * s]);
    }
}

// Cathedral spine: dorsal ridge of alternating blocks with flying buttresses.
export function cathedralSpine(bin, g, frame, z0, z1, s = 1.0, opts = {}) {
    const ridge = new THREE.BoxGeometry(0.36 * s, 0.08 * s, z0 - z1);
    uvPatch(ridge, g, 0.3);
    bin.add('armor', ridge, { pos: [0, frame.deckYAt((z0 + z1) / 2, 0) + 0.02, (z0 + z1) / 2] });
    const step = (opts.dense ? 0.34 : 0.44) * s;
    let kk = 0;
    for (let z = z0 - 0.2 * s; z > z1 + 0.1 * s; z -= step, kk++) {
        const tall = opts.dense ? kk % 3 !== 1 : kk % 2 === 0;
        const bh = ((tall ? 0.42 : 0.24) + g.range(-0.03, 0.05)) * s;
        const block = bevelPlate(0.3 * s, bh, 0.34 * s, 0.04 * s);
        uvPatch(block, g, 0.2);
        const dy = frame.deckYAt(z, 0);
        bin.add('armor', block, { pos: [0, dy + 0.04 * s, z] });
        const cap = new THREE.BoxGeometry(0.34 * s, 0.035 * s, 0.38 * s);
        uvPatch(cap, g, 0.15);
        bin.add('trim', cap, { pos: [0, dy + 0.04 * s + bh, z], subPart: true });
        if (tall) {
            for (const side of [1, -1]) {
                strut(bin, 'armor', [side * 0.5 * frame.W(z), dy - 0.06 * s, z], [side * 0.16 * s, dy + bh * 0.8, z], 0.05 * s, g);
            }
        }
    }
}

// Crenellated bridge tower with lit window strips, masts and sensor cluster.
export function bridgeTower(bin, g, frame, z0, z1, s = 1.0) {
    const zc = (z0 + z1) / 2, len = z0 - z1;
    const yb = frame.deckYAt(zc, 0) - 0.03 * s;
    const addStack = (name, geo, pos, sub = false) => { uvPatch(geo, g, 0.25); bin.add(name, geo, { pos, subPart: sub }); };
    addStack('armor', bevelPlate(0.95 * s, 0.30 * s, len, 0.06 * s), [0, yb, zc]);
    addStack('armor', bevelPlate(0.62 * s, 0.30 * s, len * 0.7, 0.05 * s), [0, yb + 0.29 * s, zc - 0.05 * s]);
    addStack('armor', bevelPlate(0.40 * s, 0.26 * s, len * 0.42, 0.05 * s), [0, yb + 0.58 * s, zc - 0.02 * s]);
    const glacis = new THREE.BoxGeometry(0.5 * s, 0.36 * s, 0.06 * s);
    glacis.rotateX(-0.6);
    addStack('armor', glacis, [0, yb + 0.42 * s, z0 - 0.12 * s], true);
    strut(bin, 'trim', [-0.25 * s, yb + 0.6 * s, z0 - 0.2 * s], [0.25 * s, yb + 0.6 * s, z0 - 0.2 * s], 0.035 * s, g);
    const winStrip = (w, h, pos, axis) => {
        const geo = axis === 'z' ? new THREE.BoxGeometry(w, h, 0.014) : new THREE.BoxGeometry(0.014, h, w);
        const row = g.int(0, 15);
        uvTransform(geo, w * 2.0, 0.045, g.range(0, 0.4), row / 16 + 0.012);
        bin.add('windows', geo, { pos, subPart: true });
    };
    winStrip(0.42 * s, 0.05 * s, [0, yb + 0.40 * s, zc - 0.05 * s + len * 0.35 + 0.01], 'z');
    winStrip(0.42 * s, 0.05 * s, [0, yb + 0.48 * s, zc - 0.05 * s + len * 0.35 + 0.01], 'z');
    winStrip(0.3 * s, 0.045 * s, [0, yb + 0.68 * s, zc - 0.02 * s + len * 0.21 + 0.01], 'z');
    for (const side of [1, -1]) {
        winStrip(len * 0.5, 0.05 * s, [side * 0.315 * s, yb + 0.44 * s, zc - 0.05 * s], 'x');
        winStrip(len * 0.3, 0.045 * s, [side * 0.205 * s, yb + 0.66 * s, zc - 0.02 * s], 'x');
    }
    const roof = yb + 0.58 * s + 0.26 * s;
    const tw = 0.2 * s, tl = len * 0.21;
    for (let t = -tl; t <= tl; t += 0.11 * s) {
        for (const side of [1, -1]) {
            const tooth = new THREE.BoxGeometry(0.045 * s, 0.06 * s, 0.05 * s);
            uvPatch(tooth, g, 0.08);
            bin.add('armor', tooth, { pos: [side * tw, roof + 0.02 * s, zc - 0.02 * s + t], subPart: true });
        }
    }
    for (let x = -tw; x <= tw; x += 0.1 * s) {
        for (const zz of [zc - 0.02 * s - tl, zc - 0.02 * s + tl]) {
            const tooth = new THREE.BoxGeometry(0.05 * s, 0.06 * s, 0.045 * s);
            uvPatch(tooth, g, 0.08);
            bin.add('armor', tooth, { pos: [x, roof + 0.02 * s, zz], subPart: true });
        }
    }
    for (const [mx, mh] of [[-0.12 * s, 0.55 * s], [0.12 * s, 0.72 * s]]) {
        let y = roof;
        for (const [r0, r1, seg] of [[0.022, 0.028, 0.45], [0.014, 0.02, 0.3], [0.007, 0.011, 0.25]]) {
            const m = new THREE.CylinderGeometry(r0 * s, r1 * s, mh * seg, 7);
            uvPatch(m, g, 0.06);
            bin.add('mech', m, { pos: [mx, y + (mh * seg) / 2, zc - 0.15 * s], subPart: y !== roof });
            y += mh * seg;
        }
        const bar = new THREE.CylinderGeometry(0.006 * s, 0.006 * s, 0.16 * s, 5);
        bar.rotateZ(Math.PI / 2);
        uvPatch(bar, g, 0.05);
        bin.add('mech', bar, { pos: [mx, roof + mh * 0.6, zc - 0.15 * s], subPart: true });
    }
    const dome = new THREE.SphereGeometry(0.11 * s, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    uvPatch(dome, g, 0.1);
    bin.add('mech', dome, { pos: [0, yb + 0.59 * s, z1 + 0.25 * s] });
    for (let i = 0; i < 5; i++) {
        const b = new THREE.BoxGeometry(g.range(0.05, 0.12) * s, g.range(0.04, 0.1) * s, g.range(0.05, 0.12) * s);
        uvPatch(b, g, 0.08);
        bin.add('mech', b, { pos: [g.range(-0.35, 0.35) * s, yb + 0.31 * s, z0 - g.range(0.1, 0.3) * s], subPart: i > 0 });
    }
}

// Flank window rows between z0 (fore) and z1 (aft), plus an optional boat bay.
export function windowRows(bin, g, frame, z0, z1, opts = {}) {
    const step = opts.step ?? 0.32;
    const yTop = opts.yTop ?? 0.05, yLow = opts.yLow ?? -0.12;
    for (let z = z0; z > z1; z -= step) {
        for (const side of [1, -1]) {
            if (g.chance(opts.skip ?? 0.25)) continue;
            const w = frame.W(z), h = frame.H(z);
            const geo = new THREE.BoxGeometry(0.014, 0.05, 0.2);
            const row = g.int(0, 15);
            uvTransform(geo, 0.4, 0.045, g.range(0, 0.5), row / 16 + 0.012);
            bin.add('windows', geo, { pos: [side * (w + 0.005), yTop * h, z] });
            if (opts.lower !== false && g.chance(0.4)) {
                const geo2 = new THREE.BoxGeometry(0.014, 0.045, 0.16);
                uvTransform(geo2, 0.32, 0.04, g.range(0, 0.5), g.int(0, 15) / 16 + 0.012);
                bin.add('windows', geo2, { pos: [side * (w + 0.005), yLow * h, z], subPart: true });
            }
        }
    }
    if (opts.boatBay !== false) {
        const bayZ = opts.bayZ ?? (z0 + z1) / 2, bw = frame.W(bayZ);
        const mouth = new THREE.BoxGeometry(0.03, 0.2, 0.34);
        uvTransform(mouth, 0.001, 0.001, 0.002, 0.002);
        bin.add('windows', mouth, { pos: [bw - 0.005, -0.05, bayZ] });
        strut(bin, 'trim', [bw + 0.02, 0.07, bayZ - 0.19], [bw + 0.02, 0.07, bayZ + 0.19], 0.03, g);
        strut(bin, 'trim', [bw + 0.02, -0.17, bayZ - 0.19], [bw + 0.02, -0.17, bayZ + 0.19], 0.03, g);
    }
}

// Angled radiator fin pair with feed pipes at z.
export function radiatorPair(bin, g, frame, z, s = 1.0) {
    for (const side of [1, -1]) {
        const w = frame.W(z), h = frame.H(z);
        const x0 = side * 0.62 * w, y0 = -0.84 * h + 0.1 * s;
        const fin = new THREE.BoxGeometry(0.55 * s, 0.022, 0.9 * s);
        fin.rotateZ(side * -0.45);
        bin.add('radiator', fin, { pos: [x0 + side * 0.26 * s, y0 - 0.13 * s, z] });
        tube(bin, 'mech', [x0, y0, z - 0.25 * s], [x0 + side * 0.3 * s, y0 - 0.16 * s, z - 0.25 * s], 0.02 * s, 6, g);
        tube(bin, 'mech', [x0, y0, z + 0.25 * s], [x0 + side * 0.3 * s, y0 - 0.16 * s, z + 0.25 * s], 0.02 * s, 6, g);
    }
}

// Big flat radiator wings for civilian hulls, mounted off a spine at [x,y,z].
export function radiatorWing(bin, g, pos, len, chord, angle = 0) {
    for (const side of [1, -1]) {
        const fin = new THREE.BoxGeometry(len, 0.02, chord);
        fin.rotateZ(side * angle);
        bin.add('radiator', fin, { pos: [pos[0] + side * (len / 2 + 0.06), pos[1], pos[2]] });
    }
}

// Ventral truss keel with capsule fuel tanks (warship style).
export function ventralTruss(bin, g, frame, z0, z1, s = 1.0) {
    const zc = (z0 + z1) / 2, len = z0 - z1;
    const yTop = -frame.H(zc) * 0.99;
    const yRail = yTop - 0.22 * s;
    for (const side of [1, -1]) {
        const rail = new THREE.BoxGeometry(0.05 * s, 0.05 * s, len);
        uvPatch(rail, g, 0.2);
        bin.add('mech', rail, { pos: [side * 0.15 * s, yRail, zc] });
    }
    for (let z = z0; z > z1; z -= 0.24 * s) {
        for (const side of [1, -1]) {
            tube(bin, 'mech', [side * 0.15 * s, yRail, z], [side * 0.22 * s, yTop, z], 0.018 * s, 6, g);
            tube(bin, 'mech', [side * 0.15 * s, yRail, z], [-side * 0.15 * s, yRail, z - 0.24 * s], 0.014 * s, 5, g);
        }
    }
    for (const [tz, tr] of [[zc + 0.28 * s, 0.13 * s], [zc - 0.3 * s, 0.12 * s]]) {
        const tank = new THREE.CapsuleGeometry(tr, 0.42 * s, 4, 14);
        tank.rotateX(Math.PI / 2);
        uvPatch(tank, g, 0.2);
        bin.add('mech', tank, { pos: [0, yRail + 0.04 * s, tz] });
        for (const dz of [-0.15 * s, 0.15 * s]) {
            const band = new THREE.CylinderGeometry(tr * 1.06, tr * 1.06, 0.03 * s, 14);
            band.rotateX(Math.PI / 2);
            uvPatch(band, g, 0.1);
            bin.add('trim', band, { pos: [0, yRail + 0.04 * s, tz + dz], subPart: true });
        }
    }
    for (const ez of [z0 + 0.05 * s, z1 - 0.05 * s]) {
        const endCap = bevelPlate(0.42 * s, 0.1 * s, 0.16 * s, 0.03 * s);
        uvPatch(endCap, g, 0.15);
        bin.add('armor', endCap, { pos: [0, yRail - 0.03 * s, ez] });
    }
}

// Spherical fuel/cargo tank with equator band and feed pipe.
export function fuelSphere(bin, g, pos, r) {
    const sphere = new THREE.SphereGeometry(r, 18, 13);
    uvPatch(sphere, g, 0.3);
    bin.add('armor', sphere, { pos });
    const band = new THREE.CylinderGeometry(r * 1.007, r * 1.007, r * 0.17, 18);
    uvPatch(band, g, 0.1);
    bin.add('trim', band, { pos, subPart: true });
    tube(bin, 'mech', [pos[0], pos[1] + r * 0.93, pos[2]], [pos[0] * 0.6, pos[1] + r * 1.67, pos[2] + r * 0.67], r * 0.083, 6, g);
}

// Main drive block: armoured skirt, engine casings, layered bell nozzles with
// glowing throats. xs: engine x positions; zCap: stern plane.
export function engineBlock(bin, g, opts) {
    const { zCap, xs } = opts;
    const s = opts.s ?? 1.0, ys = opts.ys ?? 0;
    if (opts.skirt !== false) {
        const skirt = bevelPlate(opts.skirtW ?? 1.4 * s, opts.skirtH ?? 0.55 * s, 1.1 * s, 0.12 * s);
        skirt.rotateX(-Math.PI / 2);
        uvPatch(skirt, g, 0.4);
        bin.add('armor', skirt, { pos: [0, ys, zCap + 0.15 * s] });
        const hw = (opts.skirtW ?? 1.4 * s) * 0.43, hh = (opts.skirtH ?? 0.55 * s) * 0.84;
        strut(bin, 'trim', [-hw, ys + hh, zCap - 0.36 * s], [hw, ys + hh, zCap - 0.36 * s], 0.05 * s, g);
        strut(bin, 'trim', [-hw, ys - hh, zCap - 0.36 * s], [hw, ys - hh, zCap - 0.36 * s], 0.05 * s, g);
        // rib frames over the housing so the block reads armoured, not bare -
        // hugging the housing (never proud of the hull silhouette, no trailing
        // rails: an armoured block, not scaffolding)
        for (const rz of [0.05 * s, -0.22 * s]) {
            for (const sy of [1, -1]) {
                strut(bin, 'armor', [-hw * 0.99, ys + sy * hh * 0.99, zCap + rz], [hw * 0.99, ys + sy * hh * 0.99, zCap + rz], 0.07 * s, g);
            }
            for (const sx of [1, -1]) {
                strut(bin, 'armor', [sx * hw * 0.99, ys - hh * 0.97, zCap + rz], [sx * hw * 0.99, ys + hh * 0.97, zCap + rz], 0.07 * s, g);
            }
        }
        // radiator fins on the housing flanks (stern-quarter signature)
        for (const sx of [1, -1]) {
            for (const fz of [0.22 * s, -0.28 * s]) {
                const wall = new THREE.BoxGeometry(0.018, hh * 0.95, 0.34 * s);
                bin.add('radiator', wall, { pos: [sx * (hw * 0.99 + 0.03 * s), ys, zCap + fz], subPart: true });
            }
            strut(bin, 'trim', [sx * (hw * 0.99 + 0.03 * s), ys + hh * 0.6, zCap + 0.38 * s], [sx * (hw * 0.99 + 0.03 * s), ys + hh * 0.6, zCap - 0.32 * s], 0.03 * s, g);
        }
        // dark vent maw strip above the bells
        const vent = new THREE.BoxGeometry(hw * 1.2, 0.08 * s, 0.03);
        uvTransform(vent, 0.001, 0.001, 0.002, 0.002);
        bin.add('windows', vent, { pos: [0, ys + hh * 0.55, zCap - 0.415 * s], subPart: true });
    }
    for (const ex of xs) {
        const casing = new THREE.CylinderGeometry(0.2 * s, 0.22 * s, 0.5 * s, 18);
        casing.rotateX(Math.PI / 2);
        uvPatch(casing, g, 0.2);
        bin.add('mech', casing, { pos: [ex, ys, zCap - 0.55 * s] });
        for (const rz of [-0.48 * s, -0.62 * s, -0.76 * s]) {
            const ring = new THREE.CylinderGeometry(0.225 * s, 0.225 * s, 0.035 * s, 18);
            ring.rotateX(Math.PI / 2);
            uvPatch(ring, g, 0.08);
            bin.add('armor', ring, { pos: [ex, ys, zCap + rz], subPart: true });
        }
        const bellPts = [
            new THREE.Vector2(0.13 * s, 0), new THREE.Vector2(0.11 * s, 0.06 * s), new THREE.Vector2(0.13 * s, 0.14 * s),
            new THREE.Vector2(0.19 * s, 0.24 * s), new THREE.Vector2(0.27 * s, 0.32 * s), new THREE.Vector2(0.31 * s, 0.37 * s),
        ];
        const bell = new THREE.LatheGeometry(bellPts, 20);
        bell.rotateX(-Math.PI / 2);
        uvPatch(bell, g, 0.2);
        bin.add('mech', bell, { pos: [ex, ys, zCap - 0.82 * s], subPart: true });
        const innerPts = [
            new THREE.Vector2(0.1 * s, 0.02 * s), new THREE.Vector2(0.12 * s, 0.13 * s),
            new THREE.Vector2(0.18 * s, 0.23 * s), new THREE.Vector2(0.28 * s, 0.35 * s),
        ];
        const inner = new THREE.LatheGeometry(innerPts, 20);
        inner.rotateX(-Math.PI / 2);
        bin.add('engine_glow', inner, { pos: [ex, ys, zCap - 0.82 * s], subPart: true });
        const disc = new THREE.CircleGeometry(0.17 * s, 18);
        disc.rotateY(Math.PI);
        bin.add('engine_glow', disc, { pos: [ex, ys, zCap - 0.86 * s], subPart: true });
        // exhaust plume: saturated emissive cone trailing aft - the engine
        // glow is a signature, it must read at sheet scale from any angle.
        // UVs pinned to the bright centre of the radial glow texture.
        const plume = new THREE.ConeGeometry(0.17 * s, 1.0 * s, 14, 1, true);
        plume.rotateX(-Math.PI / 2);
        uvTransform(plume, 0.03, 0.03, 0.90, 0.485); // saturated ring of the glow gradient
        bin.add('engine_glow', plume, { pos: [ex, ys, zCap - 0.9 * s - 0.5 * s], subPart: true });
        const plumeCore = new THREE.ConeGeometry(0.09 * s, 0.6 * s, 10, 1, true);
        plumeCore.rotateX(-Math.PI / 2);
        uvTransform(plumeCore, 0.03, 0.03, 0.78, 0.485);
        bin.add('engine_glow', plumeCore, { pos: [ex, ys, zCap - 0.9 * s - 0.3 * s], subPart: true });
    }
}

// Podded engine nacelle (Privateer chunk): fat cylinder casing, intake ring,
// aft bell with saturated glow. dir is +Z-forward; nacelle exhausts at -Z end.
export function engineNacelle(bin, g, pos, len, r) {
    const casing = new THREE.CylinderGeometry(r, r * 1.1, len, 16);
    casing.rotateX(Math.PI / 2);
    uvPatch(casing, g, 0.25);
    bin.add('mech', casing, { pos });
    const nose = new THREE.SphereGeometry(r, 16, 9, 0, Math.PI * 2, 0, Math.PI / 2);
    nose.rotateX(Math.PI / 2);
    uvPatch(nose, g, 0.15);
    bin.add('armor', nose, { pos: [pos[0], pos[1], pos[2] + len / 2], subPart: true });
    for (const t of [-0.28, 0.05, 0.38]) {
        const band = new THREE.CylinderGeometry(r * 1.08, r * 1.08, 0.05, 16);
        band.rotateX(Math.PI / 2);
        uvPatch(band, g, 0.1);
        bin.add('trim', band, { pos: [pos[0], pos[1], pos[2] + t * len], subPart: true });
    }
    const bell = new THREE.CylinderGeometry(r * 0.85, r * 1.05, r * 0.9, 16, 1, true);
    bell.rotateX(Math.PI / 2);
    uvPatch(bell, g, 0.1);
    bin.add('mech', bell, { pos: [pos[0], pos[1], pos[2] - len / 2 - r * 0.4], subPart: true });
    const disc = new THREE.CircleGeometry(r * 0.8, 16);
    disc.rotateY(Math.PI);
    bin.add('engine_glow', disc, { pos: [pos[0], pos[1], pos[2] - len / 2 - r * 0.35], subPart: true });
    const inner = new THREE.CylinderGeometry(r * 0.65, r * 0.95, r * 0.7, 16, 1, true);
    inner.rotateX(Math.PI / 2);
    bin.add('engine_glow', inner, { pos: [pos[0], pos[1], pos[2] - len / 2 - r * 0.45], subPart: true });
    // trailing exhaust plume cone, UVs pinned to the bright glow centre
    const plume = new THREE.ConeGeometry(r * 0.55, r * 2.0, 14, 1, true);
    plume.rotateX(-Math.PI / 2);
    uvTransform(plume, 0.03, 0.03, 0.90, 0.485); // saturated ring of the glow gradient
    bin.add('engine_glow', plume, { pos: [pos[0], pos[1], pos[2] - len / 2 - r * 0.6 - r * 1.0], subPart: true });
}

// RCS thruster quad at pos.
export function rcsQuad(bin, g, pos, s = 1.0) {
    const [x, y, z] = pos;
    const block = new THREE.BoxGeometry(0.09 * s, 0.09 * s, 0.09 * s);
    uvPatch(block, g, 0.08);
    bin.add('mech', block, { pos });
    const dirs = [[Math.sign(x) || 1, 0, 0], [0, Math.sign(y) || 1, 0], [0, 0, 1], [0, 0, -1]];
    for (const d of dirs) {
        const cone = new THREE.ConeGeometry(0.032 * s, 0.06 * s, 8);
        const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(...d).normalize());
        uvPatch(cone, g, 0.05);
        bin.add('mech', cone, { quat: q, pos: [x + d[0] * 0.07 * s, y + d[1] * 0.07 * s, z + d[2] * 0.07 * s], subPart: true });
    }
}

// Open box truss running from za to zb: 4 corner rails + zig-zag bracing.
// hw/hh: half-width and half-height of the truss box, centred on (x, y).
export function trussBox(bin, g, za, zb, hw, hh, opts = {}) {
    const x = opts.x ?? 0, y = opts.y ?? 0;
    const rs = opts.railSize ?? 0.05;
    const corners = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]];
    for (const [cx, cy] of corners) {
        const rail = new THREE.BoxGeometry(rs, rs, Math.abs(za - zb));
        uvPatch(rail, g, 0.2);
        bin.add('mech', rail, { pos: [x + cx, y + cy, (za + zb) / 2] });
    }
    const step = opts.step ?? Math.max(0.3, hw * 1.2);
    let flip = 1;
    for (let z = Math.max(za, zb) - step / 2; z > Math.min(za, zb); z -= step, flip *= -1) {
        for (let c = 0; c < 4; c++) {
            const [ax, ay] = corners[c], [bx, by] = corners[(c + 1) % 4];
            tube(bin, 'mech', [x + ax, y + ay, z], [x + bx, y + by, z - flip * step * 0.5], 0.016, 5, g);
        }
        // ring frame
        for (let c = 0; c < 4; c++) {
            const [ax, ay] = corners[c], [bx, by] = corners[(c + 1) % 4];
            strut(bin, 'mech', [x + ax, y + ay, z], [x + bx, y + by, z], 0.022, g);
        }
    }
}

// One cargo container: bevelled body, rib bands, corner castings.
export function containerBlock(bin, g, pos, w, h, d, mat) {
    const body = bevelPlate(w, h, d, 0.03);
    uvPatch(body, g, 0.22);
    bin.add(mat || (g.chance(0.5) ? 'armor' : 'mech'), body, { pos: [pos[0], pos[1] - h / 2, pos[2]] });
    const nRib = Math.max(2, Math.floor(d / 0.3));
    for (let i = 0; i < nRib; i++) {
        const z = pos[2] - d / 2 + ((i + 0.5) * d) / nRib;
        const rib = new THREE.BoxGeometry(w * 1.03, h * 0.96, 0.03);
        uvPatch(rib, g, 0.1);
        bin.add(g.chance(0.25) ? 'trim' : 'mech', rib, { pos: [pos[0], pos[1], z], subPart: true });
    }
}

// Stacked container racks along a spine: rows x cols grid of containers
// repeated over [z0, z1] in bays, with rack frames between.
export function containerRacks(bin, g, z0, z1, rows, cols, cell, opts = {}) {
    const yC = opts.y ?? 0;
    const bayLen = cell.d + 0.14;
    const nBays = Math.max(1, Math.floor((z0 - z1) / bayLen));
    for (let b = 0; b < nBays; b++) {
        const z = z0 - bayLen * (b + 0.5);
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                if (g.chance(opts.gapChance ?? 0.08)) continue; // empty socket
                const x = (c - (cols - 1) / 2) * (cell.w + 0.06);
                const y = yC + (r - (rows - 1) / 2) * (cell.h + 0.06) + cell.h / 2;
                containerBlock(bin, g, [x, y, z], cell.w, cell.h, cell.d);
            }
        }
        // bay frame ring
        const hw = (cols * (cell.w + 0.06)) / 2 + 0.03, hh = (rows * (cell.h + 0.06)) / 2 + 0.03;
        const zf = z0 - bayLen * b;
        const ring = [[-hw, yC - hh], [hw, yC - hh], [hw, yC + hh], [-hw, yC + hh]];
        for (let c2 = 0; c2 < 4; c2++) {
            const [ax, ay] = ring[c2], [bx, by] = ring[(c2 + 1) % 4];
            strut(bin, 'armor', [ax, ay, zf], [bx, by, zf], 0.05, g);
        }
    }
}

// Fore command module for civilian hulls: stacked blocks, window band,
// antenna mast, docking collar at the bow.
export function commandModule(bin, g, pos, s = 1.0) {
    const [x, y, z] = pos;
    const add = (name, geo, p, sub = true) => { uvPatch(geo, g, 0.2); bin.add(name, geo, { pos: p, subPart: sub }); };
    add('armor', bevelPlate(0.8 * s, 0.55 * s, 0.9 * s, 0.08 * s), [x, y - 0.27 * s, z], false);
    add('armor', bevelPlate(0.55 * s, 0.3 * s, 0.6 * s, 0.05 * s), [x, y + 0.28 * s, z - 0.05 * s]);
    const win = new THREE.BoxGeometry(0.5 * s, 0.06 * s, 0.014);
    uvTransform(win, s, 0.045, g.range(0, 0.4), g.int(0, 15) / 16 + 0.012);
    bin.add('windows', win, { pos: [x, y + 0.1 * s, z + 0.46 * s], subPart: true });
    const win2 = new THREE.BoxGeometry(0.36 * s, 0.05 * s, 0.014);
    uvTransform(win2, s, 0.045, g.range(0, 0.4), g.int(0, 15) / 16 + 0.012);
    bin.add('windows', win2, { pos: [x, y + 0.36 * s, z + 0.27 * s], subPart: true });
    // docking collar on the nose
    const collar = new THREE.CylinderGeometry(0.14 * s, 0.16 * s, 0.1 * s, 12);
    collar.rotateX(Math.PI / 2);
    add('trim', collar, [x, y, z + 0.5 * s]);
    const hatch = new THREE.CylinderGeometry(0.09 * s, 0.09 * s, 0.04 * s, 12);
    hatch.rotateX(Math.PI / 2);
    add('mech', hatch, [x, y, z + 0.56 * s]);
    // mast
    const mast = new THREE.CylinderGeometry(0.015 * s, 0.02 * s, 0.5 * s, 6);
    add('mech', mast, [x + 0.2 * s, y + 0.68 * s, z - 0.2 * s]);
    add('mech', new THREE.SphereGeometry(0.03 * s, 6, 5), [x + 0.2 * s, y + 0.95 * s, z - 0.2 * s]);
}

// Industrial processing drum: ribbed body of revolution with longeron pipes.
export function drumBody(bin, g, zc, len, r, opts = {}) {
    const y = opts.y ?? 0;
    const drum = new THREE.CylinderGeometry(r, r, len, opts.seg ?? 20);
    drum.rotateX(Math.PI / 2);
    uvPatch(drum, g, 0.35);
    bin.add(opts.material || 'armor', drum, { pos: [opts.x ?? 0, y, zc] });
    const nRib = opts.ribs ?? Math.max(3, Math.floor(len / (r * 0.8)));
    for (let i = 0; i <= nRib; i++) {
        const z = zc - len / 2 + (i * len) / nRib;
        const rib = new THREE.CylinderGeometry(r * 1.05, r * 1.05, 0.06, opts.seg ?? 20);
        rib.rotateX(Math.PI / 2);
        uvPatch(rib, g, 0.1);
        bin.add(i % 3 === 0 ? 'trim' : 'mech', rib, { pos: [opts.x ?? 0, y, z], subPart: true });
    }
    // longeron pipes at 4 clock positions
    for (const a of [0.6, 2.2, 4.0, 5.5]) {
        const px = Math.cos(a) * r * 1.02, py = Math.sin(a) * r * 1.02;
        tube(bin, 'mech', [(opts.x ?? 0) + px, y + py, zc - len / 2 + 0.1], [(opts.x ?? 0) + px, y + py, zc + len / 2 - 0.1], 0.028, 7, g);
    }
    // end caps
    for (const ez of [zc - len / 2, zc + len / 2]) {
        const cap = new THREE.CylinderGeometry(r * 0.85, r * 0.85, 0.1, opts.seg ?? 20);
        cap.rotateX(Math.PI / 2);
        uvPatch(cap, g, 0.15);
        bin.add('armor', cap, { pos: [opts.x ?? 0, y, ez], subPart: true });
    }
}

// Mining drill boom: truss arm from `from` toward `to`, ending in a drill
// head (cone cluster + collar) plus hydraulic ram.
export function drillBoom(bin, g, from, to, s = 1.0) {
    const a = new THREE.Vector3(...from), b = new THREE.Vector3(...to);
    const dir = b.clone().sub(a).normalize();
    const len = a.distanceTo(b);
    // twin rails with cross ties
    const up = Math.abs(dir.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    const sideV = new THREE.Vector3().crossVectors(dir, up).normalize().multiplyScalar(0.07 * s);
    for (const sgn of [1, -1]) {
        strut(bin, 'mech',
            [a.x + sideV.x * sgn, a.y + sideV.y * sgn, a.z + sideV.z * sgn],
            [b.x + sideV.x * sgn, b.y + sideV.y * sgn, b.z + sideV.z * sgn], 0.05 * s, g);
    }
    const nTie = Math.max(2, Math.floor(len / (0.25 * s)));
    for (let i = 1; i < nTie; i++) {
        const t = i / nTie;
        const p = a.clone().lerp(b, t);
        const sgn = i % 2 === 0 ? 1 : -1;
        tube(bin, 'mech', [p.x + sideV.x, p.y + sideV.y, p.z + sideV.z],
            [p.x - sideV.x, p.y - sideV.y, p.z - sideV.z], 0.016 * s, 5, g);
        if (i % 3 === 0) {
            tube(bin, 'mech', [p.x + sideV.x * sgn, p.y + sideV.y * sgn, p.z + sideV.z * sgn],
                [p.x - sideV.x * sgn + dir.x * 0.2, p.y - sideV.y * sgn + dir.y * 0.2, p.z - sideV.z * sgn + dir.z * 0.2], 0.014 * s, 5, g);
        }
    }
    // drill head
    const collar = new THREE.CylinderGeometry(0.14 * s, 0.18 * s, 0.16 * s, 12);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    uvPatch(collar, g, 0.12);
    bin.add('trim', collar, { quat: q.clone(), pos: [b.x, b.y, b.z] });
    const drill = new THREE.ConeGeometry(0.12 * s, 0.34 * s, 10);
    uvPatch(drill, g, 0.12);
    bin.add('mech', drill, { quat: q.clone(), pos: [b.x + dir.x * 0.24 * s, b.y + dir.y * 0.24 * s, b.z + dir.z * 0.24 * s], subPart: true });
    for (let i = 0; i < 3; i++) {
        const bit = new THREE.ConeGeometry(0.045 * s, 0.16 * s, 7);
        const off = new THREE.Vector3().crossVectors(dir, up).multiplyScalar(0.1 * s * Math.cos((i * Math.PI * 2) / 3));
        const off2 = up.clone().multiplyScalar(0.1 * s * Math.sin((i * Math.PI * 2) / 3));
        uvPatch(bit, g, 0.06);
        bin.add('mech', bit, { quat: q.clone(), pos: [b.x + off.x + off2.x + dir.x * 0.3 * s, b.y + off.y + off2.y + dir.y * 0.3 * s, b.z + off.z + off2.z + dir.z * 0.3 * s], subPart: true });
    }
}

// Palletised ordnance cluster (class-identity round: "still make bombers
// look like bombers" - the hung ordnance IS the identity). Frame plate
// carrying n x m FAT payload shapes that read at sheet scale: kind 'bomb' is
// a heavy blunt-nosed store with a hazard nose band and cruciform tail fins;
// kind 'torp' is a long torpedo with a glowing drive tail. Every store hangs
// visibly proud of its rack.
export function bombPallet(bin, g, basisM, n, m, s = 1.0, opts = {}) {
    const kind = opts.kind || 'bomb';
    const px = kind === 'torp' ? 0.2 * s : 0.24 * s;
    const pz = kind === 'torp' ? 0.52 * s : 0.4 * s;
    const w = n * px + 0.06 * s, d = m * pz + 0.06 * s;
    const plate = bevelPlate(w, 0.04 * s, d, 0.015 * s);
    uvPatch(plate, g, 0.15);
    bin.add('mech', plate, { basis: basisM.clone() });
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < m; j++) {
            const x = (i - (n - 1) / 2) * px;
            const z = (j - (m - 1) / 2) * pz;
            const at = (name, geo, lx, ly, lz, sub = true) => {
                uvPatch(geo, g, 0.08);
                const mm = basisM.clone().multiply(new THREE.Matrix4().makeTranslation(lx, ly, lz));
                bin.add(name, geo, { basis: mm, subPart: sub });
            };
            // drop shackle strut from plate to store
            at('mech', new THREE.BoxGeometry(0.03 * s, 0.08 * s, 0.06 * s), x, -0.04 * s, z);
            if (kind === 'torp') {
                const body = new THREE.CapsuleGeometry(0.055 * s, 0.34 * s, 4, 10);
                body.rotateX(Math.PI / 2);
                at('armor', body, x, -0.14 * s, z, false);
                const band = new THREE.CylinderGeometry(0.06 * s, 0.06 * s, 0.03 * s, 10);
                band.rotateX(Math.PI / 2);
                at('trim', band, x, -0.14 * s, z + 0.1 * s);
                for (const a of [0, Math.PI / 2]) {
                    const fin = new THREE.BoxGeometry(0.16 * s, 0.012 * s, 0.07 * s);
                    fin.rotateZ(a);
                    at('mech', fin, x, -0.14 * s, z - 0.2 * s);
                }
                const tail = new THREE.CircleGeometry(0.04 * s, 10);
                tail.rotateY(Math.PI);
                uvTransform(tail, 0.03, 0.03, 0.9, 0.485);
                const mt = basisM.clone().multiply(new THREE.Matrix4().makeTranslation(x, -0.14 * s, z - 0.26 * s));
                bin.add('engine_glow', tail, { basis: mt, subPart: true });
            } else {
                const body = new THREE.CapsuleGeometry(0.085 * s, 0.2 * s, 4, 12);
                body.rotateX(Math.PI / 2);
                at('armor', body, x, -0.15 * s, z, false);
                const nose = new THREE.CylinderGeometry(0.087 * s, 0.06 * s, 0.06 * s, 12);
                nose.rotateX(-Math.PI / 2);
                at('trim', nose, x, -0.15 * s, z + 0.16 * s);
                for (const a of [0, Math.PI / 2]) {
                    const fin = new THREE.BoxGeometry(0.22 * s, 0.015 * s, 0.09 * s);
                    fin.rotateZ(a);
                    at('mech', fin, x, -0.15 * s, z - 0.16 * s);
                }
                const ring = new THREE.CylinderGeometry(0.1 * s, 0.1 * s, 0.02 * s, 10);
                ring.rotateX(Math.PI / 2);
                at('mech', ring, x, -0.15 * s, z - 0.19 * s);
            }
        }
    }
}

// Bucket-wheel excavator head (class-identity round: miners are purpose
// built). A big toothed wheel on an axle yoke, plane vertical and facing
// forward - the working tool that reads at sheet scale. r is wheel radius,
// w the rim width; pos is the wheel centre.
export function bucketWheel(bin, g, pos, r, w = 0.3) {
    const [x, y, z] = pos;
    const rim = new THREE.CylinderGeometry(r, r, w, 16);
    rim.rotateZ(Math.PI / 2);
    uvPatch(rim, g, 0.25);
    bin.add('mech', rim, { pos });
    const hub = new THREE.CylinderGeometry(r * 0.32, r * 0.32, w * 1.4, 12);
    hub.rotateZ(Math.PI / 2);
    uvPatch(hub, g, 0.1);
    bin.add('armor', hub, { pos, subPart: true });
    // buckets around the rim: open scoop boxes with a hazard-trim lip
    const nB = 9;
    for (let i = 0; i < nB; i++) {
        const a = (i / nB) * Math.PI * 2;
        const bx = x, by = y + Math.cos(a) * r, bz = z + Math.sin(a) * r;
        const bucket = new THREE.BoxGeometry(w * 1.15, r * 0.3, r * 0.34);
        uvPatch(bucket, g, 0.1);
        const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -a);
        bin.add('armor', bucket, { quat: q, pos: [bx, by + Math.cos(a) * r * 0.12, bz + Math.sin(a) * r * 0.12], subPart: true });
        const lip = new THREE.BoxGeometry(w * 1.18, r * 0.07, r * 0.1);
        bin.add('trim', lip, { quat: q.clone(), pos: [bx, by + Math.cos(a) * r * 0.26, bz + Math.sin(a) * r * 0.26], subPart: true });
    }
    // axle stubs for the yoke
    for (const side of [1, -1]) {
        const stub = new THREE.CylinderGeometry(r * 0.12, r * 0.12, w * 0.8, 10);
        stub.rotateZ(Math.PI / 2);
        uvPatch(stub, g, 0.06);
        bin.add('mech', stub, { pos: [x + side * w * 0.9, y, z], subPart: true });
    }
}

// Ore intake maw: a dark rectangular mouth framed with hazard trim and
// grinder teeth, cut into a forward face at pos (facing +Z).
export function intakeMaw(bin, g, pos, w, h) {
    const [x, y, z] = pos;
    const mouth = new THREE.BoxGeometry(w, h, 0.05);
    uvTransform(mouth, 0.001, 0.001, 0.002, 0.002);
    bin.add('windows', mouth, { pos });
    strut(bin, 'trim', [x - w * 0.56, y + h * 0.58, z], [x + w * 0.56, y + h * 0.58, z], h * 0.14, g);
    strut(bin, 'trim', [x - w * 0.56, y - h * 0.58, z], [x + w * 0.56, y - h * 0.58, z], h * 0.14, g);
    strut(bin, 'trim', [x - w * 0.56, y - h * 0.58, z], [x - w * 0.56, y + h * 0.58, z], h * 0.14, g);
    strut(bin, 'trim', [x + w * 0.56, y - h * 0.58, z], [x + w * 0.56, y + h * 0.58, z], h * 0.14, g);
    const nT = Math.max(3, Math.floor(w / (h * 0.35)));
    for (let i = 0; i < nT; i++) {
        const tx = x - w / 2 + ((i + 0.5) * w) / nT;
        const tooth = new THREE.ConeGeometry(h * 0.1, h * 0.32, 5);
        tooth.rotateX(Math.PI);
        uvPatch(tooth, g, 0.05);
        bin.add('mech', tooth, { pos: [tx, y + h * 0.36, z + 0.02], subPart: true });
    }
}

// Faceted cockpit canopy (windows material) on a raised armour coaming.
export function canopy(bin, g, pos, s = 1.0) {
    const coaming = bevelPlate(0.34 * s, 0.1 * s, 0.5 * s, 0.04 * s);
    uvPatch(coaming, g, 0.15);
    bin.add('armor', coaming, { pos: [pos[0], pos[1], pos[2]] });
    const glass = new THREE.SphereGeometry(0.16 * s, 8, 5, 0, Math.PI * 2, 0, Math.PI / 2);
    glass.scale(1, 0.75, 1.5);
    uvTransform(glass, 0.3, 0.15, 0.05, 3 / 16 + 0.012);
    bin.add('windows', glass, { pos: [pos[0], pos[1] + 0.09 * s, pos[2]] });
    strut(bin, 'trim', [pos[0] - 0.15 * s, pos[1] + 0.1 * s, pos[2] + 0.2 * s], [pos[0] + 0.15 * s, pos[1] + 0.1 * s, pos[2] + 0.2 * s], 0.02 * s, g);
}

// External weapon hardpoint with a visible gun model, mounted on a pylon.
export function gunHardpoint(bin, g, pos, s = 1.0, down = false) {
    const dy = down ? -1 : 1;
    const pylon = new THREE.BoxGeometry(0.05 * s, 0.14 * s, 0.2 * s);
    uvPatch(pylon, g, 0.1);
    bin.add('armor', pylon, { pos: [pos[0], pos[1] + dy * 0.07 * s, pos[2]] });
    const body = new THREE.BoxGeometry(0.09 * s, 0.09 * s, 0.4 * s);
    uvPatch(body, g, 0.1);
    bin.add('mech', body, { pos: [pos[0], pos[1] + dy * 0.18 * s, pos[2]], subPart: true });
    const barrel = new THREE.CylinderGeometry(0.02 * s, 0.024 * s, 0.5 * s, 8);
    barrel.rotateX(Math.PI / 2);
    uvPatch(barrel, g, 0.06);
    bin.add('mech', barrel, { pos: [pos[0], pos[1] + dy * 0.18 * s, pos[2] + 0.4 * s], subPart: true });
    const muzzle = new THREE.CylinderGeometry(0.032 * s, 0.032 * s, 0.06 * s, 8);
    muzzle.rotateX(Math.PI / 2);
    uvPatch(muzzle, g, 0.05);
    bin.add('trim', muzzle, { pos: [pos[0], pos[1] + dy * 0.18 * s, pos[2] + 0.63 * s], subPart: true });
}

// Glowing hangar maw cut into a flank: dark mouth, saturated inner strip,
// trim frame (FreeSpace capital signature).
export function hangarMaw(bin, g, pos, w, h, side) {
    const mouth = new THREE.BoxGeometry(0.04, h, w);
    uvTransform(mouth, 0.001, 0.001, 0.002, 0.002);
    bin.add('windows', mouth, { pos });
    const glowStrip = new THREE.BoxGeometry(0.05, h * 0.18, w * 0.92);
    uvTransform(glowStrip, 0.12, 0.12, 0.44, 0.44);
    bin.add('engine_glow', glowStrip, { pos: [pos[0] - side * 0.006, pos[1] - h * 0.32, pos[2]], subPart: true });
    for (const dy of [h * 0.58, -h * 0.58]) {
        strut(bin, 'trim', [pos[0] + side * 0.03, pos[1] + dy, pos[2] - w * 0.55], [pos[0] + side * 0.03, pos[1] + dy, pos[2] + w * 0.55], 0.045, g);
    }
    for (const dz of [w * 0.55, -w * 0.55]) {
        strut(bin, 'trim', [pos[0] + side * 0.03, pos[1] - h * 0.58, pos[2] + dz], [pos[0] + side * 0.03, pos[1] + h * 0.58, pos[2] + dz], 0.045, g);
    }
}

// Sensor dish on a yoke mast.
export function dishAntenna(bin, g, pos, r, s = 1.0) {
    const mast = new THREE.CylinderGeometry(0.02 * s, 0.028 * s, 0.3 * s, 7);
    uvPatch(mast, g, 0.08);
    bin.add('mech', mast, { pos: [pos[0], pos[1] + 0.15 * s, pos[2]] });
    const dish = new THREE.SphereGeometry(r, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2.6);
    dish.scale(1, 0.42, 1);
    dish.rotateX(-Math.PI / 2.4);
    uvPatch(dish, g, 0.2);
    bin.add('radiator', dish, { pos: [pos[0], pos[1] + 0.36 * s, pos[2]], subPart: true });
    const feed = new THREE.CylinderGeometry(0.008 * s, 0.008 * s, r * 0.9, 5);
    feed.rotateX(Math.PI / 2.4);
    uvPatch(feed, g, 0.04);
    bin.add('mech', feed, { pos: [pos[0], pos[1] + 0.42 * s, pos[2] + r * 0.3], subPart: true });
}

// Ceramic hab dome with lit portholes ring.
export function habDome(bin, g, pos, r) {
    const dome = new THREE.SphereGeometry(r, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2);
    uvPatch(dome, g, 0.25);
    bin.add('armor', dome, { pos });
    const ring = new THREE.CylinderGeometry(r * 1.01, r * 1.03, r * 0.12, 18);
    uvPatch(ring, g, 0.1);
    bin.add('trim', ring, { pos: [pos[0], pos[1] + r * 0.1, pos[2]], subPart: true });
    const win = new THREE.CylinderGeometry(r * 1.015, r * 1.015, r * 0.08, 18, 1, true);
    uvTransform(win, 2.0, 0.045, 0.1, 6 / 16 + 0.012);
    bin.add('windows', win, { pos: [pos[0], pos[1] + r * 0.32, pos[2]], subPart: true });
}

// Floodlight mast for industrial hulls.
export function floodMast(bin, g, pos, h, s = 1.0) {
    const mast = new THREE.CylinderGeometry(0.02 * s, 0.03 * s, h, 6);
    uvPatch(mast, g, 0.08);
    bin.add('mech', mast, { pos: [pos[0], pos[1] + h / 2, pos[2]] });
    const bar = new THREE.BoxGeometry(0.22 * s, 0.03 * s, 0.04 * s);
    uvPatch(bar, g, 0.05);
    bin.add('mech', bar, { pos: [pos[0], pos[1] + h, pos[2]], subPart: true });
    for (const dx of [-0.08 * s, 0, 0.08 * s]) {
        const lamp = new THREE.BoxGeometry(0.05 * s, 0.04 * s, 0.03 * s);
        uvTransform(lamp, 0.06, 0.04, 0.3, 9 / 16 + 0.012);
        bin.add('windows', lamp, { pos: [pos[0] + dx, pos[1] + h - 0.04 * s, pos[2] + 0.03 * s], subPart: true });
    }
}

// Standard 4-zone greeble scatter over a lofted hull frame.
export function greebleZones(bin, g, frame, feat, budget, opts = {}) {
    const { W, H, zBow, zStern, deckYAt } = frame;
    const engX = opts.engX || [];
    const turretZ = opts.turretZ || [];
    const zCap = opts.zCap ?? zStern;
    const deckSampler = (r) => {
        const z = r.range(0.315 * zStern, 0.66 * zBow);
        const side = r.sign();
        const x = side * r.range(0.22, 0.52) * W(z);
        for (const tz of turretZ) if (Math.abs(z - tz) < 0.55 && Math.abs(x) < 0.45) return null;
        if (feat.vls && z > feat.vls.z1 && z < feat.vls.z0 && Math.abs(x) < (feat.vls.cols / 2) * 0.17 + 0.12) return null;
        return { p: [x, deckYAt(z, x) - 0.005, z], n: [0, 1, 0], t: [0, 0, 1], s: 0.85 };
    };
    const chamferSampler = (r) => {
        const z = r.range(0.74 * zStern, 0.84 * zBow);
        const side = r.sign();
        const w = W(z), h = H(z);
        if (w < 0.2) return null;
        const t = r.range(0.2, 0.8);
        const px = (0.55 + 0.45 * t) * w, py = (0.94 - 0.52 * t) * h;
        const n = [side * 0.5255, 0.4547, 0];
        return { p: [side * px, py, z], n, t: [0, 0, 1], s: 0.7 };
    };
    const ventralSampler = (r) => {
        const z = r.range(0.61 * zStern, 0.56 * zBow);
        if (feat.truss && z < feat.truss.z0 + 0.15 && z > feat.truss.z1 - 0.15) return null;
        const side = r.sign();
        const x = side * r.range(0.02, 0.2) * W(z);
        return { p: [x, -H(z) * 0.99 + 0.005, z], n: [0, -1, 0], t: [0, 0, 1], s: 0.75 };
    };
    const wS = W(zStern) || 0.4, hS = H(zStern) || 0.4;
    const sternSampler = (r) => {
        const x = r.range(-0.95 * wS, 0.95 * wS), y = r.range(-0.75 * hS, 0.75 * hS);
        if ((x * x) / (wS * wS) + (y * y) / (0.85 * hS * 0.85 * hS) > 1) return null;
        for (const ex of engX) if (Math.abs(x - ex) < 0.28 && Math.abs(y) < 0.28) return null;
        return { p: [x, y, zCap - 0.09], n: [0, 0, -1], t: [0, 1, 0], s: 0.6 };
    };
    greebleField(bin, g, Math.floor(budget * 0.36), deckSampler);
    greebleField(bin, g, Math.floor(budget * 0.34), chamferSampler);
    greebleField(bin, g, Math.floor(budget * 0.2), ventralSampler);
    greebleField(bin, g, Math.floor(budget * 0.1), sternSampler);
}
