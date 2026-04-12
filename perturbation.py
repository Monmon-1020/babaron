"""
Perturbation experiments for evaluation layer 2.

For each case, creates a perturbation that violates a specific identification
assumption, then runs the analysis pipeline on both original and perturbed data.
Compares outputs to determine detection level (0/1/2).

Detection levels:
  Level 0: No change in strength or concerns (not detected)
  Level 1: Mention of issue but strength unchanged (partial detection)
  Level 2: Strength decreases AND relevant concern flagged (full detection)

CLI:
    python perturbation.py --case castle --condition proposed --model gpt-5.4-mini --out outputs/
    python perturbation.py --case all --condition all --out outputs/
    python perturbation.py --summary --out outputs/
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import cases
import run as run_module


# ============================================================
# Perturbation functions
# ============================================================


def perturb_castle(data: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Violate parallel trends for castle (DiD) case.
    Add an upward trend to treated states' pre-treatment outcomes.
    Magnitude: ~0.04 per year added to l_homicide for treated states
    before treatment.
    """
    df = data.copy()
    # Ensure float64 for columns we'll modify to avoid dtype casting issues
    df["l_homicide"] = df["l_homicide"].astype(float)
    info = {
        "perturbation": "parallel_trends_violation",
        "description": (
            "Added upward pre-treatment trend to treated states' l_homicide "
            "(+0.04 per year before treatment), violating parallel trends."
        ),
        "target_assumption": "平行トレンド仮定",
        "magnitude": "0.04 per year (approx 50% of treatment effect)",
    }

    # Identify treated states: those that ever have post == 1
    treated_states = df.loc[df["post"] == 1, "sid"].unique()

    # For each treated state, find the first treatment year
    for sid in treated_states:
        state_mask = df["sid"] == sid
        state_data = df.loc[state_mask]
        treatment_years = state_data.loc[state_data["post"] == 1, "year"]
        if len(treatment_years) == 0:
            continue
        first_treat_year = treatment_years.min()

        # Add trend to pre-treatment periods
        pre_mask = state_mask & (df["year"] < first_treat_year)
        if pre_mask.sum() == 0:
            continue

        # Years before treatment (negative values, closer to 0 = closer to treatment)
        years_before = df.loc[pre_mask, "year"].astype(float) - float(first_treat_year)
        # Add increasing trend: further from treatment = more deviation
        # This creates a pre-treatment upward trend for treated states
        df.loc[pre_mask, "l_homicide"] = (
            df.loc[pre_mask, "l_homicide"].values + 0.04 * (years_before.values - years_before.min())
        )

    return df, info


