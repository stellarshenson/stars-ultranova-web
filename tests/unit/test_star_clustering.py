"""
Star clustering (user directive 2026-07-28).

The galaxy must clump into loose clusters rather than scatter evenly,
"visible but restrained" - no dense knots, no empty deserts. The three
assertions that make that objective:

- QUADRAT COUNT index of dispersion (variance-to-mean ratio) proves the
  clustering is present. A completely random (Poisson) field scores 1.0;
  an even scatter scores below 1.0; a clustered field scores above 1.0.
  The Poisson-disk sampler on its own is strongly UNDER-dispersed
  (measured 0.16 to 0.36), so a score above 1 can only come from the
  density field driving it.
- NEAREST-NEIGHBOUR minimum proves there are no dense knots: no two
  stars sit closer than the separation floor.
- LARGEST EMPTY CIRCLE proves there are no deserts: nowhere on the board
  is further than the stated bound from a star.

All three are measured across ten seeds.
"""

import math
import random

import pytest

from backend.services import star_field
from backend.services.galaxy_generator import (
    GalaxyGenerator, STAR_DENSITY, STAR_MARGIN, UNIVERSE_SIZES
)

SEEDS = [4242, 0, 1, 3, 42, 99, 777, 1111, 12345, 20260713]

# The medium board: 1000 x 1000 ly, 400 stars, 48.0 ly mean spacing
SIZE = "medium"
WIDTH, HEIGHT = UNIVERSE_SIZES[SIZE]
COUNT = WIDTH * HEIGHT // (STAR_DENSITY * STAR_DENSITY)
MEAN_SPACING = math.sqrt(
    (WIDTH - 2 * STAR_MARGIN) * (HEIGHT - 2 * STAR_MARGIN) / COUNT)

# The sampler's separation rails in light years. The field is built on
# mean_spacing / POISSON_FILL_FACTOR, so the rails scale with it.
SEPARATION_FLOOR_LY = (star_field.SEPARATION_FLOOR
                       / star_field.POISSON_FILL_FACTOR * MEAN_SPACING)

# Positions are rounded to whole light years, which can shave up to
# sqrt(2) ly off a pair distance
ROUNDING_SLACK = 1.5

# Largest empty circle bound, in mean spacings. Measured worst case over
# these ten seeds is 2.14; the bar keeps a margin over that.
EMPTY_CIRCLE_BOUND = 2.6 * MEAN_SPACING


def _positions(seed, clumping=star_field.CLUMPING_STRENGTH):
    """Place a medium board's stars directly through the sampler."""
    return star_field.generate_positions(
        WIDTH, HEIGHT, COUNT, STAR_MARGIN, seed, random.Random(seed),
        clumping=clumping)


def _index_of_dispersion(points):
    """
    Quadrat-count variance-to-mean ratio.

    The board is cut into square quadrats holding about five stars each -
    well below the cluster scale (260 ly) and well above the star
    separation, so the statistic sees clumping rather than either
    extreme.
    """
    quadrats = max(2, int(round(math.sqrt(len(points) / 5.0))))
    span_x = WIDTH - 2 * STAR_MARGIN
    span_y = HEIGHT - 2 * STAR_MARGIN
    counts = [0] * (quadrats * quadrats)
    for x, y in points:
        i = min(quadrats - 1, int((x - STAR_MARGIN) / span_x * quadrats))
        j = min(quadrats - 1, int((y - STAR_MARGIN) / span_y * quadrats))
        counts[i * quadrats + j] += 1
    mean = sum(counts) / len(counts)
    variance = sum((c - mean) ** 2 for c in counts) / (len(counts) - 1)
    return variance / mean


def _nearest_neighbour_min(points):
    """Smallest distance between any two stars."""
    best = float("inf")
    for i, (x, y) in enumerate(points):
        for j in range(i + 1, len(points)):
            a, b = points[j]
            d = (x - a) ** 2 + (y - b) ** 2
            if d < best:
                best = d
    return math.sqrt(best)


