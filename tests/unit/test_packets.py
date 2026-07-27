"""
Tests for mineral packets and mass drivers.

The C# reference is a stub: MassDriver.cs holds only the component
property (the driver warp rating; operator+ semantics at lines
113-123, the buggy operator* at 132-139) and TurnGenerator.cs has no
packet code anywhere. Packet flight, overfling decay and catch/impact
follow canonical Stars! rules pinned by the PACKET_* constants in
backend/core/globals.py:

  spdPacket = warp^2; caught safely when receiverWarp^2 >= spdPacket
  else recovered fraction = pct + (1 - pct)/3, pct = spdRecv/spdPacket
  rawDamage = (spdPacket - spdReceiver) * kT / 160
  dmg = rawDamage * (1 - defense population coverage)
  colonists killed = max(dmg * pop / 1000, dmg * 100)
  defenses destroyed = max(defs * dmg / 1000, dmg / 20)
  overfling decay 10/25/50 pct per year (+1/+2/+3 over, clamped),
  minimum 10 kT per mineral per decaying year
"""

import pytest

from backend.core.components.component import (
    Component, ComponentProperty, ItemType
)
from backend.core.components.ship_design import ShipDesign
from backend.core.data_structures import EmpireData, NovaPoint
from backend.core.data_structures.cargo import Cargo
from backend.core.data_structures.resources import Resources
from backend.core.game_objects.fleet import (
    Fleet, ShipToken, is_mineral_packet
)
from backend.core.game_objects.star import Star
from backend.core.globals import NOBODY
from backend.core.waypoints.waypoint import Waypoint, NoTaskObj
from backend.server.server_data import ServerData, GalacticStorm, Minefield
from backend.server.turn_generator import TurnGenerator
from backend.services.ship_specs import SimpleDesign, make_token


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_packet(key: int, owner: int, x: float, y: float,
                warp: int = 5, safe_warp: int = 5,
                ironium: int = 0, boranium: int = 0,
                germanium: int = 0,
                target: NovaPoint = None) -> Fleet:
    """Build a mineral packet pseudo-fleet with one token."""
    fleet = Fleet(name=f"Mineral Packet #{key}",
                  position=NovaPoint(x, y))
    fleet._key = (owner << 32) | key
    fleet.tokens[900] = ShipToken(
        design_key=900, design_name="Mineral Packet", quantity=1, mass=0)
    fleet.cargo = Cargo(ironium=ironium, boranium=boranium,
                        germanium=germanium)
    fleet.fuel_available = 0
    fleet.packet_warp = warp
    fleet.packet_safe_warp = safe_warp
    if target is not None:
        fleet.waypoints = [Waypoint(
            position_x=target.x, position_y=target.y,
            warp_factor=warp, destination="target", task=NoTaskObj())]
    return fleet


def make_state(*fleets: Fleet) -> ServerData:
    state = ServerData()
    for fleet in fleets:
        empire_id = fleet.owner
        if empire_id not in state.all_empires:
            empire = EmpireData()
            empire.id = empire_id
            state.all_empires[empire_id] = empire
        state.all_empires[empire_id].owned_fleets[fleet.key] = fleet
    return state


def add_star(state: ServerData, name: str, x: float, y: float,
             owner: int = NOBODY, colonists: int = 0,
             defenses: int = 0, defense_type: str = "None") -> Star:
    star = Star(name=name, position=NovaPoint(x, y))
    if owner != NOBODY:
        star.owner = owner
        if owner not in state.all_empires:
            empire = EmpireData()
            empire.id = owner
            state.all_empires[owner] = empire
        state.all_empires[owner].owned_stars[name] = star
    star.colonists = colonists
    star.defenses = defenses
    star.defense_type = defense_type
    star.resources_on_hand = Resources()
    state.all_stars[name] = star
    return star


def add_starbase(state: ServerData, star: Star, key_id: int,
                 mass_driver: int) -> Fleet:
    """Park a starbase with a mass driver at a star."""
    base = Fleet(name=f"{star.name} Base",
                 position=star.position.copy())
    base._key = (star.owner << 32) | key_id
    base.tokens[901] = ShipToken(
        design_key=901, design_name="Starbase", quantity=1,
        is_starbase=True, mass_driver=mass_driver)
    state.all_empires[star.owner].owned_fleets[base.key] = base
    star.starbase_key = base.key
    return base


