from __future__ import annotations

from typing import Any


def build_compatibility_report(
    parsed_events: list[dict[str, Any]],
    known_event_ids: set[str],
    unknown_ratio_threshold: float = 0.30,
) -> dict[str, Any]:
    total = len(parsed_events)
    if total == 0:
        return {
            "is_supported": False,
            "reason": "No parseable events found.",
            "total_events": 0,
            "known_event_count": 0,
            "unknown_event_count": 0,
            "unknown_event_ratio": 1.0,
            "known_event_ratio": 0.0,
            "unique_event_ids": 0,
            "threshold": unknown_ratio_threshold,
        }

    known = sum(1 for event in parsed_events if event.get("event_id") in known_event_ids)
    unknown = total - known
    unknown_ratio = unknown / total
    supported = unknown_ratio <= unknown_ratio_threshold

    reason = (
        "compatible"
        if supported
        else (
            "unsupported_log_profile: unknown event ratio exceeds threshold. "
            "Calibrate threshold or retrain parser/model on this source."
        )
    )

    return {
        "is_supported": supported,
        "reason": reason,
        "total_events": total,
        "known_event_count": known,
        "unknown_event_count": unknown,
        "unknown_event_ratio": unknown_ratio,
        "known_event_ratio": known / total,
        "unique_event_ids": len({event.get("event_id") for event in parsed_events}),
        "threshold": unknown_ratio_threshold,
    }

