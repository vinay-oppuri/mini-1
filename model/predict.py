"""
predict.py
==========
Load trained model → run inference → explain anomalies with Gemini.

This file does two things:
  1. AnomalyDetector class — used by your 5 agents in Phase 2
  2. main() — tests on real HDFS sequences and shows Gemini output

GEMINI SETUP (free):
  Get key : https://aistudio.google.com/app/apikey
  Set key : export GEMINI_API_KEY=your_key_here   (Linux/Mac)
            set GEMINI_API_KEY=your_key_here       (Windows)

RUN:
  python predict.py
"""

import os
import json
import math
import sys
from pathlib import Path
import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import f1_score, roc_auc_score, classification_report

from google import genai
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model.transformer_model import AnomalyTransformer


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ══════════════════════════════════════════════════════════════════
#  GEMINI EXPLAINER
# ══════════════════════════════════════════════════════════════════

def explain_with_gemini(event_sequence, template_map, anomaly_score,
                        block_id=None, api_key=None):
    """
    Ask Gemini to explain what type of anomaly was detected.

    Our Transformer detects THAT something is wrong.
    Gemini explains WHAT it is, WHY it's suspicious, and
    what action the system should take.

    Args:
        event_sequence : list of event IDs e.g. [4, 10, 4, 10, 4]
        template_map   : {"E5": 0, "E11": 1, ...} from HDFS parser
        anomaly_score  : model output probability (0.0 to 1.0)
        block_id       : HDFS block identifier (for display)
        api_key        : Gemini API key (or set GEMINI_API_KEY env var)

    Returns:
        dict with attack_type, severity, explanation, recommendation
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return {
            "attack_type"    : "Gemini not configured",
            "severity"       : "Unknown",
            "explanation"    : (
                "Set GEMINI_API_KEY environment variable to enable "
                "LLM-based anomaly explanation. "
                "Get a free key at: https://aistudio.google.com/app/apikey"
            ),
            "recommendation" : "Manual investigation required.",
        }

    # Build reverse map: event_index → event_name (e.g. 4 → "E5")
    idx_to_name = {v: k for k, v in template_map.items()}

    readable = []
    for i, eid in enumerate(event_sequence):
        name = idx_to_name.get(eid, f"E?({eid})")
        readable.append(f"  [{i+1:2d}] {name}")
    seq_text = "\n".join(readable)

    prompt = f"""
You are a cloud infrastructure expert analyzing anomalous server logs.

A Transformer deep learning model detected an ANOMALY in an HDFS 
(Hadoop Distributed File System) cloud cluster log sequence.

HDFS runs on cloud computing clusters and manages distributed data storage.
Common anomaly types include hardware failures, network errors, and data corruption.

══════════════════════════════════════
ANOMALY DETAILS
══════════════════════════════════════
Block ID      : {block_id or "Unknown"}
Anomaly Score : {anomaly_score:.4f} / 1.0  ({anomaly_score*100:.1f}% confidence)

LOG EVENT SEQUENCE (in order of occurrence):
{seq_text}

HDFS EVENT REFERENCE:
  E5  = Receiving block (normal data transfer start)
  E6  = Received block (successful transfer)
  E7  = Exception / Error during transfer
  E9  = PacketResponder interrupted (abnormal)
  E11 = Block write failed
  E22 = Replication pipeline error
  E26 = Verification failure

══════════════════════════════════════
TASK
══════════════════════════════════════
Based on the event sequence pattern above, identify:
1. What type of cloud infrastructure anomaly this is
2. How severe it is
3. Why this sequence is suspicious
4. What automated action to take

