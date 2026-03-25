"""JSON parsing and lightweight schema validation."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_json_object(raw_output: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    text = (raw_output or "").strip()
    if not text:
        return None, "empty_output"

    # remove markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return None, "json_not_object"
        return parsed, None
    except json.JSONDecodeError:
        pass

    # fallback: first JSON object block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if not isinstance(parsed, dict):
                return None, "json_not_object"
            return parsed, None
        except json.JSONDecodeError:
            return None, "json_decode_error"

    return None, "json_decode_error"


def validate_supervisor(payload: Dict[str, Any]) -> Optional[str]:
    required = ["verdict", "issues", "fix_instructions", "pass_requirements"]
    for key in required:
        if key not in payload:
            return f"missing_key:{key}"

    if payload["verdict"] not in ("OK", "NG"):
        return "invalid_verdict"

    for key in ["issues", "fix_instructions", "pass_requirements"]:
        if not isinstance(payload[key], list):
            return f"invalid_type:{key}"

    return None


def normalize_supervisor(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize supervisor payload to canonical keys:
      verdict / issues / fix_instructions / pass_requirements
    Accepts Japanese key variants:
      判定 / 修正指示 / 合格条件
    """
    out: Dict[str, Any] = dict(payload)

    if "verdict" not in out and "判定" in out:
        out["verdict"] = out.get("判定")
    if "fix_instructions" not in out and "修正指示" in out:
        out["fix_instructions"] = out.get("修正指示")
    if "pass_requirements" not in out and "合格条件" in out:
        out["pass_requirements"] = out.get("合格条件")
    if "issues" not in out:
        out["issues"] = []
    if "fatal_issues" not in out and "致命的指摘" in out:
        out["fatal_issues"] = out.get("致命的指摘")
    if "minor_issues" not in out and "軽微指摘" in out:
        out["minor_issues"] = out.get("軽微指摘")
    if "fatal_issues" not in out:
        out["fatal_issues"] = []
    if "minor_issues" not in out:
        out["minor_issues"] = []

    # Normalize list-like fields
    for key in [
        "issues",
        "fix_instructions",
        "pass_requirements",
        "fatal_issues",
        "minor_issues",
    ]:
        value = out.get(key)
        if isinstance(value, str):
            out[key] = [value]
        elif value is None:
            out[key] = []
        elif not isinstance(value, list):
            out[key] = [str(value)]

    # Keep issues aligned if caller only uses one list.
    if not out.get("issues"):
        out["issues"] = list(out.get("fatal_issues", [])) + list(out.get("minor_issues", []))

    # Normalize verdict variants
    verdict = out.get("verdict")
    if isinstance(verdict, str):
        verdict = verdict.strip()
        if verdict in ("ＯＫ", "ok", "Ok"):
            verdict = "OK"
        if verdict.lower() == "ng":
            verdict = "NG"
        out["verdict"] = verdict

    return out


