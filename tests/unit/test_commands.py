"""
Unit tests for Command classes.
Tests verify parity with C# implementation in Common/Commands/
"""
import pytest
from backend.core.commands import (
    Command, CommandMode, Message,
    WaypointCommand, DesignCommand,
    ProductionCommand, ResearchCommand
)
from backend.core.data_structures import EmpireData, TechLevel
from backend.core.waypoints.waypoint import Waypoint
from backend.core.components.ship_design import ShipDesign
from backend.core.production.production_queue import ProductionOrder
from backend.core.game_objects.fleet import Fleet


class TestCommandMode:
    """Tests for CommandMode enum."""

    def test_all_modes(self):
        """Test all command modes exist."""
        assert CommandMode.ADD.value == "Add"
        assert CommandMode.EDIT.value == "Edit"
        assert CommandMode.DELETE.value == "Delete"
        assert CommandMode.INSERT.value == "Insert"


class TestMessage:
    """Tests for Message class."""

    def test_default_constructor(self):
        """Test default message."""
        m = Message()
        assert m.audience == 0
        assert m.text == ""

    def test_with_values(self):
        """Test message with values."""
        m = Message(audience=1, text="Test", message_type="Error", fleet_key=123)
        assert m.audience == 1
        assert m.text == "Test"
        assert m.message_type == "Error"
        assert m.fleet_key == 123


class TestWaypointCommand:
    """Tests for WaypointCommand."""

    @pytest.fixture
    def empire_with_fleet(self):
        """Create empire with a fleet."""
        empire = EmpireData(id=1)
        fleet = Fleet()
        fleet.key = 100
        fleet.name = "Test Fleet"
        empire.owned_fleets[100] = fleet
        return empire

    def test_default_constructor(self):
        """Test default waypoint command."""
        cmd = WaypointCommand()
        assert cmd.mode == CommandMode.ADD
        assert cmd.fleet_key == 0
        assert cmd.index == 0
        assert cmd.waypoint is None

    def test_is_valid_fleet_not_owned(self):
        """Test validation fails for unowned fleet."""
        empire = EmpireData(id=1)
        cmd = WaypointCommand(fleet_key=999)
        valid, msg = cmd.is_valid(empire)
        assert valid is False
        assert msg is not None
        assert "do not own" in msg.text

    def test_is_valid_owned_fleet(self, empire_with_fleet):
        """Test validation succeeds for owned fleet."""
        cmd = WaypointCommand(fleet_key=100)
        valid, msg = cmd.is_valid(empire_with_fleet)
        assert valid is True
        assert msg is None

    def test_apply_add_waypoint(self, empire_with_fleet):
        """Test adding a waypoint."""
        wp = Waypoint()
        wp.destination = "Target Star"
        cmd = WaypointCommand(mode=CommandMode.ADD, waypoint=wp, fleet_key=100)
        result = cmd.apply_to_state(empire_with_fleet)
        assert result is None
        assert len(empire_with_fleet.owned_fleets[100].waypoints) == 1

    def test_apply_delete_waypoint(self, empire_with_fleet):
        """Test deleting a waypoint."""
        # First add a waypoint
        fleet = empire_with_fleet.owned_fleets[100]
        fleet.waypoints.append(Waypoint())
        assert len(fleet.waypoints) == 1

        # Then delete it
        cmd = WaypointCommand(mode=CommandMode.DELETE, fleet_key=100, index=0)
        result = cmd.apply_to_state(empire_with_fleet)
        assert result is None
        assert len(fleet.waypoints) == 0

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        wp = Waypoint()
        wp.destination = "Test"
        cmd = WaypointCommand(mode=CommandMode.INSERT, waypoint=wp, fleet_key=42, index=3)
        data = cmd.to_dict()
        cmd2 = WaypointCommand.from_dict(data)
        assert cmd2.mode == CommandMode.INSERT
        assert cmd2.fleet_key == 42
        assert cmd2.index == 3


