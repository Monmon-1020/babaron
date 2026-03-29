#!/usr/bin/env python3
"""
3-Layer Oversight Protocol Runner for Observational Causal Inference.

Layer 1: Process-level protocol  (S0 → S1 → S2 → S2-EVID → S3)
Layer 2: Operationalized rubric  (Explicit / Partial / Absent)
Layer 3: Audit implementation    (Mechanical Checks + Supervisor)
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from llm_client import LLMClient
from prompt_store import PromptStore
from rubric import evaluate_full, format_rubric_report
from schemas import (
    normalize_designer_payload,
    normalize_supervisor,
    parse_json_object,
    validate_designer,
    validate_evidence,
    validate_supervisor,
)


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def summarize(value: Any, max_len: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = " ".join(text.split())
    return text[:max_len]


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def log_step(
    out_path: Path,
    run_id: str,
    case_id: str,
    stage: str,
    attempt: int,
    role: str,
    input_summary: Any,
    raw_output: str,
    parsed: Optional[Dict[str, Any]],
    status: str,
) -> None:
    append_jsonl(
        out_path,
        {
            "run_id": run_id,
            "case_id": case_id,
            "stage": stage,
            "attempt": attempt,
            "role": role,
            "input_summary": summarize(input_summary),
            "raw_output": raw_output,
            "parsed": parsed,
            "status": status,
        },
    )


def _extend_unique(dst: List[str], src: List[str]) -> List[str]:
    for item in src:
        if item not in dst:
            dst.append(item)
    return dst


# ---------------------------------------------------------------------------
# Layer 3: Mechanical Checks (deterministic consistency checks)
# ---------------------------------------------------------------------------

def run_mechanical_checks(
    *, stage: str, parsed_designer: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Deterministic consistency checks independent from LLM supervisor output."""
    fatal: List[str] = []
    minor: List[str] = []
    fix: List[str] = []

    s1 = context.get("S1", {}) if isinstance(context.get("S1"), dict) else {}
    s1_hyps = s1.get("hypotheses", []) if isinstance(s1.get("hypotheses"), list) else []
    s1_ids = [h.get("id") for h in s1_hyps if isinstance(h, dict) and isinstance(h.get("id"), str)]

    if stage == "S2":
        plan = parsed_designer.get("experiment_plan", {})
        rules = plan.get("hypothesis_rules", []) if isinstance(plan, dict) else []
        if not isinstance(rules, list) or not rules:
            fatal.append("S2: hypothesis_rules が空、または形式不正。")
            fix.append("S2で各仮説に対し accept_if/reject_if/hold_if を必ず定義してください。")
            return {"fatal_issues": fatal, "minor_issues": minor, "fix_instructions": fix}

        rule_ids = [r["id"] for r in rules if isinstance(r, dict) and isinstance(r.get("id"), str)]
        missing = [hid for hid in s1_ids if hid not in rule_ids]
        extra = [rid for rid in rule_ids if rid not in s1_ids]
        if missing:
            fatal.append(f"S2: hypothesis_rules に不足IDがあります: {', '.join(missing)}")
            fix.append("S1で定義した全仮説IDを hypothesis_rules に含めてください。")
        if extra:
            minor.append(f"S2: S1にない仮説IDが hypothesis_rules に含まれます: {', '.join(extra)}")
            fix.append("hypothesis_rules のIDを S1 の仮説IDと一致させてください。")

        # Check identification assumptions exist
        assumptions = plan.get("identification_assumptions", []) if isinstance(plan, dict) else []
        if not isinstance(assumptions, list) or not assumptions:
            fatal.append("S2: identification_assumptions が空です。")
            fix.append("識別仮定を少なくとも1つ以上定義してください。")

        return {"fatal_issues": fatal, "minor_issues": minor, "fix_instructions": fix}

    if stage != "S3":
        return {"fatal_issues": fatal, "minor_issues": minor, "fix_instructions": fix}

    # S3 checks
    conclusion = parsed_designer.get("conclusion", {})
    judgments = conclusion.get("hypothesis_judgments", [])
    if not isinstance(judgments, list) or not judgments:
        fatal.append("S3: hypothesis_judgments が空、または形式不正。")
        fix.append("仮説ごとに判定表を作成してください。")
        return {"fatal_issues": fatal, "minor_issues": minor, "fix_instructions": fix}

    s2_evid = context.get("s2_evidence", {})
    findings = s2_evid.get("findings", []) if isinstance(s2_evid, dict) else []
    valid_evidence_ids = {
        f.get("id") for f in findings if isinstance(f, dict) and isinstance(f.get("id"), str)
    }
    not_observed = s2_evid.get("not_observed", []) if isinstance(s2_evid, dict) else []

    seen_ids = set()
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in judgments:
        hid = item.get("id")
        if not isinstance(hid, str):
            continue
        if hid in seen_ids:
            fatal.append(f"S3: 同一仮説IDが重複しています: {hid}")
        seen_ids.add(hid)
        by_id[hid] = item

    missing_h = [hid for hid in s1_ids if hid not in by_id]
    if missing_h:
        fatal.append(f"S3: 判定表に不足している仮説IDがあります: {', '.join(missing_h)}")
        fix.append("S1で定義した全仮説について hypothesis_judgments を作成してください。")

    for hid, item in by_id.items():
        decision = item.get("decision")
        evidence_ids = item.get("evidence_ids", [])
        falsify_triggered = item.get("falsify_triggered")
        accept_met = item.get("accept_condition_met")
        reject_met = item.get("reject_condition_met")
        hold_met = item.get("hold_condition_met")

        if decision in ("survive", "reject") and isinstance(evidence_ids, list) and not evidence_ids:
            fatal.append(f"S3: {hid} は {decision} 判定なのに evidence_ids が空です。")
            fix.append("survive/reject には必ず根拠となる evidence_ids を付与してください。")

        if isinstance(evidence_ids, list):
            unknown_eids = [eid for eid in evidence_ids if eid not in valid_evidence_ids]
            if unknown_eids:
                fatal.append(f"S3: {hid} に未知の evidence_id があります: {', '.join(unknown_eids)}")
                fix.append("evidence_ids は S2-EVID の findings.id のみ使用してください。")

        if all(isinstance(v, bool) for v in [accept_met, reject_met, hold_met]):
            true_count = sum([accept_met, reject_met, hold_met])
            if true_count != 1:
                fatal.append(f"S3: {hid} の条件一致フラグはちょうど1つだけ true にしてください。")
                fix.append("accept_condition_met/reject_condition_met/hold_condition_met を排他的に設定してください。")
            if decision == "survive" and (not accept_met or reject_met):
                fatal.append(f"S3: {hid} は survive なのに条件一致フラグが不整合です。")
            if decision == "reject" and not reject_met:
                fatal.append(f"S3: {hid} は reject なのに reject_condition_met が false です。")
            if decision == "hold" and not hold_met:
                fatal.append(f"S3: {hid} は hold なのに hold_condition_met が false です。")
        else:
            fatal.append(f"S3: {hid} の条件一致フラグが不足、または型不正です。")
            fix.append("各仮説に3つの条件一致フラグ（bool）を必ず出力してください。")

        if falsify_triggered is True and decision != "reject":
            fatal.append(f"S3: {hid} は反証発火なのに reject されていません。")
            fix.append("falsify_triggered=true の仮説は reject にしてください。")

    declared_survive = set(conclusion.get("which_hypotheses_survive", []))
    declared_reject = set(conclusion.get("which_rejected", []))
    computed_survive = {hid for hid, item in by_id.items() if item.get("decision") == "survive"}
    computed_reject = {hid for hid, item in by_id.items() if item.get("decision") == "reject"}
    if declared_survive != computed_survive:
        fatal.append("S3: which_hypotheses_survive が判定表と一致していません。")
        fix.append("which_hypotheses_survive を hypothesis_judgments の survive 判定と一致させてください。")
    if declared_reject != computed_reject:
        fatal.append("S3: which_rejected が判定表と一致していません。")
        fix.append("which_rejected を hypothesis_judgments の reject 判定と一致させてください。")

    strength = conclusion.get("strength")
    any_hold = any(item.get("decision") == "hold" for item in by_id.values())
    all_hold = by_id and all(item.get("decision") == "hold" for item in by_id.values())
    if strength == "strong" and any_hold:
        fatal.append("S3: hold 判定があるのに strength=strong は不可です。")
        fix.append("hold が1つでもある場合は strength を weak か hold に下げてください。")
    if strength == "strong" and isinstance(not_observed, list) and len(not_observed) > 0:
        fatal.append("S3: 主要未観測があるため strength=strong は不可です。")
        fix.append("not_observed が残る場合は strength を weak/hold にしてください。")
    if all_hold and strength != "hold":
        fatal.append("S3: 全仮説holdなら strength は hold にしてください。")

    # Check remaining_alternatives exists
    remaining = conclusion.get("remaining_alternatives", [])
    if not isinstance(remaining, list) or not remaining:
        minor.append("S3: remaining_alternatives が空です。")
        fix.append("残存する代替説明を少なくとも1つ記述してください。")

    return {"fatal_issues": fatal, "minor_issues": minor, "fix_instructions": fix}