def perturb_close_elections(data: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Violate no-manipulation for close_elections (RDD) case.
    Bunch observations just above the cutoff (0.5).
    Take observations with demvoteshare in [0.48, 0.50] and shift them
    to [0.50, 0.52].
    """
    df = data.copy()
    info = {
        "perturbation": "manipulation_violation",
        "description": (
            "Shifted observations from demvoteshare [0.48, 0.50] to [0.50, 0.52], "
            "creating bunching above the cutoff. Violates no-manipulation assumption."
        ),
        "target_assumption": "操作不可能性",
        "magnitude": "observations in [0.48, 0.50] shifted to [0.50, 0.52]",
    }

    # Find observations just below cutoff
    mask = (df["demvoteshare"] >= 0.48) & (df["demvoteshare"] < 0.50)
    n_shifted = mask.sum()

    # Shift them above the cutoff
    df.loc[mask, "demvoteshare"] = df.loc[mask, "demvoteshare"] + 0.02

    info["n_observations_shifted"] = int(n_shifted)
    return df, info


def perturb_nhefs(data: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Violate positivity for nhefs (IPW) case.
    For male + age > 60 + smokeintensity > 30, set qsmk = 0 for all
    (no quitters in this group).
    """
    df = data.copy()
    info = {
        "perturbation": "positivity_violation",
        "description": (
            "For males aged >60 with smokeintensity >30, set qsmk=0 (no quitters). "
            "Violates positivity assumption for this covariate stratum."
        ),
        "target_assumption": "Positivity（正値性）",
        "magnitude": "complete positivity violation in one covariate stratum",
    }

    # Identify the target group
    # sex may be categorical with string values; convert for safe comparison
    sex_vals = df["sex"].astype(str).str.strip()
    mask = (
        (sex_vals == "0")  # male
        & (df["age"].astype(float) > 50)
        & (df["smokeintensity"].astype(float) > 20)
    )

    n_affected = mask.sum()
    n_were_quitters = (mask & (df["qsmk"] == 1)).sum()

    # Set all to non-quitters
    df.loc[mask, "qsmk"] = 0

    info["n_observations_affected"] = int(n_affected)
    info["n_quitters_removed"] = int(n_were_quitters)
    return df, info


def perturb_nsw(data: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Violate common support for nsw (Matching) case.
    Multiply re74 and re75 for control group by 3, making
    treatment/control profiles very different.
    """
    df = data.copy()
    info = {
        "perturbation": "common_support_violation",
        "description": (
            "Multiplied re74 and re75 by 3 for control group, "
            "creating large profile differences. Violates common support."
        ),
        "target_assumption": "Common Support（共通台）",
        "magnitude": "control group earnings multiplied by 3",
    }

    control_mask = df["treat"] == 0
    n_control = control_mask.sum()

    df.loc[control_mask, "re74"] = df.loc[control_mask, "re74"] * 3
    df.loc[control_mask, "re75"] = df.loc[control_mask, "re75"] * 3

    info["n_control_modified"] = int(n_control)
    return df, info


# Registry
PERTURBATIONS = {
    "castle": perturb_castle,
    "close_elections": perturb_close_elections,
    "nhefs": perturb_nhefs,
    "nsw": perturb_nsw,
}


# ============================================================
# Detection analysis
# ============================================================


def extract_strength(s3_text: str) -> str | None:
    """Extract strength level from S3 output."""
    patterns = [
        r"結論の強さ[:：]\s*(strong|moderate|weak|hold)",
        r"strength[:：]\s*(strong|moderate|weak|hold)",
    ]
    for pattern in patterns:
        match = re.search(pattern, s3_text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def extract_concerns(s3_text: str) -> list[str]:
    """Extract residual concerns from S3 output."""
    # Find concerns section
    patterns = [
        r"残存する懸念[:：](.*?)(?=##|$)",
        r"residual_concerns[:：](.*?)(?=##|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, s3_text, re.DOTALL | re.IGNORECASE)
        if match:
            concerns_text = match.group(1).strip()
            # Split by bullet points or newlines
            lines = [
                line.strip().lstrip("- ").lstrip("* ")
                for line in concerns_text.split("\n")
                if line.strip() and line.strip() not in ("-", "*")
            ]
            return lines
    return []


def check_concern_relevance(
    concerns: list[str], perturbation_info: dict
) -> bool:
    """Check if any concern is relevant to the perturbation."""
    target = perturbation_info["target_assumption"].lower()
    keywords = {
        "平行トレンド": ["平行トレンド", "parallel trend", "pre-treatment", "事前トレンド",
                          "event study", "lead"],
        "操作不可能性": ["操作", "manipulation", "bunching", "密度", "density",
                          "mccrary"],
        "positivity（正値性）": ["positivity", "正値", "極端な重み", "extreme weight",
                                  "weight"],
        "common support（共通台）": ["common support", "共通台", "overlap", "バランス",
                                      "balance", "乖離"],
    }

    relevant_kw = keywords.get(target, [target])
    concerns_text = " ".join(concerns).lower()
    s3_lower = concerns_text

    return any(kw.lower() in s3_lower for kw in relevant_kw)


STRENGTH_ORDER = {"strong": 4, "moderate": 3, "weak": 2, "hold": 1}


def determine_detection_level(
    original_output: dict,
    perturbed_output: dict,
    perturbation_info: dict,
) -> tuple[int, dict]:
    """
    Determine the detection level (0/1/2) by comparing original and perturbed outputs.

    Returns (level, details_dict).
    """
    orig_s3 = original_output.get("llm_output", {}).get("s3", "")
    pert_s3 = perturbed_output.get("llm_output", {}).get("s3", "")

    orig_strength = extract_strength(orig_s3)
    pert_strength = extract_strength(pert_s3)

    pert_concerns = extract_concerns(pert_s3)
    concern_relevant = check_concern_relevance(pert_concerns, perturbation_info)

    # Also check the full S3 text for relevant mentions
    relevant_kw = {
        "平行トレンド仮定": ["平行トレンド", "parallel trend", "pre-treatment", "event study", "lead"],
        "操作不可能性": ["manipulation", "操作", "bunching", "density", "密度"],
        "Positivity（正値性）": ["positivity", "正値", "extreme weight", "極端な重み"],
        "Common Support（共通台）": ["common support", "共通台", "overlap", "バランス"],
    }
    target = perturbation_info["target_assumption"]
    kws = relevant_kw.get(target, [target.lower()])
    mention_in_s3 = any(kw.lower() in pert_s3.lower() for kw in kws)

    # Determine strength change
    strength_decreased = False
    if orig_strength and pert_strength:
        orig_rank = STRENGTH_ORDER.get(orig_strength, 0)
        pert_rank = STRENGTH_ORDER.get(pert_strength, 0)
        strength_decreased = pert_rank < orig_rank

    details = {
        "original_strength": orig_strength,
        "perturbed_strength": pert_strength,
        "strength_decreased": strength_decreased,
        "concern_relevant": concern_relevant,
        "mention_in_s3": mention_in_s3,
        "perturbed_concerns": pert_concerns,
    }

    # Level determination
    if strength_decreased and (concern_relevant or mention_in_s3):
        level = 2  # Full detection
    elif mention_in_s3 or concern_relevant:
        level = 1  # Partial detection
    else:
        level = 0  # No detection

    return level, details


# ============================================================
# Experiment runner
# ============================================================


def run_perturbation_experiment(
    case_id: str,
    condition: str,
    model: str = "gpt-5.4-mini",
    out_dir: str = "outputs",
) -> dict:
    """
    Run perturbation experiment for a single case x condition.

    1. Run original analysis via run_single
    2. Perturb the data
    3. Run analysis on perturbed data
    4. Compare and determine detection level
    """
    print(f"\n{'='*60}")
    print(f"Perturbation experiment: case={case_id}, condition={condition}")
    print(f"{'='*60}")

    if case_id not in PERTURBATIONS:
        print(f"  Error: No perturbation defined for case '{case_id}'")
        return None

    # 1. Run original
    print("\n--- Running original analysis ---")
    original_output = run_module.run_single(
        case_id, condition, model=model, out_dir=out_dir,
    )

    # 2. Perturb data
    print("\n--- Perturbing data ---")
    case_data = cases.load(case_id)
    perturbed_data, perturbation_info = PERTURBATIONS[case_id](case_data["data"])
    print(f"  Perturbation: {perturbation_info['description'][:80]}...")

    # 3. Run perturbed analysis
    # We need to run the same pipeline but with perturbed data.
    # Temporarily patch the data in the case loader.
    print("\n--- Running perturbed analysis ---")
    perturbed_output = _run_with_data(
        case_id, condition, perturbed_data, model=model, out_dir=out_dir,
    )

    # 4. Determine detection level
    print("\n--- Determining detection level ---")
    level, details = determine_detection_level(
        original_output, perturbed_output, perturbation_info,
    )
    print(f"  Detection level: {level}")
    print(f"  Original strength: {details['original_strength']}")
    print(f"  Perturbed strength: {details['perturbed_strength']}")
    print(f"  Strength decreased: {details['strength_decreased']}")
    print(f"  Relevant concern flagged: {details['concern_relevant']}")

    # 5. Assemble result
    result = {
        "metadata": {
            "case_id": case_id,
            "condition": condition,
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "perturbation": perturbation_info,
        "detection_level": level,
        "detection_details": details,
        "original_output_file": f"run_{case_id}_{condition}.json",
        "perturbed_output_file": f"run_{case_id}_{condition}_perturbed.json",
    }

    # Save result
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"perturbation_{case_id}_{condition}.json"
    filepath = out_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Result saved to: {filepath}")
    return result


def _run_with_data(
    case_id: str,
    condition: str,
    data: pd.DataFrame,
    model: str = "gpt-5.4-mini",
    out_dir: str = "outputs",
) -> dict:
    """
    Run the analysis pipeline with custom (perturbed) data.
    Mirrors run_single but injects the provided DataFrame.
    """
    import prompts
    import tools

    print(f"  Running with perturbed data: case={case_id}, condition={condition}")

    # Load case metadata (but use provided data)
    case_data = cases.load(case_id)
    case_data["data"] = data

    # Recompute summary stats and sample rows for perturbed data
    case_def = cases.CASES[case_id]
    display_cols = case_def.get("display_columns")
    if display_cols:
        available = [c for c in display_cols if c in data.columns]
    else:
        available = data.columns.tolist()

    desc = data[available].describe().round(3)
    case_data["summary_statistics"] = (
        f"行数: {len(data)}, 列数: {len(data.columns)}\n\n{desc.to_string()}"
    )
    case_data["sample_rows"] = data[available].head(5).to_string()

    # Format prompt
    initial_prompt = prompts.format_prompt(case_data, condition)

    # Call LLM (Phase 1)
    client = run_module.create_client()
    messages_phase1 = [{"role": "user", "content": initial_prompt}]

    t0 = time.time()
    s0_s2b_output = run_module.call_llm(client, messages_phase1, model=model)
    t1 = time.time()

    # Parse method
    method_text = run_module.parse_method_from_s2a(s0_s2b_output)
    method_key = None
    if method_text:
        method_key = tools.resolve_method(method_text)
    if method_key is None:
        method_key = case_data["default_tool"]

    # Get params and run tool
    params = run_module.parse_tool_params_from_output(s0_s2b_output, case_id, method_key)
    tool_result = run_module.run_tool(data, method_key, params)

    # Phase 2
    continuation = prompts.format_continuation(tool_result["summary"])
    messages_phase2 = [
        {"role": "user", "content": initial_prompt},
        {"role": "assistant", "content": s0_s2b_output},
        {"role": "user", "content": continuation},
    ]

    t2 = time.time()
    s3_output = run_module.call_llm(client, messages_phase2, model=model)
    t3 = time.time()

    # Assemble output
    output = {
        "metadata": {
            "case_id": case_id,
            "condition": condition,
            "model": model,
            "label": case_data["label"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase1_time_s": round(t1 - t0, 2),
            "phase2_time_s": round(t3 - t2, 2),
            "perturbed": True,
        },
        "prompt": {
            "initial_prompt": initial_prompt,
            "continuation_prompt": continuation,
        },
        "llm_output": {
            "s0_s2b": s0_s2b_output,
            "s3": s3_output,
        },
        "tool": {
            "method_text": method_text,
            "method_key": method_key,
            "params": {k: v for k, v in params.items() if k != "data"},
            "result": {
                "method": tool_result["method"],
                "summary": tool_result["summary"],
                "estimates": tool_result["estimates"],
                "diagnostics": run_module._make_serializable(
                    tool_result["diagnostics"]
                ),
            },
        },
    }

    # Save perturbed output
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"run_{case_id}_{condition}_perturbed.json"
    filepath = out_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  Perturbed output saved to: {filepath}")
    return output


def generate_summary(out_dir: str = "outputs") -> dict:
    """Aggregate all perturbation experiment results into a summary."""
    out_path = Path(out_dir)
    files = sorted(out_path.glob("perturbation_*.json"))

    if not files:
        print(f"No perturbation results found in {out_dir}")
        return None

    results = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            results.append(json.load(f))

    # Summary table
    summary_rows = []
    for r in results:
        summary_rows.append({
            "case_id": r["metadata"]["case_id"],
            "condition": r["metadata"]["condition"],
            "perturbation": r["perturbation"]["perturbation"],
            "target_assumption": r["perturbation"]["target_assumption"],
            "detection_level": r["detection_level"],
            "original_strength": r["detection_details"]["original_strength"],
            "perturbed_strength": r["detection_details"]["perturbed_strength"],
            "strength_decreased": r["detection_details"]["strength_decreased"],
            "concern_relevant": r["detection_details"]["concern_relevant"],
        })

    # Aggregate by condition
    condition_agg = {}
    for row in summary_rows:
        cond = row["condition"]
        if cond not in condition_agg:
            condition_agg[cond] = {"total": 0, "n": 0, "levels": {0: 0, 1: 0, 2: 0}}
        condition_agg[cond]["total"] += row["detection_level"]
        condition_agg[cond]["n"] += 1
        condition_agg[cond]["levels"][row["detection_level"]] += 1

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_experiments": len(results),
        "per_experiment": summary_rows,
        "per_condition": condition_agg,
    }

    # Save
    summary_path = out_path / "perturbation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Print
    print(f"\n{'='*60}")
    print("PERTURBATION EXPERIMENT SUMMARY")
    print(f"{'='*60}")
    print(f"\n--- Per condition ---")
    for cond, agg in sorted(condition_agg.items()):
        levels = agg["levels"]
        print(
            f"  {cond}: "
            f"Level 0: {levels[0]}, Level 1: {levels[1]}, Level 2: {levels[2]} "
            f"(mean: {agg['total']/agg['n']:.2f})"
        )

    print(f"\n--- Per experiment ---")
    print(f"{'Case':<20} {'Condition':<12} {'Level':>6} {'Orig':>10} {'Pert':>10} {'Concern':>8}")
    print(f"{'-'*70}")
    for row in summary_rows:
        print(
            f"{row['case_id']:<20} {row['condition']:<12} "
            f"{row['detection_level']:>6} "
            f"{row['original_strength'] or 'N/A':>10} "
            f"{row['perturbed_strength'] or 'N/A':>10} "
            f"{'Yes' if row['concern_relevant'] else 'No':>8}"
        )

    print(f"\nSaved to: {summary_path}")
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run perturbation experiments for evaluation layer 2."
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Case ID (castle/close_elections/nhefs/nsw) or 'all'",
    )
    parser.add_argument(
        "--condition",
        type=str,
        default=None,
        help="Condition (baseline/proposed) or 'all'",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.4-mini",
        help="OpenAI model name",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="outputs",
        help="Output directory",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate summary from existing perturbation results",
    )
    args = parser.parse_args()

    if args.summary:
        generate_summary(args.out)
        return

    if args.case is None:
        parser.error("--case is required (or use --summary)")

    # Resolve case list
    all_cases = list(PERTURBATIONS.keys())
    if args.case == "all":
        case_ids = all_cases
    else:
        if args.case not in all_cases:
            parser.error(f"Unknown case: {args.case}. Available: {all_cases}")
        case_ids = [args.case]

    # Resolve condition list
    if args.condition == "all":
        conditions = ["baseline", "proposed"]
    elif args.condition:
        conditions = [args.condition]
    else:
        conditions = ["baseline", "proposed"]

    # Run experiments
    results = []
    for case_id in case_ids:
        for condition in conditions:
            try:
                result = run_perturbation_experiment(
                    case_id, condition, model=args.model, out_dir=args.out,
                )
                if result:
                    results.append(result)
            except Exception as e:
                print(f"\nError in perturbation {case_id}/{condition}: {e}")
                import traceback
                traceback.print_exc()

    # Auto-generate summary
    if results:
        generate_summary(args.out)

    print(f"\n{'='*60}")
    print(f"Completed: {len(results)} perturbation experiments")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