class TestDesignCommand:
    """Tests for DesignCommand."""

    @pytest.fixture
    def empire_with_design(self):
        """Create empire with a design."""
        empire = EmpireData(id=1)
        design = ShipDesign()
        design.key = 200
        design.name = "Scout"
        empire.designs[200] = design
        return empire

    def test_default_constructor(self):
        """Test default design command."""
        cmd = DesignCommand()
        assert cmd.mode == CommandMode.ADD
        assert cmd.design is not None

    def test_is_valid_add_duplicate(self, empire_with_design):
        """Test validation fails for duplicate design."""
        design = ShipDesign()
        design.key = 200  # Same key as existing
        cmd = DesignCommand(mode=CommandMode.ADD, design=design)
        valid, msg = cmd.is_valid(empire_with_design)
        assert valid is False
        assert "re-add" in msg.text

    def test_is_valid_add_new(self, empire_with_design):
        """Test validation succeeds for new design."""
        design = ShipDesign()
        design.key = 999  # New key
        cmd = DesignCommand(mode=CommandMode.ADD, design=design)
        valid, msg = cmd.is_valid(empire_with_design)
        assert valid is True

    def test_is_valid_delete_nonexistent(self):
        """Test validation fails for deleting nonexistent design."""
        empire = EmpireData(id=1)
        cmd = DesignCommand(mode=CommandMode.DELETE, design_key=999)
        valid, msg = cmd.is_valid(empire)
        assert valid is False

    def test_apply_add_design(self):
        """Test adding a design."""
        empire = EmpireData(id=1)
        design = ShipDesign()
        design.key = 100
        design.name = "Destroyer"
        cmd = DesignCommand(mode=CommandMode.ADD, design=design)
        result = cmd.apply_to_state(empire)
        assert result is None
        assert 100 in empire.designs
        assert empire.designs[100].name == "Destroyer"

    def test_apply_delete_design(self, empire_with_design):
        """Test deleting a design."""
        cmd = DesignCommand(mode=CommandMode.DELETE, design_key=200)
        result = cmd.apply_to_state(empire_with_design)
        assert result is None
        assert 200 not in empire_with_design.designs

    def test_apply_edit_toggles_obsolete(self, empire_with_design):
        """Test edit toggles obsolete flag."""
        assert empire_with_design.designs[200].obsolete is False
        cmd = DesignCommand(mode=CommandMode.EDIT, design_key=200)
        cmd.apply_to_state(empire_with_design)
        assert empire_with_design.designs[200].obsolete is True
        # Toggle again
        cmd.apply_to_state(empire_with_design)
        assert empire_with_design.designs[200].obsolete is False

    def test_serialization_roundtrip_delete(self):
        """Test delete command serialization."""
        cmd = DesignCommand(mode=CommandMode.DELETE, design_key=42)
        data = cmd.to_dict()
        cmd2 = DesignCommand.from_dict(data)
        assert cmd2.mode == CommandMode.DELETE
        assert cmd2.design.key == 42


class TestResearchCommand:
    """Tests for ResearchCommand."""

    def test_default_constructor(self):
        """Test default research command."""
        cmd = ResearchCommand()
        assert cmd.budget == 10
        assert cmd.topics is not None

    def test_is_valid_budget_range(self):
        """Test budget validation."""
        empire = EmpireData(id=1)

        # Invalid: negative
        cmd = ResearchCommand(budget=-5)
        valid, msg = cmd.is_valid(empire)
        assert valid is False

        # Invalid: over 100
        cmd = ResearchCommand(budget=150)
        valid, msg = cmd.is_valid(empire)
        assert valid is False

        # Valid: 0
        cmd = ResearchCommand(budget=0)
        valid, _ = cmd.is_valid(empire)
        assert valid is True

        # Valid: 100
        cmd = ResearchCommand(budget=100)
        valid, _ = cmd.is_valid(empire)
        assert valid is True

    def test_is_valid_no_change(self):
        """Test validation fails if nothing changed."""
        empire = EmpireData(id=1)
        empire.research_budget = 10
        empire.research_topics = TechLevel(levels={"Energy": 1})

        cmd = ResearchCommand(budget=10, topics=TechLevel(levels={"Energy": 1}))
        valid, _ = cmd.is_valid(empire)
        # Should be invalid since nothing changed
        assert valid is False

    def test_apply_changes_state(self):
        """Test applying research command."""
        empire = EmpireData(id=1)
        topics = TechLevel(levels={"Weapons": 1, "Energy": 0})
        cmd = ResearchCommand(budget=50, topics=topics)
        result = cmd.apply_to_state(empire)
        assert result is None
        assert empire.research_budget == 50
        assert empire.research_topics.levels["Weapons"] == 1

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        topics = TechLevel(levels={"Construction": 1})
        cmd = ResearchCommand(budget=75, topics=topics)
        data = cmd.to_dict()
        cmd2 = ResearchCommand.from_dict(data)
        assert cmd2.budget == 75
        assert cmd2.topics.levels["Construction"] == 1


class TestEmpireData:
    """Tests for EmpireData class."""

    def test_default_constructor(self):
        """Test default values."""
        empire = EmpireData()
        assert empire.id == 0
        assert empire.research_budget == 10
        assert len(empire.designs) == 0
        assert len(empire.owned_fleets) == 0

    def test_get_next_fleet_key(self):
        """Test fleet key generation includes empire ID."""
        empire = EmpireData(id=5)
        key1 = empire.get_next_fleet_key()
        key2 = empire.get_next_fleet_key()

        # Keys should be different
        assert key1 != key2
        # Empire ID should be in high bits
        assert (key1 >> 32) == 5
        assert (key2 >> 32) == 5

    def test_get_next_design_key(self):
        """Test design key generation includes empire ID."""
        empire = EmpireData(id=3)
        key = empire.get_next_design_key()
        assert (key >> 32) == 3

    def test_has_trait_no_race(self):
        """Test has_trait returns False with no race."""
        empire = EmpireData()
        assert empire.has_trait("IFE") is False

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        empire = EmpireData(id=7, research_budget=35)
        empire._fleet_counter = 10
        empire._design_counter = 5
        data = empire.to_dict()
        empire2 = EmpireData.from_dict(data)
        assert empire2.id == 7
        assert empire2.research_budget == 35
        assert empire2._fleet_counter == 10
        assert empire2._design_counter == 5
