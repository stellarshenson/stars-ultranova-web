"""
Unit tests for NovaPoint class.
Tests verify parity with C# implementation in Common/DataStructures/NovaPoint.cs
"""
import pytest
import math
from backend.core.data_structures import NovaPoint


class TestNovaPoint:
    """Tests for NovaPoint class."""

    def test_default_constructor(self):
        """Test default constructor creates origin point."""
        p = NovaPoint()
        assert p.x == 0
        assert p.y == 0

    def test_constructor_with_values(self):
        """Test constructor with x, y values."""
        p = NovaPoint(x=10, y=20)
        assert p.x == 10
        assert p.y == 20

    def test_copy(self):
        """Test copy creates independent object."""
        # Port of: NovaPoint.cs lines 80-84
        p1 = NovaPoint(x=10, y=20)
        p2 = p1.copy()
        p2.x = 100
        assert p1.x == 10  # Original unchanged

    def test_equality(self):
        """Test equality operator."""
        # Port of: NovaPoint.cs lines 137-150
        p1 = NovaPoint(x=10, y=20)
        p2 = NovaPoint(x=10, y=20)
        p3 = NovaPoint(x=5, y=20)

        assert p1 == p2
        assert not (p1 == p3)
        assert p1 != p3

    def test_equality_with_tuple(self):
        """Test equality with tuple."""
        p = NovaPoint(x=10, y=20)
        assert p == (10, 20)

    def test_hash(self):
        """Test hash calculation."""
        # Port of: NovaPoint.cs lines 166-170
        p = NovaPoint(x=10, y=20)
        expected = 10 * 10000 + 20
        assert hash(p) == expected

    def test_str(self):
        """Test string representation."""
        # Port of: NovaPoint.cs lines 171-174
        p = NovaPoint(x=10, y=20)
        assert str(p) == "(10, 20)"

    def test_to_hash_string(self):
        """Test hash string for uniqueness."""
        # Port of: NovaPoint.cs lines 203-206
        p = NovaPoint(x=10, y=20)
        assert p.to_hash_string() == "10#20"

    def test_offset_with_values(self):
        """Test offset with dx, dy values."""
        # Port of: NovaPoint.cs lines 196-200
        p = NovaPoint(x=10, y=20)
        p.offset(dx=5, dy=10)
        assert p.x == 15
        assert p.y == 30

    def test_offset_with_point(self):
        """Test offset with another NovaPoint."""
        # Port of: NovaPoint.cs lines 185-189
        p1 = NovaPoint(x=10, y=20)
        p2 = NovaPoint(x=5, y=10)
        p1.offset(point=p2)
        assert p1.x == 15
        assert p1.y == 30

    def test_distance_to(self):
        """Test distance calculation."""
        # Port of: NovaPoint.cs lines 255-258
        # Note: Original uses Manhattan distance oddly - preserving exact logic
        p1 = NovaPoint(x=0, y=0)
        p2 = NovaPoint(x=3, y=4)
        # Original: sqrt((|3-0| + |4-0|)^2) = sqrt(7^2) = 7
        assert p1.distance_to(p2) == 7.0

    def test_distance_to_squared(self):
        """Test squared distance calculation."""
        # Port of: NovaPoint.cs lines 259-262
        p1 = NovaPoint(x=0, y=0)
        p2 = NovaPoint(x=3, y=4)
        # Original: (|3-0| + |4-0|)^2 = 7^2 = 49
        assert p1.distance_to_squared(p2) == 49.0

    def test_scale(self):
        """Test scaling point coordinates."""
        # Port of: NovaPoint.cs lines 263-269
        p = NovaPoint(x=10, y=20)
        scaled = p.scale(0.5)
        assert scaled.x == 5
        assert scaled.y == 10

    def test_length_squared(self):
        """Test squared length as vector."""
        # Port of: NovaPoint.cs lines 284-287
        p = NovaPoint(x=3, y=4)
        assert p.length_squared() == 25  # 3^2 + 4^2 = 25

    def test_battle_speed_vector(self):
        """Test battle speed vector normalization."""
        # Port of: NovaPoint.cs lines 275-282
        p = NovaPoint(x=3, y=4)  # Length = 5
        result = p.battle_speed_vector(10.0)
        # Should scale to length 10
        expected_x = int(3 * 10 / 5)  # 6
        expected_y = int(4 * 10 / 5)  # 8
        assert result.x == expected_x
        assert result.y == expected_y

    def test_battle_speed_vector_zero(self):
        """Test battle speed vector with zero length."""
        p = NovaPoint(x=0, y=0)
        result = p.battle_speed_vector(10.0)
        assert result.x == 0
        assert result.y == 0

    def test_addition(self):
        """Test point addition."""
        # Port of: NovaPoint.cs lines 350-353
        p1 = NovaPoint(x=10, y=20)
        p2 = NovaPoint(x=5, y=10)
        result = p1 + p2
        assert result.x == 15
        assert result.y == 30

    def test_subtraction(self):
        """Test point subtraction."""
        # Port of: NovaPoint.cs lines 354-357
        p1 = NovaPoint(x=10, y=20)
        p2 = NovaPoint(x=5, y=10)
        result = p1 - p2
        assert result.x == 5
        assert result.y == 10

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        p1 = NovaPoint(x=10, y=20)
        data = p1.to_dict()
        p2 = NovaPoint.from_dict(data)
        assert p1 == p2
