from __future__ import annotations

import re
from typing import Any, Dict, List


class ResponseAgent:
    """
    Executes response planning from policy decisions.
    """

    def respond(self, context: Dict[str, Any]) -> Dict[str, Any]:
        policy = context.get("policy", {})
        metrics = context.get("cloud_metrics", {})
        logs = context.get("raw_logs", [])

        actions = policy.get("allowed_actions", [])
        service = str(metrics.get("service", "unknown-service"))
        suspect_ip = self._extract_ip(logs)

        human_actions: List[str] = []
        for action in actions:
            if action == "send_alert":
                human_actions.append("Alert sent to admin and SOC channel.")
            elif action == "block_ip":
                if suspect_ip:
                    human_actions.append(f"IP {suspect_ip} blocked for 10 minutes.")
                else:
                    human_actions.append("Top offending source IP blocked for 10 minutes.")
            elif action == "enable_rate_limiting":
                human_actions.append(f"Rate limiting enabled for service {service}.")
            elif action == "restart_container":
                human_actions.append(f"Restart request issued for impacted {service} container.")
            elif action == "enforce_mfa":
                human_actions.append("MFA enforcement enabled for targeted account cohort.")
            elif action == "isolate_workload":
                human_actions.append(f"Workload isolation initiated for {service}.")
            elif action == "revoke_sessions":
                human_actions.append("Active sessions revoked for suspected principals.")
            elif action == "tighten_firewall":
                human_actions.append("Firewall rules tightened to drop scanner traffic.")
            elif action == "monitor":
                human_actions.append("No immediate containment. Enhanced monitoring enabled.")

        context["response"] = {
            "actions": human_actions,
            "raw_actions": actions,
        }
        return context

    def _extract_ip(self, logs: List[str]) -> str | None:
        ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        for log in logs:
            match = ip_pattern.search(log)
            if match:
                return match.group(0)
        return None

