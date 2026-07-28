"""
Stars Nova Web - Clustered star field placement.

Documented web mod. The C# reference shapes its star field with a
centre-weighted density reducer (StarMapGenerator.cs:242-276 lowers the
placement density in a disc around every star already placed, on top of
a map-centre bias), which produces a rich middle and poor corners. This
module replaces that with a statistically homogeneous field: no
privileged centre, no structurally poor corner, so the DEF-16 homeworld
fairness bound is not fighting the generator.

Two pieces:

- Seeded value-noise fBm supplies the DENSITY FIELD - organic clumps
  and voids at a controllable scale, self-contained, no dependency.
- Variable-radius Poisson-disk sampling (Bridson 2007, "Fast Poisson
  Disk Sampling in Arbitrary Dimensions") places the stars, with the
  local minimum separation driven by that field.

Because the sampler enforces a minimum separation everywhere, the
separation FLOOR makes dense knots impossible; because the separation is
also capped, the CEILING makes empty deserts impossible. The effect is
meant to read as visible but restrained.
"""

import math
import random
from typing import Callable, List, Tuple


# ---------------------------------------------------------------------------
# The four clustering dials
# ---------------------------------------------------------------------------

# 1. CLUSTER SCALE - wavelength of the density field in light years, i.e.
#    the size of one clump-or-void feature. Smaller values scatter many
#    small knots, larger values sweep a few broad regions across the map.
CLUSTER_SCALE = 260.0

# 2. ROUGHNESS - fBm octaves and per-octave amplitude falloff. More
#    octaves and a higher persistence give ragged, filamentary clumps;
#    fewer give smooth blobs.
CLUSTER_OCTAVES = 4
CLUSTER_PERSISTENCE = 0.55

# 3. CLUMPING STRENGTH - density contrast. The local separation is
#    multiplied by exp(-strength * t) with the normalised field t in
#    [-1, 1], so 0.0 is a perfectly even scatter and 0.45 spans a 2.5:1
#    separation ratio (about 6:1 in stars per unit area) before the rails
#    below clamp the tails. This is the dial the "visible but restrained"
#    verdict is made on.
CLUMPING_STRENGTH = 0.45

# 4. SEPARATION FLOOR and CEILING, as multiples of the map's mean star
#    spacing. The floor is what makes dense knots impossible, the ceiling
#    is what makes empty deserts impossible. Both bind only on the tails
#    of the noise, so they are safety rails rather than the shaping
#    mechanism.
SEPARATION_FLOOR = 0.65
SEPARATION_CEILING = 1.55

# The raw fBm is standardised over the map before the clumping curve is
# applied: the field is sampled on a coarse grid, and its own mean and
# standard deviation turn the value into a z-score. Without this a seed
# whose field happens to sit high or low overall would shift the whole
# map's star count. NOISE_SATURATION is where the z-score saturates, in
# standard deviations - beyond it the curve simply rides the rails.
NOISE_GRID = 24
NOISE_SATURATION = 1.5

# Poisson base separation as a fraction of the mean star spacing
# (sqrt(area / star count)). Bridson packs a domain tighter than the
# nominal grid spacing, and a clumped radius field yields more points
# still, so this constant is calibrated to overshoot the nominal star
# count slightly; the caller thins the surplus away, which leaves the
# minimum separation untouched.
POISSON_FILL_FACTOR = 1.29

# Bridson's k - candidate samples generated around each active point
# before it is retired.
POISSON_CANDIDATES = 20


class ValueNoise:
    """
    Seeded 2D value noise with fBm summation, in about 40 lines and
    without a dependency.

    Lattice values come from a seeded permutation table, so the field is
    reproducible from the game seed and statistically homogeneous - it
    has no centre and no preferred direction.
    """

    def __init__(self, seed: int):
        rng = random.Random(seed)
        self._perm = list(range(256))
        rng.shuffle(self._perm)
        self._values = [rng.random() for _ in range(256)]

    def _lattice(self, ix: int, iy: int) -> float:
        """Pseudo-random value in [0, 1) at integer lattice point."""
        h = self._perm[(ix + self._perm[iy & 255]) & 255]
        return self._values[h]

    def value(self, x: float, y: float) -> float:
        """Smoothly interpolated value noise in [0, 1)."""
        ix = math.floor(x)
        iy = math.floor(y)
        fx = x - ix
        fy = y - iy
        # Smoothstep so the field is C1 continuous across lattice cells
        u = fx * fx * (3.0 - 2.0 * fx)
        v = fy * fy * (3.0 - 2.0 * fy)
        v00 = self._lattice(ix, iy)
        v10 = self._lattice(ix + 1, iy)
        v01 = self._lattice(ix, iy + 1)
        v11 = self._lattice(ix + 1, iy + 1)
        a = v00 + (v10 - v00) * u
        b = v01 + (v11 - v01) * u
        return a + (b - a) * v

    def fbm(self, x: float, y: float,
            octaves: int = CLUSTER_OCTAVES,
            persistence: float = CLUSTER_PERSISTENCE) -> float:
        """Fractal sum of octaves, normalised back to [0, 1)."""
        total = 0.0
        norm = 0.0
        amplitude = 1.0
        frequency = 1.0
        for _ in range(octaves):
            total += amplitude * self.value(x * frequency, y * frequency)
            norm += amplitude
            amplitude *= persistence
            frequency *= 2.0
        return total / norm


