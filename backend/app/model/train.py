"""
train.py
========
Train the Transformer model on HDFS cloud cluster logs.

DATASET:
  Download HDFS_v1.zip from: https://zenodo.org/records/8196385
  Extract → preprocessed/ folder → copy to same folder as this script:
    Event_traces.csv     (122 MB)
    anomaly_label.csv    (18 MB)

RUN:
  python train.py

OUTPUT:
  model.pt                 ← trained model weights + metadata
  training_curves.png      ← loss and F1 plots

Expected results on RTX 4060 (~15 minutes):
  F1  > 0.97
  AUC > 0.99
"""

import os
import json
import time
import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (f1_score, roc_auc_score, classification_report,
                              confusion_matrix, precision_recall_curve)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.parser.hdfs_parser import parse_hdfs
from app.utils.dataset_builder import build_arrays, make_dataloaders
from app.model.transformer_model import AnomalyTransformer, count_parameters


# ══════════════════════════════════════════════════════════════════
#  CONFIG — change settings here
# ══════════════════════════════════════════════════════════════════

CONFIG = {
    # Data files (place in same folder as this script)
    "traces_csv"    : "data/raw_logs/hdfs/Event_traces.csv",
    "label_csv"     : "data/raw_logs/hdfs/anomaly_label.csv",
    "cache_file"    : "data/raw_logs/hdfs/hdfs_cache.json",
    "save_model"    : "model/model.pt",
    "plot_file"     : "model/training_curves.png",
    "force_reparse" : False,   # True = reload CSV even if cache exists

    # Sequence
    "max_seq_len"   : 100,
    "min_seq_len"   : 20,

    # Model (tuned for RTX 4060 8GB)
    "d_model"       : 128,   # embedding dimension
    "nhead"         : 8,     # attention heads (d_model / nhead must be int)
    "num_layers"    : 4,     # transformer encoder depth
    "dropout"       : 0.1,

    # Training
    "batch_size"    : 256,
    "num_epochs"    : 30,
    "learning_rate" : 1e-3,
    "weight_decay"  : 1e-4,
    "grad_clip"     : 1.0,
    "val_size"      : 0.10,
    "test_size"     : 0.10,
    "random_seed"   : 42,
}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if DEVICE.type == "cuda":
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")


# ══════════════════════════════════════════════════════════════════
#  TRAINING FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def train_one_epoch(model, loader, optimizer, scheduler, criterion):
    """One pass over all training batches. Returns average loss."""
    model.train()
    total_loss, n = 0.0, 0
    for X, y in loader:
        X, y  = X.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
        loss  = criterion(model(X), y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), CONFIG["grad_clip"])
        optimizer.step()
        scheduler.step()   # OneCycleLR steps every batch
        total_loss += loss.item() * len(y)
        n          += len(y)
    return total_loss / n


@torch.no_grad()
def evaluate(model, loader, criterion):
    """Evaluate on val or test set. Returns loss, true labels, probabilities."""
    model.eval()
    total_loss, n = 0.0, 0
    all_labels, all_probs = [], []
    for X, y in loader:
        X, y   = X.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
        logits = model(X)
        total_loss += criterion(logits, y).item() * len(y)
        n          += len(y)
        all_labels.extend(y.cpu().numpy())
        all_probs.extend(torch.sigmoid(logits).cpu().numpy())
    return total_loss/n, np.array(all_labels), np.array(all_probs)


def find_best_threshold(y_true, y_probs):
    """
    Find probability threshold that maximises F1 on validation set.
    Better than always using 0.5 — especially for imbalanced data.
    HDFS is ~98% normal, so 0.5 often misses many anomalies.
    """
    precision, recall, thresholds = precision_recall_curve(y_true, y_probs)
    f1_scores = np.where(
        (precision + recall) == 0, 0,
        2 * precision * recall / (precision + recall)
    )
    idx = int(np.argmax(f1_scores))
    thr = float(thresholds[idx]) if idx < len(thresholds) else 0.5
    return thr, float(f1_scores[idx])


