from __future__ import annotations

from typing import Any


class ResponseAgent:
    """Simulates response actions selected by the policy layer."""

    ACTION_MESSAGES = {
        "send_alert": "Alert sent to SOC channel and on-call engineer.",
        "block_source": "Temporary source IP block applied for 10 minutes.",
        "monitor": "Enhanced monitoring enabled; no disruptive action taken.",
        "enable_rate_limit": "Traffic rate limiting enabled on the gateway.",
        "enforce_mfa": "MFA challenge enforced for risky authentication flows.",
        "isolate_workload": "Impacted workload moved to isolation namespace.",
        "require_human_approval": "Waiting for human approval before containment action.",
    }

    def respond(self, context: dict[str, Any]) -> dict[str, Any]:
        actions = context["policy"]["allowed_actions"]
        messages = [self.ACTION_MESSAGES[action] for action in actions if action in self.ACTION_MESSAGES]

        context["response"] = {
            "actions": messages,
            "executed_actions": actions,
            "human_in_the_loop": context["policy"]["requires_human_approval"],
        }
        return context