def separation_field(seed: int, mean_spacing: float,
                     width: float, height: float,
                     clumping: float = CLUMPING_STRENGTH
                     ) -> Tuple[Callable[[float, float], float], float, float]:
    """
    Build the local-separation function driving the Poisson sampler.

    Args:
        seed: Game seed - the same seed gives the same field.
        mean_spacing: Mean star spacing in ly, sqrt(area / star count).
        width, height: Map dimensions, over which the field is
            standardised so its contrast does not vary by seed.
        clumping: Density contrast dial (CLUMPING_STRENGTH).

    Returns:
        (radius_at, r_min, r_max) - the separation in ly at a point and
        the rails it is clamped to.
    """
    noise = ValueNoise(seed)
    r_min = mean_spacing * SEPARATION_FLOOR
    r_max = mean_spacing * SEPARATION_CEILING

    samples = [
        noise.fbm(width * (i + 0.5) / NOISE_GRID / CLUSTER_SCALE,
                  height * (j + 0.5) / NOISE_GRID / CLUSTER_SCALE)
        for i in range(NOISE_GRID) for j in range(NOISE_GRID)
    ]
    mean = sum(samples) / len(samples)
    variance = sum((s - mean) ** 2 for s in samples) / len(samples)
    spread = max(1e-6, math.sqrt(variance) * NOISE_SATURATION)

    def radius_at(x: float, y: float) -> float:
        n = noise.fbm(x / CLUSTER_SCALE, y / CLUSTER_SCALE)
        # Standardised field: +1 in the densest regions, -1 in the emptiest
        t = max(-1.0, min(1.0, (n - mean) / spread))
        return max(r_min, min(r_max, mean_spacing * math.exp(-clumping * t)))

    return radius_at, r_min, r_max


def poisson_disk(width: float, height: float, margin: float,
                 radius_at: Callable[[float, float], float],
                 r_max: float, rng: random.Random,
                 candidates: int = POISSON_CANDIDATES
                 ) -> List[Tuple[float, float]]:
    """
    Variable-radius Poisson-disk sampling (Bridson).

    A candidate is accepted only when it clears max(r(candidate), r(p))
    from every existing point p, so the separation guarantee holds from
    both sides and the field's floor is a hard lower bound on the
    nearest-neighbour distance.

    Args:
        width, height: Domain size in ly.
        margin: Keep-out band along the map edge in ly.
        radius_at: Local separation function.
        r_max: Largest separation the field can return (grid sizing).
        rng: Seeded generator - drives every draw.
        candidates: Bridson's k.

    Returns:
        List of (x, y) samples, in insertion order.
    """
    lo_x, hi_x = margin, width - margin
    lo_y, hi_y = margin, height - margin
    if hi_x <= lo_x or hi_y <= lo_y:
        return []

    # Cell side r_max means every point within r_max of a candidate lies
    # in one of the 9 cells around it
    cell = r_max
    grid: dict = {}
    points: List[Tuple[float, float]] = []
    radii: List[float] = []
    active: List[int] = []

    def insert(x: float, y: float, r: float) -> int:
        index = len(points)
        points.append((x, y))
        radii.append(r)
        grid.setdefault((int(x / cell), int(y / cell)), []).append(index)
        active.append(index)
        return index

    def fits(x: float, y: float, r: float) -> bool:
        gx = int(x / cell)
        gy = int(y / cell)
        for cx in range(gx - 1, gx + 2):
            for cy in range(gy - 1, gy + 2):
                for index in grid.get((cx, cy), ()):
                    px, py = points[index]
                    need = r if r > radii[index] else radii[index]
                    if (x - px) ** 2 + (y - py) ** 2 < need * need:
                        return False
        return True

    seed_x = lo_x + rng.random() * (hi_x - lo_x)
    seed_y = lo_y + rng.random() * (hi_y - lo_y)
    insert(seed_x, seed_y, radius_at(seed_x, seed_y))

    while active:
        slot = rng.randrange(len(active))
        index = active[slot]
        px, py = points[index]
        pr = radii[index]
        placed = False
        for _ in range(candidates):
            angle = rng.random() * math.tau
            dist = pr * (1.0 + rng.random())
            x = px + math.cos(angle) * dist
            y = py + math.sin(angle) * dist
            if not (lo_x <= x <= hi_x and lo_y <= y <= hi_y):
                continue
            r = radius_at(x, y)
            if not fits(x, y, r):
                continue
            insert(x, y, r)
            placed = True
            break
        if not placed:
            # Retire the point - swap-with-last keeps this O(1) and the
            # draw order deterministic for a given seed
            active[slot] = active[-1]
            active.pop()

    return points


def generate_positions(width: int, height: int, count: int, margin: float,
                       seed: int, rng: random.Random,
                       clumping: float = CLUMPING_STRENGTH
                       ) -> List[Tuple[int, int]]:
    """
    Place `count` clustered star positions on a width x height map.

    The sampler fills the domain to exhaustion and is calibrated to
    overshoot; the surplus is thinned away with a seeded shuffle, which
    only ever increases the nearest-neighbour distance.

    Args:
        width, height: Universe dimensions in ly.
        count: Nominal star count for the map (area / spacing^2).
        margin: Keep-out band along the map edge in ly.
        seed: Game seed, driving the density field.
        rng: The generator's seeded rng, driving the sampling draws.
        clumping: Density contrast dial - the preview harness sweeps it.

    Returns:
        Up to `count` integer (x, y) positions.
    """
    usable = max(1.0, (width - 2 * margin) * (height - 2 * margin))
    mean_spacing = math.sqrt(usable / max(1, count))
    radius_at, _r_min, r_max = separation_field(
        seed, mean_spacing / POISSON_FILL_FACTOR, width, height, clumping)

    samples = poisson_disk(width, height, margin, radius_at,
                           r_max, rng)
    rng.shuffle(samples)

    positions: List[Tuple[int, int]] = []
    seen = set()
    for x, y in samples:
        key = (int(round(x)), int(round(y)))
        if key in seen:
            continue
        seen.add(key)
        positions.append(key)
        if len(positions) >= count:
            break
    return positions
