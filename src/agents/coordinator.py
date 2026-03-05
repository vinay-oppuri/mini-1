from agents.analysis_agent import AnalysisAgent
from agents.llm_explanation_agent import LLMExplanationAgent
from agents.log_agent import LogAgent
from agents.policy_agent import PolicyAgent
from agents.response_agent import ResponseAgent


class Coordinator:
    def __init__(self):
        self.log_agent = LogAgent()
        self.analysis_agent = AnalysisAgent()
        self.llm_agent = LLMExplanationAgent()
        self.policy_agent = PolicyAgent()
        self.response_agent = ResponseAgent()

    def run(self, logs, source="cloud-workload", cloud_metrics=None):
        # Step 1: collect + normalize logs
        context = self.log_agent.collect(
            logs=logs,
            source=source,
            cloud_metrics=cloud_metrics,
        )

        # Step 2: detect anomaly
        context = self.analysis_agent.analyze(context)

        # Step 3: explain anomaly / attack type
        context = self.llm_agent.explain(context)

        # Step 4: choose policy actions
        context = self.policy_agent.decide(context)

        # Step 5: generate human-readable response
        context = self.response_agent.respond(context)

        return context
