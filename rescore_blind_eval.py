#!/usr/bin/env python3
"""
Re-score existing blind_eval JSON files using a new gold_standards.json.

This is a post-processing step that doesn't make any LLM API calls.
It re-uses the LLM's matching (matched_b_id, b_decision, strength_b)
from eval_outputs/ and re-evaluates decision_match and strength_match
against acceptable_decisions/acceptable_strengths from the new gold.
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


def rescore_one(eval_data: Dict, gold: Dict) -> Dict:
    """Re-evaluate matches and strength using acceptable lists."""
    parsed = eval_data.get("parsed")
    if not parsed:
        return eval_data

    gold_acceptable_map = {
        h["id"]: h.get("acceptable_decisions", [h.get("expected_decision")])
        for h in gold["hypotheses"]
    }
    acceptable_strengths = gold.get(
        "acceptable_strengths", [gold.get("expected_strength", "weak")]
    )

    matches = parsed.get("matches", [])
    for m in matches:
        gid = m.get("analysis_a_id")
        b_dec = m.get("b_decision")
        acceptable = gold_acceptable_map.get(gid, [])
        m["a_acceptable"] = acceptable
        if b_dec is None or m.get("matched_b_id") is None:
            m["decision_match"] = False
        else:
            m["decision_match"] = b_dec in acceptable

    b_strength = parsed.get("strength_b")
    parsed["strength_a_acceptable"] = acceptable_strengths
    parsed["strength_match"] = (b_strength in acceptable_strengths) if b_strength else False

    # Recompute summary
    gold_count = len(gold["hypotheses"])
    matched = sum(1 for m in matches if m.get("matched_b_id"))
    agreed = sum(1 for m in matches if m.get("decision_match") is True)
    disagreed = sum(1 for m in matches if m.get("decision_match") is False)
    absent = gold_count - matched
    eval_data["summary"] = {
        "gold_count": gold_count,
        "matched": matched,
        "agreed": agreed,
        "disagreed": disagreed,
        "absent": absent,
        "strength_match": parsed["strength_match"],
        "agreement_rate": f"{agreed}/{gold_count}",
    }
    eval_data["parsed"] = parsed
    return eval_data


def aggregate(eval_dir: Path, gold_file: Path) -> Dict:
    with gold_file.open("r", encoding="utf-8") as f:
        gold_all = json.load(f)

    summary_rows = []
    aggregate_by_method: Dict[str, Dict] = {
        m: {
            "total_gold": 0,
            "total_agreed": 0,
            "total_cases": 0,
            "strength_agreed": 0,
        }
        for m in METHODS
    }

    for case_id in CASES:
        for method in METHODS:
            f = eval_dir / f"blind_eval_{case_id}_{method}.json"
            if not f.exists():
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            summary = data.get("summary")
            if not summary:
                continue
            row = {
                "case": case_id,
                "method": method,
                "gold_hypotheses": summary["gold_count"],
                "matched": summary["matched"],
                "decision_agreed": summary["agreed"],
                "decision_disagreed": summary["disagreed"],
                "absent": summary["absent"],
                "strength_match": summary["strength_match"],
                "agreement_rate": summary["agreement_rate"],
            }
            summary_rows.append(row)
            aggregate_by_method[method]["total_gold"] += summary["gold_count"]
            aggregate_by_method[method]["total_agreed"] += summary["agreed"]
            aggregate_by_method[method]["total_cases"] += 1
            if summary.get("strength_match"):
                aggregate_by_method[method]["strength_agreed"] += 1

    for m, agg in aggregate_by_method.items():
        if agg["total_gold"] > 0:
            agg["decision_rate_str"] = f"{agg['total_agreed']}/{agg['total_gold']}"
            agg["decision_fraction"] = round(agg["total_agreed"] / agg["total_gold"], 3)
        if agg["total_cases"] > 0:
            agg["strength_rate_str"] = f"{agg['strength_agreed']}/{agg['total_cases']}"
            agg["strength_fraction"] = round(agg["strength_agreed"] / agg["total_cases"], 3)
        combined_total = agg["total_gold"] + agg["total_cases"]
        combined_agreed = agg["total_agreed"] + agg["strength_agreed"]
        if combined_total > 0:
            agg["combined_rate_str"] = f"{combined_agreed}/{combined_total}"
            agg["combined_fraction"] = round(combined_agreed / combined_total, 3)

    return {"summary": summary_rows, "aggregate": aggregate_by_method}


def main():
    parser = argparse.ArgumentParser(description="Re-score blind eval with new gold standards (no API)")
    parser.add_argument("--input", default="eval_outputs", help="Input dir with existing blind_eval JSONs")
    parser.add_argument("--output", default="eval_outputs_v2", help="Output dir for re-scored results")
    parser.add_argument("--gold", default="gold_standards.json", help="New gold standards file")
    args = parser.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    gold_file = Path(args.gold)

    with gold_file.open("r", encoding="utf-8") as f:
        gold_all = json.load(f)

    rescored_count = 0
    for case_id in CASES:
        gold = gold_all.get(case_id)
        if not gold:
            continue
        for method in METHODS:
            in_file = in_dir / f"blind_eval_{case_id}_{method}.json"
            if not in_file.exists():
                continue
            data = json.loads(in_file.read_text(encoding="utf-8"))
            data = rescore_one(data, gold)
            out_file = out_dir / f"blind_eval_{case_id}_{method}.json"
            out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            rescored_count += 1

    print(f"Re-scored {rescored_count} files")

    # Aggregate
    agg = aggregate(out_dir, gold_file)
    out_file = out_dir / "blind_eval_summary.json"
    out_file.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSummary written to {out_file}")
    print("\n=== Aggregate ===")
    print(f"  {'method':15s} {'decision':12s} {'strength':12s} {'combined':12s}")
    for m, a in agg["aggregate"].items():
        print(f"  {m:15s} "
              f"{a.get('decision_rate_str','—'):12s} "
              f"{a.get('strength_rate_str','—'):12s} "
              f"{a.get('combined_rate_str','—'):12s}")


if __name__ == "__main__":
    main()
