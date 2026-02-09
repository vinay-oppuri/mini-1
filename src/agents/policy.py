from agents.base import BaseAgent

class PolicyAgent(BaseAgent):
    def __init__(self, policies):
        super().__init__(name="policy")
        self.policies = policies
    

    def can_handle(self, event):
        return event.get("type") == "analysis_report"

    def handle(self, event):
        severity = event["analysis"].lower()

        allowed_actions = []

        if "high" in severity:
            allowed_actions.append("isolate_resource")
        if "medium" in severity:
            allowed_actions.append("increase_monitoring")

        return {
            "type" : "policy_decision",
            "source_agent" : self.name,
            "allowed_actions" : allowed_actions,
            "original_event" : event
        }