def validate_designer(stage: str, payload: Dict[str, Any]) -> Optional[str]:
    if stage == "S1":
        hyps = payload.get("hypotheses")
        if not isinstance(hyps, list) or not (2 <= len(hyps) <= 4):
            return "invalid_hypotheses"
        for item in hyps:
            if not isinstance(item, dict):
                return "invalid_hypothesis_item"
            for key in ["id", "statement", "falsify", "distinctive_prediction"]:
                if not isinstance(item.get(key), str) or not item.get(key).strip():
                    return f"invalid_hypothesis_field:{key}"
        return None

    if stage == "S2":
        plan = payload.get("experiment_plan")
        if not isinstance(plan, dict):
            return "invalid_experiment_plan"
        for key in ["what_to_compare", "what_to_measure", "procedure", "decision_rule", "checks"]:
            if key not in plan:
                return f"missing_experiment_plan_field:{key}"
        if not isinstance(plan["checks"], list):
            return "invalid_experiment_plan_checks"
        if not isinstance(plan.get("what_to_measure"), (str, list)):
            return "invalid_experiment_plan_what_to_measure"
        rules = plan.get("hypothesis_rules")
        if not isinstance(rules, list) or not rules:
            return "invalid_hypothesis_rules"
        for rule in rules:
            if not isinstance(rule, dict):
                return "invalid_hypothesis_rule_item"
            for key in ["id", "accept_if", "reject_if", "hold_if"]:
                if not isinstance(rule.get(key), str) or not rule.get(key).strip():
                    return f"invalid_hypothesis_rule_field:{key}"
        return None

    if stage == "S3":
        c = payload.get("conclusion")
        if not isinstance(c, dict):
            return "invalid_conclusion"
        hypothesis_judgments = c.get("hypothesis_judgments")
        if not isinstance(hypothesis_judgments, list) or not hypothesis_judgments:
            return "missing_conclusion_field:hypothesis_judgments"
        for item in hypothesis_judgments:
            if not isinstance(item, dict):
                return "invalid_hypothesis_judgment_item"
            for key in [
                "id",
                "decision",
                "evidence_ids",
                "falsify_triggered",
                "accept_condition_met",
                "reject_condition_met",
                "hold_condition_met",
                "why",
            ]:
                if key not in item:
                    return f"missing_hypothesis_judgment_field:{key}"
            if item["decision"] not in ("survive", "reject", "hold"):
                return "invalid_hypothesis_judgment_decision"
            if not isinstance(item["evidence_ids"], list):
                return "invalid_hypothesis_judgment_evidence_ids"
            for bkey in [
                "falsify_triggered",
                "accept_condition_met",
                "reject_condition_met",
                "hold_condition_met",
            ]:
                if not isinstance(item[bkey], bool):
                    return f"invalid_hypothesis_judgment_{bkey}"
        required = [
            "which_hypotheses_survive",
            "which_rejected",
            "reasoning",
            "strength",
            "next_step",
        ]
        for key in required:
            if key not in c:
                return f"missing_conclusion_field:{key}"
        if not isinstance(c["which_hypotheses_survive"], list):
            return "invalid_conclusion_which_hypotheses_survive"
        if not isinstance(c["which_rejected"], list):
            return "invalid_conclusion_which_rejected"
        if c["strength"] not in ("strong", "weak", "hold"):
            return "invalid_conclusion_strength"
        return None

    return f"unknown_stage:{stage}"


def validate_evidence(payload: Dict[str, Any], stage: str = "generic") -> Optional[str]:
    if stage == "S2-EVID":
        findings = payload.get("findings")
        if not isinstance(findings, list) or len(findings) < 2:
            return "invalid_findings"
        for finding in findings:
            if not isinstance(finding, dict):
                return "invalid_finding_item"
            required = [
                "id",
                "what",
                "direction",
                "magnitude",
                "group",
            ]
            for key in required:
                if key not in finding:
                    return f"missing_finding_field:{key}"
            if not isinstance(finding["id"], str) or not finding["id"].strip():
                return "invalid_finding_id"
        if "not_observed" in payload and not isinstance(payload["not_observed"], list):
            return "invalid_not_observed"
        if "notes" in payload and not isinstance(payload["notes"], list):
            return "invalid_notes"
        if "text" in payload and not isinstance(payload["text"], str):
            return "invalid_type:text"
        return None

    if "text" not in payload:
        return "missing_key:text"
    if not isinstance(payload["text"], str):
        return "invalid_type:text"
    if "notes" in payload and not isinstance(payload["notes"], list):
        return "invalid_type:notes"
    if "research_question" in payload and not isinstance(payload["research_question"], str):
        return "invalid_type:research_question"
    if "scope" in payload and not isinstance(payload["scope"], dict):
        return "invalid_type:scope"
    for key in [
        "primary_outcomes",
        "secondary_outcomes",
        "candidate_mechanisms",
        "required_checks",
    ]:
        if key in payload and not isinstance(payload[key], list):
            return f"invalid_type:{key}"
    if "evidence_availability" in payload and not isinstance(payload["evidence_availability"], dict):
        return "invalid_type:evidence_availability"
    if "claim_boundary" in payload and not isinstance(payload["claim_boundary"], dict):
        return "invalid_type:claim_boundary"
    return None
