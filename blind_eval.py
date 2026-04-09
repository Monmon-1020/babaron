#!/usr/bin/env python3
"""
Blind evaluation script for the 4-condition oversight protocol experiment.

For each (case, method), this script extracts the S1 hypotheses and S3 judgments
from the run log, and asks an LLM (with NO knowledge of the research context) to
match them against the gold standard hypotheses by semantic content.

The LLM is told only that two analyses are being compared. It is not told:
- That this is an evaluation of an oversight protocol
- That one analysis is the "correct" answer
- The names of the protocols, papers, or authors
- Which analysis came from which method
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASES = [
    "orben_przybylski_2019",
    "twenge_2018",
    "cheng_hoekstra",
    "voight_hdl",
    "chen_huairiver",
    "angrist_krueger_1991",
]

METHODS = ["baseline", "scaffold_only", "rubric_only", "proposed"]


BLIND_PROMPT_TEMPLATE = """あなたは二つの因果推論分析結果を比較する評価者です。
研究の背景や目的は知る必要はありません。
純粋に、二つの分析が同じ因果的主張について同じ判定をしているかを比較してください。

【分析A】（参照分析）
以下の仮説と「許容される判定（acceptable_decisions）」が与えられています。
分析Bの判定がこの許容リストに含まれていれば一致とみなします。

{analysis_a_hypotheses}

結論の強さの許容範囲: {strength_a_acceptable}

【分析B】（評価対象）
以下の仮説と判定が与えられています。

{analysis_b_hypotheses}

結論の強さ: {strength_b}

【タスク】
分析Aの各仮説について、分析Bの中に同じ因果的主張を述べている仮説があるかを判定してください。

「同じ因果的主張」とは、処置（原因）と結果の方向が一致しており、本質的に同じことを主張していることを意味します。表現の違いや詳細度の違いは無視してください。

判定の一致は、分析Bの判定が分析Aの「許容される判定」リストのいずれかに含まれていればtrue、そうでなければfalseとします。対応する仮説が見つからない場合（matched_b_id が null）は decision_match を false にしてください。

以下のJSON形式で回答してください。
{{
  "matches": [
    {{
      "analysis_a_id": "G1",
      "analysis_a_statement": "...",
      "matched_b_id": "H1 or null",
      "matched_b_statement": "...",
      "match_confidence": "high/medium/low",
      "match_reasoning": "なぜ同じ主張と判断したか（1文）",
      "a_acceptable": ["survive", "hold"],
      "b_decision": "survive or null",
      "decision_match": true
    }}
  ],
  "strength_a_acceptable": ["weak"],
  "strength_b": "weak",
  "strength_match": true,
  "unmatched_b_hypotheses": ["分析Bにあるが分析Aに対応がない仮説のID"]
}}

