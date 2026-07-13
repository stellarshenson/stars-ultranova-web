"""
Wave-1 cross-feature integration: one seeded game whose wizard race
combines all three implemented gaps - non-default research costs
(energy cheap, weapons expensive), a PRT with tech grants (SS:
Electronics 5) and a nonzero leftover advantage-point budget spent on
factories - played for 10 turns through the full API.
"""

TURNS = 10

# growthRate 14 scores 43 advantage points with otherwise default
# habitability/economy - a real (unclamped) leftover budget in (0, 50)
# per Race.cs GetLeftoverAdvantagePoints (lines 215-221)
LEFTOVER_POINTS = 43

SS_RACE = {
    "name": "Integrators",
    "pluralName": "Integrators",
    "prt": "SS",
    "growthRate": 14,
    "startAtLevel3": False,
    "researchCosts": {
        "energy": "cheap", "weapons": "expensive",
        "propulsion": "normal", "construction": "normal",
        "electronics": "normal", "biotechnology": "normal",
    },
    "leftoverPointTarget": "Factories",
}


class TestWave1Integration:
    """Research fidelity + PRT starting conditions + advantage points
    interacting in a single seeded 10-turn game."""

    def test_ss_race_ten_turn_integration(self, harness):
        harness.create_game(seed=4242, size="small", players=2,
                            race=SS_RACE, accelerated_start=True)
        state = harness.state(1)

        # (a) PRT tech grants: SS starts with Electronics 5, rest 0
        # (GameInitialiser.cs ProcessPrimaryTraits, lines 187-254)
        levels = state["research"]["levels"]
        assert levels["Electronics"] == 5
        assert all(levels[key] == 0 for key in levels
                   if key != "Electronics"), levels

        # (b) Leftover advantage points on factories: one factory for
        # five points (HomeStarLeftoverpointsAdjuster.cs:54-58) on top
        # of the base 10
        home = harness.my_stars(1)[0]
        assert home["factories"] == 10 + LEFTOVER_POINTS // 5

        # (c) Exact Research.cs next costs with tech adjustment 50
        # (five levels attained): base = F(6)*10 + 50 = 130
        next_costs = state["research"]["next_costs"]
        assert next_costs["Energy"] == 65        # cheap 50%
        assert next_costs["Weapons"] == 227      # expensive 175%
        assert next_costs["Propulsion"] == 130   # standard

        # (d) Play TURNS turns with full budget on Energy; each turn
        # the level must advance exactly when the cumulative bank
        # crosses the multiplied-cost threshold reported before the
        # turn (Research.cs:43-62 via TurnGenerator research step)
        topics = {key: 0 for key in levels}
        topics["Energy"] = 1
        result = harness.submit(1, "research",
                                {"budget": 100,
                                 "topics": {"levels": topics}})
        assert result["status"] in ("applied", "unchanged")

        research = state["research"]
        for _ in range(TURNS):
            prev_level = research["levels"]["Energy"]
            prev_threshold = research["next_costs"]["Energy"]
            harness.generate_turn()
            research = harness.state(1)["research"]
            bank = research["progress"]["Energy"]
            level = research["levels"]["Energy"]
            if bank >= prev_threshold:
                assert level > prev_level, (
                    "bank crossed the multiplied cost threshold "
                    "without a level-up"
                )
            else:
                assert level == prev_level, (
                    "level advanced before the multiplied cost "
                    "threshold was reached"
                )

        # The cheap-energy race must actually level up within TURNS
        assert research["levels"]["Energy"] > 0
