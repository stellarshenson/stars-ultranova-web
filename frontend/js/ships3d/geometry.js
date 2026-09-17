// Geometry toolkit for the ship model compiler.
// A MeshBin collects many small BufferGeometries keyed by material name and
// merges them into one non-indexed mesh per material, which keeps the
// exported glb at a handful of draw calls while the source stays a soup of
// thousands of individually-placed components.

import * as THREE from '../../vendor/three/build/three.module.js';

const _m4 = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _up = new THREE.Vector3(0, 1, 0);

export class MeshBin {
    constructor() {
        this.bins = new Map(); // materialName -> geometry[]
        this.components = 0;   // count of individually placed parts
    }

    // Add a geometry under a material. opts: pos [x,y,z], rotX/rotY/rotZ (applied
    // in X,Y,Z order), quat (THREE.Quaternion, applied before pos), basis
    // (THREE.Matrix4 rotation basis), scale [x,y,z].
    add(name, geo, opts = {}) {
        let g = geo.index ? geo.toNonIndexed() : geo;
        if (!g.attributes.uv) {
            const n = g.attributes.position.count;
            g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(n * 2), 2));
        }
        if (opts.scale) g.scale(opts.scale[0], opts.scale[1], opts.scale[2]);
        if (opts.rotX) g.rotateX(opts.rotX);
        if (opts.rotY) g.rotateY(opts.rotY);
        if (opts.rotZ) g.rotateZ(opts.rotZ);
        if (opts.quat) g.applyQuaternion(opts.quat);
        if (opts.basis) g.applyMatrix4(opts.basis);
        if (opts.pos) g.translate(opts.pos[0], opts.pos[1], opts.pos[2]);
        if (!this.bins.has(name)) this.bins.set(name, []);
        this.bins.get(name).push(g);
        if (!opts.subPart) this.components += 1;
        return g;
    }

    // Merge all collected geometries into one indexed mesh per material.
    // Vertices identical in position, normal and uv are welded (exact float
    // match, deterministic first-seen order) - roughly halves the exported
    // glb size without touching shading, since duplicates share all
    // attributes by construction.
    merge(materials) {
        const group = new THREE.Group();
        const stats = { triangles: 0, vertices: 0, meshes: 0, materials: [], components: this.components, perMaterial: {} };
        for (const [name, geos] of this.bins) {
            let total = 0;
            for (const g of geos) total += g.attributes.position.count;
            const pos = new Float32Array(total * 3);
            const nor = new Float32Array(total * 3);
            const uv = new Float32Array(total * 2);
            let off = 0;
            for (const g of geos) {
                const n = g.attributes.position.count;
                pos.set(g.attributes.position.array, off * 3);
                nor.set(g.attributes.normal.array, off * 3);
                uv.set(g.attributes.uv.array, off * 2);
                off += n;
            }
            const welded = weldVertices(pos, nor, uv, total);
            const merged = new THREE.BufferGeometry();
            merged.setAttribute('position', new THREE.BufferAttribute(welded.pos, 3));
            merged.setAttribute('normal', new THREE.BufferAttribute(welded.nor, 3));
            merged.setAttribute('uv', new THREE.BufferAttribute(welded.uv, 2));
            merged.setIndex(new THREE.BufferAttribute(welded.index, 1));
            const mat = materials.get(name);
            const mesh = new THREE.Mesh(merged, mat);
            mesh.name = name;
            group.add(mesh);
            stats.triangles += total / 3;
            stats.vertices += welded.count;
            stats.meshes += 1;
            stats.materials.push(name);
            stats.perMaterial[name] = welded.count;
        }
        stats.materials.sort();
        return { group, stats };
    }
}