JSONのみを返してください。
"""


# ---------------------------------------------------------------------------
# Extraction from run logs
# ---------------------------------------------------------------------------

def find_run_file(case_id: str, method: str) -> Optional[Path]:
    """Find the run log file for a given case and method, preferring v2/v3."""
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


def extract_s1_s3(run_file: Path) -> Tuple[List[Dict], Dict]:
    """Extract S1 hypotheses and S3 conclusion from the run log.
    Returns the LAST successful S1 designer output and S3 designer output."""
    last_s1 = None
    last_s3 = None
    with run_file.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("status") != "success":
                continue
            if row.get("role") != "designer":
                continue
            stage = row.get("stage")
            parsed = row.get("parsed", {})
            if stage == "S1" and isinstance(parsed, dict):
                last_s1 = parsed
            elif stage == "S3" and isinstance(parsed, dict):
                last_s3 = parsed

    hypotheses = []
    if last_s1:
        for h in last_s1.get("hypotheses", []):
            if isinstance(h, dict):
                hypotheses.append({
                    "id": h.get("id", "?"),
                    "statement": h.get("statement", ""),
                })

    conclusion = {}
    if last_s3:
        c = last_s3.get("conclusion", {})
        if isinstance(c, dict):
            judgments = []
            for j in c.get("hypothesis_judgments", []):
                if isinstance(j, dict):
                    judgments.append({
                        "id": j.get("id", "?"),
                        "decision": j.get("decision", "?"),
                    })
            conclusion = {
                "judgments": judgments,
                "strength": c.get("strength", "?"),
            }

    return hypotheses, conclusion


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

class BlindEvalClient:
    def __init__(self, model: str = "gpt-4o", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")

        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)

    def evaluate(self, prompt: str) -> str:
        token_param = (
            {"max_completion_tokens": 4096}
            if self.model.startswith("gpt-5") or self.model.startswith("o")
            else {"max_tokens": 4096}
        )
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            **token_param,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise comparison evaluator. Return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return (response.choices[0].message.content or "").strip()


def parse_json_response(text: str) -> Optional[Dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


# ---------------------------------------------------------------------------
# Format hypotheses for the prompt
# ---------------------------------------------------------------------------

def format_gold_hypotheses(gold: Dict) -> str:
    lines = []
    for h in gold["hypotheses"]:
        acceptable = h.get("acceptable_decisions", [h.get("expected_decision", "?")])
        lines.append(f"  {h['id']}: {h['statement']}")
        lines.append(f"     許容される判定: {acceptable}")
    return "\n".join(lines)


def format_b_hypotheses(s1_hyps: List[Dict], s3_judgments: List[Dict]) -> str:
    decision_map = {j["id"]: j["decision"] for j in s3_judgments}
    lines = []
    for h in s1_hyps:
        decision = decision_map.get(h["id"], "?")
        lines.append(f"  {h['id']}: {h['statement']}")
        lines.append(f"     判定: {decision}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main evaluation flow
# ---------------------------------------------------------------------------

def evaluate_single(
    client: BlindEvalClient,
    case_id: str,
    method: str,
    gold: Dict,
    out_dir: Path,
) -> Optional[Dict]:
    """Evaluate one (case, method) pair via blind LLM matching."""
    run_file = find_run_file(case_id, method)
    if run_file is None:
        print(f"  [SKIP] no run file for {case_id} / {method}")
        return None

    s1_hyps, s3_concl = extract_s1_s3(run_file)
    if not s1_hyps or not s3_concl:
        print(f"  [SKIP] empty S1 or S3 for {case_id} / {method}")
        return None

    acceptable_strengths = gold.get("acceptable_strengths", [gold.get("expected_strength", "weak")])
    prompt = BLIND_PROMPT_TEMPLATE.format(
        analysis_a_hypotheses=format_gold_hypotheses(gold),
        strength_a_acceptable=acceptable_strengths,
        analysis_b_hypotheses=format_b_hypotheses(s1_hyps, s3_concl["judgments"]),
        strength_b=s3_concl["strength"],
    )

    raw = client.evaluate(prompt)
    parsed = parse_json_response(raw)

    # Post-process: re-compute decision_match and strength_match using
    # acceptable lists from gold (override LLM judgment for safety)
    if parsed:
        gold_acceptable_map = {h["id"]: h.get("acceptable_decisions", [h.get("expected_decision")])
                               for h in gold["hypotheses"]}
        for m in parsed.get("matches", []):
            gid = m.get("analysis_a_id")
            b_dec = m.get("b_decision")
            acceptable = gold_acceptable_map.get(gid, [])
            m["a_acceptable"] = acceptable
            if b_dec is None or m.get("matched_b_id") is None:
                m["decision_match"] = False
            else:
                m["decision_match"] = b_dec in acceptable

        b_strength = parsed.get("strength_b", s3_concl.get("strength"))
        parsed["strength_b"] = b_strength
        parsed["strength_a_acceptable"] = acceptable_strengths
        parsed["strength_match"] = b_strength in acceptable_strengths

    result = {
        "case_id": case_id,
        "method": method,
        "run_file": str(run_file),
        "prompt": prompt,
        "raw_response": raw,
        "parsed": parsed,
    }

    if parsed:
        # Compute summary stats
        matches = parsed.get("matches", [])
        gold_count = len(gold["hypotheses"])
        matched = sum(1 for m in matches if m.get("matched_b_id"))
        agreed = sum(1 for m in matches if m.get("decision_match") is True)
        disagreed = sum(1 for m in matches if m.get("decision_match") is False)
        absent = gold_count - matched
        result["summary"] = {
            "gold_count": gold_count,
            "matched": matched,
            "agreed": agreed,
            "disagreed": disagreed,
            "absent": absent,
            "strength_match": parsed.get("strength_match", False),
            "agreement_rate": f"{agreed}/{gold_count}",
        }

    out_file = out_dir / f"blind_eval_{case_id}_{method}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {out_file.name}: {result.get('summary', {}).get('agreement_rate', 'parse_error')}")
    return result


def aggregate(out_dir: Path, gold_file: Path) -> Dict:
    """Aggregate all blind_eval_*.json files into a summary.

    Aggregates both decision-level matches and strength matches separately,
    plus a combined total.
    """
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
            f = out_dir / f"blind_eval_{case_id}_{method}.json"
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
        # Combined: each case contributes (gold_count + 1) points
        combined_total = agg["total_gold"] + agg["total_cases"]
        combined_agreed = agg["total_agreed"] + agg["strength_agreed"]
        if combined_total > 0:
            agg["combined_rate_str"] = f"{combined_agreed}/{combined_total}"
            agg["combined_fraction"] = round(combined_agreed / combined_total, 3)

    return {"summary": summary_rows, "aggregate": aggregate_by_method}


def main():
    parser = argparse.ArgumentParser(description="Blind evaluation of 4-condition oversight protocol experiment")
    parser.add_argument("--model", default="gpt-4o", help="LLM model for blind matching")
    parser.add_argument("--case", default="all", help="Case ID or 'all'")
    parser.add_argument("--method", default="all", help="Method or 'all'")
    parser.add_argument("--out", default="eval_outputs", help="Output directory")
    parser.add_argument("--gold", default="gold_standards.json", help="Gold standards file")
    parser.add_argument("--summary", action="store_true", help="Just aggregate existing results")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    gold_file = Path(args.gold)

    if args.summary:
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
        return

    with gold_file.open("r", encoding="utf-8") as f:
        gold_all = json.load(f)

    cases = CASES if args.case == "all" else [args.case]
    methods = METHODS if args.method == "all" else [args.method]

    client = BlindEvalClient(model=args.model)

    all_prompts = {}
    for case_id in cases:
        gold = gold_all.get(case_id)
        if not gold:
            print(f"[SKIP] no gold standard for {case_id}")
            continue
        print(f"\n=== {case_id} ===")
        for method in methods:
            result = evaluate_single(client, case_id, method, gold, out_dir)
            if result:
                all_prompts[f"{case_id}_{method}"] = result.get("prompt", "")

    # Save all prompts for reproducibility
    prompts_file = out_dir / "blind_eval_prompts.json"
    prompts_file.write_text(json.dumps(all_prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPrompts saved to {prompts_file}")

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
