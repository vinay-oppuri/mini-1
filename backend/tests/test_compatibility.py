from __future__ import annotations

from app.core.compatibility import build_compatibility_report


def test_compatibility_report_supported() -> None:
    parsed_events = [
        {"event_id": "E1"},
        {"event_id": "E2"},
        {"event_id": "E1"},
    ]
    report = build_compatibility_report(parsed_events, {"E1", "E2", "E3"}, 0.3)
    assert report["is_supported"] is True
    assert report["unknown_event_ratio"] == 0.0


def test_compatibility_report_unsupported() -> None:
    parsed_events = [{"event_id": "E100"} for _ in range(8)] + [{"event_id": "E1"} for _ in range(2)]
    report = build_compatibility_report(parsed_events, {"E1", "E2", "E3"}, 0.3)
    assert report["is_supported"] is False
    assert report["unknown_event_ratio"] > 0.3
