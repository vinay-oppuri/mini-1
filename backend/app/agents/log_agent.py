from __future__ import annotations

import re
from collections import Counter
from typing import Any


class LogMonitoringAgent:
    """Collects logs and computes basic workload metrics."""

    def collect(self, logs: list[Any], source: str = "cloud-workload") -> dict[str, Any]:
        normalized_logs: list[str] = []
        services: list[str] = []

        for entry in logs:
            if isinstance(entry, str):
                text = entry.strip()
                if text:
                    normalized_logs.append(text)
                continue

            if isinstance(entry, dict):
                level = str(entry.get("level", "")).strip()
                service = str(entry.get("service", "")).strip()
                message = str(entry.get("message", "")).strip()
                timestamp = str(entry.get("timestamp", "")).strip()

                if service:
                    services.append(service)

                pieces = [part for part in [timestamp, level, service, message] if part]
                text = " | ".join(pieces)
                if text:
                    normalized_logs.append(text)

        service_counts = Counter(services)
        total_logs = len(normalized_logs)
        failed_logs = sum(
            1
            for log in normalized_logs
            if any(token in log.lower() for token in ["error", "failed", "timeout", "exception"])
        )
        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", " ".join(normalized_logs))

        metrics = {
            "total_logs": total_logs,
            "failed_logs": failed_logs,
            "error_rate": (failed_logs / total_logs) if total_logs else 0.0,
            "unique_source_ips": len(set(ips)),
            "top_service": service_counts.most_common(1)[0][0] if service_counts else "unknown",
            "service_distribution": dict(service_counts),
        }

        return {
            "source": source,
            "raw_logs": normalized_logs,
            "cloud_metrics": metrics,
        }

