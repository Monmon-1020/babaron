"""LLM client wrapper with mock mode for the 3-layer oversight protocol."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


class LLMClient:
    """Role-based generator for designer / supervisor."""

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

        # gpt-5.x uses max_completion_tokens; older models use max_tokens
        token_param = (
            {"max_completion_tokens": 8000}
            if self.model.startswith("gpt-5") or self.model.startswith("o")
            else {"max_tokens": 4000}
        )
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            **token_param,
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
            return json.dumps({
                "hypotheses": [
                    {
                        "id": "H1",
                        "statement": "ウェブ閲覧コンテンツのvalenceは気分に因果的影響を与える（コンテンツ→気分）",
                        "falsify": "ネガティブコンテンツへの実験的曝露が中立条件と比較して気分に有意差を生じない場合",
                        "distinctive_prediction": "実験操作によりネガティブ条件群でのみ気分が低下し、中立条件群では変化しない",
                    },
                    {
                        "id": "H2",
                        "statement": "気分状態がその後の閲覧コンテンツのvalence選択に因果的影響を与える（気分→コンテンツ）",
                        "falsify": "気分を実験的に操作した後の自由閲覧フェーズで、条件間の閲覧valenceに差がない場合",
                        "distinctive_prediction": "ネガティブ気分誘導群がより多くのネガティブコンテンツを選択する",
                    },
                    {
                        "id": "H3",
                        "statement": "観察される相関は第三変数（パーソナリティ特性等）によるスプリアスな関連である",
                        "falsify": "実験操作による因果効果が確認され、個人特性を統制した後にも効果が残る場合",
                        "distinctive_prediction": "個人特性を統制すると閲覧valenceと気分の関連が消失する",
                    },
                ],
                "hypothesis_relations": [
                    {
                        "pair": ["H1", "H2"],
                        "relation": "independent",
                        "note": "双方向因果として共存可能。H1（コンテンツ→気分）とH2（気分→コンテンツ）は同時に成立しうる",
                        "justification": "双方向因果として共存可能。H1（コンテンツ→気分）とH2（気分→コンテンツ）は同時に成立しうる",
                    },
                    {
                        "pair": ["H1", "H3"],
                        "relation": "exclusive",
                        "note": "H3はH1の効果が交絡によるものと主張するため、H1が実験で確認されればH3は棄却される",
                        "justification": "H3はH1の効果が交絡によるものと主張するため、H1が実験で確認されればH3は棄却される",
                    },
                    {
                        "pair": ["H2", "H3"],
                        "relation": "exclusive",
                        "note": "H3はH2の効果も交絡によるものと主張するため、H2が実験で確認されればH3は棄却される",
                        "justification": "H3はH2の効果も交絡によるものと主張するため、H2が実験で確認されればH3は棄却される",
                    },
                ],
            }, ensure_ascii=False)

        if role == "supervisor" and stage == "S1-CHK":
            if attempt == 0:
                return json.dumps({
                    "verdict": "NG",
                    "issues": ["H3の反証条件が実験操作の結果に依存しており、独立した検証が不明確"],
                    "fatal_issues": [],
                    "minor_issues": ["H3の反証条件が実験操作の結果に依存しており、独立した検証が不明確"],
                    "fix_instructions": ["H3の反証条件を、実験操作とは独立に検証可能な形に修正せよ"],
                    "pass_requirements": ["各仮説にテスト可能で独立した反証条件がある"],
                }, ensure_ascii=False)
            return json.dumps({
                "verdict": "OK",
                "issues": [],
                "fatal_issues": [],
                "minor_issues": [],
                "fix_instructions": [],
                "pass_requirements": ["仮説数2〜4、各仮説に反証条件・弁別予測あり"],
            }, ensure_ascii=False)

        if role == "designer" and stage == "S2":
            return json.dumps({
                "experiment_plan": {
                    "what_to_compare": "ネガティブコンテンツ曝露群 vs 中立コンテンツ群、およびラベル介入あり群 vs なし群",
                    "what_to_measure": "気分スコア（VAS）、閲覧valence（NLP定量化）、クリック行動",
                    "procedure": "Study 3で実験操作、Study 4でラベル介入を実施し、前後で気分と閲覧行動を測定",
                    "identification_assumptions": [
                        {
                            "id": "IA1",
                            "description": "ランダム割当により、条件間の気分ベースラインに系統的差異がない",
                            "if_violated": "ベースライン差が効果推定を歪め、過大/過小推定となる",
                        },
                        {
                            "id": "IA2",
                            "description": "NLPによるvalence測定が閲覧コンテンツの感情的価値を妥当に捕捉している",
                            "if_violated": "valence測定の誤分類が効果推定にノイズを加え、帰無に向かうバイアスを生じる",
                        },
                        {
                            "id": "IA3",
                            "description": "SUTVA: ある参加者の処置が他の参加者のアウトカムに影響しない",
                            "if_violated": "参加者間の情報共有等があれば処置効果が汚染される",
                        },
                    ],
                    "hypothesis_rules": [
                        {
                            "id": "H1",
                            "accept_if": "Study 3でネガティブ条件群の気分が中立群より有意に低下（p<0.05, η²p>0.01）",
                            "reject_if": "条件間の気分差が非有意またはη²p<0.01",
                            "hold_if": "有意だが効果量が小さく頑健性チェックで不安定",
                        },
                        {
                            "id": "H2",
                            "accept_if": "実験操作後の自由閲覧で条件間のvalence差が有意（p<0.05）",
                            "reject_if": "自由閲覧フェーズで条件間のvalence差が非有意",
                            "hold_if": "一部のNLP指標でのみ有意で、他では非有意",
                        },
                        {
                            "id": "H3",
                            "accept_if": "個人特性を統制すると閲覧valenceと気分の関連が消失し、実験効果も消失",
                            "reject_if": "実験操作による因果効果が再現され、統制後も関連が残る",
                            "hold_if": "統制後に関連が弱まるが完全には消失しない",
                        },
                    ],
                    "analysis_forks": [
                        "NLP指標の選択（NRC VAD / Hu-Liu / DistilBERT）",
                        "外れ値除外基準（±3SD vs ±2SD）",
                        "共変量の選択（年齢・性別・ベースライン気分）",
                    ],
                },
                "identification_assumptions": [
                    {
                        "id": "IA1",
                        "assumption": "ランダム割当により、条件間の気分ベースラインに系統的差異がない",
                        "description": "ランダム割当により、条件間の気分ベースラインに系統的差異がない",
                        "if_violated": "ベースライン差が効果推定を歪め、過大/過小推定となる",
                    },
                    {
                        "id": "IA2",
                        "assumption": "NLPによるvalence測定が閲覧コンテンツの感情的価値を妥当に捕捉している",
                        "description": "NLPによるvalence測定が閲覧コンテンツの感情的価値を妥当に捕捉している",
                        "if_violated": "valence測定の誤分類が効果推定にノイズを加え、帰無に向かうバイアスを生じる",
                    },
                ],
            }, ensure_ascii=False)

        if role == "supervisor" and stage == "S2-CHK":
            return json.dumps({
                "verdict": "OK",
                "issues": [],
                "fatal_issues": [],
                "minor_issues": [],
                "fix_instructions": [],
                "pass_requirements": ["識別仮定が明示され、各仮説にaccept/reject/hold条件が定義されている"],
            }, ensure_ascii=False)

        if role == "designer" and stage == "S3":
            evid = {}
            if isinstance(context, dict):
                inner = context.get("context", context)
                if isinstance(inner, dict):
                    evid = inner.get("s2_evidence", {})
            findings = evid.get("findings", []) if isinstance(evid, dict) else []
            evidence_ids = [f.get("id") for f in findings if isinstance(f, dict) and f.get("id")]
            if not evidence_ids:
                evidence_ids = ["E1", "E2", "E3", "E4"]

            return json.dumps({
                "conclusion": {
                    "hypothesis_judgments": [
                        {
                            "id": "H1",
                            "decision": "survive",
                            "evidence_ids": ["E2"],
                            "falsify_triggered": False,
                            "accept_condition_met": True,
                            "reject_condition_met": False,
                            "hold_condition_met": False,
                            "why": "Study 3でネガティブ条件群の気分が有意に低下（η²p=0.151）。accept条件を満たす。",
                        },
                        {
                            "id": "H2",
                            "decision": "survive",
                            "evidence_ids": ["E3"],
                            "falsify_triggered": False,
                            "accept_condition_met": True,
                            "reject_condition_met": False,
                            "hold_condition_met": False,
                            "why": "Study 3の自由閲覧フェーズでネガティブ条件群がよりネガティブなコンテンツを選択。",
                        },
                        {
                            "id": "H3",
                            "decision": "reject",
                            "evidence_ids": ["E2", "E3"],
                            "falsify_triggered": True,
                            "accept_condition_met": False,
                            "reject_condition_met": True,
                            "hold_condition_met": False,
                            "why": "実験操作による因果効果が確認され、スプリアス関連仮説は棄却。",
                        },
                    ],
                    "which_hypotheses_survive": ["H1", "H2"],
                    "which_rejected": ["H3"],
                    "relation_consistency_check": [
                        {"pair": ["H1", "H2"], "declared_relation": "independent", "judgments": ["survive", "survive"], "consistent": True, "note": "independentなのでどちらもsurvive可能"},
                        {"pair": ["H1", "H3"], "declared_relation": "exclusive", "judgments": ["survive", "reject"], "consistent": True, "note": "exclusiveで一方がsurvive、他方がreject"},
                    ],
                    "failed_hypotheses": [{"id": "H3", "reason": "実験操作による因果効果が確認され、交絡仮説は棄却", "evidence_ids": ["E2", "E3"]}],
                    "surviving_hypotheses": [
                        {"id": "H1", "remaining_weakness": "短期効果のみ確認"},
                        {"id": "H2", "remaining_weakness": "自由閲覧フェーズのみ確認"},
                    ],
                    "identification_assumption_concerns": [
                        {"id": "IA1", "violated_or_uncertain": "satisfied", "impact_on_conclusion": "ランダム割付は成立"},
                        {"id": "IA2", "violated_or_uncertain": "uncertain", "impact_on_conclusion": "NLPのvalence測定精度に不確実性あり"},
                    ],
                    "residual_alternatives": [
                        "需要特性（demand characteristics）が実験結果に影響した可能性",
                        "短期効果のみであり、長期的な閲覧-気分ループの存在は未確認",
                        "オンラインサンプルの代表性の限界",
                    ],
                    "remaining_alternatives": [
                        "需要特性（demand characteristics）が実験結果に影響した可能性",
                        "短期効果のみであり、長期的な閲覧-気分ループの存在は未確認",
                        "オンラインサンプルの代表性の限界",
                    ],
                    "flip_condition": "NLP指標の誤分類が系統的にネガティブ方向に偏っていた場合、効果は消失する",
                    "reasoning": "実験的操作（Study 3）により双方向の因果関係が支持された。介入（Study 4）でも行動変容と気分改善が確認された。",
                    "strength": "weak",
                    "strength_justification": "識別仮定の一部（NLPの精度）に不確実性が残るため、strongには至らない。",
                    "next_step": "臨床集団での再現性検証、長期介入効果の測定、NLP指標の交差検証",
                }
            }, ensure_ascii=False)

        if role == "supervisor" and stage == "S3-CHK":
            return json.dumps({
                "verdict": "OK",
                "issues": [],
                "fatal_issues": [],
                "minor_issues": [],
                "fix_instructions": [],
                "pass_requirements": ["結論がエビデンスと整合し、強さの段階づけが妥当である"],
            }, ensure_ascii=False)

        return "{}"