# ---------------------------------------------------------------------------
# Designer + Supervisor loop (Layer 3)
# ---------------------------------------------------------------------------

def run_designer_with_supervisor(
    *,
    run_id: str,
    case_id: str,
    stage: str,
    prompt_profile: str,
    max_retry: int,
    client: LLMClient,
    prompts: PromptStore,
    out_path: Path,
    context: Dict[str, Any],
) -> bool:
    """Run one stage with supervisor checks and retry loop."""
    check_stage = f"{stage}-CHK"
    feedback: List[str] = []
    previous_designer_output: Optional[Dict[str, Any]] = None
    previous_supervisor_review: Optional[Dict[str, Any]] = None

    for attempt in range(max_retry + 1):
        designer_input = {
            "case_id": case_id,
            "stage": stage,
            "attempt": attempt,
            "feedback": feedback,
            "previous_designer_output": previous_designer_output,
            "previous_supervisor_review": previous_supervisor_review,
            "context": context,
        }
        raw_designer = client.generate(
            role="designer",
            stage=stage,
            prompt_text=prompts.get("designer", stage, profile=prompt_profile),
            context=designer_input,
            attempt=attempt,
        )
        parsed_designer, parse_err = parse_json_object(raw_designer)
        if parse_err:
            log_step(out_path, run_id, case_id, stage, attempt, "designer",
                     designer_input, raw_designer, None, "parse_error")
            return False

        parsed_designer = normalize_designer_payload(stage, parsed_designer)
        val_err = validate_designer(stage, parsed_designer)
        if val_err:
            log_step(out_path, run_id, case_id, stage, attempt, "designer",
                     designer_input, raw_designer, parsed_designer, f"schema_error:{val_err}")
            return False

        log_step(out_path, run_id, case_id, stage, attempt, "designer",
                 designer_input, raw_designer, parsed_designer, "success")
        previous_designer_output = parsed_designer

        # Supervisor review
        supervisor_input = {
            "case_id": case_id,
            "stage": check_stage,
            "attempt": attempt,
            "designer_output": parsed_designer,
            "context": context,
        }
        raw_supervisor = client.generate(
            role="supervisor",
            stage=check_stage,
            prompt_text=prompts.get("supervisor", check_stage, profile=prompt_profile),
            context=supervisor_input,
            attempt=attempt,
        )
        parsed_supervisor, parse_err = parse_json_object(raw_supervisor)
        if parse_err:
            log_step(out_path, run_id, case_id, check_stage, attempt, "supervisor",
                     supervisor_input, raw_supervisor, None, "parse_error")
            return False

        parsed_supervisor = normalize_supervisor(parsed_supervisor)
        val_err = validate_supervisor(parsed_supervisor)
        if val_err:
            log_step(out_path, run_id, case_id, check_stage, attempt, "supervisor",
                     supervisor_input, raw_supervisor, parsed_supervisor, f"schema_error:{val_err}")
            return False

        # Mechanical checks (Layer 3)
        mech = run_mechanical_checks(stage=stage, parsed_designer=parsed_designer, context=context)
        fatal_mech = mech.get("fatal_issues", [])
        minor_mech = mech.get("minor_issues", [])
        fix_mech = mech.get("fix_instructions", [])
        if fatal_mech or minor_mech:
            parsed_supervisor["fatal_issues"] = _extend_unique(
                list(parsed_supervisor.get("fatal_issues", [])), list(fatal_mech))
            parsed_supervisor["minor_issues"] = _extend_unique(
                list(parsed_supervisor.get("minor_issues", [])), list(minor_mech))
            parsed_supervisor["issues"] = _extend_unique(
                list(parsed_supervisor.get("issues", [])), list(fatal_mech) + list(minor_mech))
            parsed_supervisor["fix_instructions"] = _extend_unique(
                list(parsed_supervisor.get("fix_instructions", [])), list(fix_mech))
            if fatal_mech:
                parsed_supervisor["verdict"] = "NG"

        verdict = parsed_supervisor.get("verdict")
        fatal_issues = parsed_supervisor.get("fatal_issues", []) or []
        minor_issues = parsed_supervisor.get("minor_issues", []) or []

        # Safety valve: NG with only minor issues → pass
        if verdict == "NG" and not fatal_issues and minor_issues:
            parsed_supervisor["verdict"] = "OK"
            verdict = "OK"
            parsed_supervisor["pass_requirements"] = list(
                parsed_supervisor.get("pass_requirements", [])
            ) + ["軽微指摘のみのため通過（次ステージで改善継続）"]

        if verdict == "OK":
            log_step(out_path, run_id, case_id, check_stage, attempt, "supervisor",
                     supervisor_input, raw_supervisor, parsed_supervisor, "success")
            context[stage] = parsed_designer
            context[check_stage] = parsed_supervisor
            return True

        if attempt >= max_retry:
            log_step(out_path, run_id, case_id, check_stage, attempt, "supervisor",
                     supervisor_input, raw_supervisor, parsed_supervisor, "stop_by_max_retry")
            return False

        log_step(out_path, run_id, case_id, check_stage, attempt, "supervisor",
                 supervisor_input, raw_supervisor, parsed_supervisor, "retry_required")
        previous_supervisor_review = parsed_supervisor
        feedback = parsed_supervisor.get("fix_instructions", [])

    return False


