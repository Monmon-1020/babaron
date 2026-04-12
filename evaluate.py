"""
Checklist evaluation for causal inference analysis outputs.

For each (case, condition) output:
1. Load the output JSON
2. For each checklist item, send the relevant section to gpt-4o
3. Score 0/1/2
4. Aggregate

CLI:
    python evaluate.py --case castle --condition baseline --model gpt-4o
    python evaluate.py --case all --condition all --model gpt-4o
    python evaluate.py --summary  # aggregate all results
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

load_dotenv()

# ============================================================
# Checklist definitions
# Each item: id, description (評価項目), gold_standard, section
# section indicates which part of the output is relevant:
#   "s2a" -> S2a, "s1" -> S1, "s3" -> S3, "s2b" -> S2b, "all" -> full output
# ============================================================

CHECKLIST = {
    "castle": [
        {
            "id": "a",
            "description": "手法選択がDiD（TWFE）か",
            "gold_standard": "DiD / Two-Way Fixed Effects",
            "section": "s2a",
        },
        {
            "id": "b",
            "description": "識別仮定: 平行トレンド仮定を述べているか",
            "gold_standard": "処置がなかった場合の処置群と対照群のアウトカムの時間変化が同一であること",
            "section": "s2a",
        },
        {
            "id": "c",
            "description": "平行トレンドの重要性を認識しているか",
            "gold_standard": "DiDの最も重要な仮定である",
            "section": "s2a",
        },
        {
            "id": "d",
            "description": "平行トレンドが崩れた場合の帰結を述べているか",
            "gold_standard": "ATTが識別不能になる。非平行トレンドバイアス項が残存する",
            "section": "s2a",
        },
        {
            "id": "e",
            "description": "平行トレンドの検証不可能性を認識しているか",
            "gold_standard": "定義上検証不可能（反事実が観察できないため）",
            "section": "all",
        },
        {
            "id": "f",
            "description": "OLSが常に対照群の傾きを反事実として使うことを認識しているか",
            "gold_standard": "OLSは対照群の傾きが正しいかどうかに関わらず、それを反事実として推定する",
            "section": "all",
        },
        {
            "id": "g",
            "description": "SUTVA/spilloverへの言及があるか",
            "gold_standard": "他州へのspilloverがないこと",
            "section": "s1",
        },
        {
            "id": "h",
            "description": "同時政策変更の懸念への言及があるか",
            "gold_standard": "同時期の他の政策変更がないこと（州固有の時間ショックがないこと）",
            "section": "s1",
        },
        {
            "id": "i",
            "description": "クラスター標準誤差の必要性を述べているか",
            "gold_standard": "通常のSEは過小評価する。州レベルのクラスタリングが必要",
            "section": "s2b",
        },
        {
            "id": "j",
            "description": "Staggered adoptionでのTWFE問題への言及があるか",
            "gold_standard": "異なるタイミングの処置群間比較で、すでに処置を受けた群が「対照群」として使われうる",
            "section": "all",
        },
        {
            "id": "j2",
            "description": "モデリング選択: 共変量の選択が結果に影響することを認識しているか",
            "gold_standard": "コントロール変数の有無で推定値が変わる",
            "section": "s2b",
        },
        {
            "id": "j3",
            "description": "モデリング選択: 回帰の関数形やコントロール変数の正当化があるか",
            "gold_standard": "どの共変量を含めるか、どの関数形を用いるかは解析者の自由度であり、正当化が必要",
            "section": "s2b",
        },
        {
            "id": "k",
            "description": "診断検定: Event study / lead検定への言及があるか",
            "gold_standard": "処置前期間のDiD係数がゼロであることを確認",
            "section": "all",
        },
        {
            "id": "l",
            "description": "Event study検定の限界を認識しているか",
            "gold_standard": "事前の類似性は事後の平行性を保証しない",
            "section": "all",
        },
        {
            "id": "m",
            "description": "strengthが≠ strongか",
            "gold_standard": "moderate（TWFE問題は限定的だが平行トレンドの検証不可能性は残存）",
            "section": "s3",
        },
        {
            "id": "n",
            "description": "strengthの根拠が識別仮定の状態と連動しているか",
            "gold_standard": "根拠が平行トレンドの検証不可能性やTWFE問題と結びついているか",
            "section": "s3",
        },
    ],
    "close_elections": [
        {
            "id": "a",
            "description": "手法選択がRDD（Sharp）か",
            "gold_standard": "Sharp Regression Discontinuity Design",
            "section": "s2a",
        },
        {
            "id": "b",
            "description": "識別仮定: 連続性仮定を述べているか",
            "gold_standard": "カットオフにおけるポテンシャルアウトカムの条件付き期待値がrunning variableに対して連続であること",
            "section": "s2a",
        },
        {
            "id": "c",
            "description": "連続性仮定がOVBを排除することを認識しているか",
            "gold_standard": "カットオフにおける省略変数バイアスを排除する",
            "section": "s2a",
        },
        {
            "id": "d",
            "description": "識別仮定: 操作不可能性を述べているか",
            "gold_standard": "個体がrunning variableを正確に操作してカットオフの上下を選択できないこと",
            "section": "s2a",
        },
        {
            "id": "e",
            "description": "連続性仮定が崩れた場合の帰結を述べているか",
            "gold_standard": "カットオフでのジャンプが処置効果以外の原因と区別不可 → LATE識別不能",
            "section": "s2a",
        },
        {
            "id": "f",
            "description": "操作が存在する場合の帰結を述べているか",
            "gold_standard": "カットオフ付近で処置群と対照群の構成が異なり、セレクションバイアスが生じる",
            "section": "s2a",
        },
        {
            "id": "g",
            "description": "LATEの局所性の限界を述べているか",
            "gold_standard": "RDDはカットオフ付近の局所的効果のみ推定。外的妥当性は限定的",
            "section": "all",
        },
        {
            "id": "h",
            "description": "バンド幅選択への感度を述べているか",
            "gold_standard": "推定結果がバンド幅の選択に敏感でありうる",
            "section": "s2b",
        },
        {
            "id": "i",
            "description": "関数形選択への懸念を述べているか",
            "gold_standard": "高次多項式の使用は推奨されない",
            "section": "s2b",
        },
        {
            "id": "j",
            "description": "診断検定: McCrary密度検定への言及があるか",
            "gold_standard": "running variableの密度がカットオフで不連続でないことを確認",
            "section": "all",
        },
        {
            "id": "k",
            "description": "診断検定: 共変量バランス検定への言及があるか",
            "gold_standard": "カットオフ付近で事前共変量にジャンプがないことを確認",
            "section": "all",
        },
        {
            "id": "l",
            "description": "strengthがmoderate〜strongの範囲か",
            "gold_standard": "moderate〜strong（RDDは最も信頼性の高い観察研究デザインの一つ。close electionは操作困難。ただしLATEの局所性は残存）",
            "section": "s3",
        },
        {
            "id": "m",
            "description": "strengthの根拠が識別仮定の状態と連動しているか",
            "gold_standard": "根拠が連続性仮定・操作不可能性の検証状況と結びついているか",
            "section": "s3",
        },
    ],
    "nhefs": [
        {
            "id": "a",
            "description": "手法選択がIPW（またはg推定/傾向スコア法）か",
            "gold_standard": "Inverse Probability Weighting",
            "section": "s2a",
        },
        {
            "id": "b",
            "description": "識別仮定: 条件付き交換可能性を述べているか",
            "gold_standard": "観測された共変量で条件付けた上で、処置割り当てがポテンシャルアウトカムと独立",
            "section": "s2a",
        },
        {
            "id": "c",
            "description": "交換可能性の検証不可能性を認識しているか",
            "gold_standard": "一般に交換可能性が成立するかを判定することはできない",
            "section": "all",
        },
        {
            "id": "d",
            "description": "識別仮定: Positivityを述べているか",
            "gold_standard": "共変量の全ての水準において処置を受ける確率が正であること",
            "section": "s2a",
        },
        {
            "id": "e",
            "description": "識別仮定: Consistencyを述べているか",
            "gold_standard": "観測されるアウトカムが実際に受けた処置水準に対応するポテンシャルアウトカムと一致すること",
            "section": "s2a",
        },
        {
            "id": "f",
            "description": "交換可能性が崩れた場合の帰結を述べているか",
            "gold_standard": "未観測交絡バイアスが残存し、IPW推定量はATEを一致推定しない",
            "section": "s2a",
        },
        {
            "id": "g",
            "description": "Positivityが崩れた場合の帰結を述べているか",
            "gold_standard": "極端な重みが発生し推定が不安定になる",
            "section": "all",
        },
        {
            "id": "h",
            "description": "極端な重み / stabilized weightsへの言及があるか",
            "gold_standard": "傾向スコアが0/1に近い場合の対処",
            "section": "all",
        },
        {
            "id": "i",
            "description": "傾向スコアモデルの指定への懸念があるか",
            "gold_standard": "モデルが誤指定の場合バイアスが生じる",
            "section": "s2b",
        },
        {
            "id": "j",
            "description": "未観測交絡の可能性 / 感度分析への言及があるか",
            "gold_standard": "観察研究のため条件付き交換可能性は検証不可能。感度分析で頑健性を評価すべき",
            "section": "s3",
        },
        {
            "id": "k",
            "description": "診断検定: 共変量バランス確認への言及があるか",
            "gold_standard": "IPW適用後の処置群・対照群間の共変量バランス改善を確認",
            "section": "all",
        },
        {
            "id": "l",
            "description": "診断検定: 重みの分布確認への言及があるか",
            "gold_standard": "極端な重みの有無を検査",
            "section": "all",
        },
        {
            "id": "m",
            "description": "strengthが≠ strongか",
            "gold_standard": "weak〜moderate（条件付き交換可能性は検証不可能、未観測交絡を排除不可能）",
            "section": "s3",
        },
        {
            "id": "n",
            "description": "strengthの根拠が識別仮定の状態と連動しているか",
            "gold_standard": "根拠が交換可能性の検証不可能性やpositivity違反の可能性と結びついているか",
            "section": "s3",
        },
    ],
    "nsw": [
        {
            "id": "a",
            "description": "手法選択がマッチング（PSM/subclassification等）か",
            "gold_standard": "Propensity Score Matching / Subclassification",
            "section": "s2a",
        },
        {
            "id": "b",
            "description": "識別仮定: CIA（条件付き独立性仮定）を述べているか",
            "gold_standard": "観測された共変量Xで条件付けた上で、処置割り当てがポテンシャルアウトカムと独立",
            "section": "s2a",
        },
        {
            "id": "c",
            "description": "CIAとbackdoor criterionの関係を認識しているか",
            "gold_standard": "CIAが成立すればbackdoor criterionが満たされる",
            "section": "all",
        },
        {
            "id": "d",
            "description": "識別仮定: Common Support / Overlapを述べているか",
            "gold_standard": "処置群と対照群の傾向スコア分布に十分な重なりがあること",
            "section": "s2a",
        },
        {
            "id": "e",
            "description": "CIAが崩れた場合の帰結を述べているか",
            "gold_standard": "深刻な選択バイアスが残存する",
            "section": "s2a",
        },
        {
            "id": "f",
            "description": "Common Supportが崩れた場合の帰結を述べているか",
            "gold_standard": "比較可能な対照単位がなく、推定が信頼できなくなる",
            "section": "all",
        },
        {
            "id": "g",
            "description": "バランスの概念を正しく理解しているか",
            "gold_standard": "共変量のバランスが達成 = 2群が交換可能",
            "section": "all",
        },
        {
            "id": "h",
            "description": "LaLonde (1986)の教訓への言及があるか",
            "gold_standard": "観察研究の推定値はRCT結果と大きく乖離しうる",
            "section": "all",
        },
        {
            "id": "i",
            "description": "PSMの限界への言及があるか",
            "gold_standard": "PSMは当初の期待ほど万能ではない",
            "section": "all",
        },
        {
            "id": "j",
            "description": "診断検定: 共変量バランス確認への言及があるか",
            "gold_standard": "マッチング前後での共変量バランスの改善を確認",
            "section": "all",
        },
        {
            "id": "k",
            "description": "診断検定: Common Support確認への言及があるか",
            "gold_standard": "傾向スコアの分布の重なりをヒストグラム等で確認",
            "section": "all",
        },
        {
            "id": "l",
            "description": "RCTデータとの比較可能性への言及があるか",
            "gold_standard": "NSWデータはRCTの結果を持ち、実験結果と観察研究を比較できる",
            "section": "all",
        },
        {
            "id": "m",
            "description": "strengthが分析アプローチに依存することを認識しているか",
            "gold_standard": "RCTデータ→strong。観察データでマッチング→≠ strong",
            "section": "s3",
        },
        {
            "id": "n",
            "description": "strengthの根拠が識別仮定の状態と連動しているか",
            "gold_standard": "根拠がCIA/Common Supportの状態と結びついているか",
            "section": "s3",
        },
    ],
}


SCORING_PROMPT = """\
あなたは因果推論の分析出力を採点する評価者です。

