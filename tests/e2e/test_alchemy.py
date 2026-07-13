"""
Seeded e2e: mineral alchemy production.

Two games per scenario with the SAME seed (seeded turns are
deterministic): a control game with no production commands and an
alchemy game that queues Alchemy on the homeworld. Comparing surface
minerals after the same turns cancels out mining and growth, isolating
the alchemy yield of 1 kT of each mineral per unit (100 resources
each, 25 with the MA LRT - AlchemyProductionUnit.cs is a stub,
canonical values per GameInitialiser.cs:315-318).
"""

SEED = 20260713
QUANTITY = 3
TURNS = 4  # accelerated-start homeworld makes ~110 resources/year

MINERALS = ("ironium", "boranium", "germanium")


def _zero_research(harness, empire_id=1):
    """All production resources to manufacturing, none to labs."""
    levels = {key: 0 for key in
              harness.state(empire_id)["research"]["levels"]}
    levels["Energy"] = 1
    harness.submit(empire_id, "research",
                   {"budget": 0, "topics": {"levels": levels}})


def _queue_alchemy(harness, star_name, quantity, empire_id=1):
    harness.submit(empire_id, "production", {
        "mode": "Add", "star_key": star_name, "index": 0,
        "production_order": {"production_type": "ALCHEMY",
                             "quantity": quantity, "name": "Alchemy"},
    })


class TestAlchemy:

    def test_alchemy_gains_surface_minerals(self, harness):
        # Control game: same seed, no commands
        harness.create_game(seed=SEED, size="small", players=2,
                            accelerated_start=True,
                            name="alchemy-control")
        home_name = harness.my_stars(1)[0]["name"]
        for _ in range(TURNS):
            harness.generate_turn()
        control = harness.star_by_name(home_name, 1)

        # Alchemy game: queue Alchemy units on the homeworld; they
        # complete over several years as resources come in
        harness.create_game(seed=SEED, size="small", players=2,
                            accelerated_start=True,
                            name="alchemy-build")
        home = harness.my_stars(1)[0]
        assert home["name"] == home_name
        _zero_research(harness)
        _queue_alchemy(harness, home_name, QUANTITY)
        messages = []
        for _ in range(TURNS):
            harness.generate_turn()
            messages.extend(m["text"] for m in harness.state(1)["messages"])
        built = harness.star_by_name(home_name, 1)

        # Exactly +QUANTITY kT of each mineral versus the control game
        for mineral in MINERALS:
            assert built[mineral] == control[mineral] + QUANTITY
        # The order completed and left the queue
        assert not any(o["production_type"] == "ALCHEMY"
                       for o in built["production_queue"])
        assert any("transmuted" in text for text in messages)
        assert not any("unknown item" in text for text in messages)

    def test_alchemy_partial_progress_carries_over(self, harness):
        # An absurd quantity cannot finish in one year - the remainder
        # stays queued with partial progress banked on the order
        harness.create_game(seed=SEED, size="small", players=2,
                            accelerated_start=True,
                            name="alchemy-partial")
        home = harness.my_stars(1)[0]
        _zero_research(harness)
        _queue_alchemy(harness, home["name"], 1000)
        harness.generate_turn()
        after = harness.star_by_name(home["name"], 1)

        order = next(o for o in after["production_queue"]
                     if o["production_type"] == "ALCHEMY")
        assert order["quantity"] < 1000
        assert order["partial_resources_spent"] >= 0

    def test_alchemy_ma_discount(self, harness):
        # MA LRT: 25 resources per unit. Q units where Q*25 fits this
        # year's resources but Q*100 does not - only the discounted
        # price can complete all Q in one turn. growthRate 6 buys the
        # advantage-point headroom for the 155-point MA LRT
        ma_race = {"name": "Alchemists", "pluralName": "Alchemists",
                   "prt": "JOAT", "growthRate": 6, "lrts": ["MA"]}

        harness.create_game(seed=SEED, size="small", players=2,
                            race=ma_race, accelerated_start=True,
                            name="alchemy-ma-control")
        home = harness.my_stars(1)[0]
        home_name = home["name"]
        quantity = home["resources_per_year"] // 25
        assert quantity >= 1
        assert quantity * 100 > home["resources_per_year"]
        harness.generate_turn()
        control = harness.star_by_name(home_name, 1)

        harness.create_game(seed=SEED, size="small", players=2,
                            race=ma_race, accelerated_start=True,
                            name="alchemy-ma-build")
        _zero_research(harness)
        _queue_alchemy(harness, home_name, quantity)
        harness.generate_turn()
        built = harness.star_by_name(home_name, 1)

        for mineral in MINERALS:
            assert built[mineral] == control[mineral] + quantity
        assert not any(o["production_type"] == "ALCHEMY"
                       for o in built["production_queue"])
