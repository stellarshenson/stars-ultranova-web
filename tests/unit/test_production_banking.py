"""
Unit tests for per-resource production banking (DEF-10).

Verifies parity with the C# Construct partial-build algorithm
(FactoryProductionUnit.cs:108-142, ShipProductionUnit.cs:137-180): an
order that cannot afford a full unit spends a proportional slice of
every commodity - driving the scarcest one to (about) 0 - and banks the
per-resource remaining cost on the order. The exhausted commodity trips
IsSkipped on trailing non-auto orders, so the queue blocks behind the
head order (Manufacture.cs:56-61) instead of letting trailing orders
starve it. One documented C# defect is fixed in the port: remainingCost
is reset to the full unit cost after each completed unit
(FactoryProductionUnit.cs:136-141 never resets it, charging the next
unit of a multi-quantity order only the residue).

Most tests use power-of-two costs so the double percent math is exact;
one test deliberately exercises the C# ceiling overshoot
(Resources.cs:250 "Rounding can cause one more resource to be consumed
than we have").
"""

from backend.core.commands.base import CommandMode
from backend.core.commands.production import ProductionCommand
from backend.core.data_structures import EmpireData, Resources
from backend.core.game_objects.star import Star
from backend.core.production.production_queue import (
    ProductionOrder, ProductionType
)
from backend.core.race.race import Race
from backend.server.turn_steps import StarUpdateStep
from backend.services.ship_specs import SimpleDesign


def make_empire() -> EmpireData:
    empire = EmpireData(id=1)
    empire.race = Race()
    return empire


def make_star(empire: EmpireData, ironium=100, boranium=100,
              germanium=100, energy=100) -> Star:
    star = Star()
    star.name = "Testworld"
    star.owner = empire.id
    star.colonists = 100000
    star.this_race = empire.race
    star.resources_on_hand = Resources(
        ironium=ironium, boranium=boranium,
        germanium=germanium, energy=energy)
    return star


def make_ship_design(empire: EmpireData,
                     cost: Resources) -> SimpleDesign:
    design = SimpleDesign(key=empire.get_next_design_key(),
                          name="Test Ship", cost=cost)
    empire.designs[design.key] = design
    return design


def ship_order(design: SimpleDesign, quantity=1,
               auto=False) -> ProductionOrder:
    return ProductionOrder(
        production_type=ProductionType.SHIP, quantity=quantity,
        design_key=design.key, name=design.name, is_auto_build=auto)


