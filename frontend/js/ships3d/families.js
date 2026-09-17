// Family builders: one hull-form grammar per ship family, all composing the
// shared parts library. A builder receives {bin, g, rec, feat} and assembles
// the full hull; the compiler merges and exports whatever the builder adds.
//
// Family languages (per the design directives):
// - warship: W40k mass - trireme ram prow, layered plating, gothic bands,
//   cathedral spine, crenellated tower; FreeSpace beam apertures and hangar
//   maws on capitals; blue-white engine glow
// - scout/raider: Privateer chunk - mandible prongs, canopy, fat nacelles,
//   external gun hardpoints
// - freighter/tanker: Expanse functionalism - container spines, truss keels,
//   sphere tanks, radiator wings, RCS quads
// - miner: industrial body-of-revolution drums, drill booms, hoppers,
//   floodlights, rust and hazard paint
// - bomber: ordnance frames - a spine or open truss whose spars exist to
//   hang bomb racks; NO aircraft anatomy, attitude control is RCS
// - stealth: faceted low-signature slab with internal bays
// - colony: ceramic hab drums, dense window life, dome ring
// - minelayer: dispenser drums and open mine racks, hazard trim
// - modular: Nubian truss sockets / Meta Morph radial hub
// - assault: armoured wedge, drop pods, bow ramp

import * as THREE from '../../vendor/three/build/three.module.js';
import { bevelPlate, loft, strut, tube, uvPatch, uvTransform } from './geometry.js';
import { greebleField } from './greebles.js';
import {
    PROFILE, BOX_PROFILE, CHINE_PROFILE,
    hullFromCurves, conformalPlating, ramProw, prowBlade, mandibleProws, gothicBands,
    vlsField, turret, pdMounts, cathedralSpine, bridgeTower, windowRows,
    radiatorPair, radiatorWing, ventralTruss, fuelSphere, engineBlock,
    engineNacelle, rcsQuad, trussBox, containerBlock, containerRacks,
    commandModule, drumBody, drillBoom, bombPallet, canopy, gunHardpoint,
    hangarMaw, dishAntenna, habDome, floodMast, greebleZones, broadsideDeck,
    keelFin, bucketWheel, intakeMaw,
} from './parts.js';
import { surfaceBasis } from './geometry.js';

function engineXs(n, spread) {
    const xs = [];
    for (let i = 0; i < n; i++) xs.push((i - (n - 1) / 2) * spread);
    return xs;
}

// Place a donor kitbash part (clean-licensed geometry preloaded by the
// compile page) under one of our material families. Donor geometries are
// normalized at load (unit max dimension, resting on y=0, centred in x/z);
// opts.scale sizes them into hull units. Purely additive: when the donor
// library is absent (node tests) the procedural hull is complete without
// them, and compiles stay deterministic either way.
function donorPart(ctx, name, mat, opts = {}) {
    const lib = ctx.donors;
    const src = lib && lib.get ? lib.get(name) : null;
    if (!src) return false;
    const geo = src.clone();
    uvPatch(geo, ctx.g, 0.2);
    ctx.bin.add(mat, geo, opts);
    return true;
}

function rcsRing(bin, g, frame, z, s = 1.0) {
    const w = frame.W(z), h = frame.H(z);
    for (const side of [1, -1]) {
        rcsQuad(bin, g, [side * 0.7 * w, 0.6 * h, z], s);
        rcsQuad(bin, g, [side * 0.7 * w, -0.65 * h, z], s);
    }
}

// ---- warship ladder --------------------------------------------------------

export function buildWarship(ctx) {
    const { bin, g, rec, feat } = ctx;
    const frame = hullFromCurves(bin, g, rec.hull, { flavour: rec.flavour || 0 });
    const k = frame.k;
    conformalPlating(bin, g, frame);
    if (feat.prowBlade) {
        // family ruling: EVERY warship carries the W40k armoured prow blade,
        // scaled to its class - no ram anywhere in the battle line
        prowBlade(bin, g, frame, feat.prowBlade);
    } else {
        ramProw(bin, g, frame, {
            lenFrac: feat.prowLenFrac ?? 0.19,
            beak: !!feat.beak,
            blunt: !!feat.blunt,
            beamApertures: feat.beamApertures || 0,
        });
    }
    gothicBands(bin, g, frame, feat.bandZ || []);
    if (feat.vls) vlsField(bin, g, frame, feat.vls);
    const ts = feat.turretScale ?? 1.0;
    for (const z of feat.dorsalTurretZ || []) turret(bin, g, frame, z, 1, ts, { barrels: feat.barrels ?? 2 });
    for (const z of feat.ventralTurretZ || []) turret(bin, g, frame, z, -1, ts * 0.85, { barrels: feat.barrels ?? 2 });
    for (const z of feat.pdMountZ || []) pdMounts(bin, g, frame, z, Math.max(0.8, k * 0.6));
    if (feat.spine) cathedralSpine(bin, g, frame, feat.spine.z0, feat.spine.z1, feat.spine.s ?? Math.max(0.8, k * 0.8), { dense: !!feat.spine.dense });
    if (feat.tower) bridgeTower(bin, g, frame, feat.tower.z0, feat.tower.z1, feat.tower.s ?? Math.max(0.85, k * 0.85));
    if (feat.tower2) bridgeTower(bin, g, frame, feat.tower2.z0, feat.tower2.z1, feat.tower2.s ?? Math.max(0.7, k * 0.6));
    if (feat.broadside) broadsideDeck(bin, g, frame, feat.broadside);
    if (feat.windowRows !== false) {
        const winOpts = { bayZ: 0.13 * frame.zStern, step: feat.winStep, skip: feat.winSkip };
        if (feat.broadside) {
            // gun decks own the mid-flank: lit rows tier between and above them
            winOpts.yTop = feat.broadside.winYTop ?? 0.34;
            winOpts.lower = feat.broadside.winLower ?? false;
        }
        windowRows(bin, g, frame, 0.56 * frame.zBow, 0.74 * frame.zStern, winOpts);
    }
    for (const z of feat.radiatorZ || []) radiatorPair(bin, g, frame, z, Math.max(0.8, k * 0.8));
    if (feat.truss) ventralTruss(bin, g, frame, feat.truss.z0, feat.truss.z1, Math.max(0.8, k * 0.9));
    if (feat.keelFin !== undefined) keelFin(bin, g, frame, feat.keelFin, Math.max(0.9, k * 0.8));
    for (const fs of feat.fuelSpheres || []) fuelSphere(bin, g, [fs[0], -frame.H(fs[1]) * 0.78, fs[1]], fs[2] ?? 0.3 * k);
    const zCap = frame.zStern;
    const engS = Math.max(0.9, k * 0.75) * (feat.engineScale ?? 1.0);
    let engXsArr;
    if (feat.engineRanks) {
        // two stacked exhaust ranks (dreadnought digest): one shared armoured
        // housing, bells in an upper and a lower row
        engineBlock(bin, g, { zCap, xs: [], s: engS, skirtW: frame.W(zCap + 0.5 * k) * 2.2, skirtH: frame.H(zCap + 0.5 * k) * 1.35 });
        engXsArr = [];
        for (const [n, yf] of feat.engineRanks) {
            const xs = engineXs(n, (feat.engineSpread ?? 0.42) * Math.max(1, k * 0.7));
            engineBlock(bin, g, { zCap, xs, ys: yf * frame.H(zCap + 0.5 * k), s: engS * 0.82, skirt: false });
            engXsArr.push(...xs);
        }
    } else {
        engXsArr = engineXs(feat.engines ?? 2, (feat.engineSpread ?? 0.42) * Math.max(1, k * 0.7));
        engineBlock(bin, g, { zCap, xs: engXsArr, s: engS, skirtW: frame.W(zCap + 0.5 * k) * 2.2, skirtH: frame.H(zCap + 0.5 * k) * 1.3 });
    }
    for (const zf of [0.82, -0.9]) rcsRing(bin, g, frame, zf > 0 ? zf * frame.zBow : -zf * frame.zStern, Math.max(0.8, k * 0.7));
    if (feat.hangar) {
        for (const side of feat.hangar.sides || [1]) {
            const z = feat.hangar.z;
            hangarMaw(bin, g, [side * (frame.W(z) - 0.01), -0.1 * frame.H(z), z], feat.hangar.w ?? 0.8 * k, feat.hangar.h ?? 0.4 * k, side);
        }
    }
    // donor kitbash: Kenney turret blisters seeded onto the flank chamfers and
    // a sensor garden dish aft of the superstructure (additive detail)
    const dz = feat.dorsalTurretZ || [];
    for (let i = 0; i < dz.length && i < 3; i++) {
        const z = dz[i] - 0.7 * k;
        for (const side of [1, -1]) {
            const p = [side * 0.79 * frame.W(z), 0.62 * frame.H(z), z];
            const basis = surfaceBasis(p, [side * 0.52, 0.45, 0], [0, 0, 1]);
            donorPart(ctx, i % 2 ? 'turret_single' : 'turret_double', 'mech',
                { basis, scale: [0.42 * k, 0.42 * k, 0.42 * k] });
        }
    }
    if (feat.tower) {
        const zd = feat.tower.z0 + 0.5 * k;
        donorPart(ctx, 'satelliteDish_detailed', 'mech',
            { pos: [0.3 * k, frame.deckYAt(zd, 0) - 0.02, zd], scale: [0.5 * k, 0.5 * k, 0.5 * k] });
    }
    greebleZones(bin, g, frame, feat, feat.greebleBudget || 400, { engX: engXsArr, turretZ: feat.dorsalTurretZ || [], zCap });
}

