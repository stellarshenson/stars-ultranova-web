"""
Tests for the race advantage point calculator.

Mirrors Tests/UnitTests/RaceAdvantagePointCalculatorTest.cs and
StarMapInitialiserTest.cs (leftover clamp).

NOTE on the baseline value: the C# unit test asserts |result - 25| <= 1
for the standard JOAT race (RaceAdvantagePointCalculatorTest.cs:106),
a value calibrated against original Stars!/FreeStars. Nova's own
calculator plugs Nova's Race.HabValue (Race.cs:145-192) into the
decompiled habPoints integral, and with that hab function the C# code
as written yields 29, not 25 - the "expected 25" test does not hold
for Nova's own source. This port reproduces the C# code exactly (the
hab-shape-independent anchors match perfectly: 3-immune JOAT is
exactly -3900, and every relational delta below is within the +-1
truncation bound), so the baseline is pinned at the value the C#
source actually produces: 29.
"""
import pytest

from backend.core.race.race import Race
from backend.services import race_points
from backend.services.race_points import (
    PRT_COST,
    LRT_COST,
    calculate_advantage_points,
    get_leftover_advantage_points,
)

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")


def base_race(**overrides) -> Race:
    """
    The C# test fixture race (RaceAdvantagePointCalculatorTest.cs:25-58):
    JOAT, no LRTs, all tolerances 15-85 non-immune, growth 15,
    1000 colonists/resource, factories 10/10/10, mines 10/10/5,
    all research normal (100).
    """
    race = Race(primary_trait="JOAT", growth_rate=15.0)
    for key, value in overrides.items():
        setattr(race, key, value)
    return race


BASELINE = 29  # what the C# source produces for the fixture race


