#!/usr/bin/env python3
"""
Process-level evaluation (評価B): Detect whether the protocol output mentions
specific methodological concerns identified by subsequent literature.

For each (case, method) pair, we extract the relevant fields from the run log
and ask a blind LLM whether each checkpoint question is addressed in the output.

The LLM is told NOTHING about:
- The research goal (oversight protocol comparison)
- Which condition the output came from
- Whether the answer "should" be yes or no

strength checkpoints are evaluated mechanically (no LLM): "yes" iff strength != "strong".
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CASES = [
    "web_browsing_mood",
    "orben_przybylski_2019",
    "twenge_2018",
    "cheng_hoekstra",
    "voight_hdl",
    "chen_huairiver",
]

METHODS = ["baseline", "scaffold_only", "rubric_only", "proposed"]


BLIND_PROMPT_TEMPLATE = """あなたは因果推論の分析出力を評価する評価者です。
研究の背景や目的は知る必要はありません。

以下は、ある因果推論分析の{stage}段階の出力から抽出した内容です。

---
{extracted}
---

質問：この出力の中に、以下の問題への言及がありますか？

「{question}」

以下のJSON形式で回答してください。
{{
  "answer": "yes" または "no",
  "evidence": "yesの場合、出力のどの部分が該当するか（引用または要約）。noの場合、なぜ言及がないと判断したか。",
  "confidence": "high" または "medium" または "low"
}}

注意：
- 完全に同じ表現でなくても、同じ問題について述べていれば "yes" と判定してください。
- 一般的・漠然とした言及ではなく、質問で指定された具体的な問題に対応する内容があるかを判定してください。
- 出力に該当フィールドが存在しない場合は "no" と判定してください。