// ---- scout: recon dart with mandible prongs and a big dish -----------------

export function buildScout(ctx) {
    const { bin, g, rec, feat } = ctx;
    const frame = hullFromCurves(bin, g, rec.hull, { flavour: rec.flavour || 0 });
    conformalPlating(bin, g, frame, { missChance: 0.18 });
    mandibleProws(bin, g, frame, { lenFrac: 0.17 });
    canopy(bin, g, [0, frame.deckYAt(0.45 * frame.zBow, 0) - 0.01, 0.45 * frame.zBow], 0.8);
    dishAntenna(bin, g, [0, frame.deckYAt(0.15 * frame.zStern, 0), 0.15 * frame.zStern], 0.26, 1.0);
    gothicBands(bin, g, frame, feat.bandZ || []);
    windowRows(bin, g, frame, 0.3 * frame.zBow, 0.5 * frame.zStern, { step: 0.4, boatBay: false });
    for (const z of feat.radiatorZ || []) radiatorPair(bin, g, frame, z, 0.6);
    const zCap = frame.zStern;
    engineBlock(bin, g, { zCap, xs: [0], s: 0.8, skirtW: frame.W(zCap + 0.3) * 2.1, skirtH: frame.H(zCap + 0.3) * 1.25 });
    rcsRing(bin, g, frame, 0.7 * frame.zBow, 0.7);
    rcsRing(bin, g, frame, 0.8 * frame.zStern, 0.7);
    // sensor pallet instead of guns: antenna farm on the deck
    greebleZones(bin, g, frame, feat, feat.greebleBudget || 220, { engX: [0], zCap });
}

// ---- raider: privateer chunk - central hull, fat nacelles, hardpoints ------

export function buildRaider(ctx) {
    const { bin, g, rec, feat } = ctx;
    const frame = hullFromCurves(bin, g, rec.hull, { flavour: rec.flavour || 0 });
    const k = frame.k;
    conformalPlating(bin, g, frame);
    mandibleProws(bin, g, frame, { lenFrac: 0.14, gap: 0.5 * frame.W(frame.zBow - 0.4 * k) });
    canopy(bin, g, [0, frame.deckYAt(0.5 * frame.zBow, 0) - 0.01, 0.5 * frame.zBow], Math.max(0.9, k));
    gothicBands(bin, g, frame, feat.bandZ || []);
    // fat side nacelles
    const nz = feat.nacelleZ ?? 0.45 * frame.zStern;
    const nr = feat.nacelleR ?? 0.32 * k, nlen = feat.nacelleLen ?? 3.4 * k;
    for (const side of [1, -1]) {
        const x = side * (frame.W(nz) + nr * 0.85);
        engineNacelle(bin, g, [x, -0.1 * frame.H(nz), nz], nlen, nr);
        // pylon straps
        strut(bin, 'armor', [side * frame.W(nz) * 0.7, 0.1, nz + nlen * 0.2], [x, -0.1 * frame.H(nz) + nr * 0.8, nz + nlen * 0.2], 0.09 * k, g);
        strut(bin, 'armor', [side * frame.W(nz) * 0.7, -0.1, nz - nlen * 0.2], [x, -0.1 * frame.H(nz) + nr * 0.8, nz - nlen * 0.2], 0.09 * k, g);
    }
    // external gun hardpoints along the shoulders
    for (const [hx, hz] of feat.hardpoints || []) {
        gunHardpoint(bin, g, [hx, frame.deckYAt(hz, hx), hz], Math.max(0.8, k * 0.9));
        gunHardpoint(bin, g, [hx, -frame.H(hz) * 0.95, hz], Math.max(0.8, k * 0.9), true);
    }
    if (feat.dorsalTurretZ) for (const z of feat.dorsalTurretZ) turret(bin, g, frame, z, 1, feat.turretScale ?? 0.9);
    windowRows(bin, g, frame, 0.4 * frame.zBow, 0.6 * frame.zStern, { step: 0.36, bayZ: 0.2 * frame.zStern });
    for (const z of feat.radiatorZ || []) radiatorPair(bin, g, frame, z, 0.7 * Math.max(1, k));
    const zCap = frame.zStern;
    engineBlock(bin, g, { zCap, xs: [0], s: Math.max(0.85, k * 0.8), skirtW: frame.W(zCap + 0.4) * 2.1, skirtH: frame.H(zCap + 0.4) * 1.3 });
    rcsRing(bin, g, frame, 0.75 * frame.zBow, 0.8);
    rcsRing(bin, g, frame, 0.85 * frame.zStern, 0.8);
    greebleZones(bin, g, frame, feat, feat.greebleBudget || 360, { engX: [0], turretZ: feat.dorsalTurretZ || [], zCap });
}

// ---- freighter: container spine ladder -------------------------------------

export function buildFreighter(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const spec = feat.spine; // {rows, cols, cell:{w,h,d}}
    const cell = spec.cell;
    const hw = (spec.cols * (cell.w + 0.06)) / 2 + 0.08;
    const hh = (spec.rows * (cell.h + 0.06)) / 2 + 0.08;
    // command module fore
    const cmS = feat.commandScale ?? Math.max(1.0, k * 0.75);
    commandModule(bin, g, [0, 0.1 * cmS, zFore - 0.55 * cmS], cmS);
    // spine truss under the container stacks
    const zSpine0 = zFore - 1.25 * cmS, zSpine1 = zAft + 1.7 * k;
    trussBox(bin, g, zSpine0, zSpine1, hw * 0.55, hh * 0.35, { railSize: 0.07 * Math.max(1, k * 0.8) });
    // keel beam
    const keel = new THREE.BoxGeometry(0.22 * Math.max(1, k * 0.8), 0.16 * Math.max(1, k * 0.8), zSpine0 - zSpine1 + 0.6);
    uvPatch(keel, g, 0.3);
    bin.add('armor', keel, { pos: [0, -hh - 0.1, (zSpine0 + zSpine1) / 2] });
    // container racks
    containerRacks(bin, g, zSpine0 - 0.2, zSpine1 + 0.2, spec.rows, spec.cols, cell, { gapChance: feat.gapChance ?? 0.08 });
    // fuel spheres between spine and engine
    for (const fs of feat.fuelSpheres || []) fuelSphere(bin, g, fs, fs[3] ?? 0.3 * k);
    // radiator wings near the engine
    radiatorWing(bin, g, [0.2, -hh * 0.4, zAft + 1.3 * k], 0.9 * k, 0.7 * k, 0.5);
    // engine block on an armoured stern pyramid
    const engSta = [
        { z: zAft + 1.5 * k, w: hw * 0.9, h: hh * 0.9 },
        { z: zAft + 0.5 * k, w: hw * 0.65, h: hh * 0.65 },
        { z: zAft, w: hw * 0.5, h: hh * 0.5 },
    ].map((s2) => ({ z: s2.z, pts: BOX_PROFILE.map(([px, py]) => [px * s2.w, py * s2.h]) }));
    bin.add('armor', loft(engSta, { capStart: true, capEnd: true, uScale: 3, vScale: 0.4 }), {});
    const nEng = feat.engines ?? 2;
    engineBlock(bin, g, { zCap: zAft, xs: engineXs(nEng, 0.5 * Math.max(1, k * 0.7)), s: Math.max(0.8, k * 0.65), skirt: false });
    // armed variant (Galleon): dorsal turrets over the racks + pd
    if (feat.armed) {
        for (const z of feat.armed.turretZ) {
            const mount = bevelPlate(0.5, 0.14, 0.5, 0.05);
            uvPatch(mount, g, 0.15);
            bin.add('armor', mount, { pos: [0, hh + 0.02, z] });
            const fakeFrame = { deckYAt: () => hh + 0.16, H: () => hh, W: () => hw };
            turret(bin, g, fakeFrame, z, 1, feat.armed.scale ?? 1.0);
        }
    }
    // rcs on command module and engine pyramid
    for (const [x, y, z] of [[hw * 0.5, hh * 0.6, zFore - 0.2], [-hw * 0.5, hh * 0.6, zFore - 0.2], [hw * 0.6, -hh * 0.6, zAft + 0.7], [-hw * 0.6, -hh * 0.6, zAft + 0.7]]) {
        rcsQuad(bin, g, [x, y, z], 0.9);
    }
    // greebles on the command module and stern pyramid
    const cmSampler = (r) => {
        const x = r.range(-0.35, 0.35) * cmS, z = zFore - 0.55 * cmS + r.range(-0.4, 0.4) * cmS;
        return { p: [x, 0.1 * cmS + 0.28 * cmS, z], n: [0, 1, 0], t: [0, 0, 1], s: 0.6 };
    };
    const sternSampler = (r) => {
        const t = r.range(0, 1);
        const z = zAft + 0.5 * k + t * k;
        const wz = hw * (0.65 + 0.25 * t), hz = hh * (0.65 + 0.25 * t);
        const side = r.sign();
        return { p: [r.range(-0.6, 0.6) * wz, side * hz, z], n: [0, side, 0], t: [0, 0, 1], s: 0.7 };
    };
    greebleField(bin, g, Math.floor((feat.greebleBudget || 200) * 0.5), cmSampler);
    greebleField(bin, g, Math.floor((feat.greebleBudget || 200) * 0.5), sternSampler);
    // donor kitbash: Kenney cargo pods slung off the rack flanks, deck barrel
    // clusters and a pipe run along the spine crown
    const podZs = [zSpine0 - 1.2 * k, (zSpine0 + zSpine1) / 2, zSpine1 + 1.2 * k];
    for (let i = 0; i < podZs.length; i++) {
        for (const side of [1, -1]) {
            donorPart(ctx, i % 2 ? 'craft_cargoB' : 'craft_cargoA', 'mech',
                { rotY: side > 0 ? Math.PI / 2 : -Math.PI / 2, pos: [side * (hw + 0.3 * k), -hh * 0.3, podZs[i]], scale: [0.55 * k, 0.55 * k, 0.55 * k] });
        }
    }
    donorPart(ctx, 'barrels', 'trim', { pos: [0.3 * k, hh + 0.02, zSpine1 + 0.9 * k], scale: [0.35 * k, 0.35 * k, 0.35 * k] });
    donorPart(ctx, 'pipe_straight', 'mech', { rotX: Math.PI / 2, pos: [-0.25 * k, hh + 0.06, (zSpine0 + zSpine1) / 2], scale: [0.3 * k, 2.2 * k, 0.3 * k] });
}

