"""Layer 2: Operationalized Rubric for the oversight protocol.

Evaluates research output against the protocol's rubric table.
Each item is scored as Explicit (2) / Partial (1) / Absent (0).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Rubric definition
# Each entry: (stage, item_name, description, check_function_name)
# ---------------------------------------------------------------------------

RUBRIC_ITEMS = [
    # S0
    ("S0", "推定対象の明示",
     "estimandが正式に定義され、処置・結果・対象集団が特定されている"),
    ("S0", "主要/副次アウトカムの区別",
     "主要アウトカムが事前に宣言されている"),
    ("S0", "主張の境界条件",
     "主張の適用範囲と限界が明示されている"),
    # S1
    ("S1", "競合仮説の列挙",
     "二つ以上の代替的説明が明示されている"),
    ("S1", "反証条件の設定",
     "各仮説について棄却条件が事前に定められている"),
    ("S1", "弁別予測の特定",
     "競合仮説間で異なる予測を生む条件が明示されている"),
    # S2
    ("S2", "識別仮定の明示",
     "必要な仮定が列挙され、違反時の帰結が記述されている"),
    ("S2", "判定規則の事前固定",
     "各仮説にaccept/reject/hold条件が事前に定められている"),
    ("S2", "分析分岐の管理",
     "主要な分岐点が列挙され、主分析と感度分析が区別されている"),
    # S3
    ("S3", "エビデンスとの突合",
     "各仮説の判定にエビデンスの具体的参照が付されている"),
    ("S3", "反証条件の発火確認",
     "各仮説の反証条件が発火したかどうかが明示的に検査されている"),
    ("S3", "結論の強さの段階づけ",
     "strong/weak/holdの判定が根拠とともに示されている"),
    ("S3", "残存する代替説明",
     "排除されなかった仮説・交絡・一般化の限界が明示されている"),
]


def evaluate_s0(s0: Dict[str, Any]) -> List[Tuple[str, str, int, str]]:
    """Evaluate S0 output against rubric. Returns [(stage, item, score, reason)]."""
    results = []

    # 推定対象の明示
    estimand = s0.get("estimand", "")
    rq = s0.get("research_question", "")
    if isinstance(estimand, str) and len(estimand.strip()) > 20:
        results.append(("S0", "推定対象の明示", 2, "estimandが正式に定義されている"))
    elif isinstance(rq, str) and len(rq.strip()) > 10:
        results.append(("S0", "推定対象の明示", 1, "研究課題は述べられているがestimandが形式的に定義されていない"))
    else:
        results.append(("S0", "推定対象の明示", 0, "推定対象が不明確"))

    # 主要/副次アウトカムの区別
    primary = s0.get("primary_outcomes", [])
    secondary = s0.get("secondary_outcomes", [])
    if isinstance(primary, list) and len(primary) >= 1 and isinstance(secondary, list) and len(secondary) >= 1:
        results.append(("S0", "主要/副次アウトカムの区別", 2, "主要・副次アウトカムが事前に宣言されている"))
    elif isinstance(primary, list) and len(primary) >= 1:
        results.append(("S0", "主要/副次アウトカムの区別", 1, "主要アウトカムはあるが副次の区別が不明確"))
    else:
        results.append(("S0", "主要/副次アウトカムの区別", 0, "アウトカムの事前宣言なし"))

    # 主張の境界条件
    boundary = s0.get("claim_boundary", {})
    if isinstance(boundary, dict) and len(boundary) >= 2:
        results.append(("S0", "主張の境界条件", 2, "主張の適用範囲と限界が明示されている"))
    elif isinstance(boundary, dict) and len(boundary) >= 1:
        results.append(("S0", "主張の境界条件", 1, "境界条件の記述が部分的"))
    else:
        results.append(("S0", "主張の境界条件", 0, "境界条件の記述なし"))

    return results


def evaluate_s1(s1: Dict[str, Any]) -> List[Tuple[str, str, int, str]]:
    """Evaluate S1 output against rubric."""
    results = []
    hyps = s1.get("hypotheses", [])

    # 競合仮説の列挙
    if isinstance(hyps, list) and len(hyps) >= 2:
        results.append(("S1", "競合仮説の列挙", 2, f"{len(hyps)}個の競合仮説が明示されている"))
    elif isinstance(hyps, list) and len(hyps) == 1:
        results.append(("S1", "競合仮説の列挙", 1, "仮説が1つのみ"))
    else:
        results.append(("S1", "競合仮説の列挙", 0, "競合仮説なし"))

    # 反証条件の設定
    if isinstance(hyps, list) and hyps:
        has_falsify = [h for h in hyps if isinstance(h, dict) and isinstance(h.get("falsify"), str) and len(h["falsify"].strip()) > 5]
        if len(has_falsify) == len(hyps):
            results.append(("S1", "反証条件の設定", 2, "全仮説に反証条件が定められている"))
        elif len(has_falsify) > 0:
            results.append(("S1", "反証条件の設定", 1, "一部の仮説のみ反証条件あり"))
        else:
            results.append(("S1", "反証条件の設定", 0, "反証条件の記述なし"))
    else:
        results.append(("S1", "反証条件の設定", 0, "仮説なし"))

    # 弁別予測の特定
    if isinstance(hyps, list) and hyps:
        has_dp = [h for h in hyps if isinstance(h, dict) and isinstance(h.get("distinctive_prediction"), str) and len(h["distinctive_prediction"].strip()) > 5]
        if len(has_dp) >= 2:
            results.append(("S1", "弁別予測の特定", 2, "競合仮説間の弁別予測が明示されている"))
        elif len(has_dp) >= 1:
            results.append(("S1", "弁別予測の特定", 1, "弁別予測の記述が部分的"))
        else:
            results.append(("S1", "弁別予測の特定", 0, "弁別予測なし"))
    else:
        results.append(("S1", "弁別予測の特定", 0, "仮説なし"))

    return results


def evaluate_s2(s2: Dict[str, Any]) -> List[Tuple[str, str, int, str]]:
    """Evaluate S2 output against rubric."""
    results = []
    plan = s2.get("experiment_plan", {})
    if not isinstance(plan, dict):
        plan = {}

    # 識別仮定の明示
    assumptions = plan.get("identification_assumptions", [])
    if isinstance(assumptions, list) and len(assumptions) >= 1:
        has_violated = [a for a in assumptions if isinstance(a, dict) and isinstance(a.get("if_violated"), str) and len(a["if_violated"].strip()) > 5]
        if len(has_violated) == len(assumptions):
            results.append(("S2", "識別仮定の明示", 2, "仮定が列挙され、違反時の帰結が記述されている"))
        else:
            results.append(("S2", "識別仮定の明示", 1, "仮定は列挙されるが違反時の帰結が不明"))
    else:
        results.append(("S2", "識別仮定の明示", 0, "識別仮定の記述なし"))

    # 判定規則の事前固定
    rules = plan.get("hypothesis_rules", [])
    if isinstance(rules, list) and len(rules) >= 2:
        complete = [r for r in rules if isinstance(r, dict)
                    and all(isinstance(r.get(k), str) and len(r[k].strip()) > 3 for k in ["accept_if", "reject_if", "hold_if"])]
        if len(complete) == len(rules):
            results.append(("S2", "判定規則の事前固定", 2, "全仮説にaccept/reject/hold条件が定められている"))
        else:
            results.append(("S2", "判定規則の事前固定", 1, "一部の仮説のみ条件あり"))
    else:
        results.append(("S2", "判定規則の事前固定", 0, "判定規則なし"))

    # 分析分岐の管理
    forks = plan.get("analysis_forks", [])
    if isinstance(forks, list) and len(forks) >= 2:
        results.append(("S2", "分析分岐の管理", 2, "主要な分岐点が列挙されている"))
    elif isinstance(forks, list) and len(forks) >= 1:
        results.append(("S2", "分析分岐の管理", 1, "分岐の記述が限定的"))
    else:
        results.append(("S2", "分析分岐の管理", 0, "分析分岐の記述なし"))

    return results


def evaluate_s3(s3: Dict[str, Any]) -> List[Tuple[str, str, int, str]]:
    """Evaluate S3 output against rubric."""
    results = []
    c = s3.get("conclusion", {})
    if not isinstance(c, dict):
        c = {}

    judgments = c.get("hypothesis_judgments", [])

    # エビデンスとの突合
    if isinstance(judgments, list) and judgments:
        has_evidence = [j for j in judgments if isinstance(j, dict) and isinstance(j.get("evidence_ids"), list) and len(j["evidence_ids"]) > 0]
        if len(has_evidence) == len(judgments):
            results.append(("S3", "エビデンスとの突合", 2, "全判定にエビデンス参照が付されている"))
        elif len(has_evidence) > 0:
            results.append(("S3", "エビデンスとの突合", 1, "一部の判定にのみエビデンス参照あり"))
        else:
            results.append(("S3", "エビデンスとの突合", 0, "エビデンス参照なし"))
    else:
        results.append(("S3", "エビデンスとの突合", 0, "判定表なし"))

    # 反証条件の発火確認
    if isinstance(judgments, list) and judgments:
        has_falsify = [j for j in judgments if isinstance(j, dict) and isinstance(j.get("falsify_triggered"), bool)]
        if len(has_falsify) == len(judgments):
            results.append(("S3", "反証条件の発火確認", 2, "全仮説の反証条件が検査されている"))
        elif len(has_falsify) > 0:
            results.append(("S3", "反証条件の発火確認", 1, "一部のみ検査"))
        else:
            results.append(("S3", "反証条件の発火確認", 0, "反証条件への言及なし"))
    else:
        results.append(("S3", "反証条件の発火確認", 0, "判定表なし"))

    # 結論の強さの段階づけ
    strength = c.get("strength", "")
    reasoning = c.get("reasoning", "")
    if isinstance(strength, str) and strength in ("strong", "weak", "hold") and isinstance(reasoning, str) and len(reasoning) > 20:
        results.append(("S3", "結論の強さの段階づけ", 2, f"strength={strength}が根拠とともに示されている"))
    elif isinstance(strength, str) and strength in ("strong", "weak", "hold"):
        results.append(("S3", "結論の強さの段階づけ", 1, "段階づけはあるが根拠が不十分"))
    else:
        results.append(("S3", "結論の強さの段階づけ", 0, "段階づけなし"))

    # 残存する代替説明
    remaining = c.get("remaining_alternatives", [])
    if isinstance(remaining, list) and len(remaining) >= 2:
        results.append(("S3", "残存する代替説明", 2, "残存する代替説明が明示されている"))
    elif isinstance(remaining, list) and len(remaining) >= 1:
        results.append(("S3", "残存する代替説明", 1, "部分的な記述"))
    else:
        results.append(("S3", "残存する代替説明", 0, "記述なし"))

    return results


def evaluate_full(context: Dict[str, Any]) -> List[Tuple[str, str, int, str]]:
    """Evaluate all stages present in context. Returns list of (stage, item, score, reason)."""
    results = []
    if "s0" in context:
        results.extend(evaluate_s0(context["s0"]))
    if "S1" in context:
        results.extend(evaluate_s1(context["S1"]))
    if "S2" in context:
        results.extend(evaluate_s2(context["S2"]))
    if "S3" in context:
        results.extend(evaluate_s3(context["S3"]))
    return results


def format_rubric_report(results: List[Tuple[str, str, int, str]]) -> str:
    """Format rubric results as a readable report."""
    score_labels = {0: "Absent", 1: "Partial", 2: "Explicit"}
    lines = ["## Rubric Evaluation Report", ""]
    lines.append(f"| Stage | Item | Score | Reason |")
    lines.append(f"|-------|------|-------|--------|")

    total = 0
    max_total = 0
    for stage, item, score, reason in results:
        label = score_labels.get(score, "?")
        lines.append(f"| {stage} | {item} | {label} ({score}/2) | {reason} |")
        total += score
        max_total += 2

    lines.append("")
    lines.append(f"**Total: {total}/{max_total}** ({total/max_total*100:.0f}%)" if max_total > 0 else "**No items evaluated**")
    return "\n".join(lines)