def run_designer_only(
    *,
    run_id: str,
    case_id: str,
    stage: str,
    prompt_profile: str,
    max_retry: int,
    client: LLMClient,
    prompts: PromptStore,
    out_path: Path,
    context: Dict[str, Any],
) -> bool:
    """Baseline mode: no supervisor loop."""
    feedback: List[str] = []
    previous_designer_output: Optional[Dict[str, Any]] = None

    for attempt in range(max_retry + 1):
        designer_input = {
            "case_id": case_id,
            "stage": stage,
            "attempt": attempt,
            "feedback": feedback,
            "previous_designer_output": previous_designer_output,
            "context": context,
        }
        raw_designer = client.generate(
            role="designer",
            stage=stage,
            prompt_text=prompts.get("designer", stage, profile=prompt_profile),
            context=designer_input,
            attempt=attempt,
        )
        parsed_designer, parse_err = parse_json_object(raw_designer)
        if parse_err:
            if attempt >= max_retry:
                log_step(out_path, run_id, case_id, stage, attempt, "designer",
                         designer_input, raw_designer, None, "stop_by_max_retry")
                return False
            log_step(out_path, run_id, case_id, stage, attempt, "designer",
                     designer_input, raw_designer, None, "parse_error")
            feedback = ["JSONとして解釈できません。必ず指定スキーマのJSONのみを返してください。"]
            continue

        parsed_designer = normalize_designer_payload(stage, parsed_designer)
        val_err = validate_designer(stage, parsed_designer)
        if val_err:
            if attempt >= max_retry:
                log_step(out_path, run_id, case_id, stage, attempt, "designer",
                         designer_input, raw_designer, parsed_designer, "stop_by_max_retry")
                return False
            log_step(out_path, run_id, case_id, stage, attempt, "designer",
                     designer_input, raw_designer, parsed_designer, f"schema_error:{val_err}")
            feedback = [f"スキーマ違反({val_err})です。指定された必須キーと型を満たすJSONを返してください。"]
            previous_designer_output = parsed_designer
            continue

        log_step(out_path, run_id, case_id, stage, attempt, "designer",
                 designer_input, raw_designer, parsed_designer, "success")
        context[stage] = parsed_designer
        return True

    return False


