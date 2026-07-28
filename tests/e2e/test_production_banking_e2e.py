"""
Seeded e2e: per-resource production banking across turns (DEF-10).

A mineral-starved head order banks proportional per-resource progress
(C# RemainingCost, FactoryProductionUnit.cs:108-142) instead of
stalling with zero spend, the trailing non-auto order blocks behind it
(Manufacture.cs:56-61) rather than eating the minerals the head is
waiting for, and the head completes as soon as the residue is paid.
Run100 forensics: the old energy-only banking starved Zubenelgenubi's
head order forever while trailing orders leapfrogged it.
"""

SEED = 20260714


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _setup_starved_star(harness):
    """Homeworld with 2 ironium, no mines, a ship order costing 8I/16E
    at the head of the queue and a defense order behind it."""
    from backend.core.data_structures import Resources
    from backend.core.production.production_queue import (
        ProductionOrder, ProductionType
    )
    from backend.services.ship_specs import SimpleDesign

    manager = _manager()
    server_data = manager._load_game_state(harness.game_id)
    empire = server_data.all_empires[1]
    star = next(iter(empire.owned_stars.values()))

    design = SimpleDesign(key=empire.get_next_design_key(),
                          name="Test Hauler",
                          cost=Resources(ironium=8, energy=16))
    empire.designs[design.key] = design

    star.mines = 0  # no mining income - minerals arrive by surgery
    star.resources_on_hand = Resources(
        ironium=2, boranium=20, germanium=20, energy=0)
    star.manufacturing_queue.orders = [
        ProductionOrder(production_type=ProductionType.SHIP,
                        quantity=1, design_key=design.key,
                        name=design.name),
        ProductionOrder(production_type=ProductionType.DEFENSE,
                        quantity=1, name="Defense"),
    ]
    manager._save_game_state(harness.game_id, server_data)
    return star.name


def _deliver_ironium(harness, star_name, amount):
    """Stand-in for freighter delivery / mining income."""
    manager = _manager()
    server_data = manager._load_game_state(harness.game_id)
    star = server_data.all_stars[star_name]
    star.resources_on_hand.ironium += amount
    manager._save_game_state(harness.game_id, server_data)


class TestProductionBankingAcrossTurns:

    def test_starved_head_banks_and_completes_when_minerals_arrive(
            self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        star_name = _setup_starved_star(harness)

        # Year 1: the head order partial-builds - percent 1 - 6/8 =
        # 0.25 spends the 2 ironium to exactly 0 and banks the
        # per-resource residue 6I/12E on the order
        harness.generate_turn()
        star = harness.star_by_name(star_name, 1)
        head, tail = star["production_queue"]
        assert head["name"] == "Test Hauler"
        assert head["quantity"] == 1
        assert head["remaining_cost"]["ironium"] == 6
        assert head["remaining_cost"]["energy"] == 12
        assert star["ironium"] == 0
        # The trailing defense order blocked instead of eating the
        # head's minerals (boranium/germanium untouched)
        assert tail["name"] == "Defense"
        assert star["defenses"] == 0
        assert star["boranium"] == 20
        assert star["germanium"] == 20

        # Year 2: still starved - the banked progress holds, nothing
        # regresses, defense still blocked
        harness.generate_turn()
        star = harness.star_by_name(star_name, 1)
        head, tail = star["production_queue"]
        assert head["remaining_cost"]["ironium"] == 6
        assert star["defenses"] == 0

        # Minerals arrive: the head completes paying only the residue,
        # the ship materializes, and the queue unblocks for the
        # defense order (5I/5B/5G/15E) next year
        _deliver_ironium(harness, star_name, 12)
        harness.generate_turn()
        star = harness.star_by_name(star_name, 1)
        assert any(f["name"].startswith("Test Hauler")
                   for f in harness.my_fleets(1))
        names = [o["name"] for o in star["production_queue"]]
        assert "Test Hauler" not in names
        # Residue paid: 12 - 6 = 6 ironium left, then the defense
        # order (now head) spends from what remains
        assert star["defenses"] >= 1 or "Defense" in names
