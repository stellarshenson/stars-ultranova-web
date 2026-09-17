// Donor kitbash library loader - browser-side only (the compile and gallery
// pages import it; the node determinism tests never do). Loads the clean-
// licensed CC0 kitbash parts recorded in assets/ships/LICENSES.md, flattens
// each donor glb into one BufferGeometry and normalizes it to a placement
// frame: centred in x/z, resting on y=0, max dimension 1. Family builders
// place them via donorPart() with our own material families - the donor is a
// geometry seed, never a shipped look.

import * as THREE from '../../vendor/three/build/three.module.js';
import { GLTFLoader } from '../../vendor/three/examples/jsm/loaders/GLTFLoader.js';
import { mergeGeometries } from '../../vendor/three/examples/jsm/utils/BufferGeometryUtils.js';

const KENNEY = '/assets/ships/donors/kenney-space-kit';

// Part name -> donor file. All Kenney Space Kit (CC0 1.0, kenney.nl).
export const DONOR_FILES = {
    turret_single: `${KENNEY}/turret_single.glb`,
    turret_double: `${KENNEY}/turret_double.glb`,
    satelliteDish_detailed: `${KENNEY}/satelliteDish_detailed.glb`,
    craft_cargoA: `${KENNEY}/craft_cargoA.glb`,
    craft_cargoB: `${KENNEY}/craft_cargoB.glb`,
    barrels: `${KENNEY}/barrels.glb`,
    barrels_rail: `${KENNEY}/barrels_rail.glb`,
    pipe_straight: `${KENNEY}/pipe_straight.glb`,
    pipe_cross: `${KENNEY}/pipe_cross.glb`,
    rocket_fuelA: `${KENNEY}/rocket_fuelA.glb`,
    rocket_fuelB: `${KENNEY}/rocket_fuelB.glb`,
    rocket_sidesA: `${KENNEY}/rocket_sidesA.glb`,
    rocket_sidesB: `${KENNEY}/rocket_sidesB.glb`,
    machine_generator: `${KENNEY}/machine_generator.glb`,
    machine_generatorLarge: `${KENNEY}/machine_generatorLarge.glb`,
    machine_barrel: `${KENNEY}/machine_barrel.glb`,
    supports_low: `${KENNEY}/supports_low.glb`,
    structure_detailed: `${KENNEY}/structure_detailed.glb`,
};

function flatten(gltf) {
    const geos = [];
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        let geo = o.geometry.clone();
        geo = geo.index ? geo.toNonIndexed() : geo;
        geo.applyMatrix4(o.matrixWorld);
        // keep only the attributes our material pipeline uses
        const keep = new THREE.BufferGeometry();
        keep.setAttribute('position', geo.attributes.position);
        if (geo.attributes.normal) keep.setAttribute('normal', geo.attributes.normal);
        const n = geo.attributes.position.count;
        keep.setAttribute('uv', geo.attributes.uv
            ? geo.attributes.uv
            : new THREE.BufferAttribute(new Float32Array(n * 2), 2));
        if (!geo.attributes.normal) keep.computeVertexNormals();
        geos.push(keep);
    });
    const merged = geos.length === 1 ? geos[0] : mergeGeometries(geos, false);
    // normalize: centre x/z, floor at y=0, max dimension 1
    merged.computeBoundingBox();
    const bb = merged.boundingBox;
    const size = new THREE.Vector3();
    bb.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    merged.translate(-(bb.min.x + bb.max.x) / 2, -bb.min.y, -(bb.min.z + bb.max.z) / 2);
    merged.scale(1 / maxDim, 1 / maxDim, 1 / maxDim);
    return merged;
}

// Load every donor part; returns Map(name -> BufferGeometry).
export async function loadDonorLibrary() {
    const loader = new GLTFLoader();
    const lib = new Map();
    for (const [name, url] of Object.entries(DONOR_FILES)) {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`donor fetch ${url} -> ${resp.status}`);
        const buf = await resp.arrayBuffer();
        const gltf = await new Promise((resolve, reject) => loader.parse(buf, url, resolve, reject));
        lib.set(name, flatten(gltf));
    }
    return lib;
}
