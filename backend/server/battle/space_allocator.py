"""
Stars Nova Web - Space Allocator
Ported from Common/SpaceAllocator.cs

Allocates battle grid positions for fleets.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Rectangle:
    """Simple rectangle for space allocation."""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class SpaceAllocator:
    """
    Allocates space for fleets on the battle grid.

    Chops up available space into boxes that can be given out one-by-one.
    Ported from SpaceAllocator.cs (117 lines).
    """
    grid_axis_count: int = 1
    grid_size: int = 0
    available_boxes: List[Rectangle] = field(default_factory=list)

    def __init__(self, number_of_items: int):
        """
        Initialize allocator for the given number of items.

        If the number doesn't allow a square grid, it's rounded up.

        Args:
            number_of_items: Number of items to be distributed
        """
        self.grid_axis_count = int(math.sqrt(number_of_items))
        if (self.grid_axis_count * self.grid_axis_count) != number_of_items:
            self.grid_axis_count += 1
        if self.grid_axis_count <= 0:
            self.grid_axis_count = 1
        self.available_boxes = []

    def allocate_space(self, space_size: int) -> None:
        """
        Create boxes for the allocatable space.

        Args:
            space_size: Length of one side of the square space
        """
        self.grid_size = space_size

        if self.grid_axis_count <= 0:
            self.grid_axis_count = 1

        box_side = space_size // self.grid_axis_count

        self.available_boxes = []
        for y in range(self.grid_axis_count):
            current_y = y * box_side
            for x in range(self.grid_axis_count):
                current_x = x * box_side
                box = Rectangle(
                    x=current_x,
                    y=current_y,
                    width=box_side,
                    height=box_side
                )
                self.available_boxes.append(box)

    def get_box(self, box_number: int, number_of_boxes: int) -> Rectangle:
        """
        Return a box position for placing a fleet.

        Uses a circular layout around the edge of the grid.

        Args:
            box_number: Index of the box to get
            number_of_boxes: Total number of boxes needed

        Returns:
            Rectangle with position and direction hints
        """
        boxes_from_start = box_number * 4 * self.grid_size // number_of_boxes

        # Distribute around the perimeter of the grid
        if boxes_from_start < self.grid_size:
            # Top edge, moving down
            return Rectangle(x=0, y=boxes_from_start, width=1, height=1)
        elif boxes_from_start < 2 * self.grid_size:
            # Right edge, moving left
            return Rectangle(
                x=boxes_from_start - self.grid_size,
                y=self.grid_size,
                width=1,
                height=-1
            )
        elif boxes_from_start < 3 * self.grid_size:
            # Bottom edge, moving up
            return Rectangle(
                x=self.grid_size,
                y=3 * self.grid_size - boxes_from_start,
                width=-1,
                height=1
            )
        elif boxes_from_start < 4 * self.grid_size:
            # Left edge, moving right
            return Rectangle(
                x=4 * self.grid_size - boxes_from_start,
                y=self.grid_size,
                width=-1,
                height=-1
            )
        else:
            return Rectangle(x=0, y=0, width=1, height=1)