# --------------------------------------------------------------------------
# Mass driver aggregation (MassDriver.cs semantics)
# --------------------------------------------------------------------------

class TestMassDriverAggregation:
    """ShipDesign aggregation of Mass Driver components."""

    @pytest.fixture(scope="class")
    def loader(self):
        from backend.core.components.component_loader import (
            get_component_loader, load_components
        )
        loader = get_component_loader()
        if not loader.is_loaded:
            load_components("backend/data/components.xml")
        return loader

    def _driver_design(self, loader, allocations):
        """Design on a fabricated starbase hull with catalog drivers
        allocated by name: allocations = [(name, count)]."""
        c = Component()
        c.name = "Driver Test Hull"
        c.item_type = ItemType.HULL
        c.mass = 0
        c.cost = Resources(10, 10, 10, 100)
        hull_prop = ComponentProperty()
        hull_prop.property_type = "Hull"
        hull_prop.values = {
            "fuel_capacity": 0,
            "armor_strength": 500,
            "modules": [
                {"cell_number": i + 1, "component_maximum": 4,
                 "component_type": "Orbital or Electrical",
                 "allocated_component": name,
                 "component_count": count}
                for i, (name, count) in enumerate(allocations)
            ],
        }
        c.add_property(hull_prop)
        design = ShipDesign(blueprint=c)
        design.name = "Driver Test"
        design.update()
        return design

    def test_single_driver(self, loader):
        design = self._driver_design(loader, [("Mass Driver 5", 1)])
        assert design.mass_driver == 5

    def test_two_equal_drivers_same_slot(self, loader):
        """Stack of 2+ in one slot operates one warp higher (the
        INTENDED MassDriver.cs operator* math - the C# code adds +1
        for any scalar >= 1, a bug like Computer.cs:117)."""
        design = self._driver_design(loader, [("Mass Driver 5", 2)])
        assert design.mass_driver == 6

    def test_different_drivers_across_slots(self, loader):
        """Different ratings: the better one wins
        (MassDriver.cs:113-123)."""
        design = self._driver_design(loader, [
            ("Mass Driver 5", 1), ("Mass Driver 6", 1)])
        assert design.mass_driver == 6

    def test_equal_drivers_across_slots(self, loader):
        """Equal ratings across slots add one warp
        (MassDriver.cs:113-123)."""
        design = self._driver_design(loader, [
            ("Mass Driver 6", 1), ("Mass Driver 6", 1)])
        assert design.mass_driver == 7

    def test_no_driver(self, loader):
        design = self._driver_design(loader, [])
        assert design.mass_driver == 0

    def test_simple_design_roundtrip_and_token(self):
        design = SimpleDesign(key=1, name="Base", is_starbase=True,
                              mass_driver=7)
        restored = SimpleDesign.from_dict(design.to_dict())
        assert restored.mass_driver == 7
        token = make_token(restored, 1)
        assert token.mass_driver == 7
        # Legacy dicts default to no driver
        legacy = design.to_dict()
        del legacy["mass_driver"]
        assert SimpleDesign.from_dict(legacy).mass_driver == 0

    def test_fleet_mass_driver_is_token_max(self):
        fleet = Fleet(name="Base", position=NovaPoint(0, 0))
        fleet._key = (1 << 32) | 1
        fleet.tokens[1] = ShipToken(design_key=1, quantity=1,
                                    mass_driver=5)
        fleet.tokens[2] = ShipToken(design_key=2, quantity=1,
                                    mass_driver=9)
        assert fleet.mass_driver == 9
        assert Fleet(name="x", position=NovaPoint(0, 0)).mass_driver == 0


# --------------------------------------------------------------------------
# In-flight decay
# --------------------------------------------------------------------------

