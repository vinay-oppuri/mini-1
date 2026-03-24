from __future__ import annotations

from typing import Any

from agents.analysis_agent import AnalysisAgent
from agents.log_agent import LogMonitoringAgent
from agents.policy_agent import PolicyAgent
from agents.response_agent import ResponseAgent


class CoordinatorAgent:
    """Orchestrates the multi-agent detection and response workflow."""

    def __init__(
        self,
        model_path: str = "model/model.pt",
        metadata_path: str = "model/model_metadata.json",
        parsed_output_path: str = "data/parsed_logs/latest_parsed_logs.json",
    ) -> None:
        self.log_agent = LogMonitoringAgent()
        self.analysis_agent = AnalysisAgent(
            model_path=model_path,
            metadata_path=metadata_path,
            parsed_output_path=parsed_output_path,
        )
        self.policy_agent = PolicyAgent()
        self.response_agent = ResponseAgent()

    def run(self, logs: list[Any], source: str = "cloud-workload") -> dict[str, Any]:
        context = self.log_agent.collect(logs=logs, source=source)
        context = self.analysis_agent.analyze(context)
        context = self.policy_agent.decide(context)
        context = self.response_agent.respond(context)
        context["decision"] = {
            "status": "anomaly-detected" if context["analysis"]["is_anomaly"] else "normal",
            "severity": context["policy"]["severity"],
            "final_action_count": len(context["response"]["actions"]),
        }
        return context

