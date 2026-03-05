import re


class LogAgent:
    def collect(self, logs, source="cloud-workload", cloud_metrics=None):
        text_logs = []
        services = []

        # convert logs to plain text
        for log in logs:
            if isinstance(log, str):
                text = log.strip()
                if text:
                    text_logs.append(text)
                continue

            service = str(log.get("service", "")).strip()
            message = str(log.get("message", "")).strip()
            level = str(log.get("level", "")).strip()

            if service:
                services.append(service)

            text = f"{level} {service}: {message}".strip()
            if text:
                text_logs.append(text)

        # simple metrics
        total_logs = len(text_logs)
        failed_logs = 0
        for log in text_logs:
            lowered = log.lower()
            if "error" in lowered or "failed" in lowered:
                failed_logs += 1

        ips = re.findall(r"\d+\.\d+\.\d+\.\d+", " ".join(text_logs))
        service = services[0] if services else "unknown"

        metrics = {
            "service": service,
            "total_logs": total_logs,
            "failed_logs": failed_logs,
            "error_rate": (failed_logs / total_logs) if total_logs else 0.0,
            "unique_source_ips": len(set(ips)),
        }

        # optional external metrics override
        if cloud_metrics:
            metrics.update(cloud_metrics)

        return {
            "source": source,
            "raw_logs": text_logs,
            "cloud_metrics": metrics,
        }
