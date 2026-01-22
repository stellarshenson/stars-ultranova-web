"""
Stars Nova Web - Turn Step Interface
Ported from ServerState/TurnSteps/ITurnStep.cs

Defines the API for any TurnStep used by the TurnGenerator.
"""

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..server_data import ServerData
    from ...core.commands.base import Message


class ITurnStep(ABC):
    """
    Interface for turn processing steps.

    Each turn step performs a specific phase of turn processing
    and returns any messages generated during that phase.

    Ported from ITurnStep.cs.
    """

    @abstractmethod
    def process(self, server_state: 'ServerData') -> List['Message']:
        """
        Execute this turn step.

        Args:
            server_state: The current game state.

        Returns:
            List of messages generated during this step.
        """
        pass
