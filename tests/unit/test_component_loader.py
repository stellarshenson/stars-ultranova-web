"""
Unit tests for the component loader.
"""

import pytest
from pathlib import Path

from backend.core.components.component_loader import ComponentLoader
from backend.core.game_objects.item import ItemType


# Path to components.xml
COMPONENTS_XML = Path(__file__).parent.parent.parent / "backend" / "data" / "components.xml"


class TestComponentLoader:
    """Tests for ComponentLoader class."""

    @pytest.fixture
    def loader(self):
        """Create and load a component loader."""
        loader = ComponentLoader()
        if COMPONENTS_XML.exists():
            loader.load(str(COMPONENTS_XML))
        return loader

    def test_load_components(self, loader):
        """Test loading components from XML."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        assert loader.is_loaded
        assert loader.component_count > 0

    def test_get_component_by_name(self, loader):
        """Test retrieving a component by name."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        # Get a known component
        snooper = loader.get_component("Snooper 620X")
        assert snooper is not None
        assert snooper.name == "Snooper 620X"
        assert snooper.item_type == ItemType.PLANETARY_INSTALLATIONS

    def test_component_cost(self, loader):
        """Test component cost parsing."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        snooper = loader.get_component("Snooper 620X")
        assert snooper is not None
        assert snooper.cost.ironium == 10
        assert snooper.cost.boranium == 10
        assert snooper.cost.germanium == 70
        assert snooper.cost.energy == 100

    def test_component_tech_requirements(self, loader):
        """Test component tech requirements parsing."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        snooper = loader.get_component("Snooper 620X")
        assert snooper is not None
        assert snooper.required_tech.levels["Biotechnology"] == 9
        assert snooper.required_tech.levels["Electronics"] == 23
        assert snooper.required_tech.levels["Energy"] == 7

    def test_component_properties(self, loader):
        """Test component property parsing."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        snooper = loader.get_component("Snooper 620X")
        assert snooper is not None

        # Check scanner property
        scanner_prop = snooper.get_property("Scanner")
        assert scanner_prop is not None
        assert scanner_prop.values.get("NormalScan") == 620
        assert scanner_prop.values.get("PenetratingScan") == 310

    def test_get_components_by_type(self, loader):
        """Test retrieving components by type."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        bombs = loader.get_components_by_type(ItemType.BOMB)
        assert len(bombs) > 0

        for bomb in bombs:
            assert bomb.item_type == ItemType.BOMB

    def test_component_restrictions(self, loader):
        """Test component race restrictions parsing."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        snooper = loader.get_component("Snooper 620X")
        assert snooper is not None

        # Snooper should have AR=0 (not available) and NAS=0 (not available)
        from backend.core.race.traits import RaceAvailability
        assert snooper.restrictions.availability("AR") == RaceAvailability.NOT_AVAILABLE
        assert snooper.restrictions.availability("NAS") == RaceAvailability.NOT_AVAILABLE

    def test_weapon_component(self, loader):
        """Test weapon component parsing."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        sapper = loader.get_component("Pulsed Sapper")
        assert sapper is not None
        assert sapper.item_type == ItemType.BEAM_WEAPONS

        weapon_prop = sapper.get_property("Weapon")
        assert weapon_prop is not None
        assert weapon_prop.values.get("Power") == 82
        assert weapon_prop.values.get("Range") == 3
        assert weapon_prop.values.get("Initiative") == 14
        assert weapon_prop.values.get("Accuracy") == 100
        assert weapon_prop.values.get("Group") == "shieldSapper"

    def test_bomb_component(self, loader):
        """Test bomb component parsing."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        bomb = loader.get_component("Black Cat Bomb")
        assert bomb is not None
        assert bomb.item_type == ItemType.BOMB
        assert bomb.mass == 45

        bomb_prop = bomb.get_property("Bomb")
        assert bomb_prop is not None
        assert bomb_prop.values.get("Installations") == 4
        assert bomb_prop.values.get("PopKill") == 0.9
        assert bomb_prop.values.get("MinimumKill") == 300
        assert bomb_prop.values.get("IsSmart") == False

    def test_get_stats(self, loader):
        """Test getting component statistics."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        stats = loader.get_stats()
        assert isinstance(stats, dict)
        assert len(stats) > 0

    def test_component_clone(self, loader):
        """Test cloning a component."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        original = loader.get_component("Snooper 620X")
        assert original is not None

        clone = original.clone()
        assert clone.name == original.name
        assert clone.mass == original.mass
        assert clone.cost.ironium == original.cost.ironium
        assert clone is not original

    def test_component_serialization(self, loader):
        """Test component to_dict and from_dict."""
        if not COMPONENTS_XML.exists():
            pytest.skip("components.xml not found")

        original = loader.get_component("Snooper 620X")
        assert original is not None

        data = original.to_dict()
        assert data["name"] == "Snooper 620X"
        assert data["mass"] == 0

        from backend.core.components.component import Component
        restored = Component.from_dict(data)
        assert restored.name == original.name
        assert restored.mass == original.mass


class TestTechLevel:
    """Tests for TechLevel class."""

    def test_create_empty(self):
        """Test creating empty TechLevel."""
        from backend.core.data_structures.tech_level import TechLevel

        tech = TechLevel()
        assert tech.levels["Biotechnology"] == 0
        assert tech.levels["Electronics"] == 0

    def test_create_from_values(self):
        """Test creating TechLevel from values."""
        from backend.core.data_structures.tech_level import TechLevel

        tech = TechLevel.from_values(
            biotechnology=5,
            electronics=10,
            energy=3,
            propulsion=7,
            weapons=12,
            construction=4
        )
        assert tech.levels["Biotechnology"] == 5
        assert tech.levels["Electronics"] == 10
        assert tech.levels["Weapons"] == 12

    def test_comparison_ge(self):
        """Test >= comparison."""
        from backend.core.data_structures.tech_level import TechLevel

        tech1 = TechLevel.from_values(biotechnology=10, electronics=10)
        tech2 = TechLevel.from_values(biotechnology=5, electronics=5)

        assert tech1 >= tech2
        assert not (tech2 >= tech1)

    def test_comparison_lt(self):
        """Test < comparison."""
        from backend.core.data_structures.tech_level import TechLevel

        tech1 = TechLevel.from_values(biotechnology=3)
        tech2 = TechLevel.from_values(biotechnology=5)

        assert tech1 < tech2

    def test_indexing(self):
        """Test indexing with ResearchField enum."""
        from backend.core.data_structures.tech_level import TechLevel, ResearchField

        tech = TechLevel.from_values(weapons=15)
        assert tech[ResearchField.WEAPONS] == 15

        tech[ResearchField.ENERGY] = 20
        assert tech.levels["Energy"] == 20


class TestRaceRestriction:
    """Tests for RaceRestriction class."""

    def test_default_not_required(self):
        """Test default availability is not_required."""
        from backend.core.race.traits import RaceRestriction, RaceAvailability

        restriction = RaceRestriction()
        assert restriction.availability("HE") == RaceAvailability.NOT_REQUIRED

    def test_set_restriction(self):
        """Test setting restrictions."""
        from backend.core.race.traits import RaceRestriction, RaceAvailability

        restriction = RaceRestriction()
        restriction.set_restriction("AR", RaceAvailability.REQUIRED)

        assert restriction.availability("AR") == RaceAvailability.REQUIRED

    def test_availability_check(self):
        """Test race availability checking."""
        from backend.core.race.traits import RaceRestriction, RaceAvailability

        restriction = RaceRestriction()
        restriction.set_restriction("AR", RaceAvailability.REQUIRED)

        # Race with AR trait should have access
        assert restriction.is_available_to_race(["AR", "IFE"])

        # Race without AR trait should not have access
        assert not restriction.is_available_to_race(["HE", "IFE"])

    def test_not_available_restriction(self):
        """Test NOT_AVAILABLE restriction."""
        from backend.core.race.traits import RaceRestriction, RaceAvailability

        restriction = RaceRestriction()
        restriction.set_restriction("NAS", RaceAvailability.NOT_AVAILABLE)

        # Race without NAS should have access
        assert restriction.is_available_to_race(["HE"])

        # Race with NAS should not have access
        assert not restriction.is_available_to_race(["NAS"])
