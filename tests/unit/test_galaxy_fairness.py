"""
Homeworld placement fairness (DEF-16).

The C# reference places homeworlds first on a uniform density field
with enforced minimum separation (StarMapGenerator.cs:93-106, 156-172,
215-238), making every start statistically equivalent. The web
generator keeps its GMM star field and guarantees fairness by
SELECTION: every homeworld must have at least
N_min = max(3, ceil(0.5 * median neighborhood count)) stars within
50 ly, and homeworlds are mutually separated by at least the
C#-derived min(width, height) / (2 * (floor(sqrt(players)) + 1)),
relaxable to half that on candidate shortage.

run100 regression: seed 4242 (small map) gave e1 nine stars within
50 ly and e2 one, with the second-nearest 80 ly away - the expansion
race was decided by galaxy generation before turn 1.
"""

import math

import pytest

from backend.services.galaxy_generator import GalaxyGenerator, UNIVERSE_SIZES

SEEDS = [4242, 0, 1, 3, 42, 99, 777, 1111, 12345, 20260713]

RADIUS = GalaxyGenerator.HOMEWORLD_NEIGHBORHOOD_RADIUS  # 50 ly


def _generate(seed, players, size):
    server_data = GalaxyGenerator(seed).generate(
        player_count=players, universe_size=size)
    stars = list(server_data.all_stars.values())
    homes = [
        next(iter(server_data.all_empires[i + 1].owned_stars.values()))
        for i in range(players)
    ]
    return stars, homes


def _neighborhood_counts(stars):
    counts = {}
    for star in stars:
        counts[star.name] = sum(
            1 for other in stars
            if other is not star
            and math.hypot(star.position.x - other.position.x,
                           star.position.y - other.position.y) <= RADIUS
        )
    return counts


def _n_min(counts):
    sorted_counts = sorted(counts.values())
    median = sorted_counts[len(sorted_counts) // 2]
    return max(3, math.ceil(0.5 * median))


class TestHomeworldFairness:

    @pytest.mark.parametrize("players", [2, 4])
    @pytest.mark.parametrize("seed", SEEDS)
    def test_neighborhood_floor(self, seed, players):
        """Every homeworld has at least N_min stars within 50 ly -
        the stated fairness bound; no more 1-star corner exiles."""
        stars, homes = _generate(seed, players, "small")
        counts = _neighborhood_counts(stars)
        n_min = _n_min(counts)

        for home in homes:
            assert counts[home.name] >= n_min, (
                f"seed {seed}: {home.name} has {counts[home.name]} "
                f"stars within {RADIUS} ly, floor {n_min}"
            )

    @pytest.mark.parametrize("players", [2, 4])
    @pytest.mark.parametrize("seed", SEEDS)
    def test_mutual_separation(self, seed, players):
        """Pairwise separation honors the C#-derived floor
        (StarMapGenerator.cs:160-163), relaxable to half."""
        width, height = UNIVERSE_SIZES["small"]
        player_factor = int(math.floor(math.sqrt(players))) + 1
        min_sep = min(width, height) / (2 * player_factor)

        _, homes = _generate(seed, players, "small")
        for i, a in enumerate(homes):
            for b in homes[i + 1:]:
                dist = math.hypot(a.position.x - b.position.x,
                                  a.position.y - b.position.y)
                assert dist >= 0.5 * min_sep, (
                    f"seed {seed}: {a.name} and {b.name} only "
                    f"{dist:.1f} ly apart (floor {0.5 * min_sep})"
                )

    def test_tiny_map_still_terminates(self):
        """Tiny maps (64 stars, min_sep 50) always yield a full set
        of sufficiently-dense starts via the relaxation ladder."""
        stars, homes = _generate(4242, 2, "tiny")
        counts = _neighborhood_counts(stars)
        assert len(homes) == 2
        assert len({h.name for h in homes}) == 2
        for home in homes:
            assert counts[home.name] >= 3

    def test_selection_deterministic(self):
        """Same seed twice: identical homeworlds and positions."""
        _, homes_a = _generate(4242, 2, "small")
        _, homes_b = _generate(4242, 2, "small")
        assert [h.name for h in homes_a] == [h.name for h in homes_b]
        assert [(h.position.x, h.position.y) for h in homes_a] == \
            [(h.position.x, h.position.y) for h in homes_b]

    def test_run100_seed_4242_regression(self):
        """The forensic case: both starts on seed 4242 now clear the
        floor (was 9-vs-1 within 50 ly)."""
        stars, homes = _generate(4242, 2, "small")
        counts = _neighborhood_counts(stars)
        home_counts = [counts[h.name] for h in homes]
        assert min(home_counts) >= 3
