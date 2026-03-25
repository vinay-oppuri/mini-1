from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional runtime dependency
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False


if TORCH_AVAILABLE:

    class PositionalEncoding(nn.Module):
        def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 512) -> None:
            super().__init__()
            self.dropout = nn.Dropout(p=dropout)

            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
            pe = torch.zeros(max_len, d_model)
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            self.register_buffer("pe", pe.unsqueeze(0))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = x + self.pe[:, : x.size(1)]
            return self.dropout(x)


    class AnomalyTransformer(nn.Module):
        def __init__(
            self,
            vocab_size: int,
            d_model: int = 128,
            nhead: int = 8,
            num_layers: int = 4,
            max_seq_len: int = 100,
            dropout: float = 0.1,
        ) -> None:
            super().__init__()
            if d_model % nhead != 0:
                raise ValueError(f"d_model ({d_model}) must be divisible by nhead ({nhead})")

            self.d_model = d_model
            self.embedding = nn.Embedding(vocab_size + 1, d_model, padding_idx=0)
            self.pos_encoding = PositionalEncoding(d_model, dropout=dropout, max_len=max_seq_len + 10)

            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=d_model * 4,
                dropout=dropout,
                activation="relu",
                batch_first=True,
                norm_first=True,
            )
            self.transformer = nn.TransformerEncoder(
                encoder_layer,
                num_layers=num_layers,
                enable_nested_tensor=False,
            )
            self.classifier = nn.Sequential(
                nn.LayerNorm(d_model),
                nn.Linear(d_model, d_model // 2),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(d_model // 2, 1),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            pad_mask = x == 0
            embedded = self.embedding(x) * math.sqrt(self.d_model)
            embedded = self.pos_encoding(embedded)
            encoded = self.transformer(embedded, src_key_padding_mask=pad_mask)

            real_mask = (~pad_mask).float().unsqueeze(-1)
            pooled = (encoded * real_mask).sum(1) / real_mask.sum(1).clamp(min=1.0)
            return self.classifier(pooled).squeeze(1)


class TransformerAnomalyDetector:
    """Loads transformer weights when torch is available; otherwise uses a heuristic fallback."""

    def __init__(self, model_path: str, metadata_path: str) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)

        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Missing metadata file: {self.metadata_path}")

        with self.metadata_path.open("r", encoding="utf-8") as file:
            metadata = json.load(file)

        self.threshold = float(metadata.get("threshold", 0.8))
        self.vocab_size = int(metadata.get("vocab_size", 512))
        config = metadata.get("model_config", {})
        self.max_seq_len = int(config.get("max_seq_len", 100))
        self.template_map: dict[str, int] = {}

        self.using_fallback = not TORCH_AVAILABLE
        self.model = None
        self.device = None

        if TORCH_AVAILABLE:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Missing model file: {self.model_path}")

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=False)
            self.template_map = checkpoint.get("template_map", {})

            self.model = AnomalyTransformer(
                vocab_size=self.vocab_size,
                d_model=int(config.get("d_model", 128)),
                nhead=int(config.get("nhead", 8)),
                num_layers=int(config.get("num_layers", 4)),
                max_seq_len=self.max_seq_len,
                dropout=float(config.get("dropout", 0.0)),
            ).to(self.device)
            self.model.load_state_dict(checkpoint["model_state"])
            self.model.eval()

    def predict(self, sequence: list[int]) -> dict[str, Any]:
        if self.using_fallback:
            score = self._heuristic_score(sequence)
        else:
            with torch.no_grad():
                tensor = self._to_tensor(sequence)
                score = float(torch.sigmoid(self.model(tensor)).item())

        return {
            "score": score,
            "is_anomaly": score >= self.threshold,
            "threshold": self.threshold,
            "label": "Anomaly" if score >= self.threshold else "Normal",
            "model_mode": "heuristic-fallback" if self.using_fallback else "transformer",
        }

    def _to_tensor(self, sequence: list[int]) -> torch.Tensor:
        shifted = [event + 1 for event in sequence]
        if len(shifted) >= self.max_seq_len:
            shifted = shifted[-self.max_seq_len :]
        else:
            shifted = shifted + [0] * (self.max_seq_len - len(shifted))
        return torch.tensor([shifted], dtype=torch.long, device=self.device)

    @staticmethod
    def _heuristic_score(sequence: list[int]) -> float:
        if not sequence:
            return 0.0
        max_count = max(sequence.count(value) for value in set(sequence))
        repetition_ratio = max_count / len(sequence)
        burst_factor = min(len(sequence) / 25.0, 1.0)
        score = 0.15 + (0.7 * repetition_ratio) + (0.15 * burst_factor)
        return max(0.0, min(score, 0.99))