class TestPartialBuild:

    def test_partial_build_spends_scarce_mineral_to_zero(self):
        # Cost 8I/0B/4G/16E with only 2 ironium on hand: percent
        # buildable = 1 - 6/8 = 0.25 (exact in doubles); the
        # ceil-per-commodity spend (Resources.cs:251-261) takes 2I,
        # 1G, 4E and the scarce ironium lands at exactly 0
        empire = make_empire()
        star = make_star(empire, ironium=2)
        design = make_ship_design(
            empire, Resources(ironium=8, germanium=4, energy=16))
        order = ship_order(design)
        star.manufacturing_queue.add(order)

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 0
        assert star.resources_on_hand.germanium == 99
        assert star.resources_on_hand.energy == 96
        # Quantity untouched; per-resource residue banked on the order
        assert order.quantity == 1
        assert order.remaining_cost == Resources(
            ironium=6, germanium=3, energy=12)
        # Energy mirror for the client percent display
        assert order.partial_resources_spent == 4
        assert len(star.manufacturing_queue.orders) == 1

    def test_two_scarce_commodities_take_the_minimum_percent(self):
        # Cost 8I/8G/16E with 2I/4G on hand: percent = min(1-6/8,
        # 1-4/8) = 0.25 - ironium (the scarcest) is spent to exactly 0
        empire = make_empire()
        star = make_star(empire, ironium=2, germanium=4)
        design = make_ship_design(
            empire, Resources(ironium=8, germanium=8, energy=16))
        order = ship_order(design)
        star.manufacturing_queue.add(order)

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 0
        assert star.resources_on_hand.germanium == 2
        assert star.resources_on_hand.energy == 96
        assert order.quantity == 1
        assert order.remaining_cost == Resources(
            ironium=6, germanium=6, energy=12)

    def test_ceiling_overshoot_dips_on_hand_below_zero(self):
        # C#-faithful double rounding (Resources.cs:250 comment):
        # cost 10I/5G/20E with 3I on hand gives percent
        # 1 - 7/10 = 0.30000000000000004, and ceil(10 * pct) = 4 -
        # one MORE ironium than we have, dipping on-hand to -1.
        # The order then stays skipped until income turns it positive
        empire = make_empire()
        star = make_star(empire, ironium=3)
        design = make_ship_design(
            empire, Resources(ironium=10, germanium=5, energy=20))
        order = ship_order(design)
        star.manufacturing_queue.add(order)
        step = StarUpdateStep()

        step._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == -1
        assert star.resources_on_hand.germanium == 98  # ceil(1.5) = 2
        assert star.resources_on_hand.energy == 93     # ceil(6.0..1) = 7
        assert order.remaining_cost == Resources(
            ironium=6, germanium=3, energy=13)

        # Next pass with no income: skipped, nothing spent
        step._manufacture_items(star, empire)
        assert star.resources_on_hand.ironium == -1
        assert order.remaining_cost == Resources(
            ironium=6, germanium=3, energy=13)

    def test_banked_unit_completes_then_next_unit_full_price(self):
        # Year 1 banks a partial; year 2 (minerals replenished) the
        # unit completes paying only the residue AND the next unit of
        # the same order is charged the FULL cost - locking the
        # documented C# no-reset defect fix
        # (FactoryProductionUnit.cs:136-141)
        empire = make_empire()
        star = make_star(empire, ironium=2)
        design = make_ship_design(
            empire, Resources(ironium=8, germanium=4, energy=16))
        order = ship_order(design, quantity=2)
        star.manufacturing_queue.add(order)
        step = StarUpdateStep()

        step._manufacture_items(star, empire)  # banks 2I/1G/4E
        assert order.remaining_cost == Resources(
            ironium=6, germanium=3, energy=12)

        star.resources_on_hand = Resources(
            ironium=100, boranium=100, germanium=100, energy=100)
        step._manufacture_items(star, empire)

        # Residue 6I/3G/12E + full second unit 8I/4G/16E
        assert star.resources_on_hand.ironium == 100 - 6 - 8
        assert star.resources_on_hand.germanium == 100 - 3 - 4
        assert star.resources_on_hand.energy == 100 - 12 - 16
        assert order.quantity == 0
        assert len(star.manufacturing_queue.orders) == 0
        # Both ships materialized in one fleet
        fleet = next(iter(empire.owned_fleets.values()))
        assert sum(t.quantity for t in fleet.tokens.values()) == 2

    def test_energy_only_order_banks_energy(self):
        # Mineral-free costs flow through the same Construct path:
        # a mine costing 8E with 2E on hand (percent 0.25) banks 2
        # and finishes next year for the remaining 6
        empire = make_empire()
        empire.race.mine_cost = 8
        star = make_star(empire, energy=2)
        order = ProductionOrder(production_type=ProductionType.MINE,
                                quantity=1, name="Mine")
        star.manufacturing_queue.add(order)
        step = StarUpdateStep()

        step._manufacture_items(star, empire)
        assert star.mines == 0
        assert star.resources_on_hand.energy == 0
        assert order.remaining_cost.energy == 6
        assert order.partial_resources_spent == 2

        star.resources_on_hand.energy = 10
        step._manufacture_items(star, empire)
        assert star.mines == 1
        assert star.resources_on_hand.energy == 4


