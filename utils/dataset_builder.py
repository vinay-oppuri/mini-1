"""
dataset_builder.py
==================
Builds PyTorch DataLoaders from parsed HDFS sequences.

Steps:
  1. Pad/truncate all sequences to fixed length
  2. Split into train / val / test  (stratified)
  3. Wrap in PyTorch DataLoaders
  4. Compute pos_weight for class imbalance

Padding convention:
  All event IDs shifted +1 so that 0 is free for the PAD token.
    E0 → stored as 1,  E1 → 2,  E27 → 28
  Short sequences padded with 0s on the right.
  Long sequences truncated to max_seq_len from the start.

Imported by: train.py
"""

import platform
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split


def build_arrays(sequences, labels, max_seq_len):
    """
    Pad/truncate sequences → numpy arrays ready for PyTorch.

    Returns:
        X : ndarray (N, max_seq_len)  int64
        y : ndarray (N,)              float32
    """
    X, y = [], []
    for seq, lbl in zip(sequences, labels):
        s = [e + 1 for e in seq]                      # shift +1
        if len(s) >= max_seq_len:
            s = s[:max_seq_len]                        # truncate
        else:
            s = s + [0] * (max_seq_len - len(s))      # pad
        X.append(s)
        y.append(lbl)

    X = np.array(X, dtype=np.int64)
    y = np.array(y, dtype=np.float32)
    n = len(y); na = int(y.sum())
    print(f"\n[Dataset] {n:,} total | {na:,} anomaly "
          f"({100*na/n:.1f}%) | {n-na:,} normal | seq_len={max_seq_len}")
    return X, y


class LogDataset(Dataset):
    """PyTorch Dataset wrapping event sequences and labels."""
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.long)
        self.y = torch.tensor(y, dtype=torch.float32)
    def __len__(self):
        return len(self.X)
    def __getitem__(self, i):
        return self.X[i], self.y[i]


def make_dataloaders(X, y, batch_size=256, val_size=0.10,
                     test_size=0.10, seed=42):
    """
    Split data and create DataLoaders.

    Split (stratified — same anomaly ratio in each split):
      80% Train  → model learns here
      10% Val    → monitor loss/F1, tune threshold
      10% Test   → final honest evaluation

    Returns:
        train_loader, val_loader, test_loader, pos_weight
    """
    # Split
    X_tv, X_te, y_tv, y_te = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y)
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_tv, y_tv, test_size=val_size/(1-test_size),
        random_state=seed, stratify=y_tv)

    print(f"[DataLoaders] Train:{len(X_tr):,} | "
          f"Val:{len(X_va):,} | Test:{len(X_te):,}")

    # Windows needs num_workers=0
    use_pin   = torch.cuda.is_available()
    n_workers = 0 if platform.system() == "Windows" else 4

    def _loader(X, y, shuffle):
        return DataLoader(LogDataset(X, y), batch_size=batch_size,
                          shuffle=shuffle, num_workers=n_workers,
                          pin_memory=use_pin)

    train_loader = _loader(X_tr, y_tr, True)
    val_loader   = _loader(X_va, y_va, False)
    test_loader  = _loader(X_te, y_te, False)

    # pos_weight = (#normal) / (#anomaly) in training set
    # BCEWithLogitsLoss uses this to penalise missing anomalies more
    n_norm = float((y_tr == 0).sum())
    n_anom = float((y_tr == 1).sum())
    if n_anom == 0:
        raise ValueError("No anomaly samples found in training set!")
    pos_weight = torch.tensor([n_norm / n_anom], dtype=torch.float32)
    print(f"  pos_weight = {pos_weight.item():.2f}  "
          f"(missing one anomaly costs {pos_weight.item():.1f}x more)")

    return train_loader, val_loader, test_loader, pos_weight