// ---- tanker: keel with sphere tank row -------------------------------------

export function buildTanker(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const r = feat.tankR;
    const cmS = Math.max(0.9, k * 0.8);
    commandModule(bin, g, [0, r * 0.25, zFore - 0.55 * cmS], cmS);
    trussBox(bin, g, zFore - 1.2 * cmS, zAft + 1.3 * k, r * 0.32, r * 0.3, { railSize: 0.06 * Math.max(1, k) });
    // tank row with saddle frames and a top manifold pipe
    const tanks = feat.tankZ;
    for (const tz of tanks) {
        fuelSphere(bin, g, [0, 0, tz], r);
        for (const side of [1, -1]) {
            strut(bin, 'armor', [side * r * 0.32, -r * 0.28, tz - r * 0.6], [side * r * 0.75, -r * 0.05, tz - r * 0.35], 0.05 * k, g);
            strut(bin, 'armor', [side * r * 0.32, -r * 0.28, tz + r * 0.6], [side * r * 0.75, -r * 0.05, tz + r * 0.35], 0.05 * k, g);
        }
    }
    tube(bin, 'mech', [0, r * 1.12, tanks[0]], [0, r * 1.12, tanks[tanks.length - 1]], 0.045 * k, 8, g);
    for (const tz of tanks) {
        tube(bin, 'mech', [0, r * 1.0, tz], [0, r * 1.12, tz], 0.03 * k, 6, g);
        const valve = new THREE.BoxGeometry(0.1 * k, 0.1 * k, 0.14 * k);
        uvPatch(valve, g, 0.08);
        bin.add('trim', valve, { pos: [0, r * 1.12, tz], subPart: true });
    }
    // pump house mid-keel
    const pump = bevelPlate(r * 0.7, r * 0.4, r * 0.8, 0.05);
    uvPatch(pump, g, 0.2);
    bin.add('mech', pump, { pos: [0, -r * 0.62, (tanks[0] + tanks[tanks.length - 1]) / 2] });
    radiatorWing(bin, g, [0.1, -r * 0.35, zAft + 1.1 * k], 0.8 * k, 0.6 * k, 0.45);
    engineBlock(bin, g, { zCap: zAft, xs: engineXs(feat.engines ?? 1, 0.45 * k), s: Math.max(0.8, k * 0.7), skirtW: r * 1.1, skirtH: r * 0.8 });
    for (const [x, y, z] of [[r * 0.5, r * 0.5, zFore - 0.3], [-r * 0.5, r * 0.5, zFore - 0.3], [r * 0.5, -r * 0.5, zAft + 0.8], [-r * 0.5, -r * 0.5, zAft + 0.8]]) {
        rcsQuad(bin, g, [x, y, z], 0.85);
    }
    const keelSampler = (r2) => {
        const z = r2.range(zAft + 1.2 * k, zFore - 1.3 * cmS);
        for (const tz of tanks) if (Math.abs(z - tz) < r * 0.95) return null;
        return { p: [r2.range(-0.2, 0.2) * r, -r * 0.32, z], n: [0, -1, 0], t: [0, 0, 1], s: 0.6 };
    };
    greebleField(bin, g, feat.greebleBudget || 140, keelSampler);
    // donor kitbash: Kenney rocket fuel stages as external tank stacks riding
    // the keel flanks, barrel cluster at the pump house
    for (const side of [1, -1]) {
        const tz = (tanks[0] + tanks[tanks.length - 1]) / 2;
        donorPart(ctx, side > 0 ? 'rocket_fuelA' : 'rocket_fuelB', 'mech',
            { rotX: Math.PI / 2, pos: [side * r * 0.9, -r * 0.55, tz + side * r * 0.8], scale: [r * 0.62, r * 0.62, r * 0.62] });
    }
    donorPart(ctx, 'barrels', 'trim', { pos: [0, -r * 0.42, zAft + 1.6 * k], scale: [r * 0.5, r * 0.5, r * 0.5] });
}

// ---- miner: industrial drum, drill booms, hoppers --------------------------

