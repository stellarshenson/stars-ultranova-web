"""
Unit tests for production auto-build and skip/block semantics.

Verifies parity with the C# manufacture loop: a skipped non-auto order
blocks the whole queue (ProductionOrder.IsBlocking, ProductionOrder.cs:
96-99; Manufacture.cs:56-61), a skipped auto-build order is passed over
with quantity intact and persists in the queue, and completed orders
(auto-build included) are removed (Manufacture.cs:74-83 - Nova removes
finished auto orders, there is no Stars!-style build-forever).
"""

from backend.core.data_structures import EmpireData, Resources
from backend.core.game_objects.star import Star
from backend.core.production.production_queue import (
    ProductionOrder, ProductionType
)
from backend.core.race.race import Race
from backend.core.globals import MAX_DEFENSES
from backend.server.turn_steps import StarUpdateStep


def make_empire() -> EmpireData:
    empire = EmpireData(id=1)
    empire.race = Race()
    return empire


def make_star(empire: EmpireData, colonists=100000) -> Star:
    star = Star()
    star.name = "Testworld"
    star.owner = empire.id
    star.colonists = colonists
    star.this_race = empire.race  # linked as StarUpdateStep.process() does
    star.resources_on_hand = Resources(
        ironium=100, boranium=100, germanium=100, energy=100)
    return star


def order(ptype, quantity=1, name="", auto=False) -> ProductionOrder:
    return ProductionOrder(
        production_type=ptype, quantity=quantity,
        name=name or ptype.name.title(), is_auto_build=auto)


class TestAutoBuildSerialization:
    """is_auto_build round-trips and defaults False for legacy dicts."""

    def test_order_is_auto_build_serialization_roundtrip(self):
        original = order(ProductionType.FACTORY, quantity=3, auto=True)
        restored = ProductionOrder.from_dict(original.to_dict())
        assert restored.is_auto_build is True
        assert restored.quantity == 3

    def test_legacy_dict_defaults_to_not_auto(self):
        data = order(ProductionType.MINE, quantity=2).to_dict()
        del data["is_auto_build"]
        restored = ProductionOrder.from_dict(data)
        assert restored.is_auto_build is False


