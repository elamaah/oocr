"""Field-level evaluation harness.

Layout:
    evaluation/test_images/<name>.jpg
    evaluation/ground_truth/<name>.json     # in the Invoice schema

Run:
    python evaluation/evaluate.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running this file directly from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rapidfuzz import fuzz

from extractor import extract_invoice_advanced


ROOT = Path(__file__).resolve().parent
IMAGES_DIR = ROOT / "test_images"
GT_DIR = ROOT / "ground_truth"
RESULTS_DIR = ROOT / "results"

NAME_FUZZ_THRESHOLD = 85       # rapidfuzz ratio
PRICE_TOLERANCE = 0.01         # 1%
TOTAL_TOLERANCE = 0.01         # 1%


# ──────────────────────────── Field comparators ────────────────────────────

def _eq_optional(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a == b


def _close_optional(a: Optional[float], b: Optional[float], tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if b == 0:
        return abs(a - b) <= tol
    return abs(a - b) / abs(b) <= tol


def _items_prf(predicted: list[dict], truth: list[dict]) -> tuple[float, float, float]:
    """Set-based precision/recall/F1: predicted item matches truth item if
    name fuzz ratio > threshold AND total_price (or unit_price as fallback)
    within tolerance."""
    matched_truth: set[int] = set()
    matched_pred = 0

    def price(item: dict) -> Optional[float]:
        return item.get("total_price") if item.get("total_price") is not None else item.get("unit_price")

    for p in predicted:
        for j, t in enumerate(truth):
            if j in matched_truth:
                continue
            if fuzz.ratio(str(p.get("name", "")), str(t.get("name", ""))) < NAME_FUZZ_THRESHOLD:
                continue
            if not _close_optional(price(p), price(t), PRICE_TOLERANCE):
                continue
            matched_truth.add(j)
            matched_pred += 1
            break

    precision = matched_pred / len(predicted) if predicted else (1.0 if not truth else 0.0)
    recall = matched_pred / len(truth) if truth else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


# ──────────────────────────── Per-invoice evaluation ────────────────────────────

def _evaluate_one(pred: dict, truth: dict) -> dict:
    return {
        "date_match": _eq_optional(pred.get("date"), truth.get("date")),
        "time_match": _eq_optional(pred.get("time"), truth.get("time")),
        "total_match": _close_optional(pred.get("total"), truth.get("total"), TOTAL_TOLERANCE),
        "total_abs_error": (
            None if pred.get("total") is None or truth.get("total") is None
            else abs(pred["total"] - truth["total"])
        ),
        "category_match": _eq_optional(pred.get("category"), truth.get("category")),
        "items": dict(zip(("precision", "recall", "f1"),
                          _items_prf(pred.get("items", []), truth.get("items", [])))),
    }


# ──────────────────────────── Main ────────────────────────────

def main() -> int:
    if not IMAGES_DIR.exists():
        print(f"No test images directory: {IMAGES_DIR}")
        print("Add receipt images here and matching JSON files in ground_truth/.")
        return 1

    images = sorted([p for p in IMAGES_DIR.iterdir()
                     if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    if not images:
        print(f"No images found in {IMAGES_DIR}.")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    per_invoice = []
    latencies = []

    for img_path in images:
        gt_path = GT_DIR / f"{img_path.stem}.json"
        if not gt_path.exists():
            print(f"[skip] no ground truth for {img_path.name}")
            continue
        truth = json.loads(gt_path.read_text(encoding="utf-8"))

        t0 = time.perf_counter()
        try:
            pred = extract_invoice_advanced(str(img_path))
        except Exception as e:
            print(f"[fail] {img_path.name}: {e}")
            per_invoice.append({"image": img_path.name, "error": str(e)})
            continue
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)

        record = _evaluate_one(pred, truth)
        record["image"] = img_path.name
        record["latency_s"] = elapsed
        per_invoice.append(record)

        # Persist the prediction for inspection.
        (RESULTS_DIR / f"{img_path.stem}.pred.json").write_text(
            json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"[{img_path.name:30s}] "
              f"date={'✓' if record['date_match'] else '✗'} "
              f"total={'✓' if record['total_match'] else '✗'} "
              f"items_F1={record['items']['f1']:.2f} "
              f"cat={'✓' if record['category_match'] else '✗'} "
              f"({elapsed:.1f}s)")

    # Aggregates
    valid = [r for r in per_invoice if "error" not in r]
    n = len(valid)
    if n == 0:
        print("No successful evaluations.")
        return 1

    def acc(key):
        return sum(1 for r in valid if r[key]) / n

    items_f1 = sum(r["items"]["f1"] for r in valid) / n

    summary = {
        "n_evaluated": n,
        "n_failed": len(per_invoice) - n,
        "date_accuracy": acc("date_match"),
        "time_accuracy": acc("time_match"),
        "total_within_1pct": acc("total_match"),
        "category_accuracy": acc("category_match"),
        "items_f1_mean": items_f1,
        "latency_median_s": sorted(latencies)[len(latencies) // 2] if latencies else None,
        "latency_p95_s": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else None,
    }

    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "per_invoice.json").write_text(
        json.dumps(per_invoice, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"  {k:24s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
