"""LLM client wrapper with mock mode."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


class LLMClient:
    """Role-based generator for designer/supervisor/evidence."""

    def __init__(self, mock: bool = False, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self.mock = mock
        self.model = model
        self.temperature = temperature
        self._client = None

        if not mock:
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

    def generate(
        self,
        role: str,
        stage: str,
        prompt_text: str,
        context: Dict[str, Any],
        attempt: int,
    ) -> str:
        if self.mock:
            return self._generate_mock(role=role, stage=stage, context=context, attempt=attempt)

        payload = {
            "role": role,
            "stage": stage,
            "attempt": attempt,
            "context": context,
        }
        user_text = (
            f"{prompt_text}\n\n"
            f"---\n"
            f"以下のJSONコンテキストを参照し、JSONのみで回答してください。\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=1200,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise research workflow agent. Return JSON only.",
                },
                {"role": "user", "content": user_text},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    def _generate_mock(self, role: str, stage: str, context: Dict[str, Any], attempt: int) -> str:
        break_stage = os.getenv("MOCK_BREAK_STAGE", "").strip()
        break_role = os.getenv("MOCK_BREAK_ROLE", "").strip()
        if break_stage and stage == break_stage and (not break_role or role == break_role):
            return "THIS_IS_NOT_JSON"

        if role == "designer" and stage == "S1":
            return json.dumps(
                {
                    "hypotheses": [
                        {
                            "id": "H1",
                            "statement": "政策介入は主要アウトカムを改善する",
                            "falsify": "主要指標が事前定義閾値を超えて改善しない",
                            "distinctive_prediction": "主要アウトカムのみ改善し、偽アウトカムは変化しない",
                        },
                        {
                            "id": "H2",
                            "statement": "観測効果は選択バイアスによる見かけの効果である",
                            "falsify": "事前トレンド・偽アウトカム検証で差が確認されない",
                            "distinctive_prediction": "主要アウトカムと偽アウトカムに同方向の差が出る",
                        },
                    ]
                },
                ensure_ascii=False,
            )

        if role == "supervisor" and stage == "S1-CHK":
            if attempt == 0:
                return json.dumps(
                    {
                        "verdict": "NG",
                        "issues": ["反証条件が定量閾値として弱い"],
                        "fix_instructions": ["各仮説の反証条件に具体的な判定基準を追加せよ"],
                        "pass_requirements": ["各仮説にテスト可能な棄却条件がある"],
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "verdict": "OK",
                    "issues": [],
                    "fix_instructions": [],
                    "pass_requirements": ["仮説数2〜4、各仮説に反証条件あり"],
                },
                ensure_ascii=False,
            )

        if role == "designer" and stage == "S2":
            s0 = {}
            if isinstance(context, dict):
                inner = context.get("context")
                if isinstance(inner, dict):
                    s0 = inner.get("s0", {}) if isinstance(inner.get("s0"), dict) else {}
            required_checks = s0.get("required_checks") if isinstance(s0, dict) else None
            checks = required_checks if isinstance(required_checks, list) and required_checks else [
                "parallel trend",
                "placebo",
                "heterogeneity",
            ]
            return json.dumps(
                {
                    "experiment_plan": {
                        "what_to_compare": "高曝露群と低曝露群の前後差",
                        "what_to_measure": "主要アウトカム、偽アウトカム、事前トレンド",
                        "procedure": "差の差推定と頑健性チェックを実施",
                        "decision_rule": "主要係数が閾値を満たし、偽検証で棄却されない場合に支持",
                        "checks": checks,
                        "hypothesis_rules": [
                            {
                                "id": "H1",
                                "accept_if": "主要アウトカム改善かつ偽アウトカム変化なし",
                                "reject_if": "主要アウトカムの改善なし",
                                "hold_if": "改善はあるが頑健性が不足",
                            },
                            {
                                "id": "H2",
                                "accept_if": "主要アウトカムと偽アウトカムの差が同方向",
                                "reject_if": "偽アウトカムで差が確認されない",
                                "hold_if": "一部仕様でのみ差が出る",
                            },
                        ],
                    }
                },
                ensure_ascii=False,
            )

        if role == "supervisor" and stage == "S2-CHK":
            return json.dumps(
                {
                    "verdict": "OK",
                    "issues": [],
                    "fix_instructions": [],
                    "pass_requirements": ["勝敗判定ルールが明示されている"],
                },
                ensure_ascii=False,
            )

        if role == "designer" and stage == "S3":
            evid = context.get("s2_evidence", {})
            findings = evid.get("findings", []) if isinstance(evid, dict) else []
            evidence_ids = [f.get("id") for f in findings if isinstance(f, dict) and f.get("id")]
            if not evidence_ids:
                evidence_ids = ["E1"]
            return json.dumps(
                {
                    "conclusion": {
                        "hypothesis_judgments": [
                            {
                                "id": "H1",
                                "decision": "survive",
                                "evidence_ids": evidence_ids[:1],
                                "falsify_triggered": False,
                                "accept_condition_met": True,
                                "reject_condition_met": False,
                                "hold_condition_met": False,
                                "why": "主要結果がH1と整合したため。",
                            },
                            {
                                "id": "H2",
                                "decision": "reject",
                                "evidence_ids": evidence_ids[:1],
                                "falsify_triggered": True,
                                "accept_condition_met": False,
                                "reject_condition_met": True,
                                "hold_condition_met": False,
                                "why": "主要結果がH2の反証条件に当たったため。",
                            },
                        ],
                        "which_hypotheses_survive": ["H1"],
                        "which_rejected": ["H2"],
                        "reasoning": f"実験結果を反映した。使用した証拠ID: {', '.join(evidence_ids[:2])}",
                        "strength": "weak",
                        "next_step": "追加検証として感度分析を行う",
                    }
                },
                ensure_ascii=False,
            )

        if role == "supervisor" and stage == "S3-CHK":
            return json.dumps(
                {
                    "verdict": "OK",
                    "issues": [],
                    "fix_instructions": [],
                    "pass_requirements": ["結論が証拠と整合し、過剰断定がない"],
                },
                ensure_ascii=False,
            )

        # Fallback to parse-error path testing if unknown stage is called.
        return "{}"
