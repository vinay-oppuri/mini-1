from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from agents.analysis_agent import AnalysisAgent
from agents.llm_explanation_agent import LLMExplanationAgent
from agents.log_agent import LogAgent
from agents.policy_agent import PolicyAgent
from agents.response_agent import ResponseAgent


class SecurityCoordinator:
    """
    New architecture flow:
    LogAgent -> AnalysisAgent -> LLMExplanationAgent -> PolicyAgent -> ResponseAgent
    """

    def __init__(self) -> None:
        self.log_agent = LogAgent()
        self.analysis_agent = AnalysisAgent()
        self.llm_agent = LLMExplanationAgent()
        self.policy_agent = PolicyAgent()
        self.response_agent = ResponseAgent()

    def process(
        self,
        logs: Sequence[str | Dict[str, Any]],
        source: str = "cloud-workload",
        cloud_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = self.log_agent.collect(logs=logs, source=source, cloud_metrics=cloud_metrics)
        context = self.analysis_agent.analyze(context)
        context = self.llm_agent.explain(context)
        context = self.policy_agent.decide(context)
        context = self.response_agent.respond(context)
        return context


class Coordinator:
    """
    Backward compatible wrapper:
    - If `agents` provided, uses legacy dispatch mode.
    - Otherwise uses the new security coordinator flow.
    """

    def __init__(self, agents: Optional[List[Any]] = None):
        self.agents = agents
        self._security = None if agents else SecurityCoordinator()

    def run(
        self,
        logs: Sequence[str | Dict[str, Any]],
        source: str = "cloud-workload",
        cloud_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._security is None:
            raise RuntimeError("run() is only available in architecture mode (without custom agents).")
        return self._security.process(logs=logs, source=source, cloud_metrics=cloud_metrics)

    def dispatch(self, initial_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Legacy mode
        if self.agents is not None:
            event_queue = [initial_event]
            processed_events: List[Dict[str, Any]] = []
            max_iterations = 10
            iterations = 0

            while event_queue and iterations < max_iterations:
                current_event = event_queue.pop(0)
                iterations += 1
                for agent in self.agents:
                    if not hasattr(agent, "can_handle") or not hasattr(agent, "handle"):
                        continue
                    try:
                        if agent.can_handle(current_event):
                            result = agent.handle(current_event)
                            if result:
                                event_queue.append(result)
                                processed_events.append(result)
                    except Exception as exc:
                        processed_events.append(
                            {
                                "type": "agent_error",
                                "source_agent": getattr(agent, "name", "unknown"),
                                "error": str(exc),
                                "original_event": current_event,
                            }
                        )
            return processed_events

        # New architecture mode (event wrapper)
        logs = initial_event.get("logs")
        if not logs:
            raise ValueError("Expected 'logs' in event for architecture mode.")
        source = str(initial_event.get("source", "cloud-workload"))
        cloud_metrics = initial_event.get("cloud_metrics")
        result = self.run(logs=logs, source=source, cloud_metrics=cloud_metrics)
        return [result]

