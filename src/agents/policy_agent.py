from __future__ import annotations

from typing import Any, Dict, List


class PolicyAgent:
    """
    Policy layer:
    - score > 0.9 -> block + alert
    - score > 0.8 -> alert
    """

    def decide(self, context: Dict[str, Any]) -> Dict[str, Any]:
        analysis = context.get("analysis", {})
        llm = context.get("llm_explanation", {})
        score = float(analysis.get("anomaly_score", 0.0))
        attack_type = str(llm.get("attack_type", "Unknown"))

        actions: List[str] = []
        if score > 0.9:
            actions.extend(["send_alert", "block_ip"])
        elif score > 0.8:
            actions.append("send_alert")
        else:
            actions.append("monitor")

        if attack_type == "DDoS" and score > 0.8:
            actions.extend(["enable_rate_limiting", "restart_container"])
        if attack_type == "Brute Force" and score > 0.9:
            actions.append("enforce_mfa")
        if attack_type == "Data Exfiltration" and score > 0.85:
            actions.extend(["isolate_workload", "revoke_sessions"])
        if attack_type == "Port Scan" and score > 0.8:
            actions.append("tighten_firewall")

        # Keep order deterministic while removing duplicates.
        unique_actions = list(dict.fromkeys(actions))

        context["policy"] = {
            "severity": self._severity(score),
            "allowed_actions": unique_actions,
            "score": score,
            "attack_type": attack_type,
        }
        return context

    def _severity(self, score: float) -> str:
        if score > 0.9:
            return "critical"
        if score > 0.8:
            return "high"
        if score > 0.6:
            return "medium"
        return "low"

