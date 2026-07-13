"""
Seeded e2e research fidelity scenarios.

Proves the race wizard's research economics reach gameplay end to end:
start-at-level-3 grants, the exact Research.cs next-cost numbers per
cost multiplier, cumulative-bank spillover across turns, and a cheap
research race out-leveling an expensive one over identical play.
"""

TURNS = 8

NORMAL_COSTS = {
    "energy": "normal", "weapons": "normal", "propulsion": "normal",
    "construction": "normal", "electronics": "normal",
    "biotechnology": "normal",
}


def _race(name, costs, start_at_3=False):
    # growthRate 6 buys the raw-point headroom (+3600) that keeps every
    # research-cost combination in this file legal under the
    # advantage-point gate, without touching research economics
    return {
        "name": name,
        "pluralName": name,
        "prt": "JOAT",
        "growthRate": 6,
        "startAtLevel3": start_at_3,
        "researchCosts": costs,
    }


def _focus_energy(harness, budget):
    """Submit a research command targeting Energy."""
    topics = {"Biotechnology": 0, "Electronics": 0, "Energy": 1,
              "Propulsion": 0, "Weapons": 0, "Construction": 0}
    result = harness.submit(1, "research",
                            {"budget": budget, "topics": {"levels": topics}})
    assert result["status"] in ("applied", "unchanged")


class TestResearchFidelity:
    """Wizard research economics through the full API."""

    def test_start_at_level3_costs_and_spillover(self, harness):
        costs = dict(NORMAL_COSTS, energy="cheap", weapons="expensive")
        # accelerated start compensates for the growth-6 race's slower
        # economy so a level-up still lands within TURNS turns
        harness.create_game(seed=42, size="small", players=2,
                            race=_race("Boffins", costs, start_at_3=True),
                            accelerated_start=True)

        research = harness.state(1)["research"]

        # (a) JOAT 3 + ExtraTech 1 in every field
        assert all(level == 4 for level in research["levels"].values())

        # (b) Exact Research.cs next costs: level 5 with all six fields
        # at 4 (tech adjustment 240): base = F(10)*10 + 240 = 790
        assert research["next_costs"]["Energy"] == 395      # cheap 50%
        assert research["next_costs"]["Weapons"] == 1382    # expensive 175%
        assert research["next_costs"]["Propulsion"] == 790  # standard

        # (c) Play turns with full budget on Energy; the bank must be
        # monotonically nondecreasing (cumulative, never reset on
        # level-up) and the level must rise
        _focus_energy(harness, budget=100)

        start_level = research["levels"]["Energy"]
        last_bank = research["progress"]["Energy"]
        tech_advance_seen = False

        for _ in range(TURNS):
            result = harness.generate_turn()
            research = harness.state(1)["research"]
            bank = research["progress"]["Energy"]
            assert bank >= last_bank, (
                "research bank must be cumulative - never reset"
            )
            last_bank = bank
            if any("Tech Level" in m.get("text", "")
                   for m in result["messages"]
                   if m.get("audience") in (1, 0, -1)):
                tech_advance_seen = True

        assert research["levels"]["Energy"] > start_level
        # (d) Level-up turns announce the advance
        assert tech_advance_seen

    def test_cheap_race_levels_faster_than_expensive(self, harness):
        """Identical seed and identical play: all-cheap research must
        out-level all-expensive over TURNS turns."""
        final_levels = {}
        for label, choice in (("cheap", "cheap"), ("expensive", "expensive")):
            costs = {field: choice for field in NORMAL_COSTS}
            harness.create_game(seed=42, size="small", players=2,
                                race=_race("Boffins", costs),
                                accelerated_start=True)
            _focus_energy(harness, budget=100)
            for _ in range(TURNS):
                harness.generate_turn()
            final_levels[label] = harness.state(1)["research"]["levels"]

        assert final_levels["cheap"]["Energy"] > \
            final_levels["expensive"]["Energy"]
        assert sum(final_levels["cheap"].values()) > \
            sum(final_levels["expensive"].values())
