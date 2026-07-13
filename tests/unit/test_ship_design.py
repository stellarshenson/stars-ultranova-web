"""
Unit tests for Ship Design system.
Tests verify parity with C# implementation:
- Common/Components/ShipDesign.cs
- Common/Components/Hull.cs
- Common/Components/HullModule.cs
- Common/Components/Engine.cs
"""
import pytest
from backend.core.components import (
    Hull, HullModule, Engine, ShipDesign,
    Component, ComponentProperty, ComponentLoader
)
from backend.core.data_structures.resources import Resources
from backend.core.game_objects.item import ItemType


class TestHullModule:
    """Tests for HullModule class."""

    def test_default_constructor(self):
        """Test default values."""
        m = HullModule()
        assert m.cell_number == -1
        assert m.component_maximum == 1
        assert m.component_type == ""
        assert m.component_count == 0
        assert m.allocated_component is None

    def test_is_empty_true(self):
        """Test empty module detection."""
        m = HullModule()
        assert m.is_empty() is True

    def test_is_empty_false_with_component(self):
        """Test module not empty when component allocated."""
        m = HullModule(component_type="Weapon", _component_count=2)
        c = Component()
        c.name = "Test Laser"
        m.allocated_component = c
        assert m.is_empty() is False

    def test_empty_clears_allocation(self):
        """Test empty() clears allocated component."""
        m = HullModule(_component_count=2)
        c = Component()
        m.allocated_component = c
        m.empty()
        assert m.allocated_component is None
        assert m.component_count == 0

    def test_clone(self):
        """Test module cloning."""
        m = HullModule(cell_number=5, component_maximum=3, component_type="Engine")
        clone = m.clone()
        assert clone.cell_number == 5
        assert clone.component_maximum == 3
        assert clone.component_type == "Engine"

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        m = HullModule(cell_number=3, component_maximum=4, component_type="Weapon")
        data = m.to_dict()
        m2 = HullModule.from_dict(data)
        assert m2.cell_number == 3
        assert m2.component_maximum == 4
        assert m2.component_type == "Weapon"


class TestHull:
    """Tests for Hull class."""

    def test_default_constructor(self):
        """Test default values."""
        h = Hull()
        assert h.fuel_capacity == 0
        assert h.dock_capacity == 0
        assert h.base_cargo == 0
        assert h.armor_strength == 0
        assert h.battle_initiative == 0
        assert len(h.modules) == 0

    def test_is_starbase_true(self):
        """Starbase has 0 fuel capacity."""
        h = Hull(fuel_capacity=0, dock_capacity=300)
        assert h.is_starbase is True

    def test_is_starbase_false(self):
        """Ship has positive fuel capacity."""
        h = Hull(fuel_capacity=200)
        assert h.is_starbase is False

    def test_can_refuel_starbase(self):
        """Starbase with dock can refuel."""
        h = Hull(fuel_capacity=0, dock_capacity=300)
        assert h.can_refuel is True

    def test_can_refuel_no_dock(self):
        """Starbase without dock cannot refuel."""
        h = Hull(fuel_capacity=0, dock_capacity=0)
        assert h.can_refuel is False

    def test_get_module_by_cell(self):
        """Test module lookup by cell number."""
        m1 = HullModule(cell_number=2, component_type="Weapon")
        m2 = HullModule(cell_number=5, component_type="Engine")
        h = Hull(modules=[m1, m2])
        assert h.get_module_by_cell(2) == m1
        assert h.get_module_by_cell(5) == m2
        assert h.get_module_by_cell(99) is None

    def test_get_modules_by_type(self):
        """Test module filtering by type."""
        m1 = HullModule(cell_number=1, component_type="Weapon")
        m2 = HullModule(cell_number=2, component_type="Weapon")
        m3 = HullModule(cell_number=3, component_type="Engine")
        h = Hull(modules=[m1, m2, m3])
        weapons = h.get_modules_by_type("Weapon")
        assert len(weapons) == 2

    def test_clear_all_modules(self):
        """Test clearing all module allocations."""
        c = Component()
        m1 = HullModule(_component_count=2)
        m1.allocated_component = c
        h = Hull(modules=[m1])
        h.clear_all_modules()
        assert m1.is_empty() is True

    def test_clone(self):
        """Test deep cloning hull."""
        m = HullModule(cell_number=1, component_type="Armor")
        h = Hull(fuel_capacity=200, armor_strength=150, modules=[m])
        clone = h.clone()
        assert clone.fuel_capacity == 200
        assert clone.armor_strength == 150
        assert len(clone.modules) == 1
        assert clone.modules[0].cell_number == 1

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        m = HullModule(cell_number=3, component_type="Scanner")
        h = Hull(fuel_capacity=500, base_cargo=100, modules=[m])
        data = h.to_dict()
        h2 = Hull.from_dict(data)
        assert h2.fuel_capacity == 500
        assert h2.base_cargo == 100
        assert len(h2.modules) == 1