class TestPacketDecay:
    """Overfling decay per year in flight."""

    def _fly_one_year(self, packet):
        state = make_state(packet)
        gen = TurnGenerator(state)
        gen._move_mineral_packets()
        return state

    def _distant_target(self):
        return NovaPoint(1000, 100)

    def test_no_decay_at_rated_warp(self):
        packet = make_packet(1, 1, 100, 100, warp=5, safe_warp=5,
                             ironium=1000, target=self._distant_target())
        self._fly_one_year(packet)
        assert packet.cargo.ironium == 1000

    def test_one_over_decays_ten_percent(self):
        packet = make_packet(1, 1, 100, 100, warp=6, safe_warp=5,
                             ironium=1000, target=self._distant_target())
        self._fly_one_year(packet)
        assert packet.cargo.ironium == 900

    def test_minimum_decay_per_mineral(self):
        """10% of 50 kT is 5, but decay is never below 10 kT per
        mineral per year."""
        packet = make_packet(1, 1, 100, 100, warp=6, safe_warp=5,
                             ironium=1000, boranium=50,
                             target=self._distant_target())
        self._fly_one_year(packet)
        assert packet.cargo.ironium == 900
        assert packet.cargo.boranium == 40

    def test_two_over_decays_quarter(self):
        packet = make_packet(1, 1, 100, 100, warp=7, safe_warp=5,
                             ironium=1000, target=self._distant_target())
        self._fly_one_year(packet)
        assert packet.cargo.ironium == 750

    def test_three_over_decays_half(self):
        packet = make_packet(1, 1, 100, 100, warp=8, safe_warp=5,
                             ironium=1000, target=self._distant_target())
        self._fly_one_year(packet)
        assert packet.cargo.ironium == 500

    def test_over_clamped_at_three(self):
        """Warp 9 from a rating-5 driver is 4 over but decays at the
        +3 rate (clamp)."""
        packet = make_packet(1, 1, 100, 100, warp=9, safe_warp=5,
                             ironium=1000, target=self._distant_target())
        self._fly_one_year(packet)
        assert packet.cargo.ironium == 500

    def test_decayed_to_nothing_is_removed(self):
        packet = make_packet(1, 1, 100, 100, warp=8, safe_warp=5,
                             ironium=10, target=self._distant_target())
        state = self._fly_one_year(packet)
        assert packet.cargo.mass == 0
        assert packet.key not in state.all_empires[1].owned_fleets
        assert any("decayed to nothing" in m.text
                   for m in state.all_messages)


# --------------------------------------------------------------------------
# Catch and impact
# --------------------------------------------------------------------------

