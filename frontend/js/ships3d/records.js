// Ship design records - the data side of the pipeline. A record fully
// determines the compiled model: family (which hull grammar), hull curves,
// feature layout, palette and the rng seed. The compiler interprets the
// record; changing a record (or adding one) is how new hulls are made.
//
// This module is dependency-free so node tooling can import it directly.
// All 32 flyable Stars! hulls are covered (stations are a separate wave).

// ---- palettes --------------------------------------------------------------
// Consumed by materials.js / textures.js. Geometry never reads the palette,
// so node-side determinism tests are palette-independent.

export const PALETTES = {
    warship: {
        armorBase: [59, 64, 70],
        paint: ['rgba(96,58,48,0.5)', 'rgba(70,76,56,0.5)', 'rgba(46,50,60,0.55)'],
        paintChance: 0.09, rustChance: 0.35, grimeMul: 1.0,
        trimStyle: 'gothic', trimBase: '#78633c',
        glowStops: ['#ffffff', '#cfeaff', '#5aa8e8', '#02040a'], glowColor: '#bfe4ff',
        windowDark: 0.28, mechTint: '#777c84',
    },
    olive: {
        armorBase: [60, 65, 55],
        paint: ['rgba(96,58,48,0.5)', 'rgba(54,62,44,0.55)', 'rgba(46,50,60,0.5)'],
        paintChance: 0.12, rustChance: 0.4, grimeMul: 1.1,
        trimStyle: 'gothic', trimBase: '#6e5c38',
        glowStops: ['#ffffff', '#cfeaff', '#5aa8e8', '#02040a'], glowColor: '#bfe4ff',
        windowDark: 0.32, mechTint: '#767a70',
    },
    raider: {
        armorBase: [74, 60, 52],
        paint: ['rgba(110,62,40,0.55)', 'rgba(60,52,46,0.55)', 'rgba(88,74,40,0.5)'],
        paintChance: 0.16, rustChance: 0.6, grimeMul: 1.3,
        trimStyle: 'steel', trimBase: '#8a8f96',
        glowStops: ['#fff6e0', '#ffd9a0', '#e88a3a', '#0a0402'], glowColor: '#ffcf9a',
        windowDark: 0.35, mechTint: '#6e6a62',
    },
    industrial: {
        armorBase: [92, 90, 84],
        paint: ['rgba(64,96,128,0.5)', 'rgba(150,96,40,0.5)', 'rgba(70,76,66,0.5)'],
        paintChance: 0.2, rustChance: 0.62, grimeMul: 1.5,
        trimStyle: 'hazard', trimBase: '#8f8354',
        glowStops: ['#fff6e0', '#ffd9a0', '#e88a3a', '#0a0402'], glowColor: '#ffc890',
        windowDark: 0.3, mechTint: '#7d7a72',
    },
    miner: {
        armorBase: [104, 86, 60],
        paint: ['rgba(140,84,34,0.55)', 'rgba(96,60,36,0.6)', 'rgba(84,86,74,0.5)'],
        paintChance: 0.24, rustChance: 0.75, grimeMul: 1.9,
        trimStyle: 'hazard', trimBase: '#93803e',
        glowStops: ['#fff6e0', '#ffd9a0', '#e88a3a', '#0a0402'], glowColor: '#ffc890',
        windowDark: 0.25, mechTint: '#807664',
    },
    stealth: {
        armorBase: [30, 32, 37],
        paint: ['rgba(20,22,28,0.6)', 'rgba(38,36,48,0.5)'],
        paintChance: 0.07, rustChance: 0.1, grimeMul: 0.4,
        trimStyle: 'steel', trimBase: '#4a4e58',
        glowStops: ['#e8e0ff', '#a88cff', '#5c3fd0', '#050208'], glowColor: '#9a7cff',
        windowDark: 0.72, mechTint: '#565a64',
    },
    ceramic: {
        armorBase: [172, 174, 178],
        paint: ['rgba(150,160,180,0.5)', 'rgba(190,186,170,0.5)', 'rgba(120,140,160,0.4)'],
        paintChance: 0.14, rustChance: 0.15, grimeMul: 0.7,
        trimStyle: 'steel', trimBase: '#9aa2ac',
        glowStops: ['#ffffff', '#dceaff', '#7ab8f0', '#02040a'], glowColor: '#dceaff',
        windowDark: 0.14, mechTint: '#9aa0a8',
    },
    modular: {
        armorBase: [96, 100, 106],
        paint: ['rgba(64,96,128,0.5)', 'rgba(96,58,48,0.5)', 'rgba(70,76,66,0.5)'],
        paintChance: 0.15, rustChance: 0.4, grimeMul: 1.0,
        trimStyle: 'steel', trimBase: '#8a8f96',
        glowStops: ['#ffffff', '#cfeaff', '#5aa8e8', '#02040a'], glowColor: '#bfe4ff',
        windowDark: 0.3, mechTint: '#7d828a',
    },
};