Respond ONLY in valid JSON (no markdown, no extra text):
{{
  "attack_type"    : "Short name e.g. Disk Failure / Network Error / Data Corruption",
  "severity"       : "Low OR Medium OR High OR Critical",
  "explanation"    : "2-3 sentences: what pattern makes this suspicious and what it means",
  "recommendation" : "One concrete automated action e.g. Alert operator / Trigger replication / Block node"
}}
"""

    print(f"  [Gemini] Analysing block: {block_id or 'unknown'} "
          f"(score={anomaly_score:.4f})")
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        raw = (response.text or "").strip()

        # Strip markdown fences if present
        if "```" in raw:
            parts = raw.split("```")
            raw   = parts[1] if len(parts) > 1 else parts[0]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        for k, v in [("attack_type","Unknown"), ("severity","Medium"),
                     ("explanation","Anomalous pattern detected."),
                     ("recommendation","Alert operator.")]:
            result.setdefault(k, v)

        print(f"  [Gemini] OK {result['attack_type']} ({result['severity']})")
        return result

    except json.JSONDecodeError:
        return {"attack_type": "Parse Error", "severity": "Unknown",
                "explanation": raw[:300], "recommendation": "Manual review."}
    except Exception as e:
        return {"attack_type": "API Error", "severity": "Unknown",
                "explanation": str(e), "recommendation": "Manual review."}


# ══════════════════════════════════════════════════════════════════
#  ANOMALY DETECTOR  (used by agents in Phase 2)
# ══════════════════════════════════════════════════════════════════

class AnomalyDetector:
    """
    High-level interface for cloud workload anomaly detection.

    Your 5 agents will use this class:
      from predict import AnomalyDetector

      detector = AnomalyDetector(gemini_api_key="your_key")
      result   = detector.predict(
          event_sequence = [4, 10, 4, 10, 4],
          block_id       = "blk_-123456",
          explain        = True
      )
      print(result["label"])           # "Anomaly" or "Normal"
      print(result["score"])           # 0.0 to 1.0
      print(result["gemini_analysis"]) # attack type, severity, action
    """

    def __init__(self, model_path="model/model.pt",
                 meta_path="model/model_metadata.json",
                 gemini_api_key=None):

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found: {model_path}\n"
                "Run python train.py first!"
            )

        with open(meta_path) as f:
            self.meta = json.load(f)

        self.threshold   = self.meta["threshold"]
        self.max_seq_len = self.meta["model_config"]["max_seq_len"]
        self.vocab_size  = self.meta["vocab_size"]

        cfg  = self.meta["model_config"]
        ckpt = torch.load(model_path, map_location=DEVICE, weights_only=False)

        self.template_map = ckpt.get("template_map", {})

        self.model = AnomalyTransformer(
            vocab_size  = self.vocab_size,
            d_model     = cfg["d_model"],
            nhead       = cfg["nhead"],
            num_layers  = cfg["num_layers"],
            max_seq_len = cfg["max_seq_len"],
            dropout     = 0.0,   # no dropout at inference
        ).to(DEVICE)

        self.model.load_state_dict(ckpt["model_state"])
        self.model.eval()
        self.gemini_api_key = gemini_api_key

        print(f"[AnomalyDetector] Ready")
        print(f"  Threshold : {self.threshold:.4f}")
        print(f"  Vocab     : {self.vocab_size} event types")
        print(f"  Device    : {DEVICE}")

    def _to_tensor(self, seq):
        """Shift IDs +1, pad/truncate, convert to tensor."""
        s = [e + 1 for e in seq]
        s = s[:self.max_seq_len] if len(s) >= self.max_seq_len \
            else s + [0] * (self.max_seq_len - len(s))
        return torch.tensor([s], dtype=torch.long).to(DEVICE)

    @torch.no_grad()
    def predict(self, event_sequence, block_id=None,
                raw_log=None, explain=False):
        """
        Predict whether a log sequence is anomalous.

        Args:
            event_sequence : list of event IDs from HDFS parser
            block_id       : HDFS block ID (for display/logging)
            raw_log        : optional raw log text (for Gemini context)
            explain        : call Gemini for anomalies if True

        Returns:
            dict: {
              "block_id"       : str
              "is_anomaly"     : bool
              "score"          : float  (0.0–1.0)
              "label"          : "Normal" or "Anomaly"
              "event_sequence" : list
              "gemini_analysis": dict or None
            }
        """
        score      = torch.sigmoid(
            self.model(self._to_tensor(event_sequence))
        ).item()
        is_anomaly = score >= self.threshold

        result = {
            "block_id"       : block_id or "unknown",
            "is_anomaly"     : is_anomaly,
            "score"          : round(score, 4),
            "label"          : "Anomaly" if is_anomaly else "Normal",
            "event_sequence" : event_sequence,
            "gemini_analysis": None,
        }

        if is_anomaly and explain:
            result["gemini_analysis"] = explain_with_gemini(
                event_sequence = event_sequence,
                template_map   = self.template_map,
                anomaly_score  = score,
                block_id       = block_id,
                api_key        = self.gemini_api_key,
            )

        return result


# ══════════════════════════════════════════════════════════════════
#  MAIN — Test on real HDFS sequences
# ══════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 58)
    print("  Cloud Workload Log Anomaly Detection - Prediction")
    print("=" * 58)

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    detector   = AnomalyDetector(gemini_api_key=gemini_key or None)

    # Load real sequences from cache
    cache = "data/raw_logs/hdfs/hdfs_cache.json"
    if not os.path.exists(cache):
        print(f"\nCache not found: {cache}")
        print("Run python train.py first.")
        return

    with open(cache) as f:
        c = json.load(f)

    sequences = c["sequences"]
    labels    = c["labels"]

    normal_seqs  = [(s, "blk_NORMAL")  for s, l in zip(sequences, labels) if l == 0]
    anomaly_seqs = [(s, "blk_ANOMALY") for s, l in zip(sequences, labels) if l == 1]

    print(f"\nLoaded {len(sequences):,} sequences | "
          f"{len(anomaly_seqs):,} anomaly | {len(normal_seqs):,} normal")

    # ── Test 5 normal sequences ────────────────────────────────────
    print(f"\n{'-' * 58}")
    print("Testing NORMAL sequences (expected: Normal)")
    print(f"{'-' * 58}")
    correct = 0
    for seq, bid in normal_seqs[:5]:
        r = detector.predict(seq, block_id=bid)
        ok = "OK" if r["label"] == "Normal" else "X"
        print(f"  [{ok}] Expected: Normal  | Got: {r['label']:7s} | "
              f"Score: {r['score']:.4f} | SeqLen: {len(seq)}")
        if r["label"] == "Normal":
            correct += 1
    print(f"  Result: {correct}/5 correct")

    # ── Test 5 anomaly sequences ───────────────────────────────────
    print(f"\n{'-' * 58}")
    print("Testing ANOMALY sequences (expected: Anomaly)")
    print(f"{'-' * 58}")
    correct = 0
    for seq, bid in anomaly_seqs[:5]:
        r = detector.predict(seq, block_id=bid,
                             explain=bool(gemini_key))
        ok = "OK" if r["label"] == "Anomaly" else "X"
        print(f"  [{ok}] Expected: Anomaly | Got: {r['label']:7s} | "
              f"Score: {r['score']:.4f} | SeqLen: {len(seq)}")
        if r["label"] == "Anomaly":
            correct += 1

        # Print Gemini explanation if available
        g = r.get("gemini_analysis")
        if g and g.get("attack_type") not in (None, "Gemini not configured",
                                               "API Error", "Parse Error"):
            print(f"       -> [{g['severity']}] {g['attack_type']}")
            print(f"         {g['explanation'][:110]}")
            print(f"         Action -> {g['recommendation']}")

    print(f"  Result: {correct}/5 correct")

    # ── Full dataset evaluation ────────────────────────────────────
    print(f"\n{'-' * 58}")
    print("Full Evaluation on all sequences")
    print(f"{'-' * 58}")

    all_preds, all_true, all_scores = [], [], []
    for seq, lbl in zip(sequences, labels):
        r = detector.predict(seq)
        all_preds.append(1 if r["is_anomaly"] else 0)
        all_true.append(lbl)
        all_scores.append(r["score"])

    all_preds  = np.array(all_preds)
    all_true   = np.array(all_true)
    all_scores = np.array(all_scores)

    f1  = f1_score(all_true, all_preds, zero_division=0)
    auc = roc_auc_score(all_true, all_scores)
    print(f"\n  F1 Score : {f1:.4f}")
    print(f"  AUC-ROC  : {auc:.4f}")
    print(f"\n  Classification Report:")
    print(classification_report(all_true, all_preds,
                                target_names=["Normal","Anomaly"], digits=4))


if __name__ == "__main__":
    main()
