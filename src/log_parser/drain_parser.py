from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence


_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HEX_PATTERN = re.compile(r"\b[a-fA-F0-9]{8,}\b")
_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_WS_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class ParsedEvent:
    raw: str
    template: str
    event_id: str


class DrainParser:
    """
    Lightweight Drain-style parser:
    - Normalizes variable tokens (IP, ids, numbers) to <*>.
    - Maps stable templates to event IDs (E1, E2, ...).
    """

    def __init__(self) -> None:
        self._template_to_id: Dict[str, str] = {}
        self._next_event_number = 1

    def parse(self, logs: Sequence[str]) -> List[ParsedEvent]:
        parsed: List[ParsedEvent] = []
        for line in logs:
            raw = str(line).strip()
            if not raw:
                continue
            template = self._to_template(raw)
            event_id = self._get_event_id(template)
            parsed.append(ParsedEvent(raw=raw, template=template, event_id=event_id))
        return parsed

    def _to_template(self, line: str) -> str:
        text = line.lower()
        text = _UUID_PATTERN.sub("<*>", text)
        text = _IPV4_PATTERN.sub("<*>", text)
        text = _HEX_PATTERN.sub("<*>", text)
        text = _NUMBER_PATTERN.sub("<*>", text)
        text = _WS_PATTERN.sub(" ", text).strip()
        return text

    def _get_event_id(self, template: str) -> str:
        if template not in self._template_to_id:
            self._template_to_id[template] = f"E{self._next_event_number}"
            self._next_event_number += 1
        return self._template_to_id[template]

