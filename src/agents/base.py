from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """
    Base class for all agents in the system.
    Agents are event-driven and state-aware.
    """

    def __init__(self, name: str):
        self.name = name
        self.state: Dict[str, Any] = {}

    @abstractmethod
    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Decide whether this agent should handle the event.
        """
        pass

    @abstractmethod
    def handle(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the event and return a result/event.
        """
        pass

    def update_state(self, key: str, value: Any):
        self.state[key] = value
