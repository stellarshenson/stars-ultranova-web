"""
Unit tests for Cargo class.
Tests verify parity with C# implementation in Common/DataStructures/Cargo.cs
"""
import pytest
from backend.core.data_structures import Cargo, ResourceType
from backend.core.globals import COLONISTS_PER_KILOTON


class TestCargo:
    """Tests for Cargo class."""

    def test_default_constructor(self):
        """Test default constructor creates empty cargo."""
        c = Cargo()
        assert c.ironium == 0
        assert c.boranium == 0
        assert c.germanium == 0
        assert c.colonists_in_kilotons == 0
        assert c.silicoxium == 0

    def test_from_minerals(self):
        """Test creation with mineral values."""
        c = Cargo.from_minerals(10, 20, 30, 40, 5)
        assert c.ironium == 10
        assert c.boranium == 20
        assert c.germanium == 30
        assert c.colonists_in_kilotons == 40
        assert c.silicoxium == 5

    def test_mass(self):
        """Test mass calculation includes all cargo."""
        # Port of: Cargo.cs lines 150-153
        c = Cargo.from_minerals(10, 20, 30, 40, 5)
        assert c.mass == 10 + 20 + 30 + 40 + 5

    def test_colonist_numbers(self):
        """Test colonist number calculation."""
        # Port of: Cargo.cs lines 139-145
        c = Cargo()
        c.colonists_in_kilotons = 10
        assert c.colonist_numbers == 10 * COLONISTS_PER_KILOTON

    def test_indexer_get(self):
        """Test array-like access via ResourceType."""
        # Port of: Cargo.cs lines 158-172
        c = Cargo.from_minerals(10, 20, 30, 40, 5)
        assert c[ResourceType.IRONIUM] == 10
        assert c[ResourceType.BORANIUM] == 20
        assert c[ResourceType.GERMANIUM] == 30
        assert c[ResourceType.COLONISTS_IN_KILOTONS] == 40
        assert c[ResourceType.SILICOXIUM] == 5

    def test_indexer_set(self):
        """Test array-like assignment via ResourceType."""
        c = Cargo()
        c[ResourceType.IRONIUM] = 100
        assert c.ironium == 100

    def test_scale_within_bounds(self):
        """Test scaling cargo by a factor."""
        # Port of: Cargo.cs lines 214-225
        c = Cargo.from_minerals(100, 200, 300, 400, 50)
        scaled = c.scale(0.5)
        assert scaled.ironium == 50
        assert scaled.boranium == 100
        assert scaled.germanium == 150
        assert scaled.colonists_in_kilotons == 200
        assert scaled.silicoxium == 25

    def test_scale_clamped_to_one(self):
        """Test scale factor clamped to 1."""
        # Port of: Cargo.cs lines 216-217
        c = Cargo.from_minerals(100, 100, 100, 100, 0)
        scaled = c.scale(2.0)  # Clamped to 1.0
        assert scaled.ironium == 100

    def test_scale_clamped_to_zero(self):
        """Test scale factor clamped to 0."""
        c = Cargo.from_minerals(100, 100, 100, 100, 0)
        scaled = c.scale(-1.0)  # Clamped to 0.0
        assert scaled.ironium == 0

    def test_min(self):
        """Test min returns minimum of each resource."""
        # Port of: Cargo.cs lines 277-287
        c1 = Cargo.from_minerals(10, 50, 30, 40, 0)
        c2 = Cargo.from_minerals(20, 20, 50, 10, 0)
        result = Cargo.min(c1, c2)
        assert result.ironium == 10
        assert result.boranium == 20
        assert result.germanium == 30
        assert result.colonists_in_kilotons == 10

    def test_add(self):
        """Test add mutates self."""
        # Port of: Cargo.cs lines 288-295
        c1 = Cargo.from_minerals(10, 20, 30, 40, 0)
        c2 = Cargo.from_minerals(5, 10, 15, 20, 0)
        c1.add(c2)
        assert c1.ironium == 15
        assert c1.boranium == 30

    def test_remove(self):
        """Test remove mutates self."""
        # Port of: Cargo.cs lines 297-304
        c1 = Cargo.from_minerals(10, 20, 30, 40, 0)
        c2 = Cargo.from_minerals(5, 10, 15, 20, 0)
        c1.remove(c2)
        assert c1.ironium == 5
        assert c1.boranium == 10

    def test_clear(self):
        """Test clear sets all to zero."""
        # Port of: Cargo.cs lines 309-316
        c = Cargo.from_minerals(10, 20, 30, 40, 5)
        c.clear()
        assert c.mass == 0

    def test_to_resource(self):
        """Test conversion to Resources (excludes colonists)."""
        # Port of: Cargo.cs lines 322-325
        c = Cargo.from_minerals(10, 20, 30, 40, 5)
        r = c.to_resource()
        assert r.ironium == 10
        assert r.boranium == 20
        assert r.germanium == 30
        assert r.energy == 0  # Energy not from cargo
        assert r.silicoxium == 5

    def test_str(self):
        """Test string representation."""
        # Port of: Cargo.cs lines 348-356
        c = Cargo.from_minerals(10, 20, 30, 40, 5)
        assert str(c) == "10,20,30,40,5"

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        c1 = Cargo.from_minerals(10, 20, 30, 40, 5)
        data = c1.to_dict()
        c2 = Cargo.from_dict(data)
        assert c1.ironium == c2.ironium
        assert c1.boranium == c2.boranium
        assert c1.germanium == c2.germanium
        assert c1.colonists_in_kilotons == c2.colonists_in_kilotons
        assert c1.silicoxium == c2.silicoxium
