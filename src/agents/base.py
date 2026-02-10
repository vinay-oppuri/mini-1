from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):

    def __init__(self, name: str):
        self.name = name
        self.state: Dict[str, Any] = {}

    @abstractmethod
    def can_handle(self, event: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def handle(self, event: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def update_state(self, key: str, value: Any):
        self.state[key] = value