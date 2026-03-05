from inference.inference_pipeline import InferencePipeline
from log_parser.drain_parser import DrainParser


class AnalysisAgent:
    def __init__(self):
        self.parser = DrainParser()
        self.pipeline = InferencePipeline()

    def analyze(self, context):
        logs = context["raw_logs"]

        # parse logs into templates
        parsed_events = self.parser.parse(logs)

        templates = []
        event_ids = []
        for event in parsed_events:
            templates.append(event["template"])
            event_ids.append(event["event_id"])

        # ML model score
        result = self.pipeline.score(templates)
        model_score = result.anomaly_score

        # simple rule-based score
        heuristic_score = self.simple_score(templates)

        # keep the higher score
        final_score = max(model_score, heuristic_score)
        if final_score < 0:
            final_score = 0.0
        if final_score > 1:
            final_score = 1.0

        is_anomaly = final_score >= 0.8

        context["parsed_events"] = parsed_events
        context["event_sequence"] = event_ids
        context["templates"] = templates
        context["analysis"] = {
            "anomaly_score": final_score,
            "is_anomaly": is_anomaly,
            "model_score": model_score,
            "heuristic_score": heuristic_score,
            "threshold": result.threshold,
            "raw_max_error": result.raw_max_error,
            "window_size": result.window_size,
            "padding_applied": result.padding_applied,
            "event_scores": result.event_scores,
        }

        return context

    def simple_score(self, templates):
        score = 0.0
        text = " ".join(templates).lower()

        if "failed" in text:
            score += 0.3

        if "too many requests" in text:
            score += 0.5

        if "port scan" in text:
            score += 0.4

        if "outbound" in text or "exfil" in text:
            score += 0.5

        return min(score, 1.0)
