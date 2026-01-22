"""
Stars Nova Web - Abstract AI Base Class
Ported from Nova/Ai/AbstractAI.cs

Base class for all AI implementations.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..core.data_structures.empire_data import EmpireData
    from ..core.commands.base import Command


class AbstractAI(ABC):
    """
    Abstract base class for AI implementations.

    Provides the interface that all AI implementations must follow.
    The AI generates commands that are applied to the empire state
    during turn processing.

    Ported from AbstractAI.cs.
    """

    def __init__(self):
        """Initialize the AI."""
        self.race_name: str = ""
        self.turn_number: int = -1
        self.empire_data: 'EmpireData' = None
        self.commands: List['Command'] = []

    def initialize(self, empire_data: 'EmpireData'):
        """
        Initialize the AI with empire data.

        Called once when the AI is first created or loaded.

        Args:
            empire_data: The empire data for the AI player

        Ported from AbstractAI.cs Initialize().
        """
        self.empire_data = empire_data
        if empire_data.race:
            self.race_name = empire_data.race.name
        self.turn_number = empire_data.turn_year
        self.commands = []

    @abstractmethod
    def do_move(self) -> List['Command']:
        """
        Generate commands for this turn.

        The main entry point for AI turn processing. Analyzes the
        current game state and generates appropriate commands for
        production, fleet movement, research, etc.

        Returns:
            List of commands to execute

        Ported from AbstractAI.cs DoMove().
        """
        pass

    def add_command(self, command: 'Command'):
        """
        Add a command to the pending commands list.

        Args:
            command: Command to add
        """
        self.commands.append(command)
