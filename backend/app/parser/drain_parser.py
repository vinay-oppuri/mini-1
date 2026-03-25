from __future__ import annotations

import re
from typing import Any

try:
    from drain3 import TemplateMiner
    from drain3.template_miner_config import TemplateMinerConfig
except ImportError:  # pragma: no cover - optional dependency
    TemplateMiner = None
    TemplateMinerConfig = None


class DrainParser:
    """
    Parses logs into templates and event IDs using Drain.
    Falls back to regex-based normalization when drain3 is unavailable.
    """

    def __init__(self) -> None:
        self.template_to_event_id: dict[str, str] = {}
        self._next_event_id = 1

        if TemplateMiner is not None and TemplateMinerConfig is not None:
            config = TemplateMinerConfig()
            config.profiling_enabled = False
            self.template_miner: TemplateMiner | None = TemplateMiner(config=config)
        else:
            self.template_miner = None

    def parse(self, logs: list[Any]) -> list[dict[str, str]]:
        parsed: list[dict[str, str]] = []
        for entry in logs:
            raw = self._to_text(entry)
            if not raw:
                continue

            if self.template_miner is not None:
                mined = self.template_miner.add_log_message(raw)
                template = str(mined.get("template_mined", raw)).strip()
                cluster_id = mined.get("cluster_id")
                event_id = f"E{cluster_id}" if cluster_id is not None else self._get_event_id(template)
            else:
                template = self._regex_template(raw)
                event_id = self._get_event_id(template)

            parsed.append(
                {
                    "raw": raw,
                    "template": template,
                    "event_id": event_id,
                }
            )
        return parsed

    @staticmethod
    def _to_text(entry: Any) -> str:
        if isinstance(entry, str):
            return entry.strip()
        if isinstance(entry, dict):
            level = str(entry.get("level", "")).strip()
            service = str(entry.get("service", "")).strip()
            message = str(entry.get("message", "")).strip()
            return " ".join(part for part in [level, service, message] if part).strip()
        return str(entry).strip()

    def _get_event_id(self, template: str) -> str:
        if template not in self.template_to_event_id:
            self.template_to_event_id[template] = f"E{self._next_event_id}"
            self._next_event_id += 1
        return self.template_to_event_id[template]

    @staticmethod
    def _regex_template(text: str) -> str:
        template = text.lower()
        template = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<*>", template)
        template = re.sub(r"\b\d+\b", "<*>", template)
        return template