class TestEngine:
    """Tests for Engine class."""

    def test_default_constructor(self):
        """Test default fuel consumption table."""
        e = Engine()
        assert len(e.fuel_consumption) == 10
        assert all(f == 0 for f in e.fuel_consumption)
        assert e.ram_scoop is False

    def test_free_warp_speed_none(self):
        """Test no free warp when all speeds consume fuel."""
        e = Engine(fuel_consumption=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
        assert e.free_warp_speed == 0

    def test_free_warp_speed_partial(self):
        """Test free warp at lower speeds."""
        # Warp 1-3 free (indexes 0-2 = 0)
        e = Engine(fuel_consumption=[0, 0, 0, 100, 200, 300, 400, 500, 600, 700])
        assert e.free_warp_speed == 3

    def test_get_fuel_consumption_bounds(self):
        """Test fuel consumption at various speeds."""
        e = Engine(fuel_consumption=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        assert e.get_fuel_consumption(1) == 10
        assert e.get_fuel_consumption(5) == 50
        assert e.get_fuel_consumption(10) == 100
        assert e.get_fuel_consumption(0) == 0  # Invalid
        assert e.get_fuel_consumption(11) == 0  # Invalid

    def test_optimum_speed(self):
        """Test optimum speed calculation."""
        # Port of Engine.cs - balances efficiency vs speed
        e = Engine(fuel_consumption=[0, 0, 50, 100, 150, 200, 300, 500, 800, 1200])
        speed = e.optimum_speed
        assert 1 <= speed <= 10

    def test_most_fuel_efficient_speed(self):
        """Test most fuel efficient speed ignoring travel time."""
        e = Engine(fuel_consumption=[100, 100, 100, 100, 100, 100, 100, 100, 100, 100])
        # All equal consumption - higher speed is more efficient
        assert e.most_fuel_efficient_speed == 10

    def test_clone(self):
        """Test engine cloning."""
        e = Engine(fuel_consumption=[10] * 10, ram_scoop=True, optimal_speed=7)
        clone = e.clone()
        assert clone.ram_scoop is True
        assert clone.optimal_speed == 7
        assert clone.fuel_consumption[0] == 10

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        e = Engine(fuel_consumption=[5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
                   ram_scoop=True, fastest_safe_speed=8)
        data = e.to_dict()
        e2 = Engine.from_dict(data)
        assert e2.fuel_consumption == [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
        assert e2.ram_scoop is True
        assert e2.fastest_safe_speed == 8


class TestShipDesign:
    """Tests for ShipDesign class."""

    @pytest.fixture
    def simple_hull_component(self):
        """Create a simple hull component for testing."""
        c = Component()
        c.name = "Test Hull"
        c.item_type = ItemType.HULL
        c.mass = 50
        c.cost = Resources(10, 5, 3, 25)

        hull_prop = ComponentProperty()
        hull_prop.property_type = "Hull"
        hull_prop.values = {
            "fuel_capacity": 200,
            "dock_capacity": 0,
            "base_cargo": 50,
            "armor_strength": 100,
            "battle_initiative": 2,
            "modules": [
                {"cell_number": 1, "component_maximum": 1, "component_type": "Engine"},
                {"cell_number": 2, "component_maximum": 2, "component_type": "Weapon"}
            ]
        }
        c.add_property(hull_prop)
        return c

    @pytest.fixture
    def engine_component(self):
        """Create an engine component for testing."""
        c = Component()
        c.name = "Test Engine"
        c.item_type = ItemType.ENGINE
        c.mass = 10
        c.cost = Resources(5, 0, 2, 10)

        engine_prop = ComponentProperty()
        engine_prop.property_type = "Engine"
        engine_prop.values = {
            "fuel_consumption": [0, 50, 100, 150, 200, 300, 400, 500, 700, 1000],
            "ram_scoop": False,
            "fastest_safe_speed": 9,
            "optimal_speed": 6
        }
        c.add_property(engine_prop)
        return c

    def test_default_constructor(self):
        """Test default design has no blueprint."""
        d = ShipDesign()
        assert d.blueprint is None
        assert d.hull is None

    def test_mass_from_hull(self, simple_hull_component):
        """Test mass includes hull mass."""
        d = ShipDesign(blueprint=simple_hull_component)
        d.update()
        assert d.mass == 50

    def test_cost_from_hull(self, simple_hull_component):
        """Test cost includes hull cost."""
        d = ShipDesign(blueprint=simple_hull_component)
        d.update()
        assert d.cost.ironium == 10
        assert d.cost.boranium == 5

    def test_armor_from_hull(self, simple_hull_component):
        """Test armor comes from hull base."""
        d = ShipDesign(blueprint=simple_hull_component)
        d.update()
        assert d.armor == 100

    def test_fuel_capacity_from_hull(self, simple_hull_component):
        """Test fuel capacity from hull."""
        d = ShipDesign(blueprint=simple_hull_component)
        d.update()
        assert d.fuel_capacity == 200

    def test_is_starbase_ship(self, simple_hull_component):
        """Test ship (has fuel) is not starbase."""
        d = ShipDesign(blueprint=simple_hull_component)
        assert d.is_starbase is False

    def test_battle_speed_clamped(self, simple_hull_component, engine_component):
        """Test battle speed is clamped to [0.5, 2.5]."""
        # First fit the engine to the hull
        hull = simple_hull_component
        hull_prop = hull.get_property("Hull")
        Hull_obj = Hull.from_dict(hull_prop.values)
        engine_module = Hull_obj.get_module_by_cell(1)
        engine_module.allocated_component = engine_component
        engine_module.component_count = 1

        d = ShipDesign(blueprint=hull)
        d.update()
        speed = d.battle_speed
        assert 0.5 <= speed <= 2.5

    def test_no_weapons(self, simple_hull_component):
        """Test design with no weapons."""
        d = ShipDesign(blueprint=simple_hull_component)
        d.update()
        assert d.has_weapons is False
        assert len(d.weapons) == 0

    def test_serialization_roundtrip(self, simple_hull_component):
        """Test to_dict/from_dict roundtrip."""
        d = ShipDesign(blueprint=simple_hull_component)
        d.name = "Test Ship"
        d.update()
        data = d.to_dict()
        d2 = ShipDesign.from_dict(data)
        assert d2.name == "Test Ship"
        assert d2.blueprint is not None


class TestCloaking:
    """Cloak unit curve and design aggregation (canonical Stars!
    rules - the C# reference stores cloak values but never applies
    them, ScanStep.cs:165)."""

    @pytest.fixture(scope="class")
    def loader(self):
        # ShipDesign.hull resolves allocated components through the
        # module-level loader singleton, so load that one
        from backend.core.components.component_loader import (
            get_component_loader, load_components
        )
        loader = get_component_loader()
        if not loader.is_loaded:
            load_components("backend/data/components.xml")
        return loader

    def _cloaked_design(self, loader, allocations):
        """Design on a fabricated hull with catalog components
        allocated by name: allocations = [(slot_type, name, count)]."""
        c = Component()
        c.name = "Cloak Test Hull"
        c.item_type = ItemType.HULL
        c.mass = 25
        c.cost = Resources(4, 2, 4, 10)
        hull_prop = ComponentProperty()
        hull_prop.property_type = "Hull"
        hull_prop.values = {
            "fuel_capacity": 50,
            "armor_strength": 20,
            "modules": [
                {"cell_number": i + 1, "component_maximum": 4,
                 "component_type": slot_type,
                 "allocated_component": name,
                 "component_count": count}
                for i, (slot_type, name, count) in enumerate(allocations)
            ],
        }
        c.add_property(hull_prop)
        design = ShipDesign(blueprint=c)
        design.name = "Cloak Test"
        design.update()
        return design

    def test_cloak_percent_from_units_anchors(self):
        from backend.core.components.ship_design import (
            cloak_percent_from_units
        )
        assert cloak_percent_from_units(0) == 0
        assert cloak_percent_from_units(70) == 35
        assert cloak_percent_from_units(100) == 50
        assert cloak_percent_from_units(140) == 55
        assert cloak_percent_from_units(300) == 75
        assert cloak_percent_from_units(540) == 85
        # Cap at the documented Stars! maximum of 98%
        assert cloak_percent_from_units(5000) == 98

    def test_cloak_units_from_percent_anchors(self):
        from backend.core.components.ship_design import (
            cloak_units_from_percent
        )
        assert cloak_units_from_percent(35) == 70    # Stealth Cloak
        assert cloak_units_from_percent(55) == 140   # Super-Stealth
        assert cloak_units_from_percent(75) == 300   # Transport Cloaking
        assert cloak_units_from_percent(85) == 540   # Ultra-Stealth
        assert cloak_units_from_percent(20) == 40    # Chameleon Scanner
        assert cloak_units_from_percent(25) == 50    # Depleted Neutronium

    def test_single_stealth_cloak(self, loader):
        design = self._cloaked_design(loader, [
            ("Electrical", "Stealth Cloak", 1),
        ])
        assert design.cloak_units == 70

    def test_cloak_units_stack_linearly(self, loader):
        """2 Stealth Cloaks = 140u (canonical linear unit stacking),
        NOT the C# probability stacking (57.75% -> 162u) whose result
        was never consumed."""
        design = self._cloaked_design(loader, [
            ("Electrical", "Stealth Cloak", 2),
        ])
        assert design.cloak_units == 140

    def test_shadow_shield_contributes_shield_and_cloak(self, loader):
        design = self._cloaked_design(loader, [
            ("Shield", "Shadow Shield", 1),
        ])
        assert design.shield == 75
        assert design.cloak_units == 70

    def test_tachyon_detector_count(self, loader):
        """Aggregation records the device COUNT, not the XML value 5."""
        design = self._cloaked_design(loader, [
            ("Electrical", "Tachyon Detector", 2),
        ])
        assert design.tachyon_detectors == 2

    def test_build_ship_design_cloaked_scout(self, loader):
        """Full builder path: Scout hull + engine + Stealth Cloak."""
        from backend.core.data_structures import EmpireData, TechLevel
        from backend.services.design_builder import build_ship_design

        empire = EmpireData(id=1)
        empire.research_levels = TechLevel.from_level(10)
        design, error = build_ship_design(empire, "Cloaked Scout", "Scout", [
            {"cell_number": 11, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 12, "component": "Stealth Cloak", "count": 1},
        ])
        assert error is None
        assert design.cloak_units == 70
        assert design.tachyon_detectors == 0

    def test_make_token_caches_cloak_fields(self):
        from backend.services.ship_specs import SimpleDesign, make_token
        from backend.core.game_objects.fleet import ShipToken

        design = SimpleDesign(key=5, name="Sneak", mass=25,
                              cloak_units=70, tachyon_detectors=2)
        token = make_token(design, quantity=3)
        assert token.cloak_units == 70
        assert token.tachyon_detectors == 2

        # ShipToken round-trips the cached fields
        token2 = ShipToken.from_dict(token.to_dict())
        assert token2.cloak_units == 70
        assert token2.tachyon_detectors == 2

        # SimpleDesign round-trips the new fields
        design2 = SimpleDesign.from_dict(design.to_dict())
        assert design2.cloak_units == 70
        assert design2.tachyon_detectors == 2


class TestComponentLoaderHullEngine:
    """Tests for component loader Hull/Engine parsing."""

    @pytest.fixture(scope="class")
    def loader(self):
        """Load components once for all tests."""
        l = ComponentLoader()
        l.load("backend/data/components.xml")
        return l

    def test_hull_component_has_modules(self, loader):
        """Test hull components have module slots."""
        hulls = loader.get_all_hulls()
        assert len(hulls) > 0
        hull_comp = hulls[0]
        hull_prop = hull_comp.get_property("Hull")
        assert hull_prop is not None
        modules = hull_prop.values.get("modules", [])
        assert len(modules) > 0

    def test_hull_has_fuel_capacity(self, loader):
        """Test ship hulls have fuel capacity."""
        hulls = loader.get_all_hulls()
        ship_hulls = [h for h in hulls
                      if h.get_property("Hull").values.get("fuel_capacity", 0) > 0]
        assert len(ship_hulls) > 0

    def test_engine_has_fuel_consumption(self, loader):
        """Test engines have fuel consumption table."""
        engines = loader.get_all_engines()
        assert len(engines) > 0
        engine_comp = engines[0]
        engine_prop = engine_comp.get_property("Engine")
        assert engine_prop is not None
        fuel = engine_prop.values.get("fuel_consumption", [])
        assert len(fuel) == 10

    def test_ram_scoop_engine(self, loader):
        """Test ram scoop engines have negative fuel consumption."""
        engines = loader.get_all_engines()
        settlers = loader.get_component("Settler's Delight")
        assert settlers is not None
        engine_prop = settlers.get_property("Engine")
        assert engine_prop.values.get("ram_scoop") is True
        # Ram scoops generate fuel (negative consumption)
        fuel = engine_prop.values.get("fuel_consumption", [])
        assert any(f < 0 for f in fuel)

    def test_starbase_hull(self, loader):
        """Test starbase hulls have 0 fuel capacity."""
        # Look for starbase type components
        starbases = loader.get_components_by_type(ItemType.STARBASE)
        if starbases:
            sb = starbases[0]
            hull_prop = sb.get_property("Hull")
            if hull_prop:
                assert hull_prop.values.get("fuel_capacity", 0) == 0
