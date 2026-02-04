from agents.base import BaseAgent
from llm.gemini import GeminiClient

class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="analyst")
        self.llm = GeminiClient()

    def can_handle(self, event):
        return event.get("type") == "anomaly_detected"

    def handle(self, event):
        prompt = f"""
            You are a cybersecurity analyst.

            Anomaly Event:
            {event}

            Tasks:
            1. Explain what might be happening
            2. Assess severity (low / medium / high)
            3. Suggest next investigation step
        """

        analysis = self.llm.generate(prompt)

        return {
            "type" : "analysis_report",
            "source_agent" : self.name,
            "original_event" : event,
            "analysis" : analysis
        }