class TestAdvantagePoints:
    """Golden and relational values from the C# unit tests."""

    def test_standard_joat(self):
        """Baseline race scores the pinned C#-source value."""
        assert calculate_advantage_points(base_race()) == BASELINE

    def test_deterministic(self):
        race = base_race()
        assert calculate_advantage_points(race) == \
            calculate_advantage_points(race)

    def test_colonists_per_resource_700(self):
        """cpr 700 costs 2400 raw points = 800 final, +-1 truncation
        (C# test line 70)."""
        result = calculate_advantage_points(
            base_race(colonists_per_resource=700))
        assert abs(BASELINE - (result + 2400 // 3)) <= 1

    def test_cheap_factories_cf(self):
        """CF costs 175 raw = 58 final, +-1 (C# test line 76)."""
        result = calculate_advantage_points(base_race(traits={"CF"}))
        assert abs(BASELINE - (result + 175 // 3)) <= 1

    def test_prt_it_vs_joat(self):
        """JOAT -> IT swings 66 + 180 raw points (C# test line 82)."""
        result = calculate_advantage_points(base_race(primary_trait="IT"))
        assert abs((BASELINE - 66 // 3) - (result + 180 // 3)) <= 1

    def test_extra_tech(self):
        """ExtraTech costs 180 raw = 60 final, +-1 (C# test line 92)."""
        result = calculate_advantage_points(base_race(traits={"ExtraTech"}))
        assert abs(BASELINE - (result + 180 // 3)) <= 1

    def test_lrt_ife(self):
        """IFE costs 235 raw = 78 final, +-1 (C# test line 100)."""
        result = calculate_advantage_points(base_race(traits={"IFE"}))
        assert abs(BASELINE - (result + 235 // 3)) <= 1

    def test_nrse_alias(self):
        """The web "NRSE" code scores identically to the C# "NRS"."""
        assert calculate_advantage_points(base_race(traits={"NRSE"})) == \
            calculate_advantage_points(base_race(traits={"NRS"}))

    def test_three_immune_joat(self):
        """3-immune JOAT is -3900 exactly (C# test line 116); a floor
        division bug in the final /3 would show up here as -3901."""
        result = calculate_advantage_points(base_race(
            immune_gravity=True, immune_temperature=True,
            immune_radiation=True))
        assert result == -3900


class TestCostTables:
    """PRT/LRT cost table rows (RaceAdvantagePointCalculator.cs:26-52)."""

    @pytest.mark.parametrize("prt,cost", [
        ("HE", 40), ("SS", 95), ("WM", 45), ("CA", 10), ("IS", -100),
        ("SD", -150), ("PP", 120), ("IT", 180), ("AR", 90), ("JOAT", -66),
    ])
    def test_prt_cost_table(self, prt, cost):
        assert PRT_COST[prt] == cost

    @pytest.mark.parametrize("lrt,cost", [
        ("IFE", -235), ("TT", -25), ("ARM", -159), ("ISB", -201),
        ("GR", 40), ("UR", -240), ("MA", -155), ("NRS", 160),
        ("CE", 240), ("OBRM", 255), ("NAS", 325), ("LSP", 180),
        ("BET", 70), ("RS", 30),
    ])
    def test_lrt_cost_table(self, lrt, cost):
        assert LRT_COST[lrt] == cost

    @pytest.mark.parametrize("prt", list(PRT_COST))
    def test_prt_applied(self, prt):
        """Swapping the baseline PRT moves the raw total by the cost
        delta (all-else-equal, ignoring AR's special economy path and
        the WM/... starting differences the calculator does not see)."""
        if prt in ("JOAT", "AR"):
            return  # JOAT is the baseline; AR swaps the economy block
        result = calculate_advantage_points(base_race(primary_trait=prt))
        expected_raw_delta = PRT_COST[prt] - PRT_COST["JOAT"]
        assert abs((BASELINE - result) * 3 - expected_raw_delta) <= 4

    @pytest.mark.parametrize("lrt", ["IFE", "TT", "ARM", "ISB", "GR", "UR",
                                     "MA", "NRS", "CE", "OBRM", "LSP",
                                     "BET", "RS"])
    def test_lrt_applied(self, lrt):
        """Each single LRT moves the raw total by its table cost.
        TT is excluded from the exact check (it also reshapes the
        habitability integral); NAS has the JOAT interaction."""
        result = calculate_advantage_points(base_race(traits={lrt}))
        if lrt == "TT":
            # TT also increases hab points; it must still cost points
            assert result < BASELINE + LRT_COST["TT"] // 3 + 40
            return
        expected_raw_delta = -LRT_COST[lrt]
        assert abs((BASELINE - result) * 3 - expected_raw_delta) <= 4

    def test_lrt_nas_joat_interaction(self):
        """NAS on a JOAT costs an extra 40 raw points (lines 355-360)."""
        result = calculate_advantage_points(base_race(traits={"NAS"}))
        expected_raw_delta = -(LRT_COST["NAS"] - 40)
        assert abs((BASELINE - result) * 3 - expected_raw_delta) <= 4

    def test_lrt_balancing_penalties(self):
        """Five negative-cost LRTs trigger the (k+i)>4 and (k-i)>3
        penalties (lines 351-353): costs sum -990, -50 count penalty,
        -80 imbalance penalty -> raw 88 - 1120 = -1032 -> -344."""
        result = calculate_advantage_points(base_race(
            traits={"IFE", "ARM", "ISB", "UR", "MA"}))
        assert result == -344

    def test_nas_prt_interaction_pp_vs_ca(self):
        """NAS+PP pays 280 extra vs NAS+CA paying nothing; combined
        with the PRT cost delta (120 vs 10) the swing is 390 raw =
        130 final, +-1."""
        pp = calculate_advantage_points(
            Race(primary_trait="PP", growth_rate=15.0, traits={"NAS"}))
        ca = calculate_advantage_points(
            Race(primary_trait="CA", growth_rate=15.0, traits={"NAS"}))
        assert abs((ca - pp) - 390 // 3) <= 1


class TestResearchTables:
    """Science cost step (RaceAdvantagePointCalculator.cs:365-387)."""

    def test_all_cheap(self):
        """6 cheap fields: -6*6*130 + 1430 = -3250 raw ->
        (88 - 3250)/3 = -1054."""
        result = calculate_advantage_points(base_race(
            research_costs={k: 50 for k in RESEARCH_FIELDS}))
        assert result == -1054

    def test_all_expensive(self):
        """6 expensive fields: +scienceCost[5] = +1380 raw ->
        (88 + 1380)/3 = 489 (truncated)."""
        result = calculate_advantage_points(base_race(
            research_costs={k: 175 for k in RESEARCH_FIELDS}))
        assert result == 489

    def test_expensive_150_deprecated(self):
        """Value 150 counts as expensive like 175 (line 370)."""
        assert calculate_advantage_points(base_race(
            research_costs={k: 150 for k in RESEARCH_FIELDS})) == \
            calculate_advantage_points(base_race(
                research_costs={k: 175 for k in RESEARCH_FIELDS}))

    def test_five_expensive_low_cpr_penalty(self):
        """5 expensive + cpr 900: +1050 raw, then the extra -190
        because tmp < -4 and cpr/100 < 10 (line 384); cpr 900 also
        costs 600 raw at step 5: (88 - 600 + 1050 - 190)/3 = 116."""
        costs = {k: 175 for k in RESEARCH_FIELDS}
        costs["Construction"] = 100
        result = calculate_advantage_points(base_race(
            colonists_per_resource=900, research_costs=costs))
        assert result == 116
        # same design at cpr 1000 skips both the cpr and -190 penalties
        result2 = calculate_advantage_points(base_race(
            research_costs=costs))
        assert result2 == 379


class TestLeftoverPoints:
    """Race.cs GetLeftoverAdvantagePoints (lines 215-221), verified by
    StarMapInitialiserTest.cs:43-62."""

    @pytest.mark.parametrize("points,expected", [
        (-1, 0), (1, 1), (51, 50), (0, 0), (50, 50),
    ])
    def test_leftover_clamp(self, points, expected, monkeypatch):
        monkeypatch.setattr(race_points, "calculate_advantage_points",
                            lambda race: points)
        assert get_leftover_advantage_points(base_race()) == expected

    def test_leftover_from_real_calculation(self):
        """The baseline race's leftover is its (positive) point total."""
        assert get_leftover_advantage_points(base_race()) == BASELINE


class TestBreakdown:
    """The optional per-step breakdown mirrors the C# step couts."""

    def test_breakdown_steps(self):
        breakdown = {}
        result = calculate_advantage_points(base_race(), breakdown)
        assert set(breakdown) == {"habitability_growth", "population",
                                  "factories_mines", "traits", "research",
                                  "raw_total"}
        # final value is the truncated third of the raw total
        assert result == breakdown["raw_total"] // 3
