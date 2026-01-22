"""
Unit tests for Resources class.
Tests verify parity with C# implementation in Common/DataStructures/Resources.cs
"""
import pytest
from backend.core.data_structures import Resources


class TestResources:
    """Tests for Resources class."""

    def test_default_constructor(self):
        """Test default constructor creates zero resources."""
        r = Resources()
        assert r.ironium == 0
        assert r.boranium == 0
        assert r.germanium == 0
        assert r.energy == 0
        assert r.silicoxium == 0

    def test_from_ibge(self):
        """Test creation with IBGE values."""
        r = Resources.from_ibge(10, 20, 30, 40)
        assert r.ironium == 10
        assert r.boranium == 20
        assert r.germanium == 30
        assert r.energy == 40
        assert r.silicoxium == 0

    def test_mass_excludes_energy(self):
        """Test that mass calculation excludes energy."""
        # Port of: Resources.cs lines 285-288
        r = Resources.from_ibge(10, 20, 30, 100)
        r.silicoxium = 5
        assert r.mass == 10 + 20 + 30 + 5  # 65, not 165

    def test_addition(self):
        """Test resource addition."""
        # Port of: Resources.cs lines 225-235
        r1 = Resources.from_ibge(10, 20, 30, 40)
        r2 = Resources.from_ibge(5, 10, 15, 20)
        result = r1 + r2
        assert result.ironium == 15
        assert result.boranium == 30
        assert result.germanium == 45
        assert result.energy == 60

    def test_subtraction(self):
        """Test resource subtraction."""
        # Port of: Resources.cs lines 210-220
        r1 = Resources.from_ibge(10, 20, 30, 40)
        r2 = Resources.from_ibge(5, 10, 15, 20)
        result = r1 - r2
        assert result.ironium == 5
        assert result.boranium == 10
        assert result.germanium == 15
        assert result.energy == 20

    def test_multiplication_by_int(self):
        """Test resource multiplication by integer."""
        # Port of: Resources.cs lines 237-247
        r = Resources.from_ibge(10, 20, 30, 40)
        result = r * 3
        assert result.ironium == 30
        assert result.boranium == 60
        assert result.germanium == 90
        assert result.energy == 120

    def test_multiplication_by_float(self):
        """Test resource multiplication by float (uses ceiling)."""
        # Port of: Resources.cs lines 265-275
        r = Resources.from_ibge(10, 20, 30, 40)
        result = r * 1.5
        assert result.ironium == 15  # ceil(10 * 1.5) = 15
        assert result.boranium == 30  # ceil(20 * 1.5) = 30
        assert result.germanium == 45  # ceil(30 * 1.5) = 45
        assert result.energy == 60  # ceil(40 * 1.5) = 60

    def test_multiplication_by_float_ceiling(self):
        """Test that float multiplication uses ceiling rounding."""
        # Port of: Resources.cs comment on lines 264-265
        r = Resources.from_ibge(1, 1, 1, 1)
        result = r * 0.1
        # ceil(0.1) = 1
        assert result.ironium == 1
        assert result.boranium == 1

    def test_division_returns_minimum_ratio(self):
        """Test resource division returns minimum ratio across types."""
        # Port of: Resources.cs lines 248-258
        r1 = Resources.from_ibge(20, 30, 40, 50)
        r2 = Resources.from_ibge(10, 10, 10, 10)
        result = r1 / r2
        assert result == 2.0  # 20/10 = 2.0 is minimum

    def test_greater_equal(self):
        """Test >= operator."""
        # Port of: Resources.cs lines 93-101
        r1 = Resources.from_ibge(10, 20, 30, 40)
        r2 = Resources.from_ibge(10, 20, 30, 40)
        r3 = Resources.from_ibge(5, 10, 15, 20)
        r4 = Resources.from_ibge(15, 20, 30, 40)

        assert r1 >= r2  # Equal
        assert r1 >= r3  # Greater
        assert not (r3 >= r1)  # Less
        assert not (r1 >= r4)  # r1.ironium < r4.ironium

    def test_equality(self):
        """Test equality operator."""
        # Port of: Resources.cs lines 109-169
        r1 = Resources.from_ibge(10, 20, 30, 40)
        r2 = Resources.from_ibge(10, 20, 30, 40)
        r3 = Resources.from_ibge(5, 20, 30, 40)

        assert r1 == r2
        assert not (r1 == r3)

    def test_hash(self):
        """Test hash calculation."""
        # Port of: Resources.cs lines 194-197
        r = Resources.from_ibge(10, 20, 30, 40)
        expected = 10 ^ 20 ^ 30 ^ 40
        assert hash(r) == expected

    def test_copy(self):
        """Test copy creates independent object."""
        r1 = Resources.from_ibge(10, 20, 30, 40)
        r2 = r1.copy()
        r2.ironium = 100
        assert r1.ironium == 10  # Original unchanged

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        r1 = Resources.from_ibge(10, 20, 30, 40)
        r1.silicoxium = 5
        data = r1.to_dict()
        r2 = Resources.from_dict(data)
        assert r1 == r2