class TestPacketCatchImpact:
    """Arrival resolution against the canonical formulas."""

    def _arrive(self, state, packet):
        gen = TurnGenerator(state)
        gen._move_mineral_packets()
        return gen

    def test_equal_driver_catches_safely(self):
        packet = make_packet(1, 1, 200, 100, warp=5, safe_warp=5,
                             ironium=600, boranium=200, germanium=100)
        state = make_state(packet)
        star = add_star(state, "Rcv", 200, 100, owner=2,
                        colonists=100000)
        add_starbase(state, star, 50, mass_driver=5)
        self._arrive(state, packet)
        assert star.resources_on_hand.ironium == 600
        assert star.resources_on_hand.boranium == 200
        assert star.resources_on_hand.germanium == 100
        assert star.colonists == 100000
        assert packet.key not in state.all_empires[1].owned_fleets
        assert any("has caught" in m.text for m in state.all_messages)

    def test_better_driver_catches_safely(self):
        packet = make_packet(1, 1, 200, 100, warp=5, safe_warp=5,
                             ironium=300)
        state = make_state(packet)
        star = add_star(state, "Rcv", 200, 100, owner=2,
                        colonists=50000)
        add_starbase(state, star, 50, mass_driver=9)
        self._arrive(state, packet)
        assert star.resources_on_hand.ironium == 300
        assert star.colonists == 50000

    def test_impact_worked_example(self):
        """Warp 13 packet (spd 169) vs warp 5 receiver (spd 25),
        1000 kT, zero defenses: recovered = int(1000 * (25/169 +
        (144/169)/3)) = 431 kT; raw = 144 * 1000 / 160 = 900; killed
        = max(900 * pop / 1000, 90000) rounded to 100, capped."""
        packet = make_packet(1, 1, 200, 100, warp=13, safe_warp=10,
                             ironium=1000)
        state = make_state(packet)
        star = add_star(state, "Rcv", 200, 100, owner=2,
                        colonists=1000000)
        add_starbase(state, star, 50, mass_driver=5)
        self._arrive(state, packet)
        expected_recovered = int(1000 * (25 / 169 + (144 / 169) / 3))
        assert expected_recovered == 431
        assert star.resources_on_hand.ironium == 431
        # dmg = 900, killed = max(900 * 1e6 / 1000, 90000) = 900000
        assert star.colonists == 1000000 - 900000
        assert star.defenses == 0
        assert packet.key not in state.all_empires[1].owned_fleets

    def test_impact_defense_coverage_halves_damage(self):
        """Defense population coverage scales the damage down; the
        expected values are recomputed with the same coverage the
        engine uses."""
        from backend.core.defenses import compute_defense_coverage

        def run(defenses, defense_type):
            packet = make_packet(1, 1, 200, 100, warp=13, safe_warp=10,
                                 ironium=1000)
            state = make_state(packet)
            star = add_star(state, "Rcv", 200, 100, owner=2,
                            colonists=1000000, defenses=defenses,
                            defense_type=defense_type)
            add_starbase(state, star, 50, mass_driver=5)
            coverage = compute_defense_coverage(star)["population"]
            self._arrive(state, packet)
            return star, coverage

        star, coverage = run(50, "SDI")
        assert coverage > 0.0
        dmg = 900.0 * (1.0 - coverage)
        expected_killed = min(
            1000000,
            int(round(max(dmg * 1000000 / 1000.0, dmg * 100.0)
                      / 100.0)) * 100)
        expected_destroyed = min(50, int(max(50 * dmg / 1000.0,
                                             dmg / 20.0)))
        assert star.colonists == 1000000 - expected_killed
        assert star.defenses == 50 - expected_destroyed
        # Fewer kills than the uncovered worked example
        assert expected_killed < 900000

    def test_no_driver_all_uncaught(self):
        """No starbase: spdReceiver = 0, one third recovered, full
        raw damage."""
        packet = make_packet(1, 1, 200, 100, warp=8, safe_warp=8,
                             ironium=900)
        state = make_state(packet)
        star = add_star(state, "Rcv", 200, 100, owner=2,
                        colonists=200000)
        self._arrive(state, packet)
        assert star.resources_on_hand.ironium == 300  # int(900 / 3)
        # raw = 64 * 900 / 160 = 360; killed = max(360 * 200, 36000)
        # = 72000
        assert star.colonists == 200000 - 72000
        assert packet.key not in state.all_empires[1].owned_fleets

    def test_uninhabited_target_recovery_only(self):
        packet = make_packet(1, 1, 200, 100, warp=8, safe_warp=8,
                             ironium=900)
        state = make_state(packet)
        star = add_star(state, "Rcv", 200, 100)  # unowned
        self._arrive(state, packet)
        assert star.resources_on_hand.ironium == 300
        assert star.colonists == 0
        assert packet.key not in state.all_empires[1].owned_fleets
        assert any("uninhabited" in m.text for m in state.all_messages)

    def test_reports_cleaned_on_arrival(self):
        packet = make_packet(1, 1, 200, 100, warp=5, safe_warp=5,
                             ironium=100)
        state = make_state(packet)
        star = add_star(state, "Rcv", 200, 100, owner=2,
                        colonists=10000)
        add_starbase(state, star, 50, mass_driver=5)
        state.all_empires[1].fleet_reports[packet.key] = {
            "key": packet.key}
        state.all_empires[2].fleet_reports[packet.key] = {
            "key": packet.key}
        self._arrive(state, packet)
        assert packet.key not in state.all_empires[1].fleet_reports
        assert packet.key not in state.all_empires[2].fleet_reports


# --------------------------------------------------------------------------
# Fling command validation
# --------------------------------------------------------------------------

