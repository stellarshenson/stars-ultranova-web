"""
Reproducibility proof for the seeded e2e gameplay harness.

Same seed + same submitted commands must produce identical state after
any number of generated turns; a different seed must produce a
different galaxy.
"""

TURNS = 5


def _galaxy(harness, empire_id=1):
    """Star names and positions as seen at game start."""
    return sorted(
        (s["name"], s["position_x"], s["position_y"])
        for s in harness.state(empire_id)["stars"]
    )


def _play(harness, seed):
    """Create a seeded game, submit a fixed command script, and play
    TURNS turns. Returns (galaxy, per-turn digest list)."""
    harness.create_game(seed=seed, size="small", players=2)
    galaxy = _galaxy(harness)

    # Identical command in every run: research budget + Energy focus
    levels = harness.state(1)["research"]["levels"]
    topics = {k: 0 for k in levels}
    topics["Energy"] = 1
    result = harness.submit(1, "research",
                            {"budget": 15, "topics": {"levels": topics}})
    assert result["status"] in ("applied", "unchanged")

    digests = [harness.generate_turn()["digests"] for _ in range(TURNS)]
    return galaxy, digests


class TestReproducibility:
    """Seeded games are bit-for-bit reproducible through the full API."""

    def test_same_seed_identical_galaxy_and_turns(self, harness):
        galaxy_a, digests_a = _play(harness, seed=42)
        galaxy_b, digests_b = _play(harness, seed=42)

        assert galaxy_a == galaxy_b, "same seed must produce same galaxy"
        for turn_index, (da, db) in enumerate(zip(digests_a, digests_b), 1):
            assert da == db, (
                f"state digests diverged at generated turn {turn_index}"
            )

    def test_different_seed_different_galaxy(self, harness):
        harness.create_game(seed=42, size="small", players=2)
        galaxy_a = _galaxy(harness)
        harness.create_game(seed=43, size="small", players=2)
        galaxy_b = _galaxy(harness)

        assert galaxy_a != galaxy_b, "different seeds must differ"


class TestHarnessFinders:
    """The small finder helpers return coherent views."""

    def test_finders(self, harness):
        harness.create_game(seed=7, size="small", players=2)

        stars = harness.my_stars()
        assert len(stars) == 1  # one homeworld at game start
        home = stars[0]
        assert home["intel"] == "owned"
        assert harness.star_by_name(home["name"])["name"] == home["name"]

        fleets = harness.my_fleets()
        assert len(fleets) >= 1
        assert all(f["owner"] == 1 for f in fleets)
