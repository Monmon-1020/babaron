#!/usr/bin/env python3
"""
Supervisor analysis script.

Analyzes the run logs to extract:
1. NG counts by method × stage (S1-CHK, S2-CHK, S3-CHK)
2. NG reason classification (general_quality vs causal_specific)
3. Before/after changes in Designer outputs after retries

Operates entirely on existing run_4cond_*.jsonl logs (no API calls).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


CASES = [
    "orben_przybylski_2019",
    "twenge_2018",
    "cheng_hoekstra",
    "voight_hdl",
    "chen_huairiver",
    "angrist_krueger_1991",
]
METHODS_WITH_SUPERVISOR = ["scaffold_only", "proposed"]
SUPERVISED_STAGES = ["S1-CHK", "S2-CHK", "S3-CHK"]

CAUSAL_KEYWORDS = [
    "hypothesis_relations",
    "exclusive",
    "independent",
    "nested",
    "identification",
    "識別仮定",
    "排他",
    "独立",
    "入れ子",
    "strength",
    "strong",
    "過剰断定",
    "反証",
    "falsify",
    "弁別予測",
    "distinctive",
    "媒介",
    "因果方向",
    "evidence",
]

GENERAL_KEYWORDS = [
    "曖昧",
    "不明",
    "明確でない",
    "矛盾",
    "形式",
    "スキーマ",
    "schema",
    "JSON",
    "冗長",
    "粗い",
    "簡潔",
    "missing",
    "invalid",
]


def find_run_file(case_id: str, method: str) -> Optional[Path]:
    outputs_dir = Path("outputs")
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


def classify_issue(text: str) -> str:
    """Classify a single fatal_issue text as causal_specific or general_quality."""
    if not isinstance(text, str):
        return "general_quality"
    causal_hits = sum(1 for kw in CAUSAL_KEYWORDS if kw in text)
    general_hits = sum(1 for kw in GENERAL_KEYWORDS if kw in text)
    if causal_hits > general_hits:
        return "causal_specific"
    if causal_hits > 0 and general_hits == 0:
        return "causal_specific"
    return "general_quality"


def extract_supervisor_logs(run_file: Path) -> Dict[str, Any]:
    """Walk the run log and extract supervisor verdicts + designer attempts per stage."""
    stage_data: Dict[str, Dict] = {
        "S1": {"designer_attempts": []},
        "S2": {"designer_attempts": []},
        "S3": {"designer_attempts": []},
        "S1-CHK": {"supervisor_attempts": []},
        "S2-CHK": {"supervisor_attempts": []},
        "S3-CHK": {"supervisor_attempts": []},
    }
    with run_file.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            stage = row.get("stage")
            role = row.get("role")
            if stage not in stage_data:
                continue
            entry = {
                "attempt": row.get("attempt"),
                "status": row.get("status"),
                "parsed": row.get("parsed"),
            }
            if role == "designer":
                stage_data[stage]["designer_attempts"].append(entry)
            elif role == "supervisor":
                stage_data[stage]["supervisor_attempts"].append(entry)
    return stage_data


def count_ng_per_stage(stage_data: Dict[str, Any]) -> Dict[str, int]:
    """Count NG verdicts per supervised stage."""
    ngs = {}
    for stage in SUPERVISED_STAGES:
        attempts = stage_data.get(stage, {}).get("supervisor_attempts", [])
        ng_count = sum(
            1
            for a in attempts
            if isinstance(a.get("parsed"), dict) and a["parsed"].get("verdict") == "NG"
        )
        ngs[stage] = ng_count
    return ngs


def collect_ng_issues(stage_data: Dict[str, Any]) -> List[Dict]:
    """Collect all fatal_issues from NG attempts with classification."""
    issues = []
    for stage in SUPERVISED_STAGES:
        attempts = stage_data.get(stage, {}).get("supervisor_attempts", [])
        for a in attempts:
            parsed = a.get("parsed")
            if not isinstance(parsed, dict):
                continue
            if parsed.get("verdict") != "NG":
                continue
            for issue in parsed.get("fatal_issues", []):
                issues.append({
                    "stage": stage,
                    "attempt": a.get("attempt"),
                    "category": classify_issue(issue),
                    "issue": issue,
                })
    return issues


def diff_designer_attempts(stage_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compare attempt 0 vs final successful attempt for each stage."""
    changes = {}
    for stage in ["S1", "S2", "S3"]:
        attempts = stage_data.get(stage, {}).get("designer_attempts", [])
        if len(attempts) < 2:
            continue
        first = attempts[0]
        # find last successful
        successful = [a for a in attempts if a.get("status") == "success"]
        if not successful:
            continue
        final = successful[-1]
        if first.get("attempt") == final.get("attempt"):
            continue

        first_p = first.get("parsed", {}) or {}
        final_p = final.get("parsed", {}) or {}

        stage_changes = []
        if stage == "S1":
            f_h = first_p.get("hypotheses", []) or []
            l_h = final_p.get("hypotheses", []) or []
            if len(f_h) != len(l_h):
                stage_changes.append({
                    "field": "hypothesis_count",
                    "before": len(f_h),
                    "after": len(l_h),
                })
            f_rel = first_p.get("hypothesis_relations", []) or []
            l_rel = final_p.get("hypothesis_relations", []) or []
            if len(f_rel) != len(l_rel):
                stage_changes.append({
                    "field": "hypothesis_relations_count",
                    "before": len(f_rel),
                    "after": len(l_rel),
                })
        elif stage == "S2":
            def get_ia(p):
                ep = p.get("experiment_plan", {}) or {}
                return p.get("identification_assumptions", ep.get("identification_assumptions", [])) or []
            f_ia = get_ia(first_p)
            l_ia = get_ia(final_p)
            if len(f_ia) != len(l_ia):
                stage_changes.append({
                    "field": "identification_assumptions_count",
                    "before": len(f_ia),
                    "after": len(l_ia),
                })
        elif stage == "S3":
            f_c = first_p.get("conclusion", {}) or {}
            l_c = final_p.get("conclusion", {}) or {}
            f_str = f_c.get("strength")
            l_str = l_c.get("strength")
            if f_str != l_str:
                stage_changes.append({
                    "field": "strength",
                    "before": f_str,
                    "after": l_str,
                })
            f_jud = {j.get("id"): j.get("decision") for j in f_c.get("hypothesis_judgments", []) or []}
            l_jud = {j.get("id"): j.get("decision") for j in l_c.get("hypothesis_judgments", []) or []}
            for hid in sorted(set(list(f_jud.keys()) + list(l_jud.keys()))):
                if f_jud.get(hid) != l_jud.get(hid):
                    stage_changes.append({
                        "field": f"{hid}.decision",
                        "before": f_jud.get(hid),
                        "after": l_jud.get(hid),
                    })

        if stage_changes:
            changes[stage] = {
                "retries": len(attempts) - 1,
                "changes": stage_changes,
            }
    return changes


