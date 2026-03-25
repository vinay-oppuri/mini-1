"""
hdfs_parser.py
==============
Loads preprocessed HDFS dataset — no raw log parsing needed.

DATASET DOWNLOAD:
  URL  : https://zenodo.org/records/8196385
  File : HDFS_v1.zip  (186 MB)
  Extract → open the 'preprocessed' subfolder → copy these 2 files:
    Event_traces.csv     (122 MB) — event sequences per block
    anomaly_label.csv    (18 MB)  — Normal / Anomaly labels per block

What is HDFS?
  Hadoop Distributed File System logs from a 203-node cloud cluster.
  Each "block" is a chunk of data being managed across the cluster.
  One block's logs form one sequence: [E5, E11, E22, E5, E9, ...]
  Anomalous blocks = disk failures, network errors, data corruption.

Event_traces.csv format:
  BlockId,EventSequence
  blk_-1608999687919862906,E5 E5 E22 E5 E11 E9 E11 E9
  blk_7503483334202473044,E5 E22 E5 E11 E26 E26 E26

anomaly_label.csv format:
  BlockId,Label
  blk_-1608999687919862906,Normal
  blk_7503483334202473044,Anomaly

Imported by: train.py
"""

import os
import json
import re
import pandas as pd


def _find_column(columns, predicates):
    """
    Return first column whose lowercase name satisfies any predicate.
    Returns None when no match exists.
    """
    for col in columns:
        name = col.strip().lower()
        if any(pred(name) for pred in predicates):
            return col
    return None


def _label_to_binary(value):
    """Normalize diverse label values to 0/1."""
    s = str(value).strip().lower()
    if s in {"anomaly", "abnormal", "failure", "failed", "error", "1", "true", "yes"}:
        return 1
    if s in {"normal", "success", "0", "false", "no"}:
        return 0
    try:
        return 1 if float(s) > 0 else 0
    except Exception:
        return 0


def _parse_event_tokens(raw_value):
    """
    Parse event sequences from either:
      - space format: "E5 E11 E22"
      - bracket/comma format: "[E5,E11,E22]"
    """
    if pd.isna(raw_value):
        return []

    s = str(raw_value).strip()
    if not s:
        return []

    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]

    s = s.replace("'", "").replace('"', "")
    parts = [p.strip() for p in re.split(r"[\s,]+", s) if p.strip()]
    tokens = []
    for p in parts:
        # Canonicalize e5 -> E5
        if re.fullmatch(r"[Ee]\d+", p):
            tokens.append(f"E{p[1:]}")
            continue
        # Keep generic tokens as-is for compatibility with other parsers.
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p):
            tokens.append(p)
    return tokens


