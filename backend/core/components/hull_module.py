"""
Stars Nova Web - Hull Module
Ported from Common/Components/HullModule.cs

Hull modules are the individual slots that make up a hull.
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .component import Component


@dataclass
class HullModule:
    """
    A slot within a hull that can hold components.

    Hull modules define what type of components can be fitted
    and how many can be stacked in the slot.

    Ported from HullModule.cs.
    """
    cell_number: int = -1
    component_maximum: int = 1
    component_type: str = ""
    _component_count: int = field(default=0, repr=False)
    allocated_component: Optional['Component'] = None

    @property
    def component_count(self) -> int:
        """Get the number of components allocated to this module."""
        if self._component_count == 0 and self.allocated_component is None:
            return 0
        elif self._component_count == 0 and self.allocated_component is not None:
            return 0
        else:
            return self._component_count

    @component_count.setter
    def component_count(self, value: int):
        """Set the number of components."""
        self._component_count = value

    def empty(self):
        """Remove all allocated components from this module."""
        self.allocated_component = None
        self._component_count = 0

    def is_empty(self) -> bool:
        """Check if module has no allocated components."""
        return self.allocated_component is None or self._component_count == 0

    def clone(self) -> 'HullModule':
        """Create a copy of this module."""
        return HullModule(
            cell_number=self.cell_number,
            component_maximum=self.component_maximum,
            component_type=self.component_type,
            _component_count=self._component_count,
            allocated_component=self.allocated_component  # Shallow copy intentional
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "cell_number": self.cell_number,
            "component_maximum": self.component_maximum,
            "component_type": self.component_type,
            "component_count": self._component_count
        }
        if self.allocated_component is not None:
            result["allocated_component"] = self.allocated_component.name
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'HullModule':
        """Deserialize from dictionary."""
        module = cls(
            cell_number=data.get("cell_number", -1),
            component_maximum=data.get("component_maximum", 1),
            component_type=data.get("component_type", ""),
            _component_count=data.get("component_count", 0)
        )
        # allocated_component must be resolved separately by caller
        return module
