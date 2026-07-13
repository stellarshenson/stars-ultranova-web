"""
Seeded e2e: auto-build production orders and queue reorder.

The homeworld queues an auto Factory x500 (far more than a few years
of resources can build) ahead of a concrete Mine x2. The auto order
soaks up every year's resources, so the mine behind it waits blocked
(ProductionOrder.IsBlocking, ProductionOrder.cs:96-99) while factories
keep rising and the auto order persists in the queue across turns.
A Move command then puts the mine first and it builds next year.
"""

SEED = 20260714
TURNS = 3


def _zero_research(harness, empire_id=1):
    """All production resources to manufacturing, none to labs."""
    levels = {key: 0 for key in
              harness.state(empire_id)["research"]["levels"]}
    levels["Energy"] = 1
    harness.submit(empire_id, "research",
                   {"budget": 0, "topics": {"levels": levels}})


def _setup_queue(harness, star_name, empire_id=1):
    """Auto Factory x500 first, concrete Mine x2 behind it."""
    harness.submit(empire_id, "production", {
        "mode": "Add", "star_key": star_name, "index": 0,
        "production_order": {"production_type": "FACTORY",
                             "quantity": 500, "name": "Factory",
                             "is_auto_build": True},
    })
    harness.submit(empire_id, "production", {
        "mode": "Add", "star_key": star_name, "index": 1,
        "production_order": {"production_type": "MINE",
                             "quantity": 2, "name": "Mine"},
    })


class TestProductionAutoBuild:

    def test_autobuild_skip_and_reorder(self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            accelerated_start=True)
        home = harness.my_stars(1)[0]
        home_name = home["name"]
        _zero_research(harness)
        _setup_queue(harness, home_name)

        # (a) The auto order keeps building factories over multiple
        # turns while the blocked concrete mine order waits behind it
        factories = home["factories"]
        mines = home["mines"]
        for _ in range(TURNS):
            harness.generate_turn()
            star = harness.star_by_name(home_name, 1)

            assert star["factories"] > factories  # built again this year
            factories = star["factories"]
            # Operable cap respected (FactoryProductionUnit.cs:90-95)
            assert star["factories"] <= star["operable_factories"]
            # Mine order waits: blocked, not built, not dropped
            assert star["mines"] == mines
            queue = star["production_queue"]
            assert [o["production_type"] for o in queue] == [
                "FACTORY", "MINE"]
            # Auto order persists with quantity intact minus builds
            assert queue[0]["is_auto_build"] is True
            assert queue[0]["quantity"] > 0
            assert queue[1]["is_auto_build"] is False
            assert queue[1]["quantity"] == 2

        # (b) Reorder: move the mine order to the front
        harness.submit(1, "production", {
            "mode": "Move", "star_key": home_name,
            "index": 1, "to_index": 0,
        })
        queue = harness.star_by_name(home_name, 1)["production_queue"]
        assert [o["production_type"] for o in queue] == ["MINE", "FACTORY"]

        # (c) Next year the mine builds first, then the auto factory
        # order continues with the remaining resources
        harness.generate_turn()
        star = harness.star_by_name(home_name, 1)
        assert star["mines"] == mines + 2
        assert star["factories"] > factories
        queue = star["production_queue"]
        assert [o["production_type"] for o in queue] == ["FACTORY"]
        assert queue[0]["is_auto_build"] is True

    def test_autobuild_run_is_deterministic(self, harness):
        """Same seed + same commands -> identical state digest."""
        digests = []
        for _ in range(2):
            harness.create_game(seed=SEED, size="small", players=2,
                                accelerated_start=True)
            home_name = harness.my_stars(1)[0]["name"]
            _zero_research(harness)
            _setup_queue(harness, home_name)
            harness.submit(1, "production", {
                "mode": "Move", "star_key": home_name,
                "index": 1, "to_index": 0,
            })
            for _ in range(TURNS):
                harness.generate_turn()
            digests.append(harness.state_digest(1))
        assert digests[0] == digests[1]
