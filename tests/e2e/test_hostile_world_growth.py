"""
Seeded e2e: colonist deaths on a negative-hab world (DEF-9).

Star.cs:341-345 kills 0.1 * colonists * hab_value per year, rounded to
the nearest 100 TOWARD ZERO (C# (int) cast + integer division,
Star.cs:380-383). The old Python floor rounding produced a flat -100
per year on lightly hostile worlds regardless of population; the
series here must decay proportionally to the shrinking population and
match the C# truncation exactly, year by year.
"""

SEED = 20260714
TURNS = 5


def _plant_hostile_colony(harness, colonists):
    """Give empire 1 a colony on a star its race cannot tolerate.

    Returns (star_name, hab_value) - hab_value is fixed for the run
    because nothing terraforms the star.
    """
    from backend.core.globals import NOBODY
    from backend.services.game_manager import get_game_manager

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    empire = server_data.all_empires[1]
    race = empire.race

    star = next(s for s in server_data.all_stars.values()
                if s.owner == NOBODY)
    # Push gravity 30 clicks past the race maximum: that component is
    # -0.30 and hab_value = -0.30/3 = -0.1 (temperature/radiation set
    # inside the tolerated band)
    star.gravity = race.gravity_max + 30
    star.temperature = (race.temperature_min + race.temperature_max) // 2
    star.radiation = (race.radiation_min + race.radiation_max) // 2
    star.owner = 1
    star.colonists = colonists
    star.this_race = race
    empire.owned_stars[star.name] = star
    hab_value = race.hab_value(star)
    assert hab_value < 0
    manager._save_game_state(harness.game_id, server_data)
    return star.name, hab_value


def _expected_growth(colonists, hab_value):
    """C#-exact yearly growth (Star.cs:341-345, 380-383)."""
    raw = 0.1 * colonists * hab_value
    truncated = int(raw)  # (int) cast truncates toward zero
    if truncated >= 0:
        return (truncated // 100) * 100
    return -((-truncated) // 100) * 100


class TestHostileWorldDeaths:

    def test_death_series_matches_csharp_truncation(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        star_name, hab_value = _plant_hostile_colony(
            harness, colonists=39900)

        # Deterministic expectation computed independently of
        # calculate_growth: raw deaths year 1 are
        # 0.1 * 39900 * -0.1 = -399.0 -> -300 (the floor bug gave
        # -400 here and a flat -100 on any population under 10000)
        colonists = 39900
        series = []
        expected = []
        for _ in range(TURNS):
            colonists += _expected_growth(colonists, hab_value)
            expected.append(colonists)
            harness.generate_turn()
            series.append(harness.star_by_name(star_name, 1)["colonists"])

        assert series == expected
        # Proportional decay, not a flat -100 per year: early-year
        # deaths on ~39900 colonists must exceed 100
        assert series[0] <= 39900 - 300

    def test_small_deaths_truncate_to_zero(self, harness):
        # Deaths of 1-99 colonists round to 0 (canon): with 900
        # colonists at hab -0.1 the raw growth is -9.0 -> 0, so the
        # population holds instead of bleeding 100/year
        harness.create_game(seed=SEED, size="tiny", players=2)
        star_name, hab_value = _plant_hostile_colony(
            harness, colonists=900)
        assert _expected_growth(900, hab_value) == 0

        for _ in range(3):
            harness.generate_turn()
            assert harness.star_by_name(star_name, 1)["colonists"] == 900
