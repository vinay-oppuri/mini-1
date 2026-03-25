from __future__ import annotations

import hashlib


class SequenceBuilder:
    """Converts parsed events into model-ready integer sequences."""

    def build(
        self,
        parsed_events: list[dict[str, str]],
        vocab_size: int,
        template_map: dict[str, int] | None = None,
        max_seq_len: int = 100,
    ) -> dict[str, list]:
        template_map = template_map or {}

        event_sequence: list[str] = []
        model_sequence: list[int] = []
        template_sequence: list[str] = []

        for event in parsed_events:
            event_id = event["event_id"]
            template = event["template"]

            event_sequence.append(event_id)
            template_sequence.append(template)

            if event_id in template_map:
                idx = int(template_map[event_id])
            else:
                idx = self._stable_hash(template, vocab_size)
            model_sequence.append(idx)

        if len(model_sequence) > max_seq_len:
            model_sequence = model_sequence[-max_seq_len:]
            event_sequence = event_sequence[-max_seq_len:]
            template_sequence = template_sequence[-max_seq_len:]

        return {
            "event_sequence": event_sequence,
            "template_sequence": template_sequence,
            "model_sequence": model_sequence,
        }

    @staticmethod
    def _stable_hash(template: str, vocab_size: int) -> int:
        digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
        return int(digest, 16) % max(vocab_size, 1)

