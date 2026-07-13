"""
Unit tests for the Mineral Alchemy production queue item.

The C# AlchemyProductionUnit.cs is a stub (all methods throw
NotImplementedException), so these tests verify the canonical Stars!
rules implemented in StarUpdateStep: 100 resources per unit (25 with
the MA LRT, GameInitialiser.cs:315-318), zero mineral cost, 1 kT of
each mineral produced per unit, and partial progress carried on
ProductionOrder.partial_resources_spent.
"""

from backend.core.data_structures import EmpireData, Resources
from backend.core.game_objects.star import Star
from backend.core.production.production_queue import (
    ProductionOrder, ProductionType
)
from backend.core.race.race import Race
from backend.server.turn_steps import StarUpdateStep


def make_star(name="Alchemyworld", owner=1, colonists=100000) -> Star:
    star = Star()
    star.name = name
    star.owner = owner
    star.colonists = colonists
    return star


def make_empire(ma=False) -> EmpireData:
    empire = EmpireData(id=1)
    empire.race = Race()
    if ma:
        empire.race.traits.add("MA")
    return empire


def alchemy_order(quantity=1, partial=0) -> ProductionOrder:
    return ProductionOrder(
        production_type=ProductionType.ALCHEMY, quantity=quantity,
        name="Alchemy", partial_resources_spent=partial)


class TestAlchemyCost:
    """Unit cost with and without the MA LRT."""

    def test_alchemy_costs_100_resources_without_ma(self):
        empire = make_empire()
        star = make_star()
        cost = StarUpdateStep()._get_order_cost(
            alchemy_order(), star, empire)
        assert cost.energy == 100
        assert (cost.ironium, cost.boranium, cost.germanium) == (0, 0, 0)

    def test_alchemy_costs_25_with_ma(self):
        empire = make_empire(ma=True)
        star = make_star()
        cost = StarUpdateStep()._get_order_cost(
            alchemy_order(), star, empire)
        assert cost.energy == 25
        assert (cost.ironium, cost.boranium, cost.germanium) == (0, 0, 0)


class TestAlchemyProduction:
    """The Alchemy item in the manufacture loop."""

    def test_alchemy_produces_one_kt_each_mineral(self):
        empire = make_empire()
        star = make_star()
        star.resources_on_hand = Resources(ironium=10, boranium=20,
                                           germanium=30, energy=350)
        star.manufacturing_queue.add(alchemy_order(quantity=3))

        messages = StarUpdateStep()._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 13
        assert star.resources_on_hand.boranium == 23
        assert star.resources_on_hand.germanium == 33
        assert star.resources_on_hand.energy == 50
        assert len(star.manufacturing_queue.orders) == 0
        assert any("transmuted" in m.text for m in messages)

    def test_alchemy_partial_progress(self):
        empire = make_empire()
        star = make_star()
        star.resources_on_hand = Resources(energy=150)
        star.manufacturing_queue.add(alchemy_order(quantity=2))

        step = StarUpdateStep()
        step._manufacture_items(star, empire)

        # One unit completes; the second banks 50 of its 100 resources
        assert star.resources_on_hand.ironium == 1
        assert star.resources_on_hand.boranium == 1
        assert star.resources_on_hand.germanium == 1
        assert star.resources_on_hand.energy == 0
        assert len(star.manufacturing_queue.orders) == 1
        order = star.manufacturing_queue.orders[0]
        assert order.quantity == 1
        assert order.partial_resources_spent == 50

        # Next year: 50 more resources finish the banked unit
        star.resources_on_hand.energy = 50
        step._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 2
        assert star.resources_on_hand.boranium == 2
        assert star.resources_on_hand.germanium == 2
        assert star.resources_on_hand.energy == 0
        assert len(star.manufacturing_queue.orders) == 0

    def test_alchemy_consumes_no_minerals(self):
        # A mineral-starved star can still run alchemy - resources only
        empire = make_empire()
        star = make_star()
        star.resources_on_hand = Resources(ironium=0, boranium=0,
                                           germanium=0, energy=100)
        star.manufacturing_queue.add(alchemy_order(quantity=1))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 1
        assert star.resources_on_hand.boranium == 1
        assert star.resources_on_hand.germanium == 1
        assert star.resources_on_hand.energy == 0
        assert len(star.manufacturing_queue.orders) == 0

    def test_alchemy_with_ma_builds_four_units_for_100(self):
        # "Four times more efficiently" (SecondaryTraits.cs:66)
        empire = make_empire(ma=True)
        star = make_star()
        star.resources_on_hand = Resources(energy=100)
        star.manufacturing_queue.add(alchemy_order(quantity=4))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 4
        assert star.resources_on_hand.energy == 0
        assert len(star.manufacturing_queue.orders) == 0

    def test_alchemy_queue_interaction(self):
        # A mine ahead of alchemy is paid first; alchemy gets the rest
        empire = make_empire()
        star = make_star()
        # Link the race as StarUpdateStep.process() does - the mine
        # order needs get_operable_mines() (MineProductionUnit.cs:95-101)
        star.this_race = empire.race
        star.resources_on_hand = Resources(energy=105)
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.MINE, quantity=1, name="Mine"))
        star.manufacturing_queue.add(alchemy_order(quantity=1))

        StarUpdateStep()._manufacture_items(star, empire)

        # Mine costs 5 (default race), alchemy the remaining 100
        assert star.mines == 1
        assert star.resources_on_hand.ironium == 1
        assert star.resources_on_hand.energy == 0
        assert len(star.manufacturing_queue.orders) == 0


class TestAlchemySerialization:
    """ALCHEMY orders round-trip through the generic order dict."""

    def test_alchemy_order_survives_serialization(self):
        order = alchemy_order(quantity=5, partial=30)
        restored = ProductionOrder.from_dict(order.to_dict())
        assert restored.production_type == ProductionType.ALCHEMY
        assert restored.quantity == 5
        assert restored.name == "Alchemy"
        assert restored.partial_resources_spent == 30
