// Ship model compiler: design record -> THREE.Group of merged PBR meshes.
// The group is exported to binary glTF (assets/ships/<hull>.glb) by the
// compile page; the glb is the canonical asset, everything in-game renders
// from it. Fully deterministic: same record -> same vertex counts and
// material set (asserted by tools/test_ships3d_determinism.mjs across all
// records).
//
// The compiler is a thin dispatcher: record.family selects a hull grammar
// from families.js, which composes the shared parts library (parts.js) into
// a MeshBin; the record's palette selects the baked texture set.
//
// opts.flavour (0..1) is the human-to-alien knob from the art directives:
// every record renders at any flavour without a new record. It biases the
// hull grammar (organic section morph, sheer warp, ram droop - see
// hullFromCurves / ramProw) and crossfades the palette toward the alien
// scheme below. opts.donors is an optional Map of clean-licensed kitbash
// geometries (see families.donorPart), loaded by the compile page only.
//
// Axis convention: +Z bow, -Z stern, +Y dorsal.

import * as THREE from '../../vendor/three/build/three.module.js';
import { makeRng } from './rng.js';
import { MeshBin } from './geometry.js';
import { buildMaterials } from './materials.js';
import { FAMILY_BUILDERS } from './families.js';
import { PALETTES } from './records.js';

// The far end of the flavour dial: bioship tones - iridescent grown armour,
// teal-green drive glow, sparse violet-tinged paintwork.
const ALIEN_PALETTE = {
    armorBase: [54, 66, 60],
    paint: ['rgba(60,96,80,0.5)', 'rgba(46,70,66,0.55)', 'rgba(84,60,96,0.4)'],
    paintChance: 0.13, rustChance: 0.12, grimeMul: 0.6,
    trimStyle: 'steel', trimBase: '#4f7d6a',
    glowStops: ['#eaffff', '#9dffd8', '#2fbf8f', '#020806'], glowColor: '#9fffe0',
    windowDark: 0.4, mechTint: '#5f7a72',
};

function lerp(a, b, t) { return a + (b - a) * t; }

function lerpHex(a, b, t) {
    const ca = new THREE.Color(a), cb = new THREE.Color(b);
    return '#' + ca.lerp(cb, t).getHexString();
}

const RGBA_RE = /rgba\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)/;
function lerpRgba(a, b, t) {
    const ma = RGBA_RE.exec(a.replace(/\s/g, '')), mb = RGBA_RE.exec(b.replace(/\s/g, ''));
    if (!ma || !mb) return t < 0.5 ? a : b;
    const v = (i, r) => (r ? lerp(parseFloat(ma[i]), parseFloat(mb[i]), t).toFixed(2) : Math.round(lerp(parseFloat(ma[i]), parseFloat(mb[i]), t)));
    return `rgba(${v(1)},${v(2)},${v(3)},${v(4, true)})`;
}

// Crossfade a record palette toward the alien scheme by flavour f (0..1).
export function flavourPalette(pal, f) {
    if (!f) return pal;
    const b = ALIEN_PALETTE;
    return {
        armorBase: pal.armorBase.map((v, i) => Math.round(lerp(v, b.armorBase[i], f))),
        paint: pal.paint.map((p, i) => lerpRgba(p, b.paint[i % b.paint.length], f)),
        paintChance: lerp(pal.paintChance, b.paintChance, f),
        rustChance: lerp(pal.rustChance, b.rustChance, f),
        grimeMul: lerp(pal.grimeMul, b.grimeMul, f),
        trimStyle: f > 0.5 ? b.trimStyle : pal.trimStyle,
        trimBase: lerpHex(pal.trimBase, b.trimBase, f),
        glowStops: pal.glowStops.map((c, i) => lerpHex(c, b.glowStops[i], f)),
        glowColor: lerpHex(pal.glowColor, b.glowColor, f),
        windowDark: lerp(pal.windowDark, b.windowDark, f),
        mechTint: lerpHex(pal.mechTint, b.mechTint, f),
    };
}

export async function compileShip(record, opts = {}) {
    const builder = FAMILY_BUILDERS[record.family];
    if (!builder) throw new Error(`unknown ship family: ${record.family}`);
    const flavour = opts.flavour ?? record.flavour ?? 0;
    const rng = makeRng(record.seed);
    const basePalette = PALETTES[record.palette] || PALETTES.warship;
    const palette = flavourPalette(basePalette, flavour);
    const materials = await buildMaterials(rng.fork('materials'), {
        textures: opts.textures !== false,
        textureSize: opts.textureSize || record.textureSize,
        palette,
    });
    const g = rng.fork('geometry');
    const bin = new MeshBin();

    builder({ bin, g, rec: { ...record, flavour }, feat: record.features, donors: opts.donors || null });

    const { group, stats } = bin.merge(materials);
    group.name = record.name;
    stats.record = record.name;
    stats.seed = record.seed;
    stats.flavour = flavour;
    stats.three = THREE.REVISION;
    group.userData.ship = {
        name: record.name,
        seed: record.seed,
        family: record.family,
        flavour,
        triangles: stats.triangles,
        components: stats.components,
        generator: 'stars-ultranova ships3d compiler',
    };
    return { group, stats };
}