# ---------------------------------------------------------------------------
# Case runner
# ---------------------------------------------------------------------------

def run_case(
    *,
    run_id: str,
    case_id: str,
    case_payload: Dict[str, Any],
    method: str,
    max_retry: int,
    client: LLMClient,
    prompts: PromptStore,
    out_path: Path,
) -> bool:
    context: Dict[str, Any] = {}

    # S0: initial context
    s0 = case_payload.get("S0", {"text": "", "notes": []})
    err = validate_evidence(s0, stage="S0")
    if err:
        log_step(out_path, run_id, case_id, "S0", 0, "evidence",
                 {"source": "cases.json"}, json.dumps(s0, ensure_ascii=False), s0, f"schema_error:{err}")
        return False

    context["s0"] = s0
    log_step(out_path, run_id, case_id, "S0", 0, "evidence",
             {"source": "cases.json"}, json.dumps(s0, ensure_ascii=False), s0, "success")

    prompt_profile = "baseline" if method == "baseline" else "proposed"

    run_stage = run_designer_only if method == "baseline" else run_designer_with_supervisor

    # S1
    if not run_stage(
        run_id=run_id, case_id=case_id, stage="S1",
        prompt_profile=prompt_profile, max_retry=max_retry,
        client=client, prompts=prompts, out_path=out_path, context=context,
    ):
        return False

    # S2
    if not run_stage(
        run_id=run_id, case_id=case_id, stage="S2",
        prompt_profile=prompt_profile, max_retry=max_retry,
        client=client, prompts=prompts, out_path=out_path, context=context,
    ):
        return False

    # S2-EVID
    s2e = case_payload.get("S2_EVID", {"findings": []})
    err = validate_evidence(s2e, stage="S2-EVID")
    if err:
        log_step(out_path, run_id, case_id, "S2-EVID", 0, "evidence",
                 {"source": "cases.json"}, json.dumps(s2e, ensure_ascii=False), s2e, f"schema_error:{err}")
        return False

    context["s2_evidence"] = s2e
    log_step(out_path, run_id, case_id, "S2-EVID", 0, "evidence",
             {"source": "cases.json"}, json.dumps(s2e, ensure_ascii=False), s2e, "success")

    # S3
    if not run_stage(
        run_id=run_id, case_id=case_id, stage="S3",
        prompt_profile=prompt_profile, max_retry=max_retry,
        client=client, prompts=prompts, out_path=out_path, context=context,
    ):
        return False

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3-Layer Oversight Protocol Runner")
    parser.add_argument("--case", default="all", help="Case ID or 'all'")
    parser.add_argument("--max_retry", type=int, default=2)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--method", choices=["baseline", "proposed"], default="proposed")
    parser.add_argument("--out", default=None, help="Output JSONL path")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--rubric", action="store_true", help="Run Layer 2 rubric evaluation after completion")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_path = Path(args.out) if args.out else Path(f"outputs/run_{now_ts()}.jsonl")

    with Path("cases.json").open("r", encoding="utf-8") as f:
        cases = json.load(f)

    if args.case == "all":
        case_ids = list(cases.keys())
    else:
        case_ids = [args.case]

    client = LLMClient(mock=args.mock, model=args.model, temperature=0.0)
    prompts = PromptStore("prompts")

    success_count = 0
    all_contexts: Dict[str, Dict[str, Any]] = {}

    for case_id in case_ids:
        if case_id not in cases:
            print(f"Case '{case_id}' not found in cases.json. Skipping.")
            continue
        run_id = str(uuid.uuid4())

        # We need to capture context for rubric evaluation
        context_holder: Dict[str, Any] = {}

        # Patch run_case to capture context
        case_payload = cases[case_id]
        ok = run_case(
            run_id=run_id,
            case_id=case_id,
            case_payload=case_payload,
            method=args.method,
            max_retry=max(0, args.max_retry),
            client=client,
            prompts=prompts,
            out_path=out_path,
        )

        if ok:
            success_count += 1

            # Reconstruct context from output for rubric evaluation
            if args.rubric:
                ctx = _reconstruct_context(out_path, run_id)
                all_contexts[case_id] = ctx

    print(f"Done. success={success_count}/{len(case_ids)} out={out_path}")

    # Layer 2: Rubric evaluation
    if args.rubric and all_contexts:
        print("\n" + "=" * 60)
        print("Layer 2: Rubric Evaluation")
        print("=" * 60)
        for case_id, ctx in all_contexts.items():
            print(f"\n### Case: {case_id}")
            results = evaluate_full(ctx)
            print(format_rubric_report(results))


def _reconstruct_context(out_path: Path, run_id: str) -> Dict[str, Any]:
    """Reconstruct context from JSONL output for rubric evaluation."""
    context: Dict[str, Any] = {}
    with out_path.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("run_id") != run_id:
                continue
            if row.get("status") != "success":
                continue
            parsed = row.get("parsed")
            if not isinstance(parsed, dict):
                continue
            stage = row.get("stage", "")
            role = row.get("role", "")
            if stage == "S0" and role == "evidence":
                context["s0"] = parsed
            elif stage == "S1" and role == "designer":
                context["S1"] = parsed
            elif stage == "S2" and role == "designer":
                context["S2"] = parsed
            elif stage == "S3" and role == "designer":
                context["S3"] = parsed
    return context


if __name__ == "__main__":
    main()
