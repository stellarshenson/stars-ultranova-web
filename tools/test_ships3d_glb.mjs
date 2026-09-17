// Unit test: persisted glb files exist and are structurally valid binary
// glTF 2.0 - magic, version, JSON chunk with meshes, materials and embedded
// images. Run after the compile page has saved assets/ships/<hull>.glb.
//
// Run: node tools/test_ships3d_glb.mjs [hull ...]

import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'assets', 'ships');
const hulls = process.argv.slice(2).length
    ? process.argv.slice(2)
    : readdirSync(dir).filter((f) => f.endsWith('.glb')).map((f) => f.replace(/\.glb$/, ''));

assert.ok(hulls.length > 0, 'no .glb files found in assets/ships/');

for (const hull of hulls) {
    const path = join(dir, `${hull}.glb`);
    const buf = readFileSync(path);
    assert.ok(buf.length > 12, `${hull}.glb too small`);
    assert.equal(buf.readUInt32LE(0), 0x46546c67, `${hull}.glb bad magic (not glTF)`);
    assert.equal(buf.readUInt32LE(4), 2, `${hull}.glb not glTF version 2`);
    assert.equal(buf.readUInt32LE(8), buf.length, `${hull}.glb declared length mismatch`);
    const jsonLen = buf.readUInt32LE(12);
    assert.equal(buf.readUInt32LE(16), 0x4e4f534a, `${hull}.glb first chunk is not JSON`);
    const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString('utf8'));
    assert.ok(json.meshes && json.meshes.length > 0, `${hull}.glb has no meshes`);
    assert.ok(json.materials && json.materials.length >= 5, `${hull}.glb has fewer than 5 materials`);
    assert.ok(json.images && json.images.length > 0, `${hull}.glb has no embedded texture images`);
    let tris = 0;
    for (const mesh of json.meshes) {
        for (const prim of mesh.primitives) {
            const acc = prim.indices !== undefined
                ? json.accessors[prim.indices]
                : json.accessors[prim.attributes.POSITION];
            tris += acc.count / 3;
        }
    }
    assert.ok(Number.isInteger(tris), `${hull}.glb triangle count is not integral`);
    console.log(`PASS ${hull}.glb  ${(buf.length / 1e6).toFixed(2)} MB, ${json.meshes.length} meshes, ${json.materials.length} materials, ${json.images.length} images, ${tris} triangles`);
}
