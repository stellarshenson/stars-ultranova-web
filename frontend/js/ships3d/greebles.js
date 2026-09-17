// Greeble catalogue - the small mechanical clutter that gives a hull its
// density: pipe runs, vents, antenna clusters, sensor domes, conduits,
// tanks and box stacks. Each builder works in a local frame with +Y as the
// outward surface normal and sits on y=0; the field placer orients it onto
// the hull with a surface basis.

import * as THREE from '../../vendor/three/build/three.module.js';
import { uvPatch, surfaceBasis } from './geometry.js';

function addLocal(bin, name, geo, basis, local, rng, sub) {
    const m = new THREE.Matrix4().makeTranslation(local[0], local[1], local[2]);
    const full = basis.clone().multiply(m);
    uvPatch(geo, rng, 0.12);
    bin.add(name, geo, { basis: full, subPart: sub });
}

const CATALOGUE = [
    function pipeRun(bin, rng, basis, s) {
        const n = rng.int(2, 4);
        const r = rng.range(0.018, 0.034) * s;
        let x = -rng.range(0.05, 0.12) * s, z = rng.range(-0.06, 0.06) * s;
        for (let i = 0; i < n; i++) {
            const len = rng.range(0.08, 0.22) * s;
            const horiz = i % 2 === 0;
            const geo = new THREE.CylinderGeometry(r, r, len, 8);
            if (horiz) {
                geo.rotateZ(Math.PI / 2);
                addLocal(bin, 'mech', geo, basis, [x + len / 2, r, z], rng, i > 0);
                x += len;
            } else {
                geo.rotateX(Math.PI / 2);
                addLocal(bin, 'mech', geo, basis, [x, r, z + len / 2], rng, true);
                z += len;
            }
            const joint = new THREE.SphereGeometry(r * 1.25, 8, 6);
            addLocal(bin, 'mech', joint, basis, [x, r, z], rng, true);
        }
    },
    function ventBox(bin, rng, basis, s) {
        const w = rng.range(0.1, 0.18) * s, d = rng.range(0.08, 0.14) * s, h = rng.range(0.03, 0.06) * s;
        addLocal(bin, 'mech', new THREE.BoxGeometry(w, h, d), basis, [0, h / 2, 0], rng, false);
        const slats = 3;
        for (let i = 0; i < slats; i++) {
            const g = new THREE.BoxGeometry(w * 0.85, h * 0.35, d * 0.16);
            addLocal(bin, 'armor', g, basis, [0, h * 1.05, -d * 0.3 + (i * d * 0.3)], rng, true);
        }
    },
    function antenna(bin, rng, basis, s) {
        const h = rng.range(0.22, 0.5) * s;
        const g = new THREE.CylinderGeometry(0.008 * s, 0.012 * s, h, 6);
        addLocal(bin, 'mech', g, basis, [0, h / 2, 0], rng, false);
        addLocal(bin, 'mech', new THREE.SphereGeometry(0.016 * s, 6, 5), basis, [0, h, 0], rng, true);
        if (rng.chance(0.5)) {
            const bar = new THREE.CylinderGeometry(0.006 * s, 0.006 * s, 0.1 * s, 5);
            bar.rotateZ(Math.PI / 2);
            addLocal(bin, 'mech', bar, basis, [0, h * 0.7, 0], rng, true);
        }
    },
    function sensorDome(bin, rng, basis, s) {
        const r = rng.range(0.05, 0.11) * s;
        const base = new THREE.CylinderGeometry(r * 1.15, r * 1.25, r * 0.35, 12);
        addLocal(bin, 'armor', base, basis, [0, r * 0.17, 0], rng, false);
        const dome = new THREE.SphereGeometry(r, 12, 7, 0, Math.PI * 2, 0, Math.PI / 2);
        addLocal(bin, 'mech', dome, basis, [0, r * 0.3, 0], rng, true);
    },
    function boxCluster(bin, rng, basis, s) {
        const n = rng.int(2, 4);
        let bx = 0;
        for (let i = 0; i < n; i++) {
            const w = rng.range(0.06, 0.16) * s, h = rng.range(0.04, 0.14) * s, d = rng.range(0.06, 0.16) * s;
            addLocal(bin, rng.chance(0.7) ? 'mech' : 'armor', new THREE.BoxGeometry(w, h, d), basis,
                [bx, h / 2, rng.range(-0.04, 0.04) * s], rng, i > 0);
            bx += w * rng.range(0.6, 1.0);
        }
    },
    function tankSmall(bin, rng, basis, s) {
        const r = rng.range(0.035, 0.065) * s, len = rng.range(0.12, 0.24) * s;
        const g = new THREE.CapsuleGeometry(r, len, 4, 10);
        g.rotateZ(Math.PI / 2);
        addLocal(bin, 'mech', g, basis, [0, r * 1.1, 0], rng, false);
        for (const dx of [-len * 0.3, len * 0.3]) {
            const band = new THREE.CylinderGeometry(r * 1.08, r * 1.08, 0.015 * s, 10);
            band.rotateZ(Math.PI / 2);
            addLocal(bin, 'armor', band, basis, [dx, r * 1.1, 0], rng, true);
        }
    },
    function hatch(bin, rng, basis, s) {
        const w = rng.range(0.08, 0.16) * s;
        const g = new THREE.BoxGeometry(w, 0.02 * s, w * rng.range(0.8, 1.2));
        addLocal(bin, rng.chance(0.3) ? 'trim' : 'armor', g, basis, [0, 0.01 * s, 0], rng, false);
    },
    function conduit(bin, rng, basis, s) {
        const len = rng.range(0.25, 0.6) * s;
        const g = new THREE.BoxGeometry(len, 0.03 * s, 0.05 * s);
        addLocal(bin, 'mech', g, basis, [0, 0.015 * s, 0], rng, false);
        const n = Math.floor(len / (0.1 * s));
        for (let i = 0; i < n; i++) {
            const clamp = new THREE.BoxGeometry(0.02 * s, 0.045 * s, 0.07 * s);
            addLocal(bin, 'armor', clamp, basis, [-len / 2 + (i + 0.5) * (len / n), 0.02 * s, 0], rng, true);
        }
    },
];

// Scatter `count` greebles over a zone. The zone sampler returns
// {p: [x,y,z], n: [nx,ny,nz], t: [tx,ty,tz] | null, s: scale} or null to skip.
export function greebleField(bin, rng, count, sampler) {
    for (let i = 0; i < count; i++) {
        const spot = sampler(rng);
        if (!spot) continue;
        const basis = surfaceBasis(spot.p, spot.n, spot.t || null);
        const builder = CATALOGUE[rng.int(0, CATALOGUE.length - 1)];
        builder(bin, rng, basis, spot.s || 1.0);
    }
}