export function buildMiner(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const r = feat.drumR, drumLen = feat.drumLen;
    const fl = rec.flavour || 0;
    const zDrum = zAft + 1.2 * k + drumLen / 2;
    drumBody(bin, g, zDrum, drumLen, r, { ribs: feat.ribs ?? 5, seg: 20 + Math.round(fl * 10) });
    if (feat.twinDrum) {
        drumBody(bin, g, zDrum + drumLen * 0.1, drumLen * 0.7, r * 0.55, { x: r * 1.3, y: -r * 0.15, ribs: 4 });
        drumBody(bin, g, zDrum + drumLen * 0.1, drumLen * 0.7, r * 0.55, { x: -r * 1.3, y: -r * 0.15, ribs: 4 });
    }
    // ore hoppers flanking the drum
    for (const side of feat.twinDrum ? [0] : [1, -1]) {
        const hop = bevelPlate(r * 0.9, r * 0.85, drumLen * 0.55, 0.06);
        uvPatch(hop, g, 0.25);
        bin.add('armor', hop, { pos: [side * r * 1.15, feat.twinDrum ? r * 0.9 : -r * 0.15, zDrum + drumLen * 0.05] });
        for (let i = 0; i < 3; i++) {
            const ribZ = zDrum - drumLen * 0.2 + i * drumLen * 0.25;
            strut(bin, 'trim', [side * r * 1.15 - r * 0.45, (feat.twinDrum ? r * 0.9 : -r * 0.15) + r * 0.4, ribZ],
                [side * r * 1.15 + r * 0.45, (feat.twinDrum ? r * 0.9 : -r * 0.15) + r * 0.4, ribZ], 0.04 * k, g);
        }
    }
    // forward gantry frame and drill booms converging on the work focus
    const zGantry = zDrum + drumLen / 2 + 0.3 * k;
    trussBox(bin, g, zGantry + 0.9 * k, zGantry - 0.2 * k, r * 0.55, r * 0.5, { railSize: 0.05 * Math.max(1, k) });
    const focus = [0, -r * 0.4, zFore + feat.boomReach];
    const nBooms = feat.booms;
    for (let i = 0; i < nBooms; i++) {
        const a = (i / nBooms) * Math.PI * 2 + 0.5 + fl * 0.45;
        const bx = Math.cos(a) * r * 0.55, by = Math.sin(a) * r * 0.5;
        drillBoom(bin, g, [bx, by, zGantry + 0.7 * k], [focus[0] + bx * 0.35, focus[1] + by * 0.35, focus[2]], Math.max(0.8, k));
    }
    // purpose-built working tools (class-identity round): the bucket-wheel
    // excavator head leads the ship on a yoke off the gantry - the same tool
    // language scaled up the whole miner ladder
    if (feat.bucketR) {
        const wc = [0, -r * 0.32, zFore + feat.boomReach * 0.9];
        bucketWheel(bin, g, wc, feat.bucketR, feat.bucketR * 0.42);
        for (const side of [1, -1]) {
            strut(bin, 'armor', [side * r * 0.5, r * 0.05, zGantry + 0.8 * k],
                [side * feat.bucketR * 0.6, wc[1], wc[2]], 0.06 * k, g);
        }
    }
    // ore intake maw on the drum face: where the conveyor feeds the crusher
    intakeMaw(bin, g, [0, -r * 0.28, zDrum + drumLen / 2 + 0.05], r * 0.75, r * 0.45);
    // conveyor spine from the work head back over the gantry into the maw
    const convLen = zGantry + 0.6 * k - (zDrum + drumLen / 2) + 0.5 * k;
    const conv = new THREE.BoxGeometry(r * 0.42, r * 0.2, convLen);
    conv.rotateX(0.22);
    uvPatch(conv, g, 0.2);
    bin.add('mech', conv, { pos: [0, r * 0.28, zDrum + drumLen / 2 + convLen * 0.4] });
    const convC = zDrum + drumLen / 2 + convLen * 0.4;
    for (let ci = 0; ci < 4; ci++) {
        const cz = zDrum + drumLen / 2 + (ci + 0.5) * convLen * 0.22;
        const roller = new THREE.CylinderGeometry(r * 0.07, r * 0.07, r * 0.5, 10);
        roller.rotateZ(Math.PI / 2);
        uvPatch(roller, g, 0.05);
        bin.add('trim', roller, { pos: [0, r * 0.28 + r * 0.12 - (cz - convC) * 0.22, cz], subPart: true });
    }
    // command cab atop the gantry
    commandModule(bin, g, [0, r * 0.85, zGantry + 0.4 * k], Math.max(0.65, k * 0.6));
    floodMast(bin, g, [r * 0.5, r * 0.6, zGantry + 0.6 * k], 0.5 * Math.max(1, k), Math.max(0.8, k));
    floodMast(bin, g, [-r * 0.5, r * 0.6, zGantry + 0.6 * k], 0.4 * Math.max(1, k), Math.max(0.8, k));
    radiatorWing(bin, g, [0.1, -r * 0.75, zDrum - drumLen * 0.35], 0.7 * k, 0.55 * k, 0.5);
    engineBlock(bin, g, { zCap: zAft, xs: engineXs(feat.engines ?? 1, 0.5 * k), s: Math.max(0.75, k * 0.65), skirtW: r * 1.5, skirtH: r * 1.0 });
    for (const [x, y] of [[r * 0.7, r * 0.6], [-r * 0.7, r * 0.6], [r * 0.7, -r * 0.6], [-r * 0.7, -r * 0.6]]) {
        rcsQuad(bin, g, [x, y, zGantry + 0.5 * k], 0.85);
        rcsQuad(bin, g, [x * 0.8, y * 0.8, zAft + 0.8 * k], 0.85);
    }
    // greebles over the drum surface
    const drumSampler = (r2) => {
        const a = r2.range(0.3, Math.PI - 0.3) * r2.sign();
        const z = zDrum + r2.range(-0.45, 0.45) * drumLen;
        const px = Math.sin(a) * r * 1.01, py = Math.cos(a) * r * 1.01;
        return { p: [px, py, z], n: [Math.sin(a), Math.cos(a), 0], t: [0, 0, 1], s: 0.7 };
    };
    greebleField(bin, g, feat.greebleBudget || 200, drumSampler);
    // donor kitbash: Kenney machine housings by the gantry, pipework over the
    // drum and support cradles under the hoppers
    donorPart(ctx, 'machine_generator', 'mech', { pos: [r * 0.45, r * 0.35, zGantry - 0.5 * k], scale: [r * 0.7, r * 0.7, r * 0.7] });
    donorPart(ctx, 'machine_barrel', 'trim', { pos: [-r * 0.5, r * 0.35, zGantry - 0.7 * k], scale: [r * 0.55, r * 0.55, r * 0.55] });
    donorPart(ctx, 'pipe_cross', 'mech', { pos: [0, r * 0.95, zDrum], scale: [r * 0.8, r * 0.8, r * 0.8] });
    donorPart(ctx, 'supports_low', 'mech', { pos: [0, -r * 1.15, zDrum - drumLen * 0.25], scale: [r * 0.9, r * 0.9, r * 0.9] });
}

// ---- bomber: ordnance frame (spine or twin truss, bomb racks, no wings) ----

export function buildBomber(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const s = Math.max(0.7, k);
    const twin = !!feat.twinTruss;
    const hw = feat.spineHW ?? 0.16 * s;
    // spine: heavy beam (single) or twin truss rails with cross bridges
    if (twin) {
        for (const side of [1, -1]) {
            trussBox(bin, g, zFore - 1.0 * s, zAft + 1.2 * s, hw * 0.5, hw * 0.5, { x: side * feat.trussGap, railSize: 0.05 * s });
        }
        for (let z = zFore - 1.4 * s; z > zAft + 1.3 * s; z -= 0.8 * s) {
            strut(bin, 'armor', [-feat.trussGap, hw * 0.4, z], [feat.trussGap, hw * 0.4, z], 0.07 * s, g);
            strut(bin, 'armor', [-feat.trussGap, -hw * 0.4, z], [feat.trussGap, -hw * 0.4, z], 0.07 * s, g);
        }
    } else {
        const beam = bevelPlate(hw * 2, hw * 1.6, zFore - zAft - 2.0 * s, 0.05 * s);
        uvPatch(beam, g, 0.3);
        bin.add('armor', beam, { pos: [0, -hw * 0.8, (zFore + zAft) / 2 - 0.2 * s] });
        // dorsal conduit ridge
        tube(bin, 'mech', [0, hw * 0.95, zFore - 1.2 * s], [0, hw * 0.95, zAft + 1.4 * s], 0.05 * s, 8, g);
    }
    // armoured cockpit block at the bow
    const cab = bevelPlate(0.5 * s, 0.34 * s, 0.7 * s, 0.06 * s);
    uvPatch(cab, g, 0.2);
    bin.add('armor', cab, { pos: [0, -0.17 * s, zFore - 0.45 * s] });
    const cabWin = new THREE.BoxGeometry(0.34 * s, 0.05 * s, 0.014);
    uvTransform(cabWin, s, 0.045, g.range(0, 0.4), g.int(0, 15) / 16 + 0.012);
    bin.add('windows', cabWin, { pos: [0, 0.05 * s, zFore - 0.1 * s], subPart: true });
    strut(bin, 'trim', [-0.2 * s, 0.18 * s, zFore - 0.12 * s], [0.2 * s, 0.18 * s, zFore - 0.12 * s], 0.03 * s, g);
    // ordnance spars: every spar carries pallets - if a spar carried nothing
    // it would not exist. The hung ordnance IS the identity (class-identity
    // round): alternating spars carry fat bombs and long torpedoes, every
    // store visible in rows under its rack.
    const rackRows = feat.rackRows ?? 1;
    for (let si = 0; si < feat.sparZ.length; si++) {
        const sz = feat.sparZ[si];
        const kind = si % 2 ? 'torp' : 'bomb';
        for (let row = 0; row < rackRows; row++) {
            const y = -hw * 0.7 - row * 0.42 * s;
            const span = feat.sparSpan * (1 - row * 0.18);
            strut(bin, 'armor', [-span, y, sz], [span, y, sz], 0.07 * s, g);
            for (const side of [1, -1]) {
                tube(bin, 'mech', [side * span * 0.55, y, sz], [side * span * 0.3, y + 0.3 * s + row * 0.42 * s, sz + 0.2 * s], 0.02 * s, 5, g);
            }
            const nP = feat.palletsPerSpar ?? 2;
            for (let p = 0; p < nP; p++) {
                const x = (p - (nP - 1) / 2) * (span * 1.7 / Math.max(1, nP - 1) || 0);
                const m = new THREE.Matrix4().makeTranslation(x, y - 0.05 * s, sz);
                m.multiply(new THREE.Matrix4().makeRotationX(Math.PI)); // pallet hangs downward
                bombPallet(bin, g, m, feat.palletN ?? 2, feat.palletM ?? 3, s * 0.9, { kind });
            }
        }
    }
    if (twin && feat.midPallets) {
        // palletised clusters bridged between the twin trusses
        for (let mi = 0; mi < feat.midPallets.length; mi++) {
            const m = new THREE.Matrix4().makeTranslation(0, -hw * 0.2, feat.midPallets[mi]);
            m.multiply(new THREE.Matrix4().makeRotationX(Math.PI));
            bombPallet(bin, g, m, 2, 3, s, { kind: mi % 2 ? 'bomb' : 'torp' });
        }
    }
    // drive block + RCS quads (attitude control is RCS, never a tail)
    engineBlock(bin, g, { zCap: zAft, xs: engineXs(feat.engines ?? 2, twin ? feat.trussGap : 0.34 * s), s: 0.7 * s, skirtW: (twin ? feat.trussGap * 2.6 : 0.9 * s), skirtH: 0.55 * s });
    for (const [x, y, z] of [
        [0.3 * s, 0.2 * s, zFore - 0.3 * s], [-0.3 * s, 0.2 * s, zFore - 0.3 * s],
        [0.35 * s, -0.2 * s, zAft + 1.0 * s], [-0.35 * s, -0.2 * s, zAft + 1.0 * s],
    ]) rcsQuad(bin, g, [x, y, z], 0.8 * s);
    dishAntenna(bin, g, [0, hw * 0.9, zFore - 0.9 * s], 0.14 * s, 0.7 * s);
    // donor kitbash: Kenney rocket stages hung as heavy ordnance at the spar tips
    for (let i = 0; i < feat.sparZ.length; i++) {
        if (i % 2 === 1) continue;
        for (const side of [1, -1]) {
            donorPart(ctx, side > 0 ? 'rocket_sidesA' : 'rocket_sidesB', 'armor',
                { rotX: Math.PI / 2, pos: [side * feat.sparSpan * 0.85, -hw * 0.7 - 0.28 * s, feat.sparZ[i]], scale: [0.34 * s, 0.34 * s, 0.34 * s] });
        }
    }
    // spine greebles
    const spineSampler = (r2) => {
        const z = r2.range(zAft + 1.5 * s, zFore - 1.2 * s);
        const x = r2.range(-0.8, 0.8) * (twin ? feat.trussGap : hw);
        return { p: [x, twin ? hw * 0.55 : hw * 0.85, z], n: [0, 1, 0], t: [0, 0, 1], s: 0.55 };
    };
    greebleField(bin, g, feat.greebleBudget || 120, spineSampler);
}