class TestBlockingAndSkipping:
    """IsBlocking/IsSkipped semantics in the manufacture loop."""

    def test_blocking_non_auto_halts_queue(self):
        # Factory with no germanium on hand is skipped
        # (FactoryProductionUnit.cs:90-103) and, being non-auto, blocks
        # the queue: the mine behind it is never built
        empire = make_empire()
        star = make_star(empire)
        star.resources_on_hand.germanium = 0
        star.manufacturing_queue.add(order(ProductionType.FACTORY))
        star.manufacturing_queue.add(order(ProductionType.MINE))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.factories == 0
        assert star.mines == 0
        assert len(star.manufacturing_queue.orders) == 2

    def test_auto_build_never_blocks(self):
        # Same germanium-starved star: the auto factory is skipped with
        # quantity intact and the mine behind it builds
        empire = make_empire()
        star = make_star(empire)
        star.resources_on_hand.germanium = 0
        star.manufacturing_queue.add(order(ProductionType.FACTORY, auto=True))
        star.manufacturing_queue.add(order(ProductionType.MINE))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.factories == 0
        assert star.mines == 1
        remaining = star.manufacturing_queue.orders
        assert len(remaining) == 1
        assert remaining[0].production_type == ProductionType.FACTORY
        assert remaining[0].is_auto_build is True
        assert remaining[0].quantity == 1

    def test_auto_order_persists_across_turns(self):
        # A skipped auto order stays in the queue year after year and
        # resumes building once it can (persistence across turns)
        empire = make_empire()
        star = make_star(empire)
        star.resources_on_hand.germanium = 0
        star.manufacturing_queue.add(
            order(ProductionType.FACTORY, quantity=5, auto=True))
        step = StarUpdateStep()

        for _ in range(3):  # three starved years
            star.resources_on_hand.energy = 100
            step._manufacture_items(star, empire)
            assert star.factories == 0
            assert star.manufacturing_queue.orders[0].quantity == 5

        # Germanium arrives - the order resumes
        star.resources_on_hand.germanium = 100
        star.resources_on_hand.energy = 100
        step._manufacture_items(star, empire)
        assert star.factories == 5
        assert len(star.manufacturing_queue.orders) == 0

    def test_factory_operable_cap_skips(self):
        # At the operable cap the factory unit is skipped
        # (FactoryProductionUnit.cs:90-95): auto orders spend nothing
        # and stay queued; non-auto orders block the queue
        empire = make_empire()
        star = make_star(empire)
        star.factories = star.get_operable_factories()

        # Auto: skipped, mine behind still builds
        star.manufacturing_queue.add(
            order(ProductionType.FACTORY, quantity=2, auto=True))
        star.manufacturing_queue.add(order(ProductionType.MINE))
        StarUpdateStep()._manufacture_items(star, empire)
        assert star.factories == star.get_operable_factories()
        assert star.mines == 1
        assert star.manufacturing_queue.orders[0].quantity == 2

        # Non-auto: blocks - nothing behind it is built
        star.manufacturing_queue.clear()
        star.resources_on_hand.energy = 100
        star.manufacturing_queue.add(order(ProductionType.FACTORY))
        star.manufacturing_queue.add(order(ProductionType.MINE))
        StarUpdateStep()._manufacture_items(star, empire)
        assert star.mines == 1  # unchanged
        assert star.resources_on_hand.energy == 100

    def test_factory_cap_stops_mid_stack(self):
        # IsSkipped is re-checked per unit (ProductionOrder.cs:107-126)
        # so a stack stops exactly at the operable cap
        empire = make_empire()
        star = make_star(empire)
        cap = star.get_operable_factories()
        star.factories = cap - 2
        star.resources_on_hand.energy = 1000
        star.manufacturing_queue.add(
            order(ProductionType.FACTORY, quantity=10, auto=True))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.factories == cap
        assert star.manufacturing_queue.orders[0].quantity == 8

    def test_mine_operable_cap_skips(self):
        # MineProductionUnit.cs:95-101
        empire = make_empire()
        star = make_star(empire)
        star.mines = star.get_operable_mines()
        star.manufacturing_queue.add(
            order(ProductionType.MINE, quantity=3, auto=True))
        star.manufacturing_queue.add(order(ProductionType.FACTORY))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.mines == star.get_operable_mines()
        assert star.factories == 1
        assert star.manufacturing_queue.orders[0].quantity == 3

    def test_defense_max_100_skips(self):
        # DefenseProductionUnit.cs:87-93: at MaxDefenses the unit is
        # skipped - resources are not clamp-and-wasted
        empire = make_empire()
        star = make_star(empire)
        star.defenses = MAX_DEFENSES
        star.manufacturing_queue.add(
            order(ProductionType.DEFENSE, quantity=2, auto=True))
        star.manufacturing_queue.add(order(ProductionType.MINE))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.defenses == MAX_DEFENSES
        assert star.resources_on_hand.ironium == 100  # nothing spent
        assert star.mines == 1
        assert star.manufacturing_queue.orders[0].quantity == 2

    def test_auto_order_removed_when_complete(self):
        # Nova semantics (Manufacture.cs:74-83): finished auto orders
        # leave the queue - no Stars!-style build-forever
        empire = make_empire()
        star = make_star(empire)
        star.manufacturing_queue.add(
            order(ProductionType.FACTORY, quantity=2, auto=True))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.factories == 2
        assert len(star.manufacturing_queue.orders) == 0


class TestFactoryCost:
    """Race.cs GetFactoryResources (lines 275-279)."""

    def test_factory_cost_cf_trait(self):
        empire = make_empire()
        star = make_star(empire)
        step = StarUpdateStep()

        cost = step._get_order_cost(order(ProductionType.FACTORY), star, empire)
        assert cost.germanium == 4

        empire.race.traits.add("CF")
        cost = step._get_order_cost(order(ProductionType.FACTORY), star, empire)
        assert cost.germanium == 3
