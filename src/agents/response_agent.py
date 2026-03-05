import re


class ResponseAgent:
    def respond(self, context):
        actions = context["policy"]["allowed_actions"]
        logs = context["raw_logs"]
        service = context["cloud_metrics"].get("service", "unknown-service")

        ip = self.find_ip(logs)

        messages = []
        for action in actions:
            if action == "send_alert":
                messages.append("Alert sent to admin and SOC channel.")

            elif action == "block_ip":
                if ip:
                    messages.append(f"IP {ip} blocked for 10 minutes.")
                else:
                    messages.append("Top offending source IP blocked for 10 minutes.")

            elif action == "enable_rate_limiting":
                messages.append(f"Rate limiting enabled for service {service}.")

            elif action == "restart_container":
                messages.append(f"Restart request issued for impacted {service} container.")

            elif action == "enforce_mfa":
                messages.append("MFA enforcement enabled for targeted account cohort.")

            elif action == "isolate_workload":
                messages.append(f"Workload isolation initiated for {service}.")

            elif action == "revoke_sessions":
                messages.append("Active sessions revoked for suspected principals.")

            elif action == "tighten_firewall":
                messages.append("Firewall rules tightened to drop scanner traffic.")

            elif action == "monitor":
                messages.append("No immediate containment. Enhanced monitoring enabled.")

        context["response"] = {
            "actions": messages,
            "raw_actions": actions,
        }

        return context

    def find_ip(self, logs):
        ip_pattern = r"\d+\.\d+\.\d+\.\d+"

        for log in logs:
            match = re.search(ip_pattern, log)
            if match:
                return match.group()

        return None