JSONのみを返してください。
"""


# ---------------------------------------------------------------------------
# Run log discovery and extraction
# ---------------------------------------------------------------------------

def find_run_file(case_id: str, method: str) -> Optional[Path]:
    """Find the latest run log file for a given case and method.
    Priority: v3 > v2 > original; also checks short-name aliases."""
    outputs_dir = Path("outputs")
    aliases = {
        "web_browsing_mood": ["web_browsing_mood", "kelly"],
        "orben_przybylski_2019": ["orben_przybylski_2019", "orben"],
        "twenge_2018": ["twenge_2018", "twenge"],
        "cheng_hoekstra": ["cheng_hoekstra"],
        "voight_hdl": ["voight_hdl"],
        "chen_huairiver": ["chen_huairiver"],
    }
    case_aliases = aliases.get(case_id, [case_id])
    suffixes = ["_v3", "_v2", ""]
    for alias in case_aliases:
        for suf in suffixes:
            p = outputs_dir / f"run_4cond_{method}_{alias}{suf}.jsonl"
            if p.exists():
                return p
    return None


def extract_output(jsonl_path: Path, stage: str, what_to_check: str) -> Any:
    """Extract the LAST successful Designer output for the given stage,
    then return the relevant field based on what_to_check."""
    last_parsed = None
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("stage") != stage:
                continue
            if row.get("role") != "designer":
                continue
            if row.get("status") != "success":
                continue
            parsed = row.get("parsed")
            if isinstance(parsed, dict):
                last_parsed = parsed

    if not last_parsed:
        return None

    if what_to_check == "hypotheses":
        return last_parsed.get("hypotheses", [])
    elif what_to_check == "identification_assumptions":
        # rubric/proposed has it at top level; non-extended has it inside experiment_plan
        ia = last_parsed.get("identification_assumptions", [])
        if not ia:
            plan = last_parsed.get("experiment_plan", {}) or {}
            ia = plan.get("identification_assumptions", [])
        return ia
    elif what_to_check == "experiment_plan":
        return last_parsed.get("experiment_plan", {})
    elif what_to_check == "identification_assumption_concerns":
        conclusion = last_parsed.get("conclusion", {}) or {}
        return {
            "identification_assumption_concerns": conclusion.get("identification_assumption_concerns", []),
            "residual_alternatives": conclusion.get("residual_alternatives", []),
            "remaining_alternatives": conclusion.get("remaining_alternatives", []),
        }
    elif what_to_check == "strength":
        conclusion = last_parsed.get("conclusion", {}) or {}
        return conclusion.get("strength", "")
    elif what_to_check == "conclusion":
        return last_parsed.get("conclusion", {})
    return None


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
            {"max_completion_tokens": 1500}
            if self.model.startswith("gpt-5") or self.model.startswith("o")
            else {"max_tokens": 1500}
        )
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            **token_param,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise evaluator. Return JSON only.",
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


def format_extracted(value: Any, max_chars: int = 4000) -> str:
    """Format extracted output as human-readable JSON for the prompt."""
    if value is None:
        return "(該当フィールドが存在しません)"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)) and not value:
        return "(空)"
    s = json.dumps(value, ensure_ascii=False, indent=2)
    if len(s) > max_chars:
        s = s[:max_chars] + "\n... (truncated)"
    return s


# ---------------------------------------------------------------------------
# Main evaluation flow
# ---------------------------------------------------------------------------

def evaluate_checkpoint(
    client: Optional[BlindEvalClient],
    extracted: Any,
    checkpoint: Dict,
) -> Dict:
    """Evaluate a single checkpoint. Returns the result dict."""
    cp_id = checkpoint["id"]
    stage = checkpoint["stage"]
    what_to_check = checkpoint["what_to_check"]
    question = checkpoint["question"]

    # Mechanical case: strength
    if what_to_check == "strength":
        strength_value = extracted if isinstance(extracted, str) else ""
        is_yes = strength_value != "strong" and strength_value != ""
        return {
            "id": cp_id,
            "stage": stage,
            "what_to_check": what_to_check,
            "question": question,
            "extracted_output": strength_value,
            "answer": "yes" if is_yes else "no",
            "evidence": f"strength={strength_value}",
            "confidence": "high",
            "method_used": "mechanical",
        }

    # No data → automatic no
    if extracted is None or (isinstance(extracted, (list, dict)) and not extracted):
        return {
            "id": cp_id,
            "stage": stage,
            "what_to_check": what_to_check,
            "question": question,
            "extracted_output": "(該当フィールドなし)",
            "answer": "no",
            "evidence": "出力に該当フィールドが存在しないか空である",
            "confidence": "high",
            "method_used": "no_data",
        }

    # LLM judgment
    extracted_str = format_extracted(extracted)
    prompt = BLIND_PROMPT_TEMPLATE.format(
        stage=stage,
        extracted=extracted_str,
        question=question,
    )
    raw = client.evaluate(prompt)
    parsed = parse_json_response(raw)

    if not parsed:
        return {
            "id": cp_id,
            "stage": stage,
            "what_to_check": what_to_check,
            "question": question,
            "extracted_output": extracted_str[:500],
            "answer": "no",
            "evidence": f"parse_error: {raw[:200]}",
            "confidence": "low",
            "method_used": "llm",
            "prompt": prompt,
            "raw_response": raw,
        }

    return {
        "id": cp_id,
        "stage": stage,
        "what_to_check": what_to_check,
        "question": question,
        "extracted_output": extracted_str[:500],
        "answer": parsed.get("answer", "no"),
        "evidence": parsed.get("evidence", ""),
        "confidence": parsed.get("confidence", "medium"),
        "method_used": "llm",
        "prompt": prompt,
        "raw_response": raw,
    }


def evaluate_single(
    client: Optional[BlindEvalClient],
    case_id: str,
    method: str,
    case_def: Dict,
    out_dir: Path,
) -> Optional[Dict]:
    """Evaluate one (case, method) pair against all checkpoints."""
    run_file = find_run_file(case_id, method)
    if run_file is None:
        print(f"  [SKIP] no run file for {case_id} / {method}")
        return None

    checkpoint_results = []
    for cp in case_def["checkpoints"]:
        extracted = extract_output(run_file, cp["stage"], cp["what_to_check"])
        result = evaluate_checkpoint(client, extracted, cp)
        checkpoint_results.append(result)

    yes_count = sum(1 for r in checkpoint_results if r["answer"] == "yes")
    total = len(checkpoint_results)

    output = {
        "case_id": case_id,
        "method": method,
        "run_file": str(run_file),
        "checkpoints": checkpoint_results,
        "summary": {
            "total": total,
            "yes": yes_count,
            "no": total - yes_count,
            "detection_rate": f"{yes_count}/{total}",
        },
    }

    out_file = out_dir / f"process_eval_{case_id}_{method}.json"
    out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {out_file.name}: {yes_count}/{total}")
    return output


def aggregate(out_dir: Path, checkpoints_def: Dict) -> Dict:
    """Aggregate all process_eval_*.json files into a summary."""
    by_method: Dict[str, Dict] = {m: {"total_yes": 0, "total_checkpoints": 0} for m in METHODS}
    by_case: Dict[str, Dict[str, str]] = {}
    by_stage: Dict[str, Dict[str, Dict]] = {
        "S1": {m: {"yes": 0, "total": 0} for m in METHODS},
        "S2": {m: {"yes": 0, "total": 0} for m in METHODS},
        "S3": {m: {"yes": 0, "total": 0} for m in METHODS},
    }

    for case_id in CASES:
        by_case[case_id] = {}
        for method in METHODS:
            f = out_dir / f"process_eval_{case_id}_{method}.json"
            if not f.exists():
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            yes = summary.get("yes", 0)
            total = summary.get("total", 0)
            by_method[method]["total_yes"] += yes
            by_method[method]["total_checkpoints"] += total
            by_case[case_id][method] = f"{yes}/{total}"

            for cp in data.get("checkpoints", []):
                stage = cp.get("stage")
                if stage in by_stage:
                    by_stage[stage][method]["total"] += 1
                    if cp.get("answer") == "yes":
                        by_stage[stage][method]["yes"] += 1

    for m, agg in by_method.items():
        if agg["total_checkpoints"] > 0:
            agg["rate"] = f"{agg['total_yes']}/{agg['total_checkpoints']}"
            agg["fraction"] = round(agg["total_yes"] / agg["total_checkpoints"], 3)

    by_stage_str: Dict[str, Dict[str, str]] = {}
    for stage, methods in by_stage.items():
        by_stage_str[stage] = {}
        for m, d in methods.items():
            by_stage_str[stage][m] = f"{d['yes']}/{d['total']}"

    return {
        "by_method": by_method,
        "by_case": by_case,
        "by_stage": by_stage_str,
    }


def main():
    parser = argparse.ArgumentParser(description="Process-level evaluation (評価B)")
    parser.add_argument("--model", default="gpt-4o", help="LLM model for blind judgment")
    parser.add_argument("--case", default="all", help="Case ID or 'all'")
    parser.add_argument("--method", default="all", help="Method or 'all'")
    parser.add_argument("--out", default="eval_outputs_process", help="Output directory")
    parser.add_argument("--checkpoints", default="detection_checkpoints.json", help="Checkpoints file")
    parser.add_argument("--summary", action="store_true", help="Aggregate existing results")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cp_file = Path(args.checkpoints)

    with cp_file.open("r", encoding="utf-8") as f:
        checkpoints_def = json.load(f)

    if args.summary:
        agg = aggregate(out_dir, checkpoints_def)
        out_file = out_dir / "process_eval_summary.json"
        out_file.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSummary written to {out_file}\n")
        print("=== by method ===")
        for m, a in agg["by_method"].items():
            print(f"  {m:15s} {a.get('rate','—')}  ({a.get('fraction','—')})")
        print("\n=== by stage ===")
        print(f"  {'stage':5s} {'baseline':12s} {'scaffold_only':15s} {'rubric_only':14s} {'proposed':12s}")
        for stage, methods in agg["by_stage"].items():
            print(f"  {stage:5s} "
                  f"{methods.get('baseline','—'):12s} "
                  f"{methods.get('scaffold_only','—'):15s} "
                  f"{methods.get('rubric_only','—'):14s} "
                  f"{methods.get('proposed','—'):12s}")
        return

    cases = CASES if args.case == "all" else [args.case]
    methods = METHODS if args.method == "all" else [args.method]

    client = BlindEvalClient(model=args.model)

    all_prompts: Dict[str, Any] = {}
    for case_id in cases:
        case_def = checkpoints_def.get(case_id)
        if not case_def:
            print(f"[SKIP] no checkpoints for {case_id}")
            continue
        print(f"\n=== {case_id} ===")
        for method in methods:
            result = evaluate_single(client, case_id, method, case_def, out_dir)
            if result:
                for cp in result.get("checkpoints", []):
                    if "prompt" in cp:
                        key = f"{case_id}_{method}_{cp['id']}"
                        all_prompts[key] = {
                            "prompt": cp.get("prompt"),
                            "raw_response": cp.get("raw_response"),
                        }

    prompts_file = out_dir / "process_eval_prompts.json"
    prompts_file.write_text(json.dumps(all_prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPrompts saved to {prompts_file}")

    agg = aggregate(out_dir, checkpoints_def)
    out_file = out_dir / "process_eval_summary.json"
    out_file.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary written to {out_file}\n")
    print("=== by method ===")
    for m, a in agg["by_method"].items():
        print(f"  {m:15s} {a.get('rate','—')}  ({a.get('fraction','—')})")
    print("\n=== by stage ===")
    print(f"  {'stage':5s} {'baseline':12s} {'scaffold_only':15s} {'rubric_only':14s} {'proposed':12s}")
    for stage, methods_d in agg["by_stage"].items():
        print(f"  {stage:5s} "
              f"{methods_d.get('baseline','—'):12s} "
              f"{methods_d.get('scaffold_only','—'):15s} "
              f"{methods_d.get('rubric_only','—'):14s} "
              f"{methods_d.get('proposed','—'):12s}")


if __name__ == "__main__":
    main()