// ---- stealth bomber: faceted low-signature slab with internal bays ---------

export function buildStealth(ctx) {
    const { bin, g, rec, feat } = ctx;
    const frame = hullFromCurves(bin, g, rec.hull, { profile: CHINE_PROFILE, flavour: rec.flavour || 0 });
    const k = frame.k;
    conformalPlating(bin, g, frame, { missChance: 0.05, secondaryChance: 0.05 });
    // chine trim: knife edges along the widest line
    const zs = [];
    for (let z = frame.zBow * 0.85; z > frame.zStern * 0.9; z -= 0.5 * k) zs.push(z);
    for (let i = 0; i < zs.length - 1; i++) {
        for (const side of [1, -1]) {
            strut(bin, 'armor', [side * frame.W(zs[i]), 0, zs[i]], [side * frame.W(zs[i + 1]), 0, zs[i + 1]], 0.035 * k, g);
        }
    }
    // internal weapon bays (class-identity round: a bomber with invisible
    // ordnance is just a truss): ventral bays with their DOORS swung open -
    // angled door panels hanging off both bay lips - and a rack of fat bomb
    // noses visible in the dark slot
    for (const [bz, bl] of feat.bays) {
        const bw = frame.W(bz) * 0.34;
        const yBay = -frame.H(bz) * 0.82;
        const mouth = new THREE.BoxGeometry(bw, 0.03, bl);
        uvTransform(mouth, 0.001, 0.001, 0.002, 0.002);
        bin.add('windows', mouth, { pos: [0, yBay, bz] });
        const seam = new THREE.BoxGeometry(0.014, 0.035, bl * 0.96);
        bin.add('engine_glow', seam, { pos: [0, yBay, bz], subPart: true });
        strut(bin, 'trim', [-bw * 0.55, yBay - 0.01, bz - bl / 2], [-bw * 0.55, yBay - 0.01, bz + bl / 2], 0.025, g);
        strut(bin, 'trim', [bw * 0.55, yBay - 0.01, bz - bl / 2], [bw * 0.55, yBay - 0.01, bz + bl / 2], 0.025, g);
        // open bay doors: faceted panels hinged at the lips, swung ~70 deg
        for (const side of [1, -1]) {
            const door = bevelPlate(bw * 0.52, 0.022 * k, bl * 0.96, 0.01 * k);
            uvPatch(door, g, 0.15);
            const mD = new THREE.Matrix4().makeRotationZ(side * 1.25);
            mD.setPosition(side * bw * 0.58, yBay - 0.16 * k, bz);
            bin.add('armor', door, { basis: mD });
            strut(bin, 'trim', [side * bw * 0.58, yBay - 0.02, bz - bl * 0.46], [side * bw * 0.4, yBay - 0.3 * k, bz - bl * 0.46], 0.02, g);
            strut(bin, 'trim', [side * bw * 0.58, yBay - 0.02, bz + bl * 0.46], [side * bw * 0.4, yBay - 0.3 * k, bz + bl * 0.46], 0.02, g);
        }
        // ordnance rack in the bay: bomb noses proud of the slot
        const nB = Math.max(3, Math.floor(bl / (0.28 * k)));
        for (let i = 0; i < nB; i++) {
            const z = bz - bl / 2 + ((i + 0.5) * bl) / nB;
            const bomb = new THREE.CapsuleGeometry(0.055 * k, 0.16 * k, 4, 10);
            uvPatch(bomb, g, 0.08);
            bin.add('armor', bomb, { pos: [0, yBay - 0.05 * k, z], subPart: i > 0 });
            const band = new THREE.CylinderGeometry(0.058 * k, 0.058 * k, 0.02 * k, 10);
            uvPatch(band, g, 0.05);
            bin.add('trim', band, { pos: [0, yBay - 0.09 * k, z], subPart: true });
        }
    }
    // recessed engine slots at the stern (no protruding bells)
    const zCap = frame.zStern;
    for (const ex of engineXs(feat.engines ?? 2, frame.W(zCap + 0.4 * k) * 0.8)) {
        const slot = new THREE.BoxGeometry(0.34 * k, 0.1 * k, 0.1 * k);
        uvPatch(slot, g, 0.1);
        bin.add('mech', slot, { pos: [ex, 0, zCap + 0.02] });
        const glow = new THREE.BoxGeometry(0.28 * k, 0.05 * k, 0.03);
        bin.add('engine_glow', glow, { pos: [ex, 0, zCap - 0.04 * k], subPart: true });
    }
    // faceted sensor blister, canopy strip
    const blister = new THREE.SphereGeometry(0.14 * k, 6, 4);
    blister.scale(1.6, 0.45, 1.6);
    uvPatch(blister, g, 0.15);
    bin.add('armor', blister, { pos: [0, frame.deckYAt(0.35 * frame.zBow, 0), 0.35 * frame.zBow] });
    const strip = new THREE.BoxGeometry(0.2 * k, 0.03, 0.014);
    uvTransform(strip, 0.4, 0.04, 0.1, 4 / 16 + 0.012);
    bin.add('windows', strip, { pos: [0, 0.05 * k, frame.zBow * 0.92], subPart: true });
    for (const zf of [0.7, -0.75]) rcsRing(bin, g, frame, zf > 0 ? zf * frame.zBow : -zf * frame.zStern, 0.6);
    greebleZones(bin, g, frame, feat, feat.greebleBudget || 90, { engX: [], zCap });
}

// ---- colony ship: ceramic hab drums, domes, dense windows ------------------

