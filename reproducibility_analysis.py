#!/usr/bin/env python3
"""Analyze reproducibility of proposed runs across multiple runs."""

import json
from pathlib import Path

CASES = [
    "web_browsing_mood",
    "orben_przybylski_2019",
    "twenge_2018",
    "cheng_hoekstra",
    "voight_hdl",
    "chen_huairiver",
]


def extract_summary(run_file):
    """Extract S1 hypothesis count, S3 decisions, and strength."""
    if not run_file.exists():
        return None
    s1_count = 0
    s3_decisions = {}
    strength = None
    with run_file.open() as f:
        for line in f:
            row = json.loads(line)
            if row.get("status") != "success":
                continue
            if row.get("role") != "designer":
                continue
            stage = row.get("stage")
            parsed = row.get("parsed", {})
            if not isinstance(parsed, dict):
                continue
            if stage == "S1":
                hyps = parsed.get("hypotheses", [])
                s1_count = len(hyps)
            elif stage == "S3":
                c = parsed.get("conclusion", {})
                if isinstance(c, dict):
                    judgments = c.get("hypothesis_judgments", [])
                    s3_decisions = {j["id"]: j["decision"] for j in judgments if isinstance(j, dict)}
                    strength = c.get("strength")
    if s1_count == 0 or not s3_decisions:
        return None
    return {
        "s1_count": s1_count,
        "decisions": s3_decisions,
        "strength": strength,
    }


def main():
    print("=== Reproducibility Analysis: proposed × 6 cases × 3 runs ===\n")
    print("Note: run3 mostly failed due to API rate limits. Analyzing available data.\n")

    for case in CASES:
        print(f"--- {case} ---")
        results = []
        for run in [1, 2, 3]:
            f = Path(f"outputs/repro_run{run}_proposed_{case}.jsonl")
            r = extract_summary(f)
            if r:
                decisions_str = " ".join(f"{k}={v}" for k, v in sorted(r['decisions'].items()))
                print(f"  run{run}: S1={r['s1_count']} | {decisions_str} | str={r['strength']}")
                results.append(r)
            else:
                print(f"  run{run}: [missing or empty]")

        if len(results) >= 2:
            # Check stability
            s1_counts = set(r['s1_count'] for r in results)
            strengths = set(r['strength'] for r in results)
            decisions_match = all(r['decisions'] == results[0]['decisions'] for r in results[1:])

            print(f"  → S1 hypothesis counts: {sorted(s1_counts)}")
            print(f"  → strengths: {sorted(strengths)}")
            print(f"  → decisions identical: {decisions_match}")
        print()


if __name__ == "__main__":
    main()
