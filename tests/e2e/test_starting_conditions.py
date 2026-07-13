"""
Seeded e2e proof of PRT starting conditions through the full API.

A default JOAT race starts with its tech grants; a wizard-designed IT
race starts with its extra fleet, PRT+IFE tech, accelerated-BBS
population and leftover points spent on mines.
"""

# Default wizard fields as saved by the race designer (race-wizard.js).
# colonistsPerResource 1500 buys the budget headroom for IT+IFE under
# the advantage-point gate: the race scores 69 points, so the leftover
# spend is the clamped maximum of 50 (Race.cs:215-221).
IT_RACE = {
    "name": "Testers",
    "pluralName": "Testers",
    "prt": "IT",
    "lrts": ["IFE"],
    "factoryCost": 10,
    "factoryEfficiency": 10,
    "factoryNumberPer10k": 10,
    "mineCost": 5,
    "mineEfficiency": 10,
    "mineNumberPer10k": 10,
    "colonistsPerResource": 1500,
    "gravityMin": 15, "gravityMax": 85,
    "temperatureMin": 15, "temperatureMax": 85,
    "radiationMin": 15, "radiationMax": 85,
    "growthRate": 15,
    "startAtLevel3": False,
    "leftoverPointTarget": "Mines",
}


class TestJoatStartingTech:
    """Default race (Humanoids, JOAT) starts at tech 3 everywhere."""

    def test_joat_tech_grants(self, harness):
        harness.create_game(seed=1234, size="small", players=2)
        levels = harness.state(1)["research"]["levels"]
        assert all(levels[key] == 3 for key in levels), levels


class TestItStartingConditions:
    """IT+IFE wizard race with accelerated start and Mines leftover."""

    def test_it_accelerated_scenario(self, harness):
        harness.create_game(seed=1234, size="small", players=2,
                            race=IT_RACE, accelerated_start=True)
        state = harness.state(1)

        # PRT tech grants + IFE: Propulsion 5+1, Construction 5, rest 0
        levels = state["research"]["levels"]
        assert levels["Propulsion"] == 6
        assert levels["Construction"] == 5
        assert all(levels[key] == 0 for key in levels
                   if key not in ("Propulsion", "Construction")), levels

        # Accelerated BBS population and leftover points on mines
        # (real advantage-point budget 69, clamped to 50)
        home = harness.my_stars(1)[0]
        assert home["colonists"] == 100000
        assert home["mines"] == 10 + 50 // 2

        # IT starting fleet: scout, colony ship, destroyer, privateer
        # plus the homeworld starbase
        fleet_names = {f["name"] for f in harness.my_fleets(1)}
        assert "Long Range Scout #1" in fleet_names
        assert "Santa Maria #1" in fleet_names
        assert "Stalwart Defender #1" in fleet_names
        assert "Swashbuckler #1" in fleet_names
        starbases = [f for f in harness.my_fleets(1) if f["is_starbase"]]
        assert len(starbases) == 1

        # The game still advances cleanly and the population grows
        harness.generate_turn()
        home_after = harness.my_stars(1)[0]
        assert home_after["colonists"] > 100000