export function buildColony(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const r = feat.habR;
    // hab drums in a row with dense porthole belts. Class-identity round:
    // "colony ships must be bulkier" - the fattest hulls in the fleet, a town
    // in transit: swollen tri-lobed pressure volume, greenhouse glazing glow,
    // a crown of habitat domes, visible life-support mass.
    const flC = rec.flavour || 0;
    for (const [dz, dl] of feat.drums) {
        drumBody(bin, g, dz, dl, r, { ribs: 4, seg: 22 + Math.round(flC * 10) });
        for (const beltY of [-0.35, 0.1, 0.5]) {
            const belt = new THREE.CylinderGeometry(r * 1.012, r * 1.012, 0.06, 22, 1, true);
            belt.rotateX(Math.PI / 2);
            uvTransform(belt, 3.0, 0.045, g.range(0, 0.3), g.int(0, 15) / 16 + 0.012);
            bin.add('windows', belt, { pos: [0, 0, dz + beltY * dl * 0.5], subPart: true });
        }
        // swollen flank pressure pods: the hull reads as volume, not spine
        for (const side of [1, -1]) {
            drumBody(bin, g, dz - 0.05 * dl, dl * 0.78, r * 0.52, { x: side * r * 1.08, y: -r * 0.24, ribs: 3, seg: 18 });
        }
        // greenhouse glazing: broad lit conservatory panels on the upper flanks
        for (const thetaC of [Math.PI - 0.62, Math.PI + 0.22]) {
            const glaze = new THREE.CylinderGeometry(r * 1.025, r * 1.025, dl * 0.52, 20, 1, true, thetaC, 0.4);
            glaze.rotateX(Math.PI / 2);
            uvTransform(glaze, 0.3, 0.15, 0.05, 3 / 16 + 0.012);
            bin.add('windows', glaze, { pos: [0, 0, dz + 0.05 * dl], subPart: true });
            for (const dt of [0.1, 0.3]) {
                const a = thetaC + dt;
                const mull = new THREE.BoxGeometry(0.03 * k, 0.03 * k, dl * 0.52);
                uvPatch(mull, g, 0.06);
                bin.add('trim', mull, { pos: [Math.sin(a) * r * 1.03, -Math.cos(a) * r * 1.03, dz + 0.05 * dl], subPart: true });
            }
        }
    }
    // habitat dome crown along the drum tops
    const domeSpots = [];
    for (const [dz, dl] of feat.drums) {
        domeSpots.push([0, r * 0.92, dz + 0.16 * dl]);
        domeSpots.push([r * 0.48, r * 0.76, dz - 0.18 * dl]);
        domeSpots.push([-r * 0.48, r * 0.76, dz - 0.18 * dl]);
    }
    for (let di = 0; di < Math.min(feat.domes, domeSpots.length); di++) {
        habDome(bin, g, domeSpots[di], r * (di % 3 === 0 ? 0.48 : 0.32));
    }
    commandModule(bin, g, [0, 0, zFore - 0.5 * Math.max(0.8, k * 0.7)], Math.max(0.8, k * 0.7));
    // stores: sphere tanks aft of the drums
    for (const fs of feat.fuelSpheres || []) fuelSphere(bin, g, fs, fs[3] ?? r * 0.45);
    trussBox(bin, g, feat.drums[feat.drums.length - 1][0] - feat.drums[feat.drums.length - 1][1] / 2, zAft + 1.2 * k, r * 0.4, r * 0.38, { railSize: 0.05 * k });
    radiatorWing(bin, g, [0.1, -r * 0.5, zAft + 1.1 * k], 0.9 * k, 0.6 * k, 0.35);
    engineBlock(bin, g, { zCap: zAft, xs: engineXs(feat.engines ?? 2, 0.5 * k), s: Math.max(0.8, k * 0.7), skirtW: r * 1.4, skirtH: r * 1.0 });
    for (const [x, y, z] of [[r * 0.7, r * 0.5, zFore - 0.4], [-r * 0.7, r * 0.5, zFore - 0.4], [r * 0.6, -r * 0.5, zAft + 0.8], [-r * 0.6, -r * 0.5, zAft + 0.8]]) {
        rcsQuad(bin, g, [x, y, z], 0.85);
    }
    const beltSampler = (r2) => {
        const drum = feat.drums[r2.int(0, feat.drums.length - 1)];
        const a = r2.range(0.4, Math.PI - 0.4) * r2.sign();
        const z = drum[0] + r2.range(-0.4, 0.4) * drum[1];
        return { p: [Math.sin(a) * r * 1.005, Math.cos(a) * r * 1.005, z], n: [Math.sin(a), Math.cos(a), 0], t: [0, 0, 1], s: 0.55 };
    };
    greebleField(bin, g, feat.greebleBudget || 140, beltSampler);
    // donor kitbash: Kenney life-support machine housing aft of the drums and
    // a structure truss segment on the keel
    const zPlant = feat.drums[feat.drums.length - 1][0] - feat.drums[feat.drums.length - 1][1] / 2 - 0.5 * k;
    donorPart(ctx, 'machine_generatorLarge', 'mech', { pos: [0, -r * 0.15, zPlant], scale: [r * 0.75, r * 0.75, r * 0.75] });
    donorPart(ctx, 'structure_detailed', 'mech', { pos: [0, -r * 0.55, zPlant - 0.9 * k], scale: [r * 0.8, r * 0.8, r * 0.8] });
}

// ---- mine layer: dispenser drums and open mine racks -----------------------

export function buildMinelayer(ctx) {
    const { bin, g, rec, feat } = ctx;
    const frame = hullFromCurves(bin, g, rec.hull, { profile: BOX_PROFILE, flavour: rec.flavour || 0 });
    const k = frame.k;
    conformalPlating(bin, g, frame, { missChance: 0.15 });
    // lateral dispenser drums with aft-facing muzzles
    for (const [dz, side] of feat.drums) {
        const x = side * (frame.W(dz) + 0.22 * k);
        const drum = new THREE.CylinderGeometry(0.26 * k, 0.26 * k, 1.1 * k, 14);
        drum.rotateX(Math.PI / 2);
        uvPatch(drum, g, 0.25);
        bin.add('mech', drum, { pos: [x, 0, dz] });
        for (const t of [-0.4, 0, 0.4]) {
            const band = new THREE.CylinderGeometry(0.275 * k, 0.275 * k, 0.05 * k, 14);
            band.rotateX(Math.PI / 2);
            uvPatch(band, g, 0.1);
            bin.add('trim', band, { pos: [x, 0, dz + t * 1.1 * k], subPart: true });
        }
        const muzzle = new THREE.CylinderGeometry(0.2 * k, 0.24 * k, 0.16 * k, 14);
        muzzle.rotateX(Math.PI / 2);
        uvPatch(muzzle, g, 0.1);
        bin.add('armor', muzzle, { pos: [x, 0, dz - 0.62 * k], subPart: true });
        strut(bin, 'armor', [side * frame.W(dz) * 0.8, 0.2 * k, dz + 0.3 * k], [x, 0.1 * k, dz + 0.3 * k], 0.07 * k, g);
        strut(bin, 'armor', [side * frame.W(dz) * 0.8, -0.2 * k, dz - 0.3 * k], [x, -0.1 * k, dz - 0.3 * k], 0.07 * k, g);
    }
    // open dorsal mine racks: spiked spheres in cradle rows
    const rackZ0 = feat.rack.z0, rackZ1 = feat.rack.z1;
    const y0 = frame.deckYAt((rackZ0 + rackZ1) / 2, 0) + 0.04 * k;
    for (const side of [1, -1]) {
        strut(bin, 'mech', [side * 0.22 * k, y0, rackZ0], [side * 0.22 * k, y0, rackZ1], 0.04 * k, g);
    }
    let mi = 0;
    for (let z = rackZ0 - 0.15 * k; z > rackZ1 + 0.05 * k; z -= 0.3 * k, mi++) {
        for (const side of [1, -1]) {
            if (g.chance(0.18)) continue; // dispensed slot
            const mx = side * 0.11 * k;
            const mine = new THREE.SphereGeometry(0.08 * k, 8, 6);
            uvPatch(mine, g, 0.08);
            bin.add(mi % 2 ? 'armor' : 'mech', mine, { pos: [mx, y0 + 0.1 * k, z] });
            for (const d of [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, -1]]) {
                const spike = new THREE.ConeGeometry(0.014 * k, 0.05 * k, 5);
                const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(...d));
                bin.add('trim', spike, { quat: q, pos: [mx + d[0] * 0.09 * k, y0 + 0.1 * k + d[1] * 0.09 * k, z + d[2] * 0.09 * k], subPart: true });
            }
        }
    }
    // donor kitbash: Kenney barrel rails as ready-rack mine dispensers beside
    // the dorsal racks
    for (const side of [1, -1]) {
        donorPart(ctx, 'barrels_rail', 'trim',
            { rotY: Math.PI / 2, pos: [side * 0.42 * k, y0 - 0.02 * k, (rackZ0 + rackZ1) / 2], scale: [0.5 * k, 0.5 * k, 0.5 * k] });
    }
    // crane mast over the racks
    floodMast(bin, g, [0, y0, rackZ0 + 0.2 * k], 0.5 * k, k);
    commandModule(bin, g, [0, frame.deckYAt(0.62 * frame.zBow, 0) + 0.05 * k, 0.62 * frame.zBow], Math.max(0.6, k * 0.7));
    windowRows(bin, g, frame, 0.4 * frame.zBow, 0.5 * frame.zStern, { step: 0.4, boatBay: false });
    radiatorPair(bin, g, frame, 0.35 * frame.zStern, 0.7 * Math.max(1, k));
    const zCap = frame.zStern;
    const engXsArr = engineXs(rec.features.engines ?? 2, 0.4 * k);
    engineBlock(bin, g, { zCap, xs: engXsArr, s: Math.max(0.75, k * 0.7), skirtW: frame.W(zCap + 0.4 * k) * 2.1, skirtH: frame.H(zCap + 0.4 * k) * 1.3 });
    rcsRing(bin, g, frame, 0.75 * frame.zBow, 0.8);
    rcsRing(bin, g, frame, 0.8 * frame.zStern, 0.8);
    greebleZones(bin, g, frame, feat, feat.greebleBudget || 200, { engX: engXsArr, zCap });
}

// ---- modular: Nubian socket spine / Meta Morph radial hub ------------------

