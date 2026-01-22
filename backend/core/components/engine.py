"""
Stars Nova Web - Engine
Ported from Common/Components/Engine.cs

Engine component property with fuel consumption tables.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Engine:
    """
    Engine component property defining ship propulsion.

    Engines define:
    - Fuel consumption at each warp speed (0-9 index = warp 1-10)
    - Whether it's a ram scoop (generates fuel)
    - Optimal and safe speeds

    Ported from Engine.cs.
    """
    # Fuel consumption at each warp speed (index 0 = warp 1, index 9 = warp 10)
    fuel_consumption: List[int] = field(default_factory=lambda: [0] * 10)
    ram_scoop: bool = False
    fastest_safe_speed: int = 0
    optimal_speed: int = 0

    @property
    def free_warp_speed(self) -> int:
        """
        Get max speed at which engine uses 0 fuel.

        Iterates backwards through fuel table to find highest
        warp with 0 consumption.
        """
        for i in range(9, -1, -1):
            if self.fuel_consumption[i] == 0:
                return i + 1  # Index is one less than warp speed
        return 0

    @property
    def optimum_speed(self) -> int:
        """
        Calculate the optimum travel speed.

        Balances fuel efficiency with travel time,
        accepting up to 10% higher fuel consumption for faster speed.
        """
        if self.fuel_consumption[9] == 0:
            return 10

        mpg = 9.0 / float(self.fuel_consumption[9])
        for i in range(8, -1, -1):
            if self.fuel_consumption[i] == 0:
                continue
            current_mpg = float(i) / float(self.fuel_consumption[i])
            if current_mpg > mpg * 1.1:
                mpg = current_mpg
            else:
                return i + 1
        return 1

    @property
    def most_fuel_efficient_speed(self) -> int:
        """
        Get the most fuel-efficient speed regardless of travel time.

        Calculates distance per fuel unit at each speed.
        """
        if self.fuel_consumption[9] == 0:
            return 10

        # MPG = distance / fuel = speed^2 / consumption
        mpg = 81.0 / float(self.fuel_consumption[9])  # 9^2 = 81
        for i in range(8, -1, -1):
            if self.fuel_consumption[i] == 0:
                continue
            current_mpg = float(i * i) / float(self.fuel_consumption[i])
            if current_mpg > mpg:
                mpg = current_mpg
            else:
                return i + 2
        return 1

    def get_fuel_consumption(self, warp: int) -> int:
        """
        Get fuel consumption at a given warp speed.

        Args:
            warp: Warp speed (1-10)

        Returns:
            Fuel consumption rate (per 100mg at that speed)
        """
        if warp < 1 or warp > 10:
            return 0
        return self.fuel_consumption[warp - 1]

    def clone(self) -> 'Engine':
        """Create a copy of this engine."""
        return Engine(
            fuel_consumption=list(self.fuel_consumption),
            ram_scoop=self.ram_scoop,
            fastest_safe_speed=self.fastest_safe_speed,
            optimal_speed=self.optimal_speed
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "fuel_consumption": list(self.fuel_consumption),
            "ram_scoop": self.ram_scoop,
            "fastest_safe_speed": self.fastest_safe_speed,
            "optimal_speed": self.optimal_speed
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Engine':
        """Deserialize from dictionary."""
        return cls(
            fuel_consumption=list(data.get("fuel_consumption", [0] * 10)),
            ram_scoop=data.get("ram_scoop", False),
            fastest_safe_speed=data.get("fastest_safe_speed", 0),
            optimal_speed=data.get("optimal_speed", 0)
        )

    # Operator overloads - engines don't add or scale in Stars!
    def add(self, other: 'Engine'):
        """Engines don't add - no-op."""
        pass

    def scale(self, scalar: int):
        """Engines don't scale - no-op."""
        pass
