// Deterministic seeded RNG for the ship model compiler.
// Every random decision in the pipeline flows through one of these instances;
// Math.random and Date are never used, so the same design record always
// compiles to the same mesh and the same baked textures.

export function hashString(str) {
    // FNV-1a 32-bit
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
}

export function makeRng(seed) {
    // mulberry32
    let a = typeof seed === 'string' ? hashString(seed) : (seed >>> 0);
    const next = function () {
        a |= 0;
        a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    next.range = (lo, hi) => lo + (hi - lo) * next();
    next.int = (lo, hi) => Math.floor(next.range(lo, hi + 1));
    next.pick = (arr) => arr[Math.floor(next() * arr.length) % arr.length];
    next.chance = (p) => next() < p;
    next.sign = () => (next() < 0.5 ? -1 : 1);
    next.fork = (label) => makeRng((hashString(label) ^ Math.floor(next() * 0xffffffff)) >>> 0);
    return next;
}