const MODULE_KINDS = ['cargo', 'tank', 'hab', 'weapon', 'sensor', 'radiator'];

function attachModule(bin, g, kind, pos, s) {
    if (kind === 'cargo') {
        containerBlock(bin, g, [pos[0], pos[1] + 0.2 * s, pos[2]], 0.5 * s, 0.4 * s, 0.7 * s);
    } else if (kind === 'tank') {
        fuelSphere(bin, g, [pos[0], pos[1] + 0.26 * s, pos[2]], 0.28 * s);
    } else if (kind === 'hab') {
        const drum = new THREE.CylinderGeometry(0.24 * s, 0.24 * s, 0.6 * s, 14);
        drum.rotateX(Math.PI / 2);
        uvPatch(drum, g, 0.2);
        bin.add('armor', drum, { pos: [pos[0], pos[1] + 0.24 * s, pos[2]] });
        const belt = new THREE.CylinderGeometry(0.245 * s, 0.245 * s, 0.05 * s, 14, 1, true);
        belt.rotateX(Math.PI / 2);
        uvTransform(belt, 1.6, 0.045, g.range(0, 0.3), g.int(0, 15) / 16 + 0.012);
        bin.add('windows', belt, { pos: [pos[0], pos[1] + 0.24 * s, pos[2]], subPart: true });
    } else if (kind === 'weapon') {
        const fakeFrame = { deckYAt: () => pos[1], H: () => 1, W: () => 1 };
        turret(bin, g, fakeFrame, pos[2], 1, 0.8 * s, { x: pos[0] });
    } else if (kind === 'sensor') {
        dishAntenna(bin, g, pos, 0.2 * s, s);
    } else {
        radiatorWing(bin, g, [pos[0], pos[1] + 0.15 * s, pos[2]], 0.5 * s, 0.4 * s, 0.2);
    }
}

export function buildModular(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const s = Math.max(0.9, k);
    const flM = rec.flavour || 0;
    if (feat.radial) {
        // Meta Morph: central hub sphere + radial arms ending in modules
        const hub = new THREE.SphereGeometry(0.62 * s, 18 + Math.round(flM * 10), 12 + Math.round(flM * 6));
        uvPatch(hub, g, 0.3);
        bin.add('armor', hub, { pos: [0, 0, 0] });
        const band = new THREE.CylinderGeometry(0.63 * s, 0.63 * s, 0.12 * s, 18);
        uvPatch(band, g, 0.1);
        bin.add('trim', band, { pos: [0, 0, 0], subPart: true });
        const belt = new THREE.CylinderGeometry(0.635 * s, 0.635 * s, 0.06 * s, 18, 1, true);
        uvTransform(belt, 2.5, 0.045, 0.05, 8 / 16 + 0.012);
        bin.add('windows', belt, { pos: [0, 0.18 * s, 0], subPart: true });
        const arms = feat.arms ?? 4;
        for (let i = 0; i < arms; i++) {
            const a = (i / arms) * Math.PI * 2 + Math.PI / arms + flM * 0.5;
            const dx = Math.cos(a), dy = Math.sin(a);
            const tipD = 1.5 * s;
            trussBox(bin, g, 0.25 * s, -0.25 * s, 0.1 * s, 0.1 * s, { x: dx * tipD * 0.5, y: dy * tipD * 0.5, railSize: 0.035 * s });
            strut(bin, 'mech', [dx * 0.6 * s, dy * 0.6 * s, 0.15 * s], [dx * tipD, dy * tipD, 0.1 * s], 0.05 * s, g);
            strut(bin, 'mech', [dx * 0.6 * s, dy * 0.6 * s, -0.15 * s], [dx * tipD, dy * tipD, -0.1 * s], 0.05 * s, g);
            const kind = MODULE_KINDS[i % MODULE_KINDS.length];
            attachModule(bin, g, kind, [dx * tipD, dy * tipD, 0], s * 0.9);
        }
        commandModule(bin, g, [0, 0.1 * s, zFore - 0.5 * s], 0.8 * s);
        tube(bin, 'mech', [0, 0, 0.6 * s], [0, 0.1 * s, zFore - 0.9 * s], 0.08 * s, 8, g);
        tube(bin, 'mech', [0, 0, -0.6 * s], [0, 0, zAft + 1.1 * s], 0.08 * s, 8, g);
    } else {
        // Nubian: socket spine - truss keel with module sockets dorsal,
        // ventral and lateral; every socket filled with a standard module
        trussBox(bin, g, zFore - 1.1 * s, zAft + 1.3 * s, 0.24 * s, 0.24 * s, { railSize: 0.06 * s });
        const beam = bevelPlate(0.34 * s, 0.28 * s, zFore - zAft - 2.6 * s, 0.04 * s);
        uvPatch(beam, g, 0.3);
        bin.add('armor', beam, { pos: [0, -0.14 * s, (zFore + zAft) / 2] });
        commandModule(bin, g, [0, 0.12 * s, zFore - 0.55 * s], 0.85 * s);
        let ki = 0;
        for (const sz of feat.socketZ) {
            // dorsal socket
            const collar = new THREE.CylinderGeometry(0.12 * s, 0.14 * s, 0.08 * s, 10);
            uvPatch(collar, g, 0.08);
            bin.add('trim', collar, { pos: [0, 0.3 * s, sz] });
            attachModule(bin, g, MODULE_KINDS[ki++ % MODULE_KINDS.length], [0, 0.36 * s, sz], s * 0.9);
            // ventral socket
            const collar2 = new THREE.CylinderGeometry(0.12 * s, 0.14 * s, 0.08 * s, 10);
            uvPatch(collar2, g, 0.08);
            bin.add('trim', collar2, { pos: [0, -0.3 * s, sz], rotX: Math.PI });
            const kind2 = MODULE_KINDS[(ki + 2) % MODULE_KINDS.length];
            if (kind2 === 'tank' || kind2 === 'cargo') attachModule(bin, g, kind2, [0, -0.95 * s, sz], s * 0.8);
            else attachModule(bin, g, 'cargo', [0, -0.95 * s, sz], s * 0.8);
            // lateral sockets on alternating stations
            if (ki % 2 === 0) {
                for (const side of [1, -1]) {
                    strut(bin, 'mech', [side * 0.24 * s, 0, sz], [side * 0.6 * s, 0, sz], 0.05 * s, g);
                    attachModule(bin, g, side > 0 ? 'tank' : 'sensor', [side * 0.75 * s, -0.2 * s, sz], s * 0.7);
                }
            }
        }
    }
    radiatorWing(bin, g, [0.1, -0.3 * s, zAft + 1.0 * s], 0.8 * s, 0.5 * s, 0.4);
    engineBlock(bin, g, { zCap: zAft, xs: engineXs(feat.engines ?? 3, 0.42 * s), s: 0.85 * s, skirtW: 1.4 * s, skirtH: 0.6 * s });
    for (const [x, y, z] of [[0.4 * s, 0.3 * s, zFore - 0.3 * s], [-0.4 * s, 0.3 * s, zFore - 0.3 * s], [0.4 * s, -0.3 * s, zAft + 0.9 * s], [-0.4 * s, -0.3 * s, zAft + 0.9 * s]]) {
        rcsQuad(bin, g, [x, y, z], 0.85);
    }
    const spineSampler = (r2) => {
        const z = r2.range(zAft + 1.4 * s, zFore - 1.2 * s);
        return { p: [r2.range(-0.14, 0.14) * s, 0.26 * s, z], n: [0, 1, 0], t: [0, 0, 1], s: 0.5 };
    };
    greebleField(bin, g, feat.greebleBudget || 150, spineSampler);
}

// ---- assault transport: armoured wedge with drop pods ----------------------