def _largest_empty_circle(points, probes=80):
    """
    Largest distance from a board location to its nearest star, sampled
    on a probe grid. Stars are bucketed into cells of one mean spacing
    so each probe only looks at the rings around it.
    """
    cell = MEAN_SPACING
    buckets = {}
    for point in points:
        buckets.setdefault((int(point[0] / cell), int(point[1] / cell)),
                           []).append(point)

    span_x = WIDTH - 2 * STAR_MARGIN
    span_y = HEIGHT - 2 * STAR_MARGIN
    worst = 0.0
    for i in range(probes):
        px = STAR_MARGIN + (i + 0.5) / probes * span_x
        for j in range(probes):
            py = STAR_MARGIN + (j + 0.5) / probes * span_y
            gx, gy = int(px / cell), int(py / cell)
            best = float("inf")
            ring = 1
            while True:
                for cx in range(gx - ring, gx + ring + 1):
                    for cy in range(gy - ring, gy + ring + 1):
                        for a, b in buckets.get((cx, cy), ()):
                            d = (px - a) ** 2 + (py - b) ** 2
                            if d < best:
                                best = d
                if best < (ring * cell) ** 2 or ring > 12:
                    break
                ring += 1
            worst = max(worst, math.sqrt(best))
    return worst


class TestClusteringPresent:

    @pytest.mark.parametrize("seed", SEEDS)
    def test_index_of_dispersion_above_random(self, seed):
        """Clustered field scores above the Poisson baseline of 1.0."""
        vmr = _index_of_dispersion(_positions(seed))
        assert vmr > 1.0, f"seed {seed}: index of dispersion {vmr:.2f}"

    def test_mean_index_of_dispersion(self):
        """Averaged over the ten seeds the clustering is clearly
        present, not a marginal effect."""
        scores = [_index_of_dispersion(_positions(s)) for s in SEEDS]
        mean = sum(scores) / len(scores)
        assert mean >= 1.3, f"mean index of dispersion {mean:.2f}"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_beats_even_scatter_control(self, seed):
        """The same sampler with the clumping dial at zero is an even
        scatter - strongly under-dispersed. The gap between the two is
        the clustering the density field contributes."""
        clumped = _index_of_dispersion(_positions(seed))
        control = _index_of_dispersion(_positions(seed, clumping=0.0))
        assert control < 0.5, (
            f"seed {seed}: even-scatter control scored {control:.2f}, "
            "so the sampler is not the regular baseline assumed here")
        assert clumped - control >= 0.7, (
            f"seed {seed}: clumped {clumped:.2f} vs control "
            f"{control:.2f}")


class TestNoKnotsNoDeserts:

    @pytest.mark.parametrize("seed", SEEDS)
    def test_no_dense_knots(self, seed):
        """Nearest-neighbour minimum clears the separation floor, so
        the field cannot collapse into a knot."""
        nearest = _nearest_neighbour_min(_positions(seed))
        assert nearest >= SEPARATION_FLOOR_LY - ROUNDING_SLACK, (
            f"seed {seed}: closest pair {nearest:.1f} ly, floor "
            f"{SEPARATION_FLOOR_LY:.1f} ly")

    @pytest.mark.parametrize("seed", SEEDS)
    def test_no_empty_deserts(self, seed):
        """Largest empty circle stays inside the stated bound, so the
        voids never open into a desert."""
        empty = _largest_empty_circle(_positions(seed))
        assert empty <= EMPTY_CIRCLE_BOUND, (
            f"seed {seed}: largest empty circle {empty:.1f} ly, bound "
            f"{EMPTY_CIRCLE_BOUND:.1f} ly")


class TestFieldDeterminism:

    def test_same_seed_same_field(self):
        """A seed reproduces the galaxy exactly."""
        assert _positions(4242) == _positions(4242)

    def test_different_seeds_differ(self):
        """Different seeds give different galaxies."""
        assert _positions(4242) != _positions(99)

    def test_star_count_scales_with_area(self):
        """Density is constant across the size tiers: a bigger board is
        a bigger galaxy, not an emptier one."""
        for size, (width, height) in UNIVERSE_SIZES.items():
            expected = width * height // (STAR_DENSITY * STAR_DENSITY)
            server_data = GalaxyGenerator(4242).generate(
                player_count=2, universe_size=size)
            assert len(server_data.all_stars) == expected, size
