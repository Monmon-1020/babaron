"""
Variable anonymization for contamination control.

Replaces all variable names, research questions, and data descriptions
with generic names (treatment_X, outcome_Y, covar_1, covar_2, etc.)
to prevent LLMs from relying on training data memorization.

CLI:
    python anonymize.py --case castle
    python anonymize.py --case all
    python anonymize.py --case castle --show-mapping
"""

import argparse
import json
import sys

import pandas as pd

import cases


def build_variable_mapping(case_id: str) -> dict:
    """
    Build a mapping from original variable names to anonymized names.
    Returns dict: {original_name: anonymized_name, ...}
    """
    case_def = cases.CASES[case_id]
    params = case_def["default_params"]
    tool = case_def["default_tool"]

    mapping = {}
    covar_counter = 1
    group_counter = 1
    time_counter = 1
    inst_counter = 1

    # Identify treatment variable(s)
    if tool in ("did", "ipw", "matching"):
        treatment_var = params["treatment"]
        mapping[treatment_var] = "treatment_X"
    elif tool == "iv":
        mapping[params["endogenous"]] = "endogenous_X"
    elif tool == "rdd":
        mapping[params["running_var"]] = "running_var_R"

    # Identify outcome variable
    if tool == "ols":
        mapping[params["outcome"]] = "outcome_Y"
    else:
        mapping[params["outcome"]] = "outcome_Y"

    # Identify group/time for DiD
    if tool == "did":
        mapping[params["group"]] = "group_G"
        mapping[params["time"]] = "time_T"

    # Identify instruments for IV
    if tool == "iv" and "instruments" in params:
        for inst in params["instruments"]:
            mapping[inst] = f"instrument_Z{inst_counter}"
            inst_counter += 1

    # Identify covariates
    cov_key = "covariates" if tool != "ols" else "regressors"
    covariates = params.get(cov_key, [])
    if covariates:
        for cov in covariates:
            if cov not in mapping:
                mapping[cov] = f"covar_{covar_counter}"
                covar_counter += 1

    # Map remaining columns in the dataset
    df = case_def["loader"].load_pandas().data
    for col in df.columns:
        if col not in mapping:
            # Lead/lag variables for event study
            if col.startswith("lead") and col[4:].isdigit():
                mapping[col] = f"pre_event_{col[4:]}"
            elif col.startswith("lag") and col[3:].isdigit():
                mapping[col] = f"post_event_{col[3:]}"
            else:
                mapping[col] = f"var_{covar_counter}"
                covar_counter += 1

    return mapping


def anonymize_dataframe(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Rename DataFrame columns using the mapping."""
    rename_map = {col: mapping[col] for col in df.columns if col in mapping}
    return df.rename(columns=rename_map)


def anonymize_params(params: dict, mapping: dict) -> dict:
    """Anonymize parameter dict (variable names -> anonymized names)."""
    new_params = {}
    for key, val in params.items():
        if isinstance(val, str) and val in mapping:
            new_params[key] = mapping[val]
        elif isinstance(val, list):
            new_params[key] = [mapping.get(v, v) for v in val]
        else:
            new_params[key] = val
    return new_params


def anonymize_case(case_id: str) -> tuple[dict, dict]:
    """
    Anonymize a case: replace variable names, research question,
    and data description with generic versions.

    Args:
        case_id: case identifier (castle, close_elections, nhefs, nsw)

    Returns:
        (anonymized_case_data, variable_mapping)
        anonymized_case_data has same format as cases.load() output.
        variable_mapping: {original_name: anonymized_name}
    """
    if case_id not in cases.CASES:
        raise ValueError(
            f"Unknown case_id: {case_id}. Available: {list(cases.CASES.keys())}"
        )

    # Build mapping
    mapping = build_variable_mapping(case_id)
    reverse_mapping = {v: k for k, v in mapping.items()}

    # Load original data
    original = cases.load(case_id)
    df = original["data"]

    # Anonymize dataframe
    anon_df = anonymize_dataframe(df, mapping)

    # Generic research question
    case_def = cases.CASES[case_id]
    tool = case_def["default_tool"]
    params = case_def["default_params"]

    if tool in ("did", "ipw", "matching"):
        anon_question = (
            "Does treatment_X have a causal effect on outcome_Y? "
            "Analyze the relationship between the treatment and outcome "
            "using the provided data."
        )
    elif tool == "rdd":
        anon_question = (
            "Is there a discontinuity in outcome_Y at the cutoff of running_var_R? "
            "Analyze the causal effect at the threshold using the provided data."
        )
    elif tool == "iv":
        anon_question = (
            "Does endogenous_X have a causal effect on outcome_Y? "
            "Use instrument_Z1 as an instrumental variable."
        )
    else:
        anon_question = (
            "What is the relationship between the key variables? "
            "Analyze using the provided data."
        )

    # Generic data description
    anon_description = (
        f"Panel/cross-sectional dataset with {len(anon_df)} observations "
        f"and {len(anon_df.columns)} variables. "
        "Variable names have been anonymized. "
        "Use the variable list and summary statistics to understand the data."
    )

    # Anonymized variable list
    anon_var_lines = []
    for orig_name, anon_name in mapping.items():
        # Only include columns present in the data
        if orig_name in df.columns:
            anon_var_lines.append(f"- {anon_name}: (anonymized variable)")
    anon_variable_list = "\n".join(anon_var_lines)

    # Summary statistics on anonymized data
    display_cols = anon_df.columns.tolist()
    # Limit to key columns
    if len(display_cols) > 20:
        key_anon = [mapping.get(c, c) for c in (case_def.get("display_columns") or df.columns.tolist()[:20])
                    if c in mapping]
        key_anon = [c for c in key_anon if c in anon_df.columns]
        if key_anon:
            display_cols = key_anon

    desc = anon_df[display_cols].describe().round(3)
    anon_summary = (
        f"行数: {len(anon_df)}, 列数: {len(anon_df.columns)}\n\n"
        f"{desc.to_string()}"
    )
    anon_sample = anon_df[display_cols].head(5).to_string()

    # Anonymize default params
    anon_params = anonymize_params(params, mapping)

    return (
        {
            "case_id": case_id,
            "data": anon_df,
            "research_question": anon_question,
            "data_description": anon_description,
            "variable_list": anon_variable_list,
            "summary_statistics": anon_summary,
            "sample_rows": anon_sample,
            "default_tool": original["default_tool"],
            "default_params": anon_params,
            "label": f"{original['label']} (anonymized)",
        },
        mapping,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Anonymize variable names for contamination control."
    )
    parser.add_argument(
        "--case",
        type=str,
        required=True,
        help="Case ID (castle/close_elections/nhefs/nsw) or 'all'",
    )
    parser.add_argument(
        "--show-mapping",
        action="store_true",
        help="Print the variable name mapping",
    )
    args = parser.parse_args()

    if args.case == "all":
        case_ids = cases.list_cases()
    else:
        case_ids = [args.case]

    for case_id in case_ids:
        print(f"\n{'='*60}")
        print(f"Anonymizing: {case_id}")
        print(f"{'='*60}")

        anon_data, mapping = anonymize_case(case_id)

        print(f"  Original columns: {len(mapping)}")
        print(f"  Data shape: {anon_data['data'].shape}")
        print(f"  Research question: {anon_data['research_question'][:80]}...")
        print(f"  Default params: {anon_data['default_params']}")

        if args.show_mapping:
            print(f"\n  Variable mapping:")
            for orig, anon in sorted(mapping.items()):
                print(f"    {orig:30s} -> {anon}")

        print()


if __name__ == "__main__":
    main()