以下は因果推論分析の出力です。

---
{relevant_output}
---

採点項目: {checklist_item}
Gold Standard: {gold_standard}

この出力は上記の採点項目を満たしていますか？
以下の基準で0/1/2を判定してください:
- 2: 正確かつ十分に言及されている
- 1: 言及はあるが不正確または不完全
- 0: 言及なし

JSON形式で回答: {{"score": 0/1/2, "evidence": "根拠"}}
"""


def create_client() -> OpenAI:
    """Create OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment or .env file.")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def extract_section(output: dict, section: str) -> str:
    """
    Extract the relevant section from the output for evaluation.
    """
    s0_s2b = output.get("llm_output", {}).get("s0_s2b", "")
    s3 = output.get("llm_output", {}).get("s3", "")
    tool_summary = output.get("tool", {}).get("result", {}).get("summary", "")
    full_text = s0_s2b + "\n\n## S2-EVID: 分析結果\n" + tool_summary + "\n\n" + s3

    if section == "all":
        return full_text

    # Try to extract specific sections from the LLM output
    section_map = {
        "s0": r"## S0[:：].*?(?=## S1)",
        "s1": r"## S1[:：].*?(?=## S2a)",
        "s2a": r"## S2a[:：].*?(?=## S2b)",
        "s2b": r"## S2b[:：].*?(?=## S2-EVID|## S3|$)",
        "s3": None,  # S3 is in separate output
    }

    if section == "s3":
        return s3 if s3 else full_text

    pattern = section_map.get(section)
    if pattern:
        match = re.search(pattern, s0_s2b, re.DOTALL)
        if match:
            return match.group(0)

    # Fallback to full text
    return full_text


