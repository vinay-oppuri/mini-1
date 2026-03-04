from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Optional, Sequence


_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class LogAgent:
    """
    Collects cloud logs and basic operational metrics used by downstream agents.
    """

    def collect(
        self,
        logs: Sequence[str | Dict[str, Any]],
        source: str = "cloud-workload",
        cloud_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_logs = []
        for log in logs:
            text = self._to_text_line(log)
            if text:
                normalized_logs.append(text)
        metrics = self._build_metrics(logs, normalized_logs)
        if cloud_metrics:
            metrics.update(cloud_metrics)

        return {
            "source": source,
            "raw_logs": normalized_logs,
            "cloud_metrics": metrics,
        }

    def _to_text_line(self, log: str | Dict[str, Any]) -> str:
        if isinstance(log, str):
            return log.strip()

        timestamp = str(log.get("timestamp", "")).strip()
        level = str(log.get("level", "")).strip().upper()
        service = str(log.get("service", "")).strip()
        message = str(log.get("message", "")).strip()

        if service and message:
            prefix = f"{level} " if level else ""
            return f"{prefix}{service}: {message}".strip()

        event_type = str(log.get("event_type", "")).strip().lower()
        resource = str(log.get("resource", "")).strip().lower()
        user = str(log.get("user", "")).strip().lower()
        ip = str(log.get("ip", "")).strip()
        status = str(log.get("status", "")).strip().lower()

        if not any([event_type, resource, user, ip, status]):
            return ""

        service_name = resource or "unknown-service"
        action = event_type or "event"
        user_part = f"user={user}" if user else ""
        ip_part = f"ip={ip}" if ip else ""
        status_part = status if status else "unknown"
        core = f"{status_part} {service_name}: {action} {user_part} {ip_part}".strip()
        if timestamp:
            return f"{timestamp} {core}".strip()
        return core

    def _build_metrics(
        self,
        original_logs: Sequence[str | Dict[str, Any]],
        normalized_logs: Sequence[str],
    ) -> Dict[str, Any]:
        total = len(normalized_logs)
        failed = sum(
            1
            for line in normalized_logs
            if any(token in line.lower() for token in ["failed", "error", "timeout", "denied"])
        )
        ips = _IP_PATTERN.findall("\n".join(normalized_logs))

        services = []
        timestamps = []
        for raw in original_logs:
            if isinstance(raw, dict):
                service = str(raw.get("service") or raw.get("resource") or "").strip()
                if service:
                    services.append(service)
                ts = str(raw.get("timestamp", "")).strip()
                parsed = self._parse_ts(ts)
                if parsed:
                    timestamps.append(parsed)

        request_rate_per_sec = 0.0
        if len(timestamps) >= 2:
            start = min(timestamps)
            end = max(timestamps)
            duration = max((end - start).total_seconds(), 1.0)
            request_rate_per_sec = total / duration

        top_service = Counter(services).most_common(1)
        service = top_service[0][0] if top_service else "unknown"

        return {
            "service": service,
            "total_logs": total,
            "failed_logs": failed,
            "error_rate": round((failed / total), 4) if total else 0.0,
            "unique_source_ips": len(set(ips)),
            "request_rate_per_sec": round(request_rate_per_sec, 2),
        }

    def _parse_ts(self, value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
