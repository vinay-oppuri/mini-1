"""
transformer_model.py
====================
Transformer model for cloud workload log anomaly detection.

Architecture:
  Input  →  Embedding  →  Positional Encoding
         →  Transformer Encoder (Self-Attention × 4)
         →  Masked Mean Pooling
         →  Classifier
         →  Anomaly Score (0.0 = Normal, 1.0 = Anomaly)

Why Transformer over LSTM:
  - Reads the ENTIRE sequence at once (not step by step)
  - Self-attention: every log event can relate to every other event
    e.g. a write-failure at step 3 correlating with disk-error at step 47
  - Faster on GPU, handles long sequences better

Imported by: train.py, predict.py
"""

import math
import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    """
    Injects position information into embeddings.
    Without this, the model treats [E1,E2,E3] same as [E3,E2,E1].
    Uses sine/cosine waves — from "Attention is All You Need" (2017).
    """
    def __init__(self, d_model, dropout=0.1, max_len=512):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe  = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float()
                        * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x):
        # x: (batch, seq_len, d_model)
        return self.dropout(x + self.pe[:, :x.size(1)])


class AnomalyTransformer(nn.Module):
    """
    Transformer-based binary classifier for log anomaly detection.
    Used for HDFS cloud cluster log sequences.
    """
    def __init__(
        self,
        vocab_size:  int,          # number of unique Drain event templates
        d_model:     int   = 128,  # embedding + attention dimension
        nhead:       int   = 8,    # attention heads (d_model % nhead == 0)
        num_layers:  int   = 4,    # stacked encoder layers
        max_seq_len: int   = 50,   # max sequence length
        dropout:     float = 0.1,  # regularization rate
    ):
        super().__init__()
        assert d_model % nhead == 0, \
            f"d_model ({d_model}) must be divisible by nhead ({nhead})"

        self.d_model = d_model

        # Embedding: integer event ID → dense vector
        # vocab_size+1 because index 0 is reserved for PAD token
        self.embedding = nn.Embedding(vocab_size + 1, d_model, padding_idx=0)

        self.pos_encoding = PositionalEncoding(d_model, dropout,
                                                max_len=max_seq_len + 10)

        # Transformer Encoder: self-attention across all events in sequence
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout, activation="relu",
            batch_first=True,   # (batch, seq, features)
            norm_first=True,    # Pre-LayerNorm: more stable training
        )
        self.transformer = nn.TransformerEncoder(
            enc_layer, num_layers=num_layers,
            enable_nested_tensor=False,
        )

        # Classifier head: d_model → 1 (anomaly logit)
        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
        )

        # Xavier weight init: keeps gradients healthy at start of training
        for name, p in self.named_parameters():
            if "weight" in name and p.dim() > 1:
                nn.init.xavier_uniform_(p)
            elif "bias" in name:
                nn.init.zeros_(p)

    def forward(self, x):
        """
        Args:
            x: LongTensor (batch_size, seq_len) — padded event ID sequences
        Returns:
            logits: FloatTensor (batch_size,) — raw anomaly scores
                    Apply sigmoid to get probabilities.
        """
        pad_mask = (x == 0)                                    # True where PAD

        # Embed and scale (scaling from original Transformer paper)
        emb = self.embedding(x) * math.sqrt(self.d_model)     # (B, L, D)
        emb = self.pos_encoding(emb)                           # (B, L, D)

        # Self-attention: every event attends to every other event
        enc = self.transformer(emb, src_key_padding_mask=pad_mask)  # (B, L, D)

        # Masked mean pool: average over real events only (ignore PAD)
        real  = (~pad_mask).float().unsqueeze(-1)              # (B, L, 1)
        pool  = (enc * real).sum(1) / real.sum(1).clamp(min=1) # (B, D)

        return self.classifier(pool).squeeze(1)                # (B,)


def count_parameters(model):
    """Print number of trainable parameters."""
    total     = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total params     : {total:,}")
    print(f"  Trainable params : {trainable:,}")
    return trainable


if __name__ == "__main__":
    model = AnomalyTransformer(vocab_size=30, d_model=128, nhead=8,
                                num_layers=4, max_seq_len=50)
    count_parameters(model)
    x = torch.randint(0, 31, (4, 50))
    x[:, 40:] = 0   # last 10 positions are PAD
    out = torch.sigmoid(model(x))
    print(f"Input: {x.shape}  Output: {out.shape}")
    print(f"Scores: {out.tolist()}")
    print("Model works correctly!")
