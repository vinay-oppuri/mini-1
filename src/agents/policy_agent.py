class PolicyAgent:
    def decide(self, context):
        score = context["analysis"]["anomaly_score"]
        attack_type = context["llm_explanation"]["attack_type"]

        actions = []

        # basic decision from score
        if score > 0.9:
            actions.append("send_alert")
            actions.append("block_ip")
        elif score > 0.8:
            actions.append("send_alert")
        else:
            actions.append("monitor")

        # attack-specific actions
        if attack_type == "DDoS" and score > 0.8:
            actions.append("enable_rate_limiting")
            actions.append("restart_container")

        if attack_type == "Brute Force" and score > 0.9:
            actions.append("enforce_mfa")

        if attack_type == "Data Exfiltration" and score > 0.85:
            actions.append("isolate_workload")
            actions.append("revoke_sessions")

        if attack_type == "Port Scan" and score > 0.8:
            actions.append("tighten_firewall")

        # remove duplicates, keep same order
        unique_actions = []
        for action in actions:
            if action not in unique_actions:
                unique_actions.append(action)

        context["policy"] = {
            "severity": self.get_severity(score),
            "allowed_actions": unique_actions,
            "score": score,
            "attack_type": attack_type,
        }

        return context

    def get_severity(self, score):
        if score > 0.9:
            return "critical"
        if score > 0.8:
            return "high"
        if score > 0.6:
            return "medium"
        return "low"