def analyze_all() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ng_counts": {m: {s: {"total_ng": 0, "cases": []} for s in SUPERVISED_STAGES} for m in METHODS_WITH_SUPERVISOR},
        "issue_classification": {m: {"general_quality": 0, "causal_specific": 0, "examples": []} for m in METHODS_WITH_SUPERVISOR},
        "designer_changes": {m: {} for m in METHODS_WITH_SUPERVISOR},
    }
    for method in METHODS_WITH_SUPERVISOR:
        for case in CASES:
            run_file = find_run_file(case, method)
            if run_file is None:
                continue
            stage_data = extract_supervisor_logs(run_file)

            ngs = count_ng_per_stage(stage_data)
            for stage, n in ngs.items():
                if n > 0:
                    out["ng_counts"][method][stage]["total_ng"] += n
                    out["ng_counts"][method][stage]["cases"].append(case)

            issues = collect_ng_issues(stage_data)
            for issue in issues:
                cat = issue["category"]
                out["issue_classification"][method][cat] += 1
                if len(out["issue_classification"][method]["examples"]) < 8:
                    out["issue_classification"][method]["examples"].append({
                        "case": case,
                        "stage": issue["stage"],
                        "category": cat,
                        "issue": issue["issue"][:200],
                    })

            changes = diff_designer_attempts(stage_data)
            if changes:
                out["designer_changes"][method][case] = changes
    return out


def main():
    parser = argparse.ArgumentParser(description="Supervisor analysis (no API)")
    parser.add_argument("--out", default="eval_outputs_v2/supervisor_analysis.json")
    args = parser.parse_args()

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_all()
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Analysis written to {out_file}\n")
    print("=== NG Counts by Stage ===")
    for method in METHODS_WITH_SUPERVISOR:
        print(f"\n  {method}:")
        for stage in SUPERVISED_STAGES:
            d = result["ng_counts"][method][stage]
            print(f"    {stage}: total_ng={d['total_ng']:3d}  cases={d['cases']}")

    print("\n=== Issue Classification ===")
    for method in METHODS_WITH_SUPERVISOR:
        c = result["issue_classification"][method]
        total = c["general_quality"] + c["causal_specific"]
        print(f"  {method}: general={c['general_quality']:3d}  causal_specific={c['causal_specific']:3d}  total={total:3d}")

    print("\n=== Designer Changes (case count where Designer changed after retry) ===")
    for method in METHODS_WITH_SUPERVISOR:
        cases = result["designer_changes"][method]
        print(f"  {method}: {len(cases)} cases changed")
        for case_id, change in list(cases.items())[:6]:
            stages = list(change.keys())
            print(f"    {case_id}: stages {stages}")


if __name__ == "__main__":
    main()