class TestFlingValidation:
    """submit_command('fling_packet') validation and effects."""

    @pytest.fixture
    def game(self, tmp_path):
        from backend.services.game_manager import GameManager

        manager = GameManager(str(tmp_path / "test.db"))
        created = manager.create_game("t", 2, "tiny", seed=99)
        game_id = created["id"]
        server_data = manager._load_game_state(game_id)
        empire = server_data.all_empires[1]
        home = next(s for s in empire.owned_stars.values())
        starbase = empire.owned_fleets[home.starbase_key]
        # Fit a rating-5 driver by state surgery
        for token in starbase.tokens.values():
            token.mass_driver = 5
        home.resources_on_hand.ironium = 500
        home.resources_on_hand.boranium = 300
        home.resources_on_hand.germanium = 200
        target = next(s for s in server_data.all_stars.values()
                      if s.name != home.name)
        return manager, game_id, server_data, empire, home, target

    def _fling(self, game, **data):
        manager, game_id, _, _, home, target = game
        payload = {"star": home.name, "target": target.name,
                   "warp": 5, "ironium": 100}
        payload.update(data)
        return manager.submit_command(game_id, 1, "fling_packet",
                                      payload)

    def test_rejects_unowned_star(self, game):
        result = self._fling(game, star="Nowhere")
        assert "error" in result

    def test_rejects_missing_starbase(self, game):
        manager, game_id, server_data, empire, home, target = game
        saved = home.starbase_key
        home.starbase_key = None
        result = self._fling(game)
        assert "No starbase" in result["error"]
        home.starbase_key = saved

    def test_rejects_starbase_without_driver(self, game):
        manager, game_id, server_data, empire, home, target = game
        starbase = empire.owned_fleets[home.starbase_key]
        for token in starbase.tokens.values():
            token.mass_driver = 0
        result = self._fling(game)
        assert "No mass driver" in result["error"]

    def test_rejects_bad_warp(self, game):
        assert "error" in self._fling(game, warp=4)   # below rating
        assert "error" in self._fling(game, warp=9)   # above rating + 3
        result = self._fling(game, warp=8)            # rating + 3 is fine
        assert result.get("status") == "applied"

    def test_warp_capped_at_thirteen(self, game):
        manager, game_id, server_data, empire, home, target = game
        starbase = empire.owned_fleets[home.starbase_key]
        for token in starbase.tokens.values():
            token.mass_driver = 12
        assert "error" in self._fling(game, warp=14)  # 12 + 3 > cap 13
        assert self._fling(game, warp=13).get("status") == "applied"

    def test_rejects_target_self(self, game):
        manager, game_id, server_data, empire, home, target = game
        result = self._fling(game, target=home.name)
        assert "error" in result

    def test_rejects_bad_amounts(self, game):
        assert "error" in self._fling(game, ironium=0)      # zero total
        assert "error" in self._fling(game, ironium=-5)     # negative
        assert "error" in self._fling(game, ironium=501)    # over surface

    def test_success_deducts_and_creates_packet(self, game):
        manager, game_id, server_data, empire, home, target = game
        result = self._fling(game, warp=6, ironium=100, boranium=50,
                             germanium=25)
        assert result["status"] == "applied"
        assert home.resources_on_hand.ironium == 400
        assert home.resources_on_hand.boranium == 250
        assert home.resources_on_hand.germanium == 175
        packet = empire.owned_fleets[result["fleet_key"]]
        assert is_mineral_packet(packet)
        assert packet.packet_warp == 6
        assert packet.packet_safe_warp == 5
        assert packet.cargo.ironium == 100
        assert packet.cargo.boranium == 50
        assert packet.cargo.germanium == 25
        assert packet.fuel_available == 0
        assert len(packet.tokens) == 1
        assert packet.owner == 1
        wp = packet.waypoints[0]
        assert wp.position.x == target.position.x
        assert wp.position.y == target.position.y
        assert wp.warp_factor == 6
        assert wp.destination == target.name

    def test_packet_fields_serialization_roundtrip(self, game):
        manager, game_id, server_data, empire, home, target = game
        result = self._fling(game, warp=7, ironium=60)
        key = result["fleet_key"]
        # Full persistence round trip through the manager serializers
        restored = manager._deserialize_state(
            manager._serialize_state(server_data))
        packet = restored.all_empires[1].owned_fleets[key]
        assert packet.packet_warp == 7
        assert packet.packet_safe_warp == 5

    def test_legacy_fleet_dict_defaults(self):
        fleet = Fleet(name="Old Fleet", position=NovaPoint(1, 2))
        fleet._key = (1 << 32) | 3
        data = fleet.to_dict()
        del data["packet_warp"]
        del data["packet_safe_warp"]
        restored = Fleet.from_dict(data)
        assert restored.packet_warp == 0
        assert restored.packet_safe_warp == 0
        assert not is_mineral_packet(restored)