class TestQueueBlocking:

    def test_starved_head_blocks_trailing_order_needing_the_mineral(self):
        # The head ship order partial-builds ironium to 0; the
        # trailing non-auto defense order (needs ironium) is skipped
        # and, per IsBlocking (Manufacture.cs:56-61), blocks - it
        # consumes nothing, closing the DEF-10 starvation
        empire = make_empire()
        star = make_star(empire, ironium=2)
        design = make_ship_design(
            empire, Resources(ironium=8, energy=16))
        head = ship_order(design)
        star.manufacturing_queue.add(head)
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.DEFENSE, quantity=1,
            name="Defense"))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.resources_on_hand.ironium == 0
        assert head.remaining_cost is not None
        assert star.defenses == 0
        assert len(star.manufacturing_queue.orders) == 2

    def test_trailing_auto_skipped_and_mineral_free_order_builds(self):
        # A trailing AUTO order needing the exhausted mineral is
        # passed over without blocking; a later mineral-free order
        # (mine, energy only) still builds - exactly the C# shape
        empire = make_empire()
        star = make_star(empire, ironium=2)
        design = make_ship_design(
            empire, Resources(ironium=8, energy=16))
        head = ship_order(design)
        star.manufacturing_queue.add(head)
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.DEFENSE, quantity=1,
            name="Defense", is_auto_build=True))
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.MINE, quantity=1,
            name="Mine"))

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.defenses == 0
        assert star.mines == 1
        assert head.remaining_cost is not None

    def test_starved_head_completes_as_mining_supplies_residue(self):
        # Regression for the run100 Zubenelgenubi starvation: the
        # head order makes progress every year as minerals trickle in
        # (never sitting at zero progress while a trailing order eats
        # its minerals) and completes once the residue is paid.
        # Halving incomes keep every percent exact: remaining ironium
        # runs 16 -> 8 -> 4 -> 2 -> complete
        empire = make_empire()
        star = make_star(empire, ironium=8)
        design = make_ship_design(
            empire, Resources(ironium=16, energy=4))
        head = ship_order(design)
        star.manufacturing_queue.add(head)
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.DEFENSE, quantity=1,
            name="Defense"))
        step = StarUpdateStep()

        remaining_series = []
        for income in (4, 2, 2):
            step._manufacture_items(star, empire)
            assert head.remaining_cost is not None
            remaining_series.append(head.remaining_cost.ironium)
            assert star.defenses == 0  # blocked, not starving the head
            star.resources_on_hand.ironium += income
            star.resources_on_hand.energy = 100
        step._manufacture_items(star, empire)

        assert remaining_series == [8, 4, 2]
        assert head.quantity == 0
        assert len(empire.owned_fleets) == 1


class TestSerializationAndMigration:

    def test_remaining_cost_round_trips(self):
        order = ProductionOrder(
            production_type=ProductionType.SHIP, quantity=2,
            design_key=101, name="Ship",
            remaining_cost=Resources(ironium=7, germanium=3, energy=14),
            partial_resources_spent=6)
        restored = ProductionOrder.from_dict(order.to_dict())
        assert restored.remaining_cost == Resources(
            ironium=7, germanium=3, energy=14)
        assert restored.partial_resources_spent == 6

    def test_legacy_dict_without_remaining_cost_loads(self):
        data = ProductionOrder(
            production_type=ProductionType.MINE, quantity=1,
            name="Mine", partial_resources_spent=2).to_dict()
        del data["remaining_cost"]
        restored = ProductionOrder.from_dict(data)
        assert restored.remaining_cost is None
        assert restored.partial_resources_spent == 2

    def test_legacy_energy_scalar_migrates_on_first_pass(self):
        # A pre-DEF-10 save banked only partial_resources_spent: the
        # first manufacture pass charges cost minus the banked energy
        # (mine costing 5E with 2E banked completes for 3E)
        empire = make_empire()
        star = make_star(empire, energy=10)
        order = ProductionOrder(production_type=ProductionType.MINE,
                                quantity=1, name="Mine",
                                partial_resources_spent=2)
        star.manufacturing_queue.add(order)

        StarUpdateStep()._manufacture_items(star, empire)

        assert star.mines == 1
        assert star.resources_on_hand.energy == 7

    def test_add_command_rejects_prebuilt_remaining_cost(self):
        # ProductionCommand.cs:140-143 anti-tamper: an ADDed order
        # must arrive with no banked progress
        empire = make_empire()
        star = make_star(empire)
        empire.owned_stars[star.key] = star
        order = ProductionOrder(
            production_type=ProductionType.MINE, quantity=1,
            name="Mine",
            remaining_cost=Resources(energy=3))
        command = ProductionCommand(mode=CommandMode.ADD,
                                    production_order=order,
                                    star_key=star.key)
        valid, _message = command.is_valid(empire)
        assert valid is False