// ---- hull curve helpers ----------------------------------------------------

// Warship sheer-line template as fractions of length (destroyer heritage).
const WZ = [0.5, 0.44, 0.34, 0.22, 0.08, -0.08, -0.24, -0.36, -0.46];
const WW = [0.05, 0.26, 0.58, 0.74, 0.85, 0.84, 0.76, 0.66, 0.58];
const WH = [0.09, 0.44, 0.72, 0.86, 0.95, 0.93, 0.86, 0.78, 0.72];

function loftedHull(L, beamF, heightF, stations) {
    const k = L / 10;
    return {
        length: L,
        widthCurve: WZ.map((z, i) => [z * L, WW[i] * k * beamF]),
        heightCurve: WZ.map((z, i) => [z * L, WH[i] * k * heightF]),
        stations,
    };
}

// Line-warship sheer template per the board digests: slab-sided - beam and
// depth hold a near-constant plateau over the mid 70% and taper hard only at
// the ends, so the hull reads as a long armoured cathedral, not an egg.
// The forward stations hold real beam so the integral ram wedge (ramProw)
// roots into armoured mass instead of an egg taper - the wedge, not the
// skin loft, is what closes the bow.
const CW = [0.30, 0.62, 0.80, 0.86, 0.88, 0.88, 0.87, 0.84, 0.78];
const CH = [0.38, 0.68, 0.86, 0.92, 0.96, 0.96, 0.94, 0.90, 0.86];

// beam = 0.176 * L * beamF, depth = 0.192 * L * heightF with this template,
// so beamF = 5.68 / (L:B) and heightF = (depth/beam) / ((L:B) * 0.192).
function capitalHull(L, beamF, heightF, stations) {
    const k = L / 10;
    return {
        length: L,
        widthCurve: WZ.map((z, i) => [z * L, CW[i] * k * beamF]),
        heightCurve: WZ.map((z, i) => [z * L, CH[i] * k * heightF]),
        stations,
    };
}

function scale(k, entries) { return entries.map((v) => v * k); }

// ---- records ---------------------------------------------------------------

