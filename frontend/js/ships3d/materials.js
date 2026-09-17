// Material set builder. With textures enabled (browser) every material
// carries canvas-baked PBR maps tinted by the record's palette; with
// textures disabled (node unit tests) the same material NAMES are produced
// with plain colours, so the compiled geometry and material set stay
// identical either way. The palette never influences geometry.

import * as THREE from '../../vendor/three/build/three.module.js';

export const MATERIAL_NAMES = ['armor', 'mech', 'trim', 'windows', 'engine_glow', 'radiator'];

const DEFAULT_PALETTE = {
    armorBase: [59, 64, 70],
    paint: ['rgba(96,58,48,0.5)', 'rgba(70,76,56,0.5)', 'rgba(46,50,60,0.55)'],
    paintChance: 0.09, rustChance: 0.35, grimeMul: 1.0,
    trimStyle: 'gothic', trimBase: '#78633c',
    glowStops: ['#ffffff', '#cfeaff', '#5aa8e8', '#02040a'], glowColor: '#bfe4ff',
    windowDark: 0.28, mechTint: '#777c84',
};

export async function buildMaterials(rng, opts = {}) {
    const withTex = opts.textures !== false;
    const pal = { ...DEFAULT_PALETTE, ...(opts.palette || {}) };
    const mats = new Map();

    let armorMaps = null, trimMaps = null, windowTex = null, glowTex = null, radTex = null;
    if (withTex) {
        const T = await import('./textures.js');
        armorMaps = T.bakeArmorSet(rng.fork('tex-armor'), opts.textureSize || 1024, pal);
        trimMaps = T.bakeTrimSet(rng.fork('tex-trim'), 512, pal);
        windowTex = T.bakeWindowEmissive(rng.fork('tex-windows'), 512, pal);
        glowTex = T.bakeEngineGlow(128, pal);
        radTex = T.bakeRadiatorEmissive(256);
    }

    const std = (params) => new THREE.MeshStandardMaterial(params);
    const [ar, ag, ab] = pal.armorBase;

    mats.set('armor', std(withTex ? {
        map: armorMaps.map,
        normalMap: armorMaps.normalMap,
        normalScale: new THREE.Vector2(1.0, 1.0),
        roughnessMap: armorMaps.mrMap,
        metalnessMap: armorMaps.mrMap,
        roughness: 1.0,
        metalness: 1.0,
    } : { color: (ar << 16) | (ag << 8) | ab, roughness: 0.6, metalness: 0.85 }));

    mats.set('mech', std(withTex ? {
        map: armorMaps.map,
        color: new THREE.Color(pal.mechTint), // darkens the shared armour map for machinery
        normalMap: armorMaps.normalMap,
        normalScale: new THREE.Vector2(1.3, 1.3),
        roughnessMap: armorMaps.mrMap,
        metalnessMap: armorMaps.mrMap,
        roughness: 1.0,
        metalness: 1.0,
    } : { color: 0x24262a, roughness: 0.65, metalness: 0.9 }));

    mats.set('trim', std(withTex ? {
        map: trimMaps.map,
        normalMap: trimMaps.normalMap,
        normalScale: new THREE.Vector2(1.1, 1.1),
        roughnessMap: trimMaps.mrMap,
        metalnessMap: trimMaps.mrMap,
        roughness: 1.0,
        metalness: 1.0,
    } : { color: 0x78633c, roughness: 0.35, metalness: 1.0 }));

    mats.set('windows', std(withTex ? {
        color: 0x05070a,
        roughness: 0.35,
        metalness: 0.2,
        emissive: 0xffffff,
        emissiveMap: windowTex,
        emissiveIntensity: 1.8,
    } : { color: 0x05070a, emissive: 0xffd9a0, emissiveIntensity: 1.5 }));

    mats.set('engine_glow', std(withTex ? {
        color: 0x000000,
        roughness: 1.0,
        metalness: 0.0,
        emissive: new THREE.Color(pal.glowColor),
        emissiveMap: glowTex,
        emissiveIntensity: 5.0,
        side: THREE.DoubleSide,
    } : { color: 0x000000, emissive: 0x8fd4ff, emissiveIntensity: 4.0, side: THREE.DoubleSide }));

    mats.set('radiator', std(withTex ? {
        color: 0x1a1c20,
        roughness: 0.55,
        metalness: 0.4,
        emissive: 0xffffff,
        emissiveMap: radTex,
        emissiveIntensity: 1.1,
    } : { color: 0x1a1c20, emissive: 0xff8a3d, emissiveIntensity: 1.0 }));

    for (const [name, m] of mats) m.name = name;
    return mats;
}