# --------------------------------------------------------------------------
# Exclusions
# --------------------------------------------------------------------------

class TestPacketExclusions:
    """Packets are skipped by storms, minefields, sweeping, scores
    and the main movement loop (via is_mineral_packet, which also
    matches numbered names - the old exact-match checks did not)."""

    def test_is_mineral_packet_variants(self):
        named = Fleet(name="Mineral Packet #2", position=NovaPoint(0, 0))
        assert is_mineral_packet(named)
        flagged = Fleet(name="Anything", position=NovaPoint(0, 0))
        flagged.packet_warp = 5
        assert is_mineral_packet(flagged)
        plain = Fleet(name="Fleet #1", position=NovaPoint(0, 0))
        assert not is_mineral_packet(plain)

    def test_storms_skip_packets(self):
        packet = make_packet(2, 1, 300, 300, ironium=100)
        state = make_state(packet)
        state.all_storms[1] = GalacticStorm(
            key=1, x=300, y=300, radius=50,
            velocity_x=0, velocity_y=0, intensity=1.0)
        gen = TurnGenerator(state)
        gen._process_storms()
        assert packet.tokens[900].damage_percent == 0
        assert packet.cargo.ironium == 100

    def test_detonating_minefield_skips_packets(self):
        packet = make_packet(2, 1, 300, 300, ironium=100)
        state = make_state(packet)
        state.all_minefields[1] = Minefield(
            key=1, owner=2, position_x=300, position_y=300,
            number_of_mines=500, mine_type=0, detonate=True)
        state.all_empires[2] = EmpireData()
        state.all_empires[2].id = 2
        gen = TurnGenerator(state)
        gen._detonate_minefields()
        assert packet.tokens[900].damage_percent == 0

    def test_scores_exclude_packets(self):
        from backend.server.scores import Scores

        fleet = Fleet(name="Fleet #1", position=NovaPoint(0, 0))
        fleet._key = (1 << 32) | 1
        fleet.tokens[1] = ShipToken(design_key=1, design_name="Scout",
                                    quantity=1, mass=25)
        state = make_state(fleet)
        empire = state.all_empires[1]
        empire.designs[1] = SimpleDesign(key=1, name="Scout")
        empire.designs[900] = SimpleDesign(key=900,
                                           name="Mineral Packet")
        baseline = Scores(state).get_scores()[0].unarmed_ships

        packet = make_packet(7, 1, 50, 50, ironium=5000)
        empire.owned_fleets[packet.key] = packet
        with_packet = Scores(state).get_scores()[0]
        assert with_packet.unarmed_ships == baseline

    def test_movement_loop_skips_numbered_packet(self):
        """Regression: 'Mineral Packet #N' used to slip past the
        exact-match skip in the main movement loop and move twice per
        turn. A full generated turn must move it exactly one year."""
        from backend.services.game_manager import GameManager

        # A real game gives generate() everything it needs (stars,
        # players, nebulae); dust is cleared for exact flight math
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            manager = GameManager(str(tmp) + "/test.db")
            created = manager.create_game("t", 2, "tiny", seed=42)
            game_id = created["id"]
            server_data = manager._load_game_state(game_id)
            server_data.nebula_field.regions = []
            empire = server_data.all_empires[1]
            home = next(s for s in empire.owned_stars.values())
            starbase = empire.owned_fleets[home.starbase_key]
            for token in starbase.tokens.values():
                token.mass_driver = 5
            home.resources_on_hand.ironium = 500
            # Far target so the packet stays in flight
            target = max(
                (s for s in server_data.all_stars.values()
                 if s.name != home.name),
                key=lambda s: (s.position.x - home.position.x) ** 2
                + (s.position.y - home.position.y) ** 2)
            result = manager.submit_command(
                game_id, 1, "fling_packet",
                {"star": home.name, "target": target.name,
                 "warp": 5, "ironium": 100})
            assert result["status"] == "applied"
            packet = empire.owned_fleets[result["fleet_key"]]
            start = packet.position.copy()
            manager.generate_turn(game_id)
            moved = ((packet.position.x - start.x) ** 2
                     + (packet.position.y - start.y) ** 2) ** 0.5
            # One year at warp 5 covers 25 ly; a double move would
            # cover 50
            assert moved == pytest.approx(25, abs=1.5)