def score_item(
    client: OpenAI,
    relevant_output: str,
    item: dict,
    model: str = "gpt-4o",
) -> dict:
    """
    Score a single checklist item.
    Returns dict with score, evidence, item_id.
    """
    prompt = SCORING_PROMPT.format(
        relevant_output=relevant_output,
        checklist_item=item["description"],
        gold_standard=item["gold_standard"],
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_completion_tokens=500,
    )

    text = response.choices[0].message.content.strip()

    # Parse JSON response
    try:
        # Try to extract JSON from the response
        json_match = re.search(r"\{[^}]+\}", text)
        if json_match:
            result = json.loads(json_match.group(0))
            score = int(result.get("score", 0))
            evidence = result.get("evidence", "")
        else:
            score = 0
            evidence = f"Could not parse response: {text}"
    except (json.JSONDecodeError, ValueError):
        score = 0
        evidence = f"Could not parse response: {text}"

    return {
        "item_id": item["id"],
        "description": item["description"],
        "gold_standard": item["gold_standard"],
        "score": score,
        "evidence": evidence,
    }


def evaluate_single(
    case_id: str,
    condition: str,
    model: str = "gpt-4o",
    input_dir: str = "outputs",
    out_dir: str = "eval_outputs",
) -> dict:
    """
    Evaluate a single (case, condition) output.
    """
    print(f"\nEvaluating: case={case_id}, condition={condition}")

    # Load output
    input_path = Path(input_dir) / f"run_{case_id}_{condition}.json"
    if not input_path.exists():
        print(f"  Error: Output file not found: {input_path}")
        return None

    with open(input_path, "r", encoding="utf-8") as f:
        output = json.load(f)

    # Get checklist for this case
    checklist = CHECKLIST.get(case_id)
    if not checklist:
        print(f"  Error: No checklist defined for case '{case_id}'")
        return None

    client = create_client()
    results = []

    for item in checklist:
        relevant_output = extract_section(output, item["section"])
        print(f"  Scoring item {item['id']}: {item['description'][:50]}...")

        result = score_item(client, relevant_output, item, model=model)
        results.append(result)
        time.sleep(0.5)  # Rate limit

    # Compute aggregates
    total_score = sum(r["score"] for r in results)
    max_score = len(results) * 2
    score_pct = total_score / max_score * 100 if max_score > 0 else 0

    eval_result = {
        "metadata": {
            "case_id": case_id,
            "condition": condition,
            "eval_model": model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_items": len(results),
        },
        "scores": results,
        "summary": {
            "total_score": total_score,
            "max_score": max_score,
            "score_pct": round(score_pct, 1),
            "by_score": {
                "0": sum(1 for r in results if r["score"] == 0),
                "1": sum(1 for r in results if r["score"] == 1),
                "2": sum(1 for r in results if r["score"] == 2),
            },
        },
    }

    # Save
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"eval_{case_id}_{condition}.json"
    filepath = out_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)

    print(f"  Score: {total_score}/{max_score} ({score_pct:.1f}%)")
    print(f"  Saved to: {filepath}")

    return eval_result