def print_test_results(y_true, y_probs, threshold):
    """Print full classification report on test set."""
    y_pred = (y_probs >= threshold).astype(int)
    print(f"\n{'═'*58}")
    print(f"  TEST RESULTS  (threshold = {threshold:.4f})")
    print(f"{'═'*58}")
    print(classification_report(y_true, y_pred,
                                target_names=["Normal", "Anomaly"], digits=4))
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    f1  = f1_score(y_true, y_pred, zero_division=0)
    auc = roc_auc_score(y_true, y_probs)
    print(f"  F1 Score  : {f1:.4f}   (1.0 = perfect)")
    print(f"  AUC-ROC   : {auc:.4f}   (1.0 = perfect, 0.5 = random)")
    print(f"\n  Anomalies caught  : {tp} / {tp+fn}  "
          f"({100*tp/(tp+fn+1e-9):.1f}%)")
    print(f"  False alarms      : {fp}")
    print(f"  Missed anomalies  : {fn}  ← minimize this")
    return {"f1": f1, "auc": auc, "threshold": threshold,
            "tp": int(tp), "fp": int(fp), "fn": int(fn)}


def save_plots(train_losses, val_losses, val_f1s, path):
    """Save training curves to PNG."""
    ep = range(1, len(train_losses) + 1)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4))

    a1.plot(ep, train_losses, label="Train", marker="o", markersize=3)
    a1.plot(ep, val_losses,   label="Val",   marker="s", markersize=3)
    a1.set_xlabel("Epoch"); a1.set_ylabel("Loss")
    a1.set_title("Training & Validation Loss")
    a1.legend(); a1.grid(alpha=0.3)

    a2.plot(ep, val_f1s, color="green", marker="^", markersize=3)
    a2.set_xlabel("Epoch"); a2.set_ylabel("F1 Score")
    a2.set_title("Validation F1 Score")
    a2.set_ylim(0, 1); a2.grid(alpha=0.3)

    plt.suptitle("Cloud Workload Log Anomaly Detection — Training (HDFS)")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Plot saved → {path}")


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print("\n" + "═"*58)
    print("  Cloud Workload Log Anomaly Detection — Training")
    print("  Dataset : HDFS (203-node cloud cluster, LogHub)")
    print("  Model   : Transformer Encoder (binary classifier)")
    print("═"*58)
    print(f"\n  Device : {DEVICE}")
    if DEVICE.type == "cuda":
        print(f"  GPU    : {torch.cuda.get_device_name(0)}")
        print(f"  VRAM   : "
              f"{torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")

    # ── 1. Parse HDFS logs ─────────────────────────────────────────
    print("\n[1/6] Loading HDFS preprocessed sequences...")
    sequences, labels, template_map = parse_hdfs(
        traces_path = CONFIG["traces_csv"],
        label_path  = CONFIG["label_csv"],
        cache_path  = CONFIG["cache_file"],
        force       = CONFIG["force_reparse"],
        min_seq_len = CONFIG["min_seq_len"],
    )
    vocab_size = len(template_map)

    # ── 2. Build arrays ────────────────────────────────────────────
    print("\n[2/6] Building padded arrays...")
    X, y = build_arrays(sequences, labels, CONFIG["max_seq_len"])

    # ── 3. DataLoaders ─────────────────────────────────────────────
    print("\n[3/6] Creating DataLoaders...")
    tr_loader, va_loader, te_loader, pos_weight = make_dataloaders(
        X, y,
        batch_size = CONFIG["batch_size"],
        val_size   = CONFIG["val_size"],
        test_size  = CONFIG["test_size"],
        seed       = CONFIG["random_seed"],
    )

    # ── 4. Build model ─────────────────────────────────────────────
    print("\n[4/6] Building Transformer model...")
    model = AnomalyTransformer(
        vocab_size  = vocab_size,
        d_model     = CONFIG["d_model"],
        nhead       = CONFIG["nhead"],
        num_layers  = CONFIG["num_layers"],
        max_seq_len = CONFIG["max_seq_len"],
        dropout     = CONFIG["dropout"],
    ).to(DEVICE)
    count_parameters(model)

    # ── 5. Loss + Optimizer + Scheduler ───────────────────────────
    # BCEWithLogitsLoss: binary cross entropy with sigmoid built in
    # pos_weight: penalises missing anomalies more than false alarms
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(DEVICE))

    # AdamW: Adam with weight decay — better generalisation
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=CONFIG["learning_rate"],
        weight_decay=CONFIG["weight_decay"],
    )

    # OneCycleLR: warmup for 10% of training → cosine decay
    # Fastest convergence for Transformer training
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr          = CONFIG["learning_rate"],
        steps_per_epoch = len(tr_loader),
        epochs          = CONFIG["num_epochs"],
        pct_start       = 0.1,
        anneal_strategy = "cos",
    )

    # ── 6. Training loop ───────────────────────────────────────────
    print(f"\n[5/6] Training {CONFIG['num_epochs']} epochs...")
    print("─"*58)

    best_val_loss = float("inf")
    train_losses, val_losses, val_f1s = [], [], []
    t0 = time.time()

    for epoch in range(1, CONFIG["num_epochs"] + 1):
        tr = train_one_epoch(model, tr_loader, optimizer, scheduler, criterion)
        vl, vy, vp = evaluate(model, va_loader, criterion)
        vf = f1_score(vy, (vp >= 0.5).astype(int), zero_division=0)

        train_losses.append(tr)
        val_losses.append(vl)
        val_f1s.append(vf)

        print(f"  Epoch {epoch:2d}/{CONFIG['num_epochs']} | "
              f"Train: {tr:.4f} | Val: {vl:.4f} | "
              f"F1: {vf:.4f} | "
              f"LR: {optimizer.param_groups[0]['lr']:.2e}")

        # Save best model (lowest validation loss)
        if vl < best_val_loss:
            best_val_loss = vl
            torch.save({
                "model_state" : model.state_dict(),
                "epoch"       : epoch,
                "vocab_size"  : vocab_size,
                "template_map": template_map,
                "config"      : CONFIG,
            }, CONFIG["save_model"])
            print(f"    ✓ Best model saved")

    elapsed = time.time() - t0
    print(f"\n  Training complete in {elapsed/60:.1f} minutes")

    # ── Find best threshold on validation set ─────────────────────
    print("\n[6/6] Finding optimal threshold + final evaluation...")
    ckpt = torch.load(CONFIG["save_model"], map_location=DEVICE,
                      weights_only=False)
    model.load_state_dict(ckpt["model_state"])

    _, vy, vp       = evaluate(model, va_loader, criterion)
    threshold, vf1  = find_best_threshold(vy, vp)
    print(f"  Optimal threshold : {threshold:.4f}  (val F1={vf1:.4f})")

    # Save threshold into checkpoint
    ckpt["threshold"] = threshold
    torch.save(ckpt, CONFIG["save_model"])

    # ── Final test evaluation ──────────────────────────────────────
    _, ty, tp = evaluate(model, te_loader, criterion)
    results   = print_test_results(ty, tp, threshold)

    # ── Save plots + metadata ──────────────────────────────────────
    save_plots(train_losses, val_losses, val_f1s, CONFIG["plot_file"])

    meta = {
        "vocab_size"   : vocab_size,
        "threshold"    : threshold,
        "model_config" : {k: CONFIG[k] for k in
                          ["d_model","nhead","num_layers","max_seq_len","dropout"]},
        "test_metrics" : results,
        "dataset"      : "HDFS (LogHub) — 203-node cloud cluster logs",
        "model"        : "Transformer Encoder binary classifier",
    }
    with open("model/model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n  ✓ Model saved    → {CONFIG['save_model']}")
    print(f"  ✓ Metadata saved → model/model_metadata.json")
    print(f"  ✓ Plot saved     → {CONFIG['plot_file']}")
    print(f"\n  Next: python predict.py")


if __name__ == "__main__":
    main()