export const SHIP_RECORDS = {

    // -- warship mass ladder ------------------------------------------------
    // Proportions are MEASURED, not invented: L:B and depth ratios per class
    // come from the anatomy digests in walkthrough/reference/ships/README.md
    // (W40k capitals long and deep, never wide; beam the smallest dimension).
    // With loftedHull, beam = 0.17 * L * beamF and depth = 0.19 * L * heightF,
    // so beamF = 5.882 / (L:B) and heightF = (depth/beam) / ((L:B) * 0.19).
    scout: {
        name: 'scout', label: 'Scout', family: 'scout', palette: 'warship',
        seed: 'ultranova-scout-mk1', textureSize: 512,
        hull: loftedHull(4.5, 0.75, 0.68, 16),
        features: { bandZ: [1.2, -0.9], radiatorZ: [-1.3], greebleBudget: 260 },
    },
    frigate: {
        // digest: L:B 4.5:1, near-square section, plough wedge front quarter,
        // no broadside, 2-3 centreline blisters, low aft bridge notch, 2 bells
        name: 'frigate', label: 'Frigate', family: 'warship', palette: 'warship',
        seed: 'ultranova-frigate-mk1', textureSize: 512,
        hull: capitalHull(7, 1.26, 1.05, 26),
        features: {
            // one prow language for the family: the W40k underbite blade,
            // scaled to the smallest hull in the battle line
            prowBlade: { lenFrac: 0.32, bands: 3 },
            dorsalTurretZ: [1.6, 0.4], ventralTurretZ: [0.9], pdMountZ: [1.2, -0.2],
            tower: { z0: -1.1, z1: -2.1, s: 0.62 },
            engines: 2, radiatorZ: [-1.6], truss: { z0: 0.1, z1: -0.85 },
            fuelSpheres: [[0.24, -2.5, 0.21], [-0.24, -2.5, 0.21]],
            bandZ: [2.35, 0.6, -1.7], greebleBudget: 520, turretScale: 0.85,
        },
    },
    destroyer: {
        // digest: L:B 5.5:1, depth 1.2x beam, layered ram beak at 22%, one
        // dorsal spinal weapons trench, 2-3 flank blisters, one-deck aft
        // superstructure with masts, 3 bells
        name: 'destroyer', label: 'Destroyer', family: 'warship', palette: 'warship',
        seed: 'ultranova-destroyer-mk1', textureSize: 1024,
        hull: capitalHull(10, 1.03, 1.14, 32),
        features: {
            // family blade, destroyer scale
            prowBlade: { lenFrac: 0.30, bands: 4, apertures: 1 },
            dorsalTurretZ: [2.55, 1.5], ventralTurretZ: [0.8], pdMountZ: [2.0, 0.0, -1.6],
            vls: { z0: 3.4, z1: 2.75, cols: 2, rows: 6 },
            // silhouette-distance round: destroyer stays LOW-SLUNG - the lean
            // trench hull against the cruiser's tall stern-castle
            spine: { z0: 0.9, z1: -1.4 }, tower: { z0: -1.55, z1: -3.0, s: 0.62 },
            engines: 3, radiatorZ: [-2.0, -3.1], truss: { z0: 0.2, z1: -1.2 },
            fuelSpheres: [[0.34, -3.6, 0.3], [-0.34, -3.6, 0.3]],
            bandZ: [3.3, 1.9, -0.2, -3.3], greebleBudget: 780,
        },
    },
    cruiser: {
        // digest (Lunar anchor): L:B 6.5:1, depth 1.4x beam, ram prow front
        // quarter, FIRST true broadside - one casemate row per flank spanning
        // the middle 40%, first spine crenellation, stern-castle bridge,
        // 3 bells plus ventral keel fin
        name: 'cruiser', label: 'Cruiser', family: 'warship', palette: 'warship',
        seed: 'ultranova-cruiser-mk1', textureSize: 1024,
        hull: capitalHull(14, 0.87, 1.12, 36),
        features: {
            // family blade, cruiser scale
            prowBlade: { lenFrac: 0.28, bands: 5, apertures: 2 },
            dorsalTurretZ: [3.6, 2.2], ventralTurretZ: [1.2], pdMountZ: [2.9, 0.5, -1.7],
            vls: { z0: 4.6, z1: 3.8, cols: 2, rows: 7 },
            // silhouette-distance round: the stern-castle bridge and raised
            // crenellated spine are the cruiser's skyline against the destroyer
            spine: { z0: 1.4, z1: -2.4, s: 1.35 }, tower: { z0: -2.4, z1: -4.4, s: 1.7 },
            engines: 3, radiatorZ: [-2.9, -4.5], keelFin: -4.6,
            fuelSpheres: [[0.46, -5.0, 0.4], [-0.46, -5.0, 0.4]],
            bandZ: [4.8, 2.7, -0.3, -4.6], greebleBudget: 1050, turretScale: 1.2,
            broadside: { z0: 2.8, z1: -2.8, guns: 6, tiers: [0.06] },
            hangar: { z: -3.4, sides: [1], w: 0.9, h: 0.45 },
        },
    },
    'battle-cruiser': {
        // digest: leanest at L:B 7.5:1, depth 1.5x beam, sharper 28% ram with
        // gothic beak, one casemate row PLUS a dorsal trainable turret rank
        // (never two tiers), raked bridge, 4 bells in an oversized flat
        // housing with radiator wings
        name: 'battle-cruiser', label: 'Battle Cruiser', family: 'warship', palette: 'warship',
        seed: 'ultranova-battle-cruiser-mk1', textureSize: 1024,
        hull: capitalHull(18, 0.76, 1.04, 40),
        features: {
            // corrected prow ruling: no ram - the W40k blade; lean = deeper
            // rake only, full family authority in mass and beam
            prowBlade: { lenFrac: 0.32, lean: true, apertures: 2, bands: 5 },
            dorsalTurretZ: [4.7, 3.4, 2.1, -0.6], ventralTurretZ: [1.7], pdMountZ: [3.7, 0.7, -2.3],
            vls: { z0: 5.7, z1: 4.95, cols: 3, rows: 6 },
            spine: { z0: 1.9, z1: -2.7 }, tower: { z0: -2.9, z1: -5.5, s: 1.35 },
            engines: 4, engineScale: 1.15, engineSpread: 0.5, radiatorZ: [-3.7, -5.8],
            truss: { z0: 0.4, z1: -2.2 },
            fuelSpheres: [[0.52, -6.5, 0.46], [-0.52, -6.5, 0.46]],
            bandZ: [5.5, 3.5, -0.4, -6.0], greebleBudget: 1300, turretScale: 1.35,
            broadside: { z0: 4.4, z1: -3.4, guns: 8, tiers: [0.1] },
            hangar: { z: -4.2, sides: [1], w: 1.1, h: 0.5 },
        },
    },
    battleship: {
        // digest (Retribution anchor): L:B 7:1, depth 1.6x beam (2.5x with
        // spine towers), wedge prow front fifth, the flank IS the ship - TWO
        // gun-deck tiers over 55% of length, crenellated tower spine, dense
        // emissive window city, massive winged stern-castle, 3 giant bells
        name: 'battleship', label: 'Battleship', family: 'warship', palette: 'warship',
        seed: 'ultranova-battleship-mk1', textureSize: 1024,
        hull: capitalHull(22, 0.81, 1.19, 42),
        features: {
            // corrected prow ruling: the armoured blade DOMINATES the bow -
            // broad keel forward, face raked back and narrowing to the crest
            prowBlade: { lenFrac: 0.26, apertures: 2, bands: 6, crestRise: 1.14 },
            dorsalTurretZ: [5.7, 4.0], ventralTurretZ: [2.7, 0.3], pdMountZ: [4.5, 1.5, -1.3, -3.5],
            vls: { z0: 8.0, z1: 6.7, cols: 4, rows: 8 },
            spine: { z0: 3.2, z1: -4.6, s: 1.9 }, tower: { z0: -4.8, z1: -7.6, s: 1.9 },
            engines: 3, engineScale: 1.5, engineSpread: 0.6, radiatorZ: [-4.5, -6.9],
            truss: { z0: 0.5, z1: -2.7 },
            fuelSpheres: [[0.72, -8.0, 0.56], [-0.72, -8.0, 0.56]],
            bandZ: [7.6, 4.3, -0.5, -7.3], greebleBudget: 1120, turretScale: 1.6,
            winStep: 0.2, winSkip: 0.12,
            broadside: { z0: 6.1, z1: -6.0, guns: 10, tiers: [0.24, -0.1] },
            hangar: { z: -7.0, sides: [1, -1], w: 1.2, h: 0.55 },
        },
    },
    dreadnought: {
        // digest (Oberon/Despoiler): out-deeps rather than out-lengthens -
        // L:B 6.5:1 but depth 2x beam, short blunt 18% ram, THREE stepped
        // broadside tiers plus ventral gun platforms, continuous fortified
        // spine city midships-to-stern, tallest buttressed bridge castle,
        // 4-5 bells stacked in two exhaust ranks with radiator walls
        name: 'dreadnought', label: 'Dreadnought', family: 'warship', palette: 'warship',
        seed: 'ultranova-dreadnought-mk1', textureSize: 1024,
        hull: capitalHull(28, 0.87, 1.60, 44),
        features: {
            // corrected prow ruling: shortest, tallest blade - mass over reach
            prowBlade: { lenFrac: 0.22, apertures: 3, bands: 7, crestRise: 1.08 },
            dorsalTurretZ: [7.3, 5.3], ventralTurretZ: [3.5, 1.5, -0.5, -2.5], pdMountZ: [5.7, 2.3, -1.7, -4.5],
            vls: { z0: 9.9, z1: 8.5, cols: 4, rows: 10 },
            spine: { z0: 3.4, z1: -6.2, s: 2.1, dense: true },
            tower: { z0: -6.4, z1: -9.6, s: 2.3 }, tower2: { z0: -0.4, z1: -2.6, s: 1.2 },
            engineRanks: [[3, 0.62], [2, -0.62]], engineScale: 1.3, engineSpread: 0.62,
            radiatorZ: [-5.7, -8.7], truss: { z0: 0.6, z1: -3.3 },
            fuelSpheres: [[0.9, -10.1, 0.7], [-0.9, -10.1, 0.7]],
            bandZ: [9.7, 5.5, 1.0, -3.1, -9.3], greebleBudget: 1150, turretScale: 1.9,
            winStep: 0.2, winSkip: 0.12,
            broadside: { z0: 7.4, z1: -7.4, guns: 11, tiers: [0.3, 0.04, -0.22] },
            hangar: { z: -8.2, sides: [1, -1], w: 1.4, h: 0.6 },
        },
    },

    // -- raiders (Privateer chunk) ------------------------------------------
    // silhouette-distance round: the two raiders were near-twins (IoU 0.92).
    // Privateer = fat stubby armed trader; Rogue = lean smuggler dominated by
    // twin outboard nacelle booms. Same grammar, opposite proportions.
    privateer: {
        name: 'privateer', label: 'Privateer', family: 'raider', palette: 'raider',
        seed: 'ultranova-privateer-mk1', textureSize: 512,
        hull: loftedHull(7, 1.5, 1.15, 22),
        features: {
            nacelleZ: -1.4, nacelleR: 0.22, nacelleLen: 2.0,
            hardpoints: [[0.5, 1.5], [-0.5, 1.5]],
            bandZ: [2.0, -0.6], radiatorZ: [-2.1], greebleBudget: 380,
        },
    },
    rogue: {
        // stealth palette: the Rogue is the Super Stealth chassis - a dark
        // smuggler hull, not another rust trader like the Privateer
        name: 'rogue', label: 'Rogue', family: 'raider', palette: 'stealth',
        seed: 'ultranova-rogue-mk1', textureSize: 512,
        hull: loftedHull(12, 0.78, 0.92, 26),
        features: {
            nacelleZ: -1.4, nacelleR: 0.55, nacelleLen: 4.8,
            hardpoints: [[0.5, 2.5], [-0.5, 2.5], [0.62, 0.2], [-0.62, 0.2]],
            dorsalTurretZ: [1.2], turretScale: 0.95,
            bandZ: [3.4, -0.9, -3.6], radiatorZ: [-3.6], greebleBudget: 480,
        },
    },

    // -- freighter container-spine ladder -----------------------------------
    'small-freighter': {
        name: 'small-freighter', label: 'Small Freighter', family: 'freighter', palette: 'industrial',
        seed: 'ultranova-small-freighter-mk1', textureSize: 512,
        hull: { length: 8 },
        features: {
            spine: { rows: 1, cols: 1, cell: { w: 0.6, h: 0.55, d: 0.95 } },
            engines: 1, fuelSpheres: [[0, -0.6, -2.2, 0.3]], greebleBudget: 150,
        },
    },
    'medium-freighter': {
        name: 'medium-freighter', label: 'Medium Freighter', family: 'freighter', palette: 'industrial',
        seed: 'ultranova-medium-freighter-mk1', textureSize: 512,
        hull: { length: 11 },
        features: {
            spine: { rows: 1, cols: 2, cell: { w: 0.62, h: 0.58, d: 1.0 } },
            engines: 2, fuelSpheres: [[0, -0.7, -3.2, 0.34]], greebleBudget: 190,
        },
    },
    'large-freighter': {
        name: 'large-freighter', label: 'Large Freighter', family: 'freighter', palette: 'industrial',
        seed: 'ultranova-large-freighter-mk1', textureSize: 512,
        hull: { length: 15 },
        features: {
            spine: { rows: 2, cols: 2, cell: { w: 0.66, h: 0.6, d: 1.1 } },
            engines: 2, fuelSpheres: [[0.5, -0.9, -4.6, 0.4], [-0.5, -0.9, -4.6, 0.4]],
            greebleBudget: 240,
        },
    },
    'super-freighter': {
        name: 'super-freighter', label: 'Super Freighter', family: 'freighter', palette: 'industrial',
        seed: 'ultranova-super-freighter-mk1', textureSize: 1024,
        hull: { length: 20 },
        features: {
            spine: { rows: 2, cols: 3, cell: { w: 0.7, h: 0.65, d: 1.2 } },
            engines: 3, fuelSpheres: [[0.7, -1.1, -6.4, 0.48], [-0.7, -1.1, -6.4, 0.48]],
            greebleBudget: 300,
        },
    },
    galleon: {
        // silhouette-distance round: the galleon read as just another
        // container spine (IoU 0.87 vs super-freighter). Armed merchantman
        // identity: a single WIDE FLAT cargo deck - unique in the ladder -
        // with a dorsal line of four oversized turrets standing proud of it
        name: 'galleon', label: 'Galleon', family: 'freighter', palette: 'industrial',
        seed: 'ultranova-galleon-mk1', textureSize: 1024,
        hull: { length: 17 },
        features: {
            spine: { rows: 1, cols: 3, cell: { w: 0.66, h: 0.72, d: 1.15 } },
            engines: 3, armed: { turretZ: [5.2, 2.6, 0.0, -2.6], scale: 1.4 },
            commandScale: 1.6,
            fuelSpheres: [[0.6, -1.0, -5.4, 0.44], [-0.6, -1.0, -5.4, 0.44]],
            greebleBudget: 280,
        },
    },

    // -- fuel tankers --------------------------------------------------------
    'fuel-transport': {
        name: 'fuel-transport', label: 'Fuel Transport', family: 'tanker', palette: 'industrial',
        seed: 'ultranova-fuel-transport-mk1', textureSize: 512,
        hull: { length: 9 },
        features: { tankR: 0.85, tankZ: [1.9, 0.1, -1.7], engines: 1, greebleBudget: 150 },
    },
    'super-fuel-transport': {
        name: 'super-fuel-transport', label: 'Super-Fuel Transport', family: 'tanker', palette: 'industrial',
        seed: 'ultranova-super-fuel-transport-mk1', textureSize: 512,
        hull: { length: 15 },
        features: { tankR: 1.35, tankZ: [3.5, 0.7, -2.1], engines: 2, greebleBudget: 210 },
    },

    // -- mining ladder -------------------------------------------------------
    // class-identity round: purpose-built working tools - bucket wheel, ore
    // intake maw and conveyor spine - the SAME tool language up the ladder
    'midget-miner': {
        name: 'midget-miner', label: 'Midget Miner', family: 'miner', palette: 'miner',
        seed: 'ultranova-midget-miner-mk1', textureSize: 512,
        hull: { length: 5 },
        features: { drumR: 0.5, drumLen: 1.6, ribs: 4, booms: 1, boomReach: 0.7, bucketR: 0.3, engines: 1, greebleBudget: 120 },
    },
    'mini-miner': {
        name: 'mini-miner', label: 'Mini Miner', family: 'miner', palette: 'miner',
        seed: 'ultranova-mini-miner-mk1', textureSize: 512,
        hull: { length: 7 },
        features: { drumR: 0.65, drumLen: 2.2, ribs: 5, booms: 2, boomReach: 0.8, bucketR: 0.38, engines: 1, greebleBudget: 170 },
    },
    miner: {
        name: 'miner', label: 'Miner', family: 'miner', palette: 'miner',
        seed: 'ultranova-miner-mk1', textureSize: 512,
        hull: { length: 10 },
        features: { drumR: 0.9, drumLen: 3.2, ribs: 6, booms: 2, boomReach: 1.0, bucketR: 0.52, engines: 2, greebleBudget: 230 },
    },
    'maxi-miner': {
        name: 'maxi-miner', label: 'Maxi Miner', family: 'miner', palette: 'miner',
        seed: 'ultranova-maxi-miner-mk1', textureSize: 512,
        hull: { length: 14 },
        features: { drumR: 1.15, drumLen: 4.6, ribs: 7, booms: 3, boomReach: 1.3, bucketR: 0.7, engines: 2, greebleBudget: 300 },
    },
    'ultra-miner': {
        name: 'ultra-miner', label: 'Ultra Miner', family: 'miner', palette: 'miner',
        seed: 'ultranova-ultra-miner-mk1', textureSize: 1024,
        hull: { length: 18 },
        features: { drumR: 1.4, drumLen: 5.8, ribs: 8, booms: 4, boomReach: 1.6, bucketR: 0.92, twinDrum: true, engines: 3, greebleBudget: 380 },
    },

    // -- ordnance frames (no aircraft anatomy in vacuum) --------------------
    // class-identity round: the hung ordnance IS the identity - fat distinct
    // payload shapes in visible rows on every rack, reading at sheet scale
    'mini-bomber': {
        name: 'mini-bomber', label: 'Mini Bomber', family: 'bomber', palette: 'olive',
        seed: 'ultranova-mini-bomber-mk1', textureSize: 512,
        hull: { length: 6 },
        features: {
            sparZ: [1.3, 0.1], sparSpan: 1.0, palletsPerSpar: 2, palletN: 2, palletM: 2,
            engines: 1, greebleBudget: 110,
        },
    },
    'b17-bomber': {
        name: 'b17-bomber', label: 'B-17 Bomber', family: 'bomber', palette: 'olive',
        seed: 'ultranova-b17-bomber-mk1', textureSize: 512,
        hull: { length: 12 },
        features: {
            sparZ: [3.3, 2.0, 0.7, -0.6], sparSpan: 1.35, rackRows: 2,
            palletsPerSpar: 2, palletN: 2, palletM: 3, spineHW: 0.22,
            engines: 2, greebleBudget: 190,
        },
    },
    'stealth-bomber': {
        name: 'stealth-bomber', label: 'Stealth Bomber', family: 'stealth', palette: 'stealth',
        seed: 'ultranova-stealth-bomber-mk1', textureSize: 512,
        hull: loftedHull(11, 1.55, 0.42, 18),
        features: { bays: [[1.6, 1.6], [-0.9, 1.4]], engines: 2, greebleBudget: 120 },
    },
    'b52-bomber': {
        name: 'b52-bomber', label: 'B-52 Bomber', family: 'bomber', palette: 'olive',
        seed: 'ultranova-b52-bomber-mk1', textureSize: 1024,
        hull: { length: 17 },
        features: {
            twinTruss: true, trussGap: 0.6, sparZ: [4.6, 3.1, 1.6, 0.1, -1.4],
            sparSpan: 1.85, palletsPerSpar: 2, palletN: 2, palletM: 3,
            midPallets: [3.9, 2.3, 0.8, -0.7], spineHW: 0.26,
            engines: 4, greebleBudget: 240,
        },
    },

    // -- colony --------------------------------------------------------------
    // class-identity round: "colony ships must be bulkier" - the fattest
    // hulls in the fleet, a town in transit: swollen tri-lobed volume, dome
    // crown, greenhouse glazing glow, visible life-support mass
    'mini-colony-ship': {
        name: 'mini-colony-ship', label: 'Mini-Colony Ship', family: 'colony', palette: 'ceramic',
        seed: 'ultranova-mini-colony-ship-mk1', textureSize: 512,
        hull: { length: 7 },
        features: {
            habR: 0.95, drums: [[1.3, 2.4]], domes: 3, engines: 1,
            fuelSpheres: [[0, -0.15, -1.6, 0.42]], greebleBudget: 170,
        },
    },
    'colony-ship': {
        name: 'colony-ship', label: 'Colony Ship', family: 'colony', palette: 'ceramic',
        seed: 'ultranova-colony-ship-mk1', textureSize: 1024,
        hull: { length: 13 },
        features: {
            habR: 1.55, drums: [[3.9, 2.6], [0.9, 3.0]], domes: 6, engines: 3,
            fuelSpheres: [[0.8, -0.5, -3.9, 0.6], [-0.8, -0.5, -3.9, 0.6], [0, -0.9, -4.4, 0.5]],
            greebleBudget: 320,
        },
    },

    // -- mine layers ---------------------------------------------------------
    'mini-mine-layer': {
        name: 'mini-mine-layer', label: 'Mini Mine Layer', family: 'minelayer', palette: 'industrial',
        seed: 'ultranova-mini-mine-layer-mk1', textureSize: 512,
        hull: loftedHull(7, 1.1, 0.9, 18),
        features: {
            drums: [[-1.3, 1], [-1.3, -1]], rack: { z0: 1.6, z1: -0.4 },
            engines: 2, greebleBudget: 210,
        },
    },
    'super-mine-layer': {
        name: 'super-mine-layer', label: 'Super Mine Layer', family: 'minelayer', palette: 'industrial',
        seed: 'ultranova-super-mine-layer-mk1', textureSize: 512,
        hull: loftedHull(13, 1.15, 0.95, 26),
        features: {
            drums: [[-2.7, 1], [-2.7, -1], [-0.7, 1], [-0.7, -1]],
            rack: { z0: 3.3, z1: -0.3 },
            engines: 3, greebleBudget: 300,
        },
    },

    // -- modular -------------------------------------------------------------
    nubian: {
        name: 'nubian', label: 'Nubian', family: 'modular', palette: 'modular',
        seed: 'ultranova-nubian-mk1', textureSize: 1024,
        hull: { length: 14 },
        features: {
            socketZ: [4.4, 3.0, 1.6, 0.2, -1.2, -2.6],
            engines: 3, greebleBudget: 280,
        },
    },
    'meta-morph': {
        name: 'meta-morph', label: 'Meta Morph', family: 'modular', palette: 'modular',
        seed: 'ultranova-meta-morph-mk1', textureSize: 512,
        hull: { length: 10 },
        features: { radial: true, arms: 5, engines: 2, greebleBudget: 220 },
    },

    // -- unmanned probe ------------------------------------------------------
    // Class-identity round ruling 6 ("and probes?"): the Armed Probe design
    // (HE / WM starter) no longer rides the generic scout hull. UNMANNED
    // identity: no windows, no habitat mass - an instrument bus with sensor
    // booms and dishes and a drive block wildly oversized for its length.
    probe: {
        name: 'probe', label: 'Armed Probe', family: 'probe', palette: 'ceramic',
        seed: 'ultranova-probe-mk1', textureSize: 512,
        hull: { length: 4.5 },
        features: { booms: 3, boomLen: 1.1, engines: 1, greebleBudget: 340 },
    },

    // -- assault wedge -------------------------------------------------------
    'assault-transport': {
        name: 'assault-transport', label: 'Assault Transport', family: 'assault', palette: 'olive',
        seed: 'ultranova-assault-transport-mk1', textureSize: 1024,
        hull: loftedHull(13, 1.25, 0.85, 26),
        features: {
            podZ: [1.3, 0.1, -1.1], dorsalTurretZ: [2.7, -0.7], pdMountZ: [1.9, -2.3],
            tower: { z0: -2.7, z1: -4.3 }, bandZ: [3.5, 0.7, -3.7],
            engines: 4, greebleBudget: 500, turretScale: 1.05,
        },
    },
};

export const HULL_NAMES = Object.keys(SHIP_RECORDS);

// Frontend-only design -> model overrides: designs whose backend hull art
// does not fit them render their own model instead. The backend hull tables
// are untouched - this mapping lives entirely on the client side.
export const DESIGN_MODEL_OVERRIDES = {
    'Armed Probe': 'probe',
};