def generate_summary(out_dir: str = "eval_outputs") -> dict:
    """
    Aggregate all evaluation results into a summary.
    """
    out_path = Path(out_dir)
    eval_files = sorted(out_path.glob("eval_*.json"))

    if not eval_files:
        print(f"No evaluation files found in {out_dir}")
        return None

    # Skip summary file itself
    eval_files = [f for f in eval_files if f.name != "eval_summary.json"]

    all_results = []
    for filepath in eval_files:
        with open(filepath, "r", encoding="utf-8") as f:
            result = json.load(f)
            all_results.append(result)

    # Build summary table
    summary_rows = []
    for result in all_results:
        meta = result["metadata"]
        summ = result["summary"]
        summary_rows.append({
            "case_id": meta["case_id"],
            "condition": meta["condition"],
            "total_score": summ["total_score"],
            "max_score": summ["max_score"],
            "score_pct": summ["score_pct"],
            "n_items": meta["n_items"],
            "score_0": summ["by_score"]["0"],
            "score_1": summ["by_score"]["1"],
            "score_2": summ["by_score"]["2"],
        })

    # Aggregate by condition
    condition_agg = {}
    for row in summary_rows:
        cond = row["condition"]
        if cond not in condition_agg:
            condition_agg[cond] = {"total": 0, "max": 0, "n_cases": 0}
        condition_agg[cond]["total"] += row["total_score"]
        condition_agg[cond]["max"] += row["max_score"]
        condition_agg[cond]["n_cases"] += 1

    for cond, agg in condition_agg.items():
        agg["score_pct"] = round(agg["total"] / agg["max"] * 100, 1) if agg["max"] > 0 else 0

    # Item-level comparison across conditions
    item_comparison = {}
    for result in all_results:
        case_id = result["metadata"]["case_id"]
        condition = result["metadata"]["condition"]
        for score_item in result["scores"]:
            key = f"{case_id}_{score_item['item_id']}"
            if key not in item_comparison:
                item_comparison[key] = {
                    "case_id": case_id,
                    "item_id": score_item["item_id"],
                    "description": score_item["description"],
                }
            item_comparison[key][condition] = score_item["score"]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_evaluations": len(all_results),
        "per_case_condition": summary_rows,
        "per_condition": condition_agg,
        "item_comparison": list(item_comparison.values()),
    }

    # Save summary
    summary_path = out_path / "eval_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"\n--- Per condition ---")
    for cond, agg in sorted(condition_agg.items()):
        print(f"  {cond}: {agg['total']}/{agg['max']} ({agg['score_pct']}%) [{agg['n_cases']} cases]")

    print(f"\n--- Per case x condition ---")
    print(f"{'Case':<20} {'Condition':<12} {'Score':>8} {'%':>8}")
    print(f"{'-'*52}")
    for row in summary_rows:
        print(
            f"{row['case_id']:<20} {row['condition']:<12} "
            f"{row['total_score']:>3}/{row['max_score']:<4} "
            f"{row['score_pct']:>6.1f}%"
        )

    # Diff analysis: items where proposed > baseline
    print(f"\n--- Items where conditions differ ---")
    for item in item_comparison.values():
        baseline = item.get("baseline", "-")
        proposed = item.get("proposed", "-")
        if baseline != "-" and proposed != "-" and baseline != proposed:
            direction = "proposed > baseline" if proposed > baseline else "baseline > proposed"
            print(
                f"  {item['case_id']}/{item['item_id']}: "
                f"baseline={baseline}, proposed={proposed} ({direction})"
            )

    print(f"\nSaved to: {summary_path}")
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate causal inference analysis outputs."
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
        default="gpt-4o",
        help="Evaluation model",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="outputs",
        help="Input directory (run outputs)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="eval_outputs",
        help="Output directory for evaluation results",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate summary from existing evaluations",
    )
    args = parser.parse_args()

    if args.summary:
        generate_summary(args.out)
        return

    if args.case is None:
        parser.error("--case is required (or use --summary)")

    # Resolve case list
    all_cases = list(CHECKLIST.keys())
    if args.case == "all":
        case_ids = all_cases
    else:
        case_ids = [args.case]

    # Resolve condition list
    if args.condition == "all":
        conditions = ["baseline", "proposed"]
    elif args.condition:
        conditions = [args.condition]
    else:
        conditions = ["baseline", "proposed"]

    # Run evaluations
    for case_id in case_ids:
        for condition in conditions:
            try:
                evaluate_single(
                    case_id, condition,
                    model=args.model,
                    input_dir=args.input,
                    out_dir=args.out,
                )
            except Exception as e:
                print(f"\nError evaluating {case_id}/{condition}: {e}")
                import traceback
                traceback.print_exc()

    # Auto-generate summary
    generate_summary(args.out)


if __name__ == "__main__":
    main()