def parse_hdfs(
    traces_path:  str  = "data/raw_logs/hdfs/Event_traces.csv",
    label_path:   str  = "data/raw_logs/hdfs/anomaly_label.csv",
    cache_path:   str  = "data/raw_logs/hdfs/hdfs_cache.json",
    force:        bool = False,
    min_seq_len:  int  = 2,
):
    """
    Load preprocessed HDFS sequences and labels.

    Args:
        traces_path : path to Event_traces.csv
        label_path  : path to anomaly_label.csv
        cache_path  : JSON cache (saves ~20s on subsequent runs)
        force       : re-load from CSV even if cache exists
        min_seq_len : skip blocks with fewer events

    Returns:
        sequences    (list[list[int]]): event ID sequences
        labels       (list[int]):       0=Normal, 1=Anomaly
        template_map (dict):            {"E1": 0, "E2": 1, ...}
    """

    # ── Load from cache ───────────────────────────────────────────
    if os.path.exists(cache_path) and not force:
        print(f"[HDFS Parser] Loading cache: {cache_path}")
        with open(cache_path) as f:
            c = json.load(f)
        n = len(c["sequences"]); na = sum(c["labels"])
        print(f"  {n:,} sequences | {na:,} anomaly | {n-na:,} normal")
        print(f"  Vocabulary: {len(c['template_map'])} event types")
        return c["sequences"], c["labels"], c["template_map"]

    # ── Check files exist ─────────────────────────────────────────
    for path, name in [(traces_path, "Event_traces.csv"),
                       (label_path,  "anomaly_label.csv")]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"\n'{name}' not found: {path}\n"
                "Download HDFS_v1.zip from: https://zenodo.org/records/8196385\n"
                "Extract -> preprocessed/ folder -> copy to your project folder."
            )

    # ── Load labels ───────────────────────────────────────────────
    print("[HDFS Parser] Loading labels...")
    df = pd.read_csv(label_path)
    df.columns = [c.strip() for c in df.columns]
    id_col = _find_column(
        df.columns,
        [lambda c: "block" in c, lambda c: c == "id"]
    )
    lbl_col = _find_column(
        df.columns,
        [lambda c: "label" in c]
    )
    if id_col is None or lbl_col is None:
        raise ValueError(
            "Could not detect required columns in anomaly label file.\n"
            f"Found columns: {list(df.columns)}\n"
            "Expected a block-id column (e.g., BlockId) and a label column."
        )
    block_labels = {
        str(r[id_col]).strip():
        _label_to_binary(r[lbl_col])
        for _, r in df.iterrows()
    }
    na = sum(block_labels.values())
    print(f"  {len(block_labels):,} blocks | {na:,} anomaly | "
          f"{len(block_labels)-na:,} normal")

    # ── Load event traces ─────────────────────────────────────────
    print(f"\n[HDFS Parser] Loading Event_traces.csv (~20 seconds)...")
    df2 = pd.read_csv(traces_path)
    df2.columns = [c.strip() for c in df2.columns]
    blk_col = _find_column(
        df2.columns,
        [lambda c: "block" in c, lambda c: c == "id"]
    )
    seq_col = _find_column(
        df2.columns,
        [lambda c: any(k in c for k in (
            "eventsequence", "event_sequence", "sequence", "trace", "feature", "features", "events"
        ))]
    )

    # Fallback: infer sequence column from sample content containing event tokens (E1, E2, ...).
    if seq_col is None:
        scored = {}
        for col in df2.columns:
            if col == blk_col:
                continue
            sample = df2[col].dropna().astype(str).head(200)
            score = int(sum(bool(re.search(r"\bE\d+\b", s)) for s in sample))
            if score > 0:
                scored[col] = score
        if scored:
            seq_col = max(scored, key=scored.get)
            print(f"  Auto-detected sequence column by content: {seq_col}")

    if blk_col is None or seq_col is None:
        raise ValueError(
            "Could not detect required columns in Event_traces.csv.\n"
            f"Found columns: {list(df2.columns)}\n"
            "Expected block id (e.g., BlockId) and sequence/events column "
            "(e.g., EventSequence, Trace, Features)."
        )

    # ── Build event vocabulary ─────────────────────────────────────
    # Collect all unique event names (E1, E2, ... E28)
    all_events = set()
    for raw in df2[seq_col].dropna():
        all_events.update(_parse_event_tokens(raw))

    # Natural sort: E1, E2, ..., E9, E10, E11 (not E1, E10, E11, E2)
    def nat_key(s):
        return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', s)]

    template_map = {name: idx for idx, name in
                    enumerate(sorted(all_events, key=nat_key))}

    print(f"  Vocabulary ({len(template_map)} event types):")
    for name, idx in sorted(template_map.items(), key=lambda x: x[1]):
        print(f"    {name} -> index {idx}")

    # ── Build sequences ───────────────────────────────────────────
    sequences, labels = [], []
    skipped = 0

    for blk_raw, seq_raw in df2[[blk_col, seq_col]].itertuples(index=False, name=None):
        blk_id  = str(blk_raw).strip()
        tokens = _parse_event_tokens(seq_raw)

        if blk_id not in block_labels:
            skipped += 1; continue

        seq = [template_map[t] for t in tokens
               if t.strip() in template_map]

        if len(seq) < min_seq_len:
            continue

        sequences.append(seq)
        labels.append(block_labels[blk_id])

    n = len(sequences); na = sum(labels)
    print(f"\n[HDFS Parser] Done!")
    print(f"  Sequences  : {n:,}")
    print(f"  Normal     : {n-na:,}  ({100*(n-na)/n:.1f}%)")
    print(f"  Anomaly    : {na:,}  ({100*na/n:.1f}%)")
    print(f"  Skipped    : {skipped:,} (not in label file)")

    # ── Save cache ────────────────────────────────────────────────
    with open(cache_path, "w") as f:
        json.dump({"sequences": sequences, "labels": labels,
                   "template_map": template_map}, f)
    print(f"  Cache saved -> {cache_path}")

    return sequences, labels, template_map


if __name__ == "__main__":
    seqs, labels, tmpl = parse_hdfs()
    id2name = {v: k for k, v in tmpl.items()}
    print(f"\nSample normal  : {[id2name[e] for e in seqs[0]]}")
    ai = next(i for i, l in enumerate(labels) if l == 1)
    print(f"Sample anomaly : {[id2name[e] for e in seqs[ai]]}")
