// Unit test: the ships3d design-record compiler is deterministic for EVERY
// hull record. Same record must produce the same vertex counts (total and
// per material) and the same material set on repeated compiles. Runs in node
// against the vendored three.js module build, textures disabled (no DOM).
//
// Run: node tools/test_ships3d_determinism.mjs [hull ...]

import assert from 'node:assert/strict';
import { compileShip } from '../frontend/js/ships3d/compiler.js';
import { SHIP_RECORDS, HULL_NAMES } from '../frontend/js/ships3d/records.js';

// Minimum detail bars per hull class. Capitals must carry serious mass;
// even the smallest utility hull must not regress to a ten-box silhouette.
// Rebuild bar: capitals compile at 150k+ triangles in the browser (donor
// parts add a few thousand on top of these node-side procedural counts).
const MIN_TRIANGLES = {
    dreadnought: 170000, battleship: 155000, 'battle-cruiser': 145000,
    cruiser: 130000, destroyer: 85000, frigate: 50000,
    'assault-transport': 70000, nubian: 45000, 'ultra-miner': 55000,
};
const DEFAULT_MIN_TRIANGLES = 12000;

const filtered = process.argv.slice(2).length > 0;
const hulls = filtered ? process.argv.slice(2) : HULL_NAMES;
if (!filtered) assert.ok(hulls.length >= 30, `expected the full hull roster (30+), got ${hulls.length}`);

let totalTris = 0;
for (const name of hulls) {
    const record = SHIP_RECORDS[name];
    assert.ok(record, `unknown ship record: ${name}`);
    const a = await compileShip(record, { textures: false });
    const b = await compileShip(record, { textures: false });

    assert.deepEqual(a.stats.materials, b.stats.materials, `${name}: material set differs between compiles`);
    assert.equal(a.stats.vertices, b.stats.vertices, `${name}: vertex count differs between compiles`);
    assert.equal(a.stats.triangles, b.stats.triangles, `${name}: triangle count differs between compiles`);
    assert.deepEqual(a.stats.perMaterial, b.stats.perMaterial, `${name}: per-material vertex counts differ`);
    assert.equal(a.stats.components, b.stats.components, `${name}: component count differs`);

    const minTris = MIN_TRIANGLES[name] ?? DEFAULT_MIN_TRIANGLES;
    assert.ok(a.stats.triangles >= minTris,
        `${name}: must carry real detail (>= ${minTris} triangles), got ${a.stats.triangles}`);
    assert.ok(a.stats.materials.length >= 5,
        `${name}: expected at least 5 materials, got ${a.stats.materials.join(', ')}`);
    assert.ok(a.stats.components > 50,
        `${name}: expected > 50 placed components, got ${a.stats.components}`);

    totalTris += a.stats.triangles;
    console.log(`PASS ${name.padEnd(22)} ${String(a.stats.triangles).padStart(7)} tris  ` +
        `${String(a.stats.vertices).padStart(8)} verts  ${String(a.stats.components).padStart(5)} components  ` +
        `[${a.stats.materials.join(', ')}]`);
}

console.log(`PASS ships3d determinism: ${hulls.length} hulls, ${totalTris.toLocaleString()} triangles total`);