export function buildAssault(ctx) {
    const { bin, g, rec, feat } = ctx;
    const frame = hullFromCurves(bin, g, rec.hull, { profile: BOX_PROFILE, flavour: rec.flavour || 0 });
    const k = frame.k;
    conformalPlating(bin, g, frame, { missChance: 0.08, secondaryChance: 0.22 });
    // family prow ruling: the armoured underbite blade, assault scale
    prowBlade(bin, g, frame, { lenFrac: 0.2, bands: 3 });
    gothicBands(bin, g, frame, feat.bandZ || []);
    // bow assault ramp: trim-framed dark slab under the prow
    const rz = 0.62 * frame.zBow;
    const ramp = new THREE.BoxGeometry(frame.W(rz) * 0.7, 0.05 * k, 1.1 * k);
    ramp.rotateX(0.18);
    uvTransform(ramp, 0.001, 0.001, 0.002, 0.002);
    bin.add('windows', ramp, { pos: [0, -frame.H(rz) * 0.9, rz] });
    strut(bin, 'trim', [-frame.W(rz) * 0.36, -frame.H(rz) * 0.88, rz - 0.55 * k], [-frame.W(rz) * 0.36, -frame.H(rz) * 0.98, rz + 0.55 * k], 0.05 * k, g);
    strut(bin, 'trim', [frame.W(rz) * 0.36, -frame.H(rz) * 0.88, rz - 0.55 * k], [frame.W(rz) * 0.36, -frame.H(rz) * 0.98, rz + 0.55 * k], 0.05 * k, g);
    // drop pod rows on the ventral flanks
    for (const pz of feat.podZ) {
        for (const side of [1, -1]) {
            for (let i = 0; i < 3; i++) {
                const x = side * frame.W(pz) * (0.3 + i * 0.25);
                const pod = new THREE.CapsuleGeometry(0.11 * k, 0.2 * k, 4, 10);
                uvPatch(pod, g, 0.12);
                bin.add(i % 2 ? 'mech' : 'armor', pod, { pos: [x, -frame.H(pz) * 0.92 - 0.08 * k, pz] });
                const clampG = new THREE.BoxGeometry(0.06 * k, 0.1 * k, 0.06 * k);
                uvPatch(clampG, g, 0.05);
                bin.add('trim', clampG, { pos: [x, -frame.H(pz) * 0.88, pz], subPart: true });
            }
        }
    }
    for (const z of feat.dorsalTurretZ || []) turret(bin, g, frame, z, 1, feat.turretScale ?? 1.0);
    for (const z of feat.pdMountZ || []) pdMounts(bin, g, frame, z, Math.max(0.8, k * 0.7));
    if (feat.tower) bridgeTower(bin, g, frame, feat.tower.z0, feat.tower.z1, feat.tower.s ?? Math.max(0.8, k * 0.75));
    // donor kitbash: Kenney cargo craft clamped dorsally as drop-craft
    for (let i = 0; i < (feat.podZ || []).length; i++) {
        const z = feat.podZ[i] + 0.55 * k;
        donorPart(ctx, i % 2 ? 'craft_cargoA' : 'craft_cargoB', 'mech',
            { pos: [(i % 2 ? -1 : 1) * frame.W(z) * 0.4, frame.deckYAt(z, 0) - 0.02, z], scale: [0.5 * k, 0.5 * k, 0.5 * k] });
    }
    windowRows(bin, g, frame, 0.45 * frame.zBow, 0.6 * frame.zStern, { step: 0.3, bayZ: 0.3 * frame.zStern });
    radiatorPair(bin, g, frame, 0.45 * frame.zStern, Math.max(0.8, k * 0.8));
    const zCap = frame.zStern;
    const engXsArr = engineXs(feat.engines ?? 4, 0.4 * k);
    engineBlock(bin, g, { zCap, xs: engXsArr, s: Math.max(0.8, k * 0.7), skirtW: frame.W(zCap + 0.4 * k) * 2.15, skirtH: frame.H(zCap + 0.4 * k) * 1.3 });
    rcsRing(bin, g, frame, 0.78 * frame.zBow, Math.max(0.8, k * 0.7));
    rcsRing(bin, g, frame, 0.85 * frame.zStern, Math.max(0.8, k * 0.7));
    greebleZones(bin, g, frame, feat, feat.greebleBudget || 420, { engX: engXsArr, turretZ: feat.dorsalTurretZ || [], zCap });
}

// ---- probe: unmanned instrument platform, disproportionate drive -----------
// Class-identity round ruling: the Armed Probe gets its own hull. UNMANNED
// identity - no windows, no canopy, no habitat mass anywhere; an instrument
// bus hung with sensor booms and dishes, pushed by a drive block sized for a
// ship three times its length.

export function buildProbe(ctx) {
    const { bin, g, rec, feat } = ctx;
    const L = rec.hull.length, k = L / 10;
    const zFore = L * 0.5, zAft = -L * 0.5;
    const s = Math.max(0.5, k);
    // faceted octagonal instrument bus
    const busR = 0.16 * L;
    const oct = [];
    for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2 + Math.PI / 8;
        oct.push([Math.sin(a), Math.cos(a)]);
    }
    const busSta = [
        { z: 0.34 * L, r: 0.55 * busR },
        { z: 0.24 * L, r: busR },
        { z: -0.08 * L, r: busR },
        { z: -0.16 * L, r: 0.7 * busR },
    ].map((st) => ({ z: st.z, pts: oct.map(([px, py]) => [px * st.r, py * st.r]) }));
    bin.add('armor', loft(busSta, { capStart: true, capEnd: true, uScale: 2, vScale: 0.6 }), {});
    // bus facet plates and equipment band
    for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2 + Math.PI / 8;
        const p = [Math.sin(a) * busR * 1.0, Math.cos(a) * busR * 1.0, 0.08 * L];
        const basis = surfaceBasis(p, [Math.sin(a), Math.cos(a), 0], [0, 0, 1]);
        const plate = bevelPlate(busR * 0.62, 0.035 * L, 0.22 * L, 0.01 * L);
        uvPatch(plate, g, 0.2);
        bin.add(i % 3 ? 'armor' : 'trim', plate, { basis, subPart: i > 0 });
    }
    // main dish forward: the probe looks WITH instruments, not windows
    dishAntenna(bin, g, [0, busR * 0.9, 0.3 * L], 0.3 * L, 1.4 * s);
    dishAntenna(bin, g, [busR * 0.7, -busR * 0.5, 0.2 * L], 0.14 * L, 0.8 * s);
    // radial instrument booms with sensor clusters at the tips
    const nBooms = feat.booms ?? 3;
    for (let i = 0; i < nBooms; i++) {
        const a = (i / nBooms) * Math.PI * 2 + Math.PI / 6;
        const dx = Math.cos(a), dy = Math.sin(a);
        const tip = [dx * feat.boomLen * L * 0.42, dy * feat.boomLen * L * 0.42, 0.05 * L];
        strut(bin, 'mech', [dx * busR * 0.9, dy * busR * 0.9, 0.1 * L], tip, 0.022 * L, g);
        strut(bin, 'mech', [dx * busR * 0.9, dy * busR * 0.9, -0.05 * L], [tip[0], tip[1], tip[2] - 0.04 * L], 0.016 * L, g);
        const cluster = new THREE.BoxGeometry(0.07 * L, 0.07 * L, 0.1 * L);
        uvPatch(cluster, g, 0.1);
        bin.add('mech', cluster, { pos: tip });
        const eye = new THREE.SphereGeometry(0.035 * L, 10, 7);
        uvPatch(eye, g, 0.06);
        bin.add('trim', eye, { pos: [tip[0], tip[1], tip[2] + 0.07 * L], subPart: true });
        const whisker = new THREE.CylinderGeometry(0.004 * L, 0.006 * L, 0.3 * L, 5);
        const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(dx, dy, 0));
        uvPatch(whisker, g, 0.04);
        bin.add('mech', whisker, { quat: q, pos: [tip[0] + dx * 0.15 * L, tip[1] + dy * 0.15 * L, tip[2]], subPart: true });
    }
    // radiator wings off the bus
    radiatorWing(bin, g, [0.05 * L, -busR * 0.7, -0.05 * L], 0.3 * L, 0.22 * L, 0.35);
    // disproportionate drive: tanks and a drive block sized for a far larger
    // ship - most of the probe IS the engine
    for (const side of [1, -1]) {
        fuelSphere(bin, g, [side * busR * 0.75, 0, -0.26 * L], busR * 0.62);
    }
    trussBox(bin, g, -0.16 * L, zAft + 0.4 * s, busR * 0.5, busR * 0.5, { railSize: 0.02 * L });
    engineBlock(bin, g, { zCap: zAft, xs: [0], s: 1.35 * s, skirtW: 2.6 * busR, skirtH: 2.2 * busR });
    for (const [x, y] of [[busR * 0.8, busR * 0.8], [-busR * 0.8, busR * 0.8], [busR * 0.8, -busR * 0.8], [-busR * 0.8, -busR * 0.8]]) {
        rcsQuad(bin, g, [x, y, 0.28 * L], 0.7 * s);
        rcsQuad(bin, g, [x * 0.9, y * 0.9, -0.2 * L], 0.7 * s);
    }
    // instrument greebles over the bus skin - equipment, never windows
    const busSampler = (r2) => {
        const a = r2.range(0, Math.PI * 2);
        const z = r2.range(-0.12, 0.28) * L;
        return { p: [Math.sin(a) * busR * 1.03, Math.cos(a) * busR * 1.03, z], n: [Math.sin(a), Math.cos(a), 0], t: [0, 0, 1], s: 0.5 };
    };
    greebleField(bin, g, feat.greebleBudget || 300, busSampler);
}

export const FAMILY_BUILDERS = {
    warship: buildWarship,
    scout: buildScout,
    raider: buildRaider,
    freighter: buildFreighter,
    tanker: buildTanker,
    miner: buildMiner,
    bomber: buildBomber,
    stealth: buildStealth,
    colony: buildColony,
    minelayer: buildMinelayer,
    modular: buildModular,
    assault: buildAssault,
    probe: buildProbe,
};