// Weld exactly-equal vertices (position + normal + uv, raw float32 bits) into
// an indexed vertex list. First-seen order keeps the result deterministic.
function weldVertices(pos, nor, uv, total) {
    const pi = new Int32Array(pos.buffer);
    const ni = new Int32Array(nor.buffer);
    const ti = new Int32Array(uv.buffer);
    const map = new Map();
    const index = new Uint32Array(total);
    const remap = new Uint32Array(total);
    let count = 0;
    for (let v = 0; v < total; v++) {
        const key = `${pi[v * 3]},${pi[v * 3 + 1]},${pi[v * 3 + 2]},${ni[v * 3]},${ni[v * 3 + 1]},${ni[v * 3 + 2]},${ti[v * 2]},${ti[v * 2 + 1]}`;
        let idx = map.get(key);
        if (idx === undefined) {
            idx = count;
            map.set(key, idx);
            remap[count] = v;
            count += 1;
        }
        index[v] = idx;
    }
    const wpos = new Float32Array(count * 3);
    const wnor = new Float32Array(count * 3);
    const wuv = new Float32Array(count * 2);
    for (let i = 0; i < count; i++) {
        const v = remap[i];
        wpos[i * 3] = pos[v * 3]; wpos[i * 3 + 1] = pos[v * 3 + 1]; wpos[i * 3 + 2] = pos[v * 3 + 2];
        wnor[i * 3] = nor[v * 3]; wnor[i * 3 + 1] = nor[v * 3 + 1]; wnor[i * 3 + 2] = nor[v * 3 + 2];
        wuv[i * 2] = uv[v * 2]; wuv[i * 2 + 1] = uv[v * 2 + 1];
    }
    return { pos: wpos, nor: wnor, uv: wuv, index, count };
}

// Flat-shade a geometry: non-indexed with per-face normals.
export function flatShade(geo) {
    const g = geo.index ? geo.toNonIndexed() : geo;
    g.computeVertexNormals();
    return g;
}

// Scale and offset the uv attribute so each component samples its own patch
// of the shared texture atlas instead of the same corner.
export function uvPatch(geo, rng, scale = 0.25) {
    const uv = geo.attributes.uv;
    if (!uv) return geo;
    const ou = rng(), ov = rng();
    for (let i = 0; i < uv.count; i++) {
        uv.setXY(i, uv.getX(i) * scale + ou, uv.getY(i) * scale + ov);
    }
    return geo;
}

// Explicit uv transform (used for window strips that must map onto one
// row of the window texture).
export function uvTransform(geo, su, sv, ou, ov) {
    const uv = geo.attributes.uv;
    for (let i = 0; i < uv.count; i++) {
        uv.setXY(i, uv.getX(i) * su + ou, uv.getY(i) * sv + ov);
    }
    return geo;
}

// Bevelled plate: rectangular slab with chamfered top edges, origin at the
// bottom centre, +Y up. Reads as an armour plate instead of a raw box.
export function bevelPlate(w, h, d, bevel) {
    const hw = w / 2, hd = d / 2;
    const b = Math.min(bevel, hw * 0.6, hd * 0.6, h * 0.9);
    const iw = hw - b, id = hd - b, y1 = Math.max(h - b, h * 0.4);
    const r0 = [[-hw, 0, -hd], [hw, 0, -hd], [hw, 0, hd], [-hw, 0, hd]];
    const r1 = [[-hw, y1, -hd], [hw, y1, -hd], [hw, y1, hd], [-hw, y1, hd]];
    const r2 = [[-iw, h, -id], [iw, h, -id], [iw, h, id], [-iw, h, id]];
    const pos = [];
    const quad = (a, bb, c, dd) => { pos.push(...a, ...bb, ...c, ...a, ...c, ...dd); };
    for (let i = 0; i < 4; i++) {
        const j = (i + 1) % 4;
        quad(r0[j], r0[i], r1[i], r1[j]); // side, outward
        quad(r1[j], r1[i], r2[i], r2[j]); // bevel, outward
    }
    quad(r2[3], r2[2], r2[1], r2[0]); // top (wound so normal is +Y)
    quad(r0[0], r0[1], r0[2], r0[3]); // bottom (-Y)
    const geo = new THREE.BufferGeometry();
    const arr = new Float32Array(pos);
    geo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
    // planar uv from x,z
    const uv = new Float32Array((arr.length / 3) * 2);
    for (let i = 0; i < arr.length / 3; i++) {
        uv[i * 2] = (arr[i * 3] + hw) / Math.max(w, 0.001);
        uv[i * 2 + 1] = (arr[i * 3 + 2] + hd) / Math.max(d, 0.001);
    }
    geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    geo.computeVertexNormals();
    return geo;
}

