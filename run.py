"""
Main runner for causal inference analysis.

Flow:
1. Load case data
2. Format prompt (common input + condition instructions)
3. Send to LLM -> get S0-S2b output
4. Parse S2a to find chosen method
5. Call appropriate tool from tools.py
6. Format S2-EVID with tool results
7. Send continuation prompt -> get S3 output
8. Save full output as JSON

CLI:
    python run.py --case castle --condition baseline --model gpt-5.4-mini --out outputs/
    python run.py --case all --condition all  # run all 4x2=8
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

import cases
import prompts
import tools

load_dotenv()


def create_client() -> OpenAI:
    """Create OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment or .env file.")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def call_llm(
    client: OpenAI,
    messages: list[dict],
    model: str = "gpt-5.4-mini",
    temperature: float = 0.0,
    max_completion_tokens: int = 8000,
) -> str:
    """Call the LLM and return the response text."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )
    return response.choices[0].message.content


def parse_method_from_s2a(text: str) -> str | None:
    """
    Parse the chosen method from S2a section of LLM output.
    Looks for '選択した手法:' line.
    """
    # Try to find '選択した手法:' pattern
    patterns = [
        r"選択した手法[:：]\s*(.+)",
        r"選択した手法\s*[:：]\s*(.+)",
        r"手法選択[:：]\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            method_text = match.group(1).strip()
            return method_text
    return None


def parse_tool_params_from_output(text: str, case_id: str, method_key: str) -> dict:
    """
    Try to extract tool parameters from LLM output.
    Falls back to default parameters for the case.
    """
    case_data = cases.CASES[case_id]
    defaults = case_data["default_params"]

    # For now, use defaults. A more sophisticated parser could extract
    # variable names from the LLM output, but defaults are reliable.
    return defaults


def run_tool(data, method_key: str, params: dict) -> dict:
    """Run the appropriate analysis tool."""
    tool_func = tools.TOOLS.get(method_key)
    if tool_func is None:
        return {
            "method": method_key,
            "summary": f"Error: Unknown tool '{method_key}'",
            "estimates": {},
            "diagnostics": {},
        }

    try:
        if method_key == "did":
            return tool_func(
                data,
                treatment=params["treatment"],
                outcome=params["outcome"],
                group=params["group"],
                time=params["time"],
                covariates=params.get("covariates"),
            )
        elif method_key == "iv":
            return tool_func(
                data,
                endogenous=params["endogenous"],
                outcome=params["outcome"],
                instruments=params["instruments"],
                covariates=params.get("covariates"),
            )
        elif method_key == "rdd":
            return tool_func(
                data,
                outcome=params["outcome"],
                running_var=params["running_var"],
                cutoff=params["cutoff"],
                bandwidth=params.get("bandwidth"),
            )
        elif method_key == "matching":
            return tool_func(
                data,
                treatment=params["treatment"],
                outcome=params["outcome"],
                covariates=params["covariates"],
            )
        elif method_key == "ipw":
            return tool_func(
                data,
                treatment=params["treatment"],
                outcome=params["outcome"],
                covariates=params["covariates"],
            )
        elif method_key == "ols":
            return tool_func(
                data,
                outcome=params["outcome"],
                regressors=params["regressors"],
            )
        else:
            return {
                "method": method_key,
                "summary": f"Error: No handler for tool '{method_key}'",
                "estimates": {},
                "diagnostics": {},
            }
    except Exception as e:
        return {
            "method": method_key,
            "summary": f"Error running {method_key}: {e}",
            "estimates": {},
            "diagnostics": {},
        }


def generate_sensitivity_variants(method_key: str, params: dict, data) -> list[dict]:
    """
    Generate alternative parameter sets for sensitivity analysis.
    Returns a list of dicts: {"label": str, "params": dict}.
    Typically 2-3 variants per method.
    """
    variants = []

    if method_key == "did":
        # Variant 1: without covariates
        no_cov_params = {k: v for k, v in params.items()}
        no_cov_params["covariates"] = None
        variants.append({"label": "DiD: 共変量なし", "params": no_cov_params})

        # Variant 2: with subset of covariates (economic only)
        if params.get("covariates"):
            econ_covs = [c for c in params["covariates"]
                         if c in ("unemployrt", "poverty", "l_income")]
            if econ_covs:
                econ_params = {k: v for k, v in params.items()}
                econ_params["covariates"] = econ_covs
                variants.append({"label": "DiD: 経済変数のみ", "params": econ_params})

    elif method_key == "rdd":
        # Variant 1: half bandwidth
        half_bw_params = {k: v for k, v in params.items()}
        half_bw_params["bandwidth"] = 0.125  # half of typical ~0.25
        variants.append({"label": "RDD: バンド幅 0.125 (狭い)", "params": half_bw_params})

        # Variant 2: double bandwidth
        double_bw_params = {k: v for k, v in params.items()}
        double_bw_params["bandwidth"] = 0.5  # double of typical ~0.25
        variants.append({"label": "RDD: バンド幅 0.5 (広い)", "params": double_bw_params})

    elif method_key == "ipw":
        # Drop one covariate at a time (pick 2-3 substantively important ones)
        covariates = params.get("covariates", [])
        # Drop wt71 (baseline weight)
        if "wt71" in covariates:
            drop_params = {k: v for k, v in params.items()}
            drop_params["covariates"] = [c for c in covariates if c != "wt71"]
            variants.append({"label": "IPW: wt71除外", "params": drop_params})
        # Drop smokeintensity
        if "smokeintensity" in covariates:
            drop_params = {k: v for k, v in params.items()}
            drop_params["covariates"] = [c for c in covariates if c != "smokeintensity"]
            variants.append({"label": "IPW: smokeintensity除外", "params": drop_params})

    elif method_key == "matching":
        covariates = params.get("covariates", [])
        # Drop re74
        if "re74" in covariates:
            drop_params = {k: v for k, v in params.items()}
            drop_params["covariates"] = [c for c in covariates if c != "re74"]
            variants.append({"label": "Matching: re74除外", "params": drop_params})
        # Drop re75
        if "re75" in covariates:
            drop_params = {k: v for k, v in params.items()}
            drop_params["covariates"] = [c for c in covariates if c != "re75"]
            variants.append({"label": "Matching: re75除外", "params": drop_params})

    elif method_key == "ols":
        regressors = params.get("regressors", [])
        if len(regressors) > 1:
            # Drop last regressor
            drop_params = {k: v for k, v in params.items()}
            drop_params["regressors"] = regressors[:-1]
            variants.append({
                "label": f"OLS: {regressors[-1]}除外",
                "params": drop_params,
            })
            # Drop first regressor
            drop_params2 = {k: v for k, v in params.items()}
            drop_params2["regressors"] = regressors[1:]
            variants.append({
                "label": f"OLS: {regressors[0]}除外",
                "params": drop_params2,
            })

    return variants


def run_sensitivity(data, method_key: str, params: dict) -> list[dict]:
    """
    Run sensitivity analyses for the given method and parameters.
    Returns list of {"label": str, "result": tool_result_dict}.
    """
    variants = generate_sensitivity_variants(method_key, params, data)
    results = []
    for variant in variants:
        try:
            result = run_tool(data, method_key, variant["params"])
            results.append({
                "label": variant["label"],
                "params": {k: v for k, v in variant["params"].items() if k != "data"},
                "result": {
                    "method": result["method"],
                    "summary": result["summary"],
                    "estimates": result["estimates"],
                },
            })
        except Exception as e:
            results.append({
                "label": variant["label"],
                "params": {k: v for k, v in variant["params"].items() if k != "data"},
                "result": {"method": method_key, "summary": f"Error: {e}", "estimates": {}},
            })
    return results


def format_sensitivity_summary(sensitivity_results: list[dict]) -> str:
    """Format sensitivity results as a text summary for the LLM."""
    if not sensitivity_results:
        return ""
    lines = ["\n\n=== 感度分析結果 ==="]
    for sr in sensitivity_results:
        lines.append(f"\n--- {sr['label']} ---")
        lines.append(sr["result"]["summary"])
    return "\n".join(lines)


def run_single(
    case_id: str,
    condition: str,
    model: str = "gpt-5.4-mini",
    out_dir: str = "outputs",
    sensitivity: bool = False,
    anonymize: bool = False,
) -> dict:
    """
    Run a single case x condition experiment.
    Returns the full output dict.
    """
    print(f"\n{'='*60}")
    print(f"Running: case={case_id}, condition={condition}, model={model}")
    print(f"{'='*60}")

    # 1. Load case data
    print("Loading case data...")
    if anonymize:
        import anonymize as anon_module
        case_data, var_mapping = anon_module.anonymize_case(case_id)
        print(f"  Anonymized: {len(var_mapping)} variables mapped")
    else:
        case_data = cases.load(case_id)
        var_mapping = None
    data = case_data["data"]

    # 2. Format prompt
    print("Formatting prompt...")
    initial_prompt = prompts.format_prompt(case_data, condition)

    # 3. Send to LLM (S0-S2b)
    print("Calling LLM for S0-S2b...")
    client = create_client()
    messages_phase1 = [{"role": "user", "content": initial_prompt}]

    t0 = time.time()
    s0_s2b_output = call_llm(client, messages_phase1, model=model)
    t1 = time.time()
    print(f"  Phase 1 completed in {t1 - t0:.1f}s")

    # 4. Parse chosen method
    method_text = parse_method_from_s2a(s0_s2b_output)
    print(f"  Parsed method: {method_text}")

    method_key = None
    if method_text:
        method_key = tools.resolve_method(method_text)

    if method_key is None:
        print(f"  Could not resolve method. Using default: {case_data['default_tool']}")
        method_key = case_data["default_tool"]

    print(f"  Resolved tool: {method_key}")

    # 5. Get tool parameters
    params = parse_tool_params_from_output(s0_s2b_output, case_id, method_key)
    print(f"  Tool params: {params}")

    # 6. Run tool
    print(f"Running {method_key} tool...")
    tool_result = run_tool(data, method_key, params)
    print(f"  Tool completed. Method: {tool_result['method']}")

    # 6b. Run sensitivity analysis (optional)
    sensitivity_results = []
    if sensitivity:
        print("Running sensitivity analyses...")
        sensitivity_results = run_sensitivity(data, method_key, params)
        print(f"  Completed {len(sensitivity_results)} sensitivity runs")

    # 7. Send continuation prompt with tool results
    print("Calling LLM for S3...")
    tool_summary = tool_result["summary"]
    if sensitivity and sensitivity_results:
        tool_summary += format_sensitivity_summary(sensitivity_results)
    continuation = prompts.format_continuation(tool_summary, include_sensitivity=sensitivity)
    messages_phase2 = [
        {"role": "user", "content": initial_prompt},
        {"role": "assistant", "content": s0_s2b_output},
        {"role": "user", "content": continuation},
    ]

    t2 = time.time()
    s3_output = call_llm(client, messages_phase2, model=model)
    t3 = time.time()
    print(f"  Phase 2 completed in {t3 - t2:.1f}s")

    # 8. Assemble full output
    output = {
        "metadata": {
            "case_id": case_id,
            "condition": condition,
            "model": model,
            "label": case_data["label"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase1_time_s": round(t1 - t0, 2),
            "phase2_time_s": round(t3 - t2, 2),
            "sensitivity": sensitivity,
            "anonymized": anonymize,
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
                "diagnostics": _make_serializable(tool_result["diagnostics"]),
            },
        },
    }

    # Add sensitivity results if available
    if sensitivity and sensitivity_results:
        output["sensitivity"] = _make_serializable(sensitivity_results)

    # Add anonymization mapping if used
    if var_mapping:
        output["anonymization"] = {"variable_mapping": var_mapping}

    # Save output
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    suffix_parts = [case_id, condition]
    if anonymize:
        suffix_parts.append("anon")
    if sensitivity:
        suffix_parts.append("sens")
    filename = f"run_{'_'.join(suffix_parts)}.json"
    filepath = out_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Output saved to: {filepath}")
    return output


def _make_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def main():
    parser = argparse.ArgumentParser(
        description="Run causal inference analysis experiments."
    )
    parser.add_argument(
        "--case",
        type=str,
        default="castle",
        help="Case ID (castle/close_elections/nhefs/nsw) or 'all'",
    )
    parser.add_argument(
        "--condition",
        type=str,
        default="baseline",
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
        "--sensitivity",
        action="store_true",
        help="Run sensitivity analyses with alternative parameters",
    )
    parser.add_argument(
        "--anonymize",
        action="store_true",
        help="Anonymize variable names before running",
    )
    args = parser.parse_args()

    # Resolve case list
    if args.case == "all":
        case_ids = cases.list_cases()
    else:
        case_ids = [args.case]

    # Resolve condition list
    if args.condition == "all":
        conditions = ["baseline", "proposed"]
    else:
        conditions = [args.condition]

    # Run all combinations
    results = []
    for case_id in case_ids:
        for condition in conditions:
            try:
                result = run_single(
                    case_id, condition, args.model, args.out,
                    sensitivity=args.sensitivity,
                    anonymize=args.anonymize,
                )
                results.append(result)
            except Exception as e:
                print(f"\nError running {case_id}/{condition}: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Completed: {len(results)} / {len(case_ids) * len(conditions)} runs")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
