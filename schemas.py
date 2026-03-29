"""JSON parsing, schema validation, and rubric evaluation for the 3-layer protocol."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Layer 0: JSON parsing
# ---------------------------------------------------------------------------

def parse_json_object(raw_output: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    text = (raw_output or "").strip()
    if not text:
        return None, "empty_output"

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


# ---------------------------------------------------------------------------
# Layer 1: Protocol schema validation (S0 / S1 / S2 / S3)
# ---------------------------------------------------------------------------

def validate_s0(payload: Dict[str, Any]) -> Optional[str]:
    """Validate S0: estimand, scope, primary/secondary outcomes, claim boundary."""
    if "text" not in payload:
        return "missing_key:text"
    if not isinstance(payload["text"], str):
        return "invalid_type:text"
    for key in ["research_question", "estimand", "scope", "claim_boundary"]:
        if key not in payload:
            return f"missing_key:{key}"
    if not isinstance(payload.get("scope"), dict):
        return "invalid_type:scope"
    if not isinstance(payload.get("claim_boundary"), dict):
        return "invalid_type:claim_boundary"
    for key in ["primary_outcomes", "secondary_outcomes"]:
        if key in payload and not isinstance(payload[key], list):
            return f"invalid_type:{key}"
    return None


def validate_s1(payload: Dict[str, Any]) -> Optional[str]:
    """Validate S1: competing hypotheses with falsify conditions and distinctive predictions."""
    hyps = payload.get("hypotheses")
    if not isinstance(hyps, list) or len(hyps) < 2:
        return "invalid_hypotheses:need_at_least_2"
    for item in hyps:
        if not isinstance(item, dict):
            return "invalid_hypothesis_item"
        for key in ["id", "statement", "falsify", "distinctive_prediction"]:
            val = item.get(key)
            if not isinstance(val, str) or not val.strip():
                return f"invalid_hypothesis_field:{key}"
    return None


def validate_s2(payload: Dict[str, Any]) -> Optional[str]:
    """Validate S2: experiment plan with identification assumptions, decision rules, forks."""
    plan = payload.get("experiment_plan")
    if not isinstance(plan, dict):
        return "invalid_experiment_plan"

    for key in ["identification_assumptions", "hypothesis_rules", "analysis_forks"]:
        if key not in plan:
            return f"missing_experiment_plan_field:{key}"

    # identification_assumptions
    assumptions = plan["identification_assumptions"]
    if not isinstance(assumptions, list) or not assumptions:
        return "invalid_identification_assumptions"
    for a in assumptions:
        if not isinstance(a, dict):
            return "invalid_assumption_item"
        for key in ["id", "description", "if_violated"]:
            if not isinstance(a.get(key), str) or not a[key].strip():
                return f"invalid_assumption_field:{key}"

    # hypothesis_rules
    rules = plan["hypothesis_rules"]
    if not isinstance(rules, list) or not rules:
        return "invalid_hypothesis_rules"
    for rule in rules:
        if not isinstance(rule, dict):
            return "invalid_hypothesis_rule_item"
        for key in ["id", "accept_if", "reject_if", "hold_if"]:
            if not isinstance(rule.get(key), str) or not rule[key].strip():
                return f"invalid_hypothesis_rule_field:{key}"

    # analysis_forks
    forks = plan["analysis_forks"]
    if not isinstance(forks, list):
        return "invalid_analysis_forks"

    # optional but validated if present
    for key in ["what_to_compare", "what_to_measure", "procedure"]:
        if key in plan and not isinstance(plan[key], str):
            return f"invalid_type:{key}"

    return None


def validate_s3(payload: Dict[str, Any]) -> Optional[str]:
    """Validate S3: conclusion with hypothesis judgments, strength, remaining alternatives."""
    c = payload.get("conclusion")
    if not isinstance(c, dict):
        return "invalid_conclusion"

    judgments = c.get("hypothesis_judgments")
    if not isinstance(judgments, list) or not judgments:
        return "missing_conclusion_field:hypothesis_judgments"

    for item in judgments:
        if not isinstance(item, dict):
            return "invalid_hypothesis_judgment_item"
        for key in [
            "id", "decision", "evidence_ids",
            "falsify_triggered",
            "accept_condition_met", "reject_condition_met", "hold_condition_met",
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
            "accept_condition_met", "reject_condition_met", "hold_condition_met",
        ]:
            if not isinstance(item[bkey], bool):
                return f"invalid_hypothesis_judgment_{bkey}"

    for key in [
        "which_hypotheses_survive", "which_rejected",
        "reasoning", "strength", "next_step",
        "remaining_alternatives",
    ]:
        if key not in c:
            return f"missing_conclusion_field:{key}"

    if not isinstance(c["which_hypotheses_survive"], list):
        return "invalid_conclusion_which_hypotheses_survive"
    if not isinstance(c["which_rejected"], list):
        return "invalid_conclusion_which_rejected"
    if c["strength"] not in ("strong", "weak", "hold"):
        return "invalid_conclusion_strength"
    if not isinstance(c["remaining_alternatives"], list):
        return "invalid_conclusion_remaining_alternatives"

    return None


def validate_designer(stage: str, payload: Dict[str, Any]) -> Optional[str]:
    if stage == "S1":
        return validate_s1(payload)
    if stage == "S2":
        return validate_s2(payload)
    if stage == "S3":
        return validate_s3(payload)
    return f"unknown_stage:{stage}"


def validate_evidence(payload: Dict[str, Any], stage: str = "generic") -> Optional[str]:
    if stage == "S0":
        return validate_s0(payload)
    if stage == "S2-EVID":
        findings = payload.get("findings")
        if not isinstance(findings, list) or len(findings) < 2:
            return "invalid_findings"
        for f in findings:
            if not isinstance(f, dict):
                return "invalid_finding_item"
            for key in ["id", "what", "direction", "magnitude", "group"]:
                if key not in f:
                    return f"missing_finding_field:{key}"
            if not isinstance(f["id"], str) or not f["id"].strip():
                return "invalid_finding_id"
        if "not_observed" in payload and not isinstance(payload["not_observed"], list):
            return "invalid_not_observed"
        return None
    return None


# ---------------------------------------------------------------------------
# Supervisor normalization and validation
# ---------------------------------------------------------------------------

def normalize_supervisor(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(payload)

    if "verdict" not in out and "判定" in out:
        out["verdict"] = out["判定"]
    if "fix_instructions" not in out and "修正指示" in out:
        out["fix_instructions"] = out["修正指示"]
    if "pass_requirements" not in out and "合格条件" in out:
        out["pass_requirements"] = out["合格条件"]
    if "issues" not in out:
        out["issues"] = []
    if "fatal_issues" not in out:
        out["fatal_issues"] = []
    if "minor_issues" not in out:
        out["minor_issues"] = []

    for key in ["issues", "fix_instructions", "pass_requirements", "fatal_issues", "minor_issues"]:
        value = out.get(key)
        if isinstance(value, str):
            out[key] = [value]
        elif value is None:
            out[key] = []
        elif not isinstance(value, list):
            out[key] = [str(value)]

    if not out.get("issues"):
        out["issues"] = list(out.get("fatal_issues", [])) + list(out.get("minor_issues", []))

    verdict = out.get("verdict")
    if isinstance(verdict, str):
        verdict = verdict.strip()
        if verdict.lower() in ("ok", "ｏｋ"):
            verdict = "OK"
        if verdict.lower() == "ng":
            verdict = "NG"
        out["verdict"] = verdict

    return out


def validate_supervisor(payload: Dict[str, Any]) -> Optional[str]:
    for key in ["verdict", "issues", "fix_instructions", "pass_requirements"]:
        if key not in payload:
            return f"missing_key:{key}"
    if payload["verdict"] not in ("OK", "NG"):
        return "invalid_verdict"
    for key in ["issues", "fix_instructions", "pass_requirements"]:
        if not isinstance(payload[key], list):
            return f"invalid_type:{key}"
    return None


# ---------------------------------------------------------------------------
# Designer output normalization
# ---------------------------------------------------------------------------

def normalize_designer_payload(stage: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    if stage != "S3":
        return out
    conclusion = out.get("conclusion")
    if not isinstance(conclusion, dict):
        return out

    # Normalize strength
    strength = conclusion.get("strength")
    if isinstance(strength, str):
        s = strength.strip().lower()
        strength_mapping = {
            "strong": "strong", "high": "strong",
            "weak": "weak", "moderate": "weak", "medium": "weak",
            "hold": "hold", "uncertain": "hold", "pending": "hold",
            "保留": "hold", "弱い": "weak", "強い": "strong",
        }
        if s in strength_mapping:
            conclusion["strength"] = strength_mapping[s]

    # Normalize hypothesis judgment decisions: accept→survive, etc.
    decision_mapping = {
        "accept": "survive", "accepted": "survive",
        "survive": "survive", "survived": "survive", "support": "survive",
        "reject": "reject", "rejected": "reject",
        "hold": "hold", "pending": "hold", "uncertain": "hold",
    }
    judgments = conclusion.get("hypothesis_judgments", [])
    if isinstance(judgments, list):
        for item in judgments:
            if isinstance(item, dict) and isinstance(item.get("decision"), str):
                d = item["decision"].strip().lower()
                if d in decision_mapping:
                    item["decision"] = decision_mapping[d]

    # Normalize which_hypotheses_survive key variants
    if "which_hypotheses_survive" not in conclusion:
        for alt_key in ["which_accepted", "which_survive", "accepted_hypotheses"]:
            if alt_key in conclusion:
                conclusion["which_hypotheses_survive"] = conclusion[alt_key]
                break
        else:
            conclusion["which_hypotheses_survive"] = []

    if "which_rejected" not in conclusion:
        conclusion["which_rejected"] = []

    if "remaining_alternatives" not in conclusion:
        conclusion["remaining_alternatives"] = []

    out["conclusion"] = conclusion
    return out