// Loft a closed profile along stations. stations: [{z, pts: [[x,y], ...]}],
// every station has the same point count, points ordered clockwise when the
// ship is viewed from the bow (+Z looking down -Z). Stations ordered bow to
// stern (decreasing z). Produces an outward-facing flat-shaded skin with
// optional end caps.
export function loft(stations, opts = {}) {
    const pos = [];
    const uvs = [];
    const nSta = stations.length;
    const nPts = stations[0].pts.length;
    const uScale = opts.uScale || 3.0;
    const vScale = opts.vScale || 0.35;
    const P = (i, j) => {
        const s = stations[i];
        const p = s.pts[j % nPts];
        return [p[0], p[1], s.z];
    };
    for (let i = 0; i < nSta - 1; i++) {
        for (let j = 0; j < nPts; j++) {
            const a = P(i, j), b = P(i, j + 1), c = P(i + 1, j + 1), d = P(i + 1, j);
            pos.push(...a, ...b, ...c, ...a, ...c, ...d);
            const u0 = (j / nPts) * uScale, u1 = ((j + 1) / nPts) * uScale;
            const v0 = stations[i].z * vScale, v1 = stations[i + 1].z * vScale;
            uvs.push(u0, v0, u1, v0, u1, v1, u0, v0, u1, v1, u0, v1);
        }
    }
    const cap = (i, flip) => {
        let cx = 0, cy = 0;
        const s = stations[i];
        for (const p of s.pts) { cx += p[0]; cy += p[1]; }
        cx /= nPts; cy /= nPts;
        for (let j = 0; j < nPts; j++) {
            const a = [cx, cy, s.z], b = P(i, j + 1), c = P(i, j);
            if (flip) pos.push(...a, ...c, ...b); else pos.push(...a, ...b, ...c);
            uvs.push(0.5, 0.5, 0.6, 0.5, 0.5, 0.6);
        }
    };
    if (opts.capStart) cap(0, false);          // bow cap faces +Z
    if (opts.capEnd) cap(nSta - 1, true);      // stern cap faces -Z
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geo.computeVertexNormals();
    return geo;
}

// Basis matrix whose +Y axis points along `normal`, positioned at `p`.
// tangentHint fixes the in-plane orientation when it matters.
export function surfaceBasis(p, normal, tangentHint) {
    const n = new THREE.Vector3().fromArray(normal).normalize();
    let t;
    if (tangentHint) {
        t = new THREE.Vector3().fromArray(tangentHint);
        t.sub(n.clone().multiplyScalar(t.dot(n))).normalize();
    } else {
        const ref = Math.abs(n.y) < 0.9 ? _up : new THREE.Vector3(0, 0, 1);
        t = new THREE.Vector3().crossVectors(ref, n).normalize();
    }
    const bt = new THREE.Vector3().crossVectors(n, t);
    const m = new THREE.Matrix4().makeBasis(t, n, bt);
    m.setPosition(p[0], p[1], p[2]);
    return m;
}

// Strut: box running from point a to point b with square cross-section s.
export function strut(bin, name, a, b, s, rng) {
    const av = new THREE.Vector3().fromArray(a);
    const bv = new THREE.Vector3().fromArray(b);
    const len = av.distanceTo(bv);
    if (len < 0.001) return;
    const geo = new THREE.BoxGeometry(s, len, s);
    const dir = bv.clone().sub(av).normalize();
    _q.setFromUnitVectors(_up, dir);
    const mid = av.clone().add(bv).multiplyScalar(0.5);
    if (rng) uvPatch(geo, rng, 0.1);
    bin.add(name, geo, { quat: _q.clone(), pos: [mid.x, mid.y, mid.z] });
}

// Tube strut: cylinder from a to b, radius r.
export function tube(bin, name, a, b, r, seg = 6, rng = null) {
    const av = new THREE.Vector3().fromArray(a);
    const bv = new THREE.Vector3().fromArray(b);
    const len = av.distanceTo(bv);
    if (len < 0.001) return;
    const geo = new THREE.CylinderGeometry(r, r, len, seg);
    const dir = bv.clone().sub(av).normalize();
    _q.setFromUnitVectors(_up, dir);
    const mid = av.clone().add(bv).multiplyScalar(0.5);
    if (rng) uvPatch(geo, rng, 0.08);
    bin.add(name, geo, { quat: _q.clone(), pos: [mid.x, mid.y, mid.z] });
}
