#!/usr/bin/env python3
"""
Rubric-independent metrics for the 4-condition oversight protocol experiment.

Computes two metrics directly from existing run logs (no LLM, no gold standard):

1. Overclaim suppression rate: fraction of (case, method) outputs where
   strength != "strong"

2. Evidence grounding rate: fraction of survive/reject judgments that have
   non-empty evidence_ids
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional


CASES = [
    "web_browsing_mood",
    "orben_przybylski_2019",
    "twenge_2018",
    "cheng_hoekstra",
    "voight_hdl",
    "chen_huairiver",
]

METHODS = ["baseline", "scaffold_only", "rubric_only", "proposed"]


def find_run_file(case_id: str, method: str, outputs_dir: Path) -> Optional[Path]:
    """Find run file for a (case, method), preferring v3 > v2 > original."""
    candidates = [
        f"run_4cond_{method}_{case_id}_v3.jsonl",
        f"run_4cond_{method}_{case_id}_v2.jsonl",
        f"run_4cond_{method}_{case_id}.jsonl",
    ]
    for c in candidates:
        p = outputs_dir / c
        if p.exists():
            return p
    return None


def extract_s3(run_file: Path) -> Optional[Dict]:
    """Extract the LAST successful S3 designer output."""
    last_s3 = None
    with run_file.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("status") != "success":
                continue
            if row.get("role") != "designer":
                continue
            if row.get("stage") == "S3":
                parsed = row.get("parsed", {})
                if isinstance(parsed, dict):
                    last_s3 = parsed.get("conclusion")
    return last_s3 if isinstance(last_s3, dict) else None


def compute_metrics(outputs_dir: Path) -> Dict:
    overclaim = {m: {"suppressed": 0, "total": 0} for m in METHODS}
    grounding = {m: {"grounded": 0, "total": 0} for m in METHODS}
    per_case_details = []

    for case_id in CASES:
        for method in METHODS:
            run_file = find_run_file(case_id, method, outputs_dir)
            if run_file is None:
                continue
            conclusion = extract_s3(run_file)
            if not conclusion:
                continue

            # Overclaim metric
            strength = conclusion.get("strength", "?")
            overclaim[method]["total"] += 1
            if strength != "strong":
                overclaim[method]["suppressed"] += 1

            # Evidence grounding metric
            judgments = conclusion.get("hypothesis_judgments", [])
            case_grounded = 0
            case_total = 0
            for j in judgments:
                if not isinstance(j, dict):
                    continue
                if j.get("decision") in ("survive", "reject"):
                    case_total += 1
                    grounding[method]["total"] += 1
                    eids = j.get("evidence_ids", [])
                    if isinstance(eids, list) and len(eids) > 0:
                        case_grounded += 1
                        grounding[method]["grounded"] += 1

            per_case_details.append({
                "case": case_id,
                "method": method,
                "strength": strength,
                "judgments_with_evidence": f"{case_grounded}/{case_total}",
            })

    # Compute rates
    for m, agg in overclaim.items():
        if agg["total"] > 0:
            agg["rate"] = round(agg["suppressed"] / agg["total"], 3)
    for m, agg in grounding.items():
        if agg["total"] > 0:
            agg["rate"] = round(agg["grounded"] / agg["total"], 3)

    return {
        "overclaim_suppression": overclaim,
        "evidence_grounding": grounding,
        "per_case_details": per_case_details,
    }


def main():
    parser = argparse.ArgumentParser(description="Rubric-independent metrics")
    parser.add_argument("--outputs", default="outputs", help="Outputs directory")
    parser.add_argument("--out", default="eval_outputs/metrics_summary.json", help="Output file")
    args = parser.parse_args()

    outputs_dir = Path(args.outputs)
    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(outputs_dir)
    out_file.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Metrics written to {out_file}\n")
    print("=== Overclaim Suppression (strength != strong) ===")
    for m, a in metrics["overclaim_suppression"].items():
        print(f"  {m:15s} {a.get('suppressed', 0)}/{a.get('total', 0)}  ({a.get('rate', '—')})")
    print("\n=== Evidence Grounding (survive/reject with evidence_ids) ===")
    for m, a in metrics["evidence_grounding"].items():
        print(f"  {m:15s} {a.get('grounded', 0)}/{a.get('total', 0)}  ({a.get('rate', '—')})")


if __name__ == "__main__":
    main()
