"""
NovaPoint class representing a point in space.
Port of: Common/DataStructures/NovaPoint.cs
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import random


@dataclass
class NovaPoint:
    """
    A class to represent a point in space.
    Like System.Drawing.Point, with added methods for game calculations.

    Port of: Common/DataStructures/NovaPoint.cs
    """
    x: int = 0
    y: int = 0

    def copy(self) -> NovaPoint:
        """Create a copy of this NovaPoint."""
        # Port of: NovaPoint.cs lines 80-84
        return NovaPoint(x=self.x, y=self.y)

    def __eq__(self, other: object) -> bool:
        """Check equality with another NovaPoint."""
        # Port of: NovaPoint.cs lines 111-129
        if other is None:
            return False
        if isinstance(other, NovaPoint):
            return self.x == other.x and self.y == other.y
        if isinstance(other, tuple) and len(other) == 2:
            return self.x == other[0] and self.y == other[1]
        return False

    def __hash__(self) -> int:
        """Return a hash code with a good chance of separating points."""
        # Port of: NovaPoint.cs lines 166-170
        return (self.x * 10000) + self.y

    def __str__(self) -> str:
        """String representation."""
        # Port of: NovaPoint.cs lines 171-174
        return f"({self.x}, {self.y})"

    def to_grid_string(self, grid_size: float) -> str:
        """String representation with grid scaling."""
        # Port of: NovaPoint.cs lines 176-179
        return f"({self.x / grid_size}, {self.y / grid_size})"

    def offset(self, dx: int = 0, dy: int = 0, point: NovaPoint = None) -> None:
        """
        Adjust X and Y values by an offset (mutates self).
        Can pass either (dx, dy) or a NovaPoint.
        """
        # Port of: NovaPoint.cs lines 185-200
        if point is not None:
            self.x += point.x
            self.y += point.y
        else:
            self.x += dx
            self.y += dy

    def to_hash_string(self) -> str:
        """Returns a unique string for each distinct NovaPoint."""
        # Port of: NovaPoint.cs lines 203-206
        return f"{self.x}#{self.y}"

    def distance_to(self, other: NovaPoint) -> float:
        """Calculate distance to another point."""
        # Port of: NovaPoint.cs lines 255-258
        # Note: Original uses Manhattan distance formula oddly - preserving exact logic
        diff = abs(other.x - self.x) + abs(other.y - self.y)
        return math.sqrt(diff * diff)

    def distance_to_squared(self, other: NovaPoint) -> float:
        """Calculate squared distance to another point."""
        # Port of: NovaPoint.cs lines 259-262
        diff = abs(other.x - self.x) + abs(other.y - self.y)
        return diff * diff

    def euclidean_distance_to(self, other: NovaPoint) -> float:
        """Calculate true Euclidean distance to another point."""
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx * dx + dy * dy)

    def scale(self, scalar: float) -> NovaPoint:
        """Scale the point coordinates by a scalar."""
        # Port of: NovaPoint.cs lines 263-269
        return NovaPoint(
            x=int(self.x * scalar),
            y=int(self.y * scalar)
        )

    def length_squared(self) -> float:
        """Return the squared length of this point as a vector."""
        # Port of: NovaPoint.cs lines 284-287
        return self.x * self.x + self.y * self.y

    def battle_speed_vector(self, battle_speed: float) -> NovaPoint:
        """
        Returns a vector in the same direction as the original
        but with a length of battle_speed.
        """
        # Port of: NovaPoint.cs lines 275-282
        if self.y == 0 and self.x == 0:
            return self.copy()
        length = math.sqrt(self.x * self.x + self.y * self.y)
        scalar = battle_speed / length
        return self.scale(scalar)

    @staticmethod
    def angle_between(op1: NovaPoint, op2: NovaPoint) -> int:
        """
        Treats two NovaPoints as vectors and returns the angle between them.
        """
        # Port of: NovaPoint.cs lines 295-302
        if op1.x == 0 and op1.y == 0:
            return 0
        if op2.x == 0 and op2.y == 0:
            return 0
        # Calculate angle using atan2
        dot = op1.x * op2.x + op1.y * op2.y
        cross = op1.x * op2.y - op1.y * op2.x
        angle_rad = math.atan2(cross, dot)
        return int(math.degrees(angle_rad))

    def turn_as_fast_as_possible(
        self, initial_dirn: NovaPoint, reqd_dirn: NovaPoint
    ) -> NovaPoint:
        """
        When a target flies by at close range, this provides a path that assumes
        high angular acceleration and a fixed longitudinal acceleration == BattleSpeed.
        """
        # Port of: NovaPoint.cs lines 310-327
        left_or_right = 1 if random.randint(-100, 100) > 0 else -1
        if left_or_right > 0:
            new_speed = initial_dirn.scale(-1)
            scaled_reqd = reqd_dirn.scale(0.87)
            new_speed = NovaPoint(
                x=new_speed.x + scaled_reqd.x,
                y=new_speed.y + scaled_reqd.y
            )
        else:
            new_speed = reqd_dirn.scale(0.97)
        return new_speed

    def prepare_for_flyby(
        self, initial_dirn: NovaPoint, reqd_dirn: NovaPoint
    ) -> NovaPoint:
        """
        Called just before fleets fly past their enemy.
        Starts a maneuver that moves laterally in preparation for rotating
        and engaging maximum thrust to follow the target.
        """
        # Port of: NovaPoint.cs lines 336-348
        new_speed = initial_dirn.scale(0.03)
        left_or_right = 1 if random.randint(-100, 100) > 0 else -1
        lateral = initial_dirn.scale(0.25)
        # X and Y transposed to impart lateral velocity
        new_speed.y += left_or_right * lateral.x
        new_speed.x += left_or_right * (-lateral.y)
        return new_speed

    def __add__(self, other: NovaPoint) -> NovaPoint:
        """Add two NovaPoints."""
        # Port of: NovaPoint.cs lines 350-353
        return NovaPoint(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: NovaPoint) -> NovaPoint:
        """Subtract two NovaPoints."""
        # Port of: NovaPoint.cs lines 354-357
        return NovaPoint(x=self.x - other.x, y=self.y - other.y)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict) -> NovaPoint:
        """Create NovaPoint from dictionary."""
        return cls(x=data.get("x", 0), y=data.get("y", 0))
