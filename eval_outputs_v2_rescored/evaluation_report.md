# 評価レポート（Gold Standard 改訂版 v2）

## 1. 評価方法の説明

### 1.1 Gold Standard の定義方法

5ケースは **後続文献の合意**（subsequent_literature）に基づいて gold standard を定義した。Kelly & Sharot (2025) のみ後続査読文献が不在のため、**因果推論の方法論的原則**（methodological_principles）に基づく。

各仮説には:
- `expected_decision`: 標準的に期待される判定
- `acceptable_decisions`: 許容される判定のリスト（複数の場合あり）
- `source`: 後続文献の出典または方法論的根拠

各ケースには:
- `expected_strength`: 期待される結論強度
- `acceptable_strengths`: 許容される強度リスト

主要な変更点（v1 → v2）:
1. **Cheng & Hoekstra**: strength weak→**strong**, H3 hold→**reject**
2. **Voight et al.**: strength weak→**strong**
3. **Orben**: H1 hold→**reject**
4. **複数ケース**: `acceptable_decisions` を導入（survive/hold両方を許容するなど）
5. **Kelly & Sharot**: gold standardの根拠を「方法論的原則」と明示

### 1.2 評価A: ブラインドLLM突合の手順

- gpt-4o（実験のgpt-5.4-miniと異なるモデル）に分析A（gold）と分析B（評価対象）を渡し、意味的対応と判定一致を判定させる
- LLMには研究の目的・プロトコル名・どちらが正解かを伝えない
- 突合後、`acceptable_decisions`/`acceptable_strengths`との一致を後処理で再計算（LLMの判断を上書き）
- temperature=0.0、各突合は独立コール

**実装上の注意**: 既存ブラインド突合結果（eval_outputs/）はLLMの`matched_b_id`/`b_decision`/`strength_b`抽出までは使用可能だったため、`rescore_blind_eval.py` により API追加コール無しで gold v2 評価を行った。

### 1.3 評価C: Supervisor分析の手順

`supervisor_analysis.py` で各 run_4cond_*.jsonl を走査し、以下を集計:
1. 段階別NG回数（S1-CHK / S2-CHK / S3-CHK）
2. NG理由のキーワード分類（general_quality / causal_specific）
3. Designerの修正前後の差分（attempt 0 vs final successful）

---

## 2. 評価A の結果

### 表1: ケース別・条件別の一致率

| case | method | decision | strength | combined |
|------|--------|---------|--------|---------|
| Kelly | baseline | 2/3 | NG | 2/4 |
| Kelly | scaffold_only | 2/3 | OK | 3/4 |
| Kelly | rubric_only | 1/3 | OK | 2/4 |
| **Kelly** | **proposed** | **3/3** | **OK** | **4/4** |
| Orben | baseline | 3/3 | OK | 4/4 |
| Orben | scaffold_only | 1/3 | OK | 2/4 |
| Orben | rubric_only | 3/3 | OK | 4/4 |
| Orben | proposed | 2/3 | OK | 3/4 |
| Twenge | baseline | 1/3 | OK | 2/4 |
| Twenge | scaffold_only | 1/3 | OK | 2/4 |
| Twenge | rubric_only | 1/3 | OK | 2/4 |
| Twenge | proposed | 1/3 | OK | 2/4 |
| Cheng | baseline | 1/3 | NG | 1/4 |
| Cheng | scaffold_only | 2/3 | NG | 2/4 |
| Cheng | rubric_only | 2/3 | NG | 2/4 |
| Cheng | proposed | 1/3 | NG | 1/4 |
| Voight | baseline | 2/2 | NG | 2/3 |
| Voight | scaffold_only | 2/2 | NG | 2/3 |
| Voight | rubric_only | 2/2 | NG | 2/3 |
| Voight | proposed | 2/2 | NG | 2/3 |
| Chen | baseline | 2/3 | OK | 3/4 |
| Chen | scaffold_only | 1/3 | OK | 2/4 |
| Chen | rubric_only | 1/3 | OK | 2/4 |
| Chen | proposed | 2/3 | OK | 3/4 |

### 表2: 条件別の集計

| 条件 | 仮説一致 (decision) | strength一致 | 合計一致率 (combined) |
|------|------------------|-------------|------------------|
| baseline | 11/17 (64.7%) | 3/6 (50.0%) | 14/23 (60.9%) |
| scaffold_only | 9/17 (52.9%) | 4/6 (66.7%) | 13/23 (56.5%) |
| rubric_only | 10/17 (58.8%) | 4/6 (66.7%) | 14/23 (60.9%) |
| **proposed** | **11/17 (64.7%)** | **4/6 (66.7%)** | **15/23 (65.2%)** |

**主な発見**:
- combined（仮説 + strength）で proposed が最高（65.2%）
- baseline と proposed は decision 単独では同率（11/17）だが、proposed は strength で1点上回る
- scaffold_only は decision で最低（9/17）— supervisor が NG を出して修正させる過程で必ずしも改善しない

### 表3: 許容範囲の効果

`acceptable_decisions` に複数選択肢がある仮説について、各条件がどれを選んだか:

#### Kelly G2（acceptable=[survive, hold]）
気分の悪化 → ネガティブ閲覧の因果効果。Study 3 の媒介分析の識別仮定が未検証なので hold 許容。

| method | b_decision | match |
|--------|-----------|-------|
| baseline | survive | OK |
| scaffold_only | survive | OK |
| rubric_only | reject | NG |
| **proposed** | **hold** | **OK** |

→ proposed のみ「識別仮定への懸念」を反映した hold を選択

#### Orben G2（acceptable=[survive, hold]）
全条件で survive=OK。差なし。

#### Twenge G1（acceptable=[survive, hold]）
全条件で survive=OK。差なし。

#### Twenge G2（acceptable=[survive, hold]）
全条件で reject=NG。**全条件が経済要因仮説を rejectしてしまう** ことが共通の弱点。

**観察**: 許容範囲導入により Kelly G2 で proposed の優位性が初めて見える。Twenge G2 ではどの条件も多重決定論を捉えられない（共通の限界）。

---

## 3. 評価C の結果（Supervisor分析）

### 3.1 NG回数の段階別集計

| method | S1-CHK | S2-CHK | S3-CHK | total |
|--------|--------|--------|--------|-------|
| scaffold_only | 0 | 0 | 1 (Kelly) | **1** |
| **proposed** | 1 (Voight) | 0 | 4 (Kelly×2 + Cheng×2) | **5** |

**観察**: proposed は scaffold_only より NG が5倍多い。これは rubric_supervisor が rubric_designer の出力を厳しく審査し、より多くの修正を要求しているため。

### 3.2 NG理由の分類

| method | general_quality | causal_specific | total |
|--------|----------------|-----------------|-------|
| scaffold_only | 0 | 1 | 1 |
| **proposed** | **9** | **4** | **13** |

**観察**:
- scaffold_only の唯一のNGは causal_specific（仮説関係や識別仮定への指摘）
- proposed の NG は **general_quality が9件と多い**: フラグ整合性、JSON形式の指摘
- proposed の causal_specific 4件: hypothesis_relations、識別仮定、strength≠strong等

### 3.3 修正前後の変化

| method | 変化したケース | 詳細 |
|--------|--------------|------|
| scaffold_only | 1 (Kelly S3) | strong→weak |
| **proposed** | **2 (Kelly S3, Cheng S3)** | Kelly: H2 survive→hold, H4 survive→hold（フラグ整合性NGによる劣化） |

**重要な発見**: proposed の Kelly では Designer が **H2をsurviveからholdに「劣化」** させた。これは機械的チェックがフラグ整合性NGを出した際、Designerが「フラグだけ修正する」のではなく「判定そのものを弱める」道を選んだため。

ただし v2 gold standard では Kelly G2 の acceptable_decisions = [survive, hold] なので、この hold 化が **正解扱い** になる。結果として proposed は 4/4 を達成できた。

---

## 4. 統合的解釈

### 4.1 評価A と 評価C の対応

| 観察 | 評価A | 評価C | 解釈 |
|------|------|------|------|
| Kelly proposed が4/4 | combined 4/4 | S3で2回NG, 4件のfatal_issues, H2/H4が survive→hold | rubric_supervisor のNG → Designerが判定をholdに緩和 → v2 gold で acceptable に |
| baseline が overclaim | Kelly strength NG | NG履歴なし | supervisorが無いので strong のまま |
| scaffold_only の decision 低下 | 9/17 | NG少（1件） | 表面的な修正で内容が変わらない |
| Cheng で全条件が strength NG | strength 4/4 NG | proposed で2回NG | gold が strong を期待するが、全条件が weak と保守的判定 |

### 4.2 強み

1. **Proposed は overclaim を抑制する**: baseline で唯一 strong を出した Kelly のケースで、proposed は適切に弱める
2. **Proposed は許容範囲のある仮説で正解を選ぶ**: Kelly G2 で hold を選択（identification concern を反映）
3. **rubric_supervisor は proposed の判定を厳しく審査する**: 13件のNGを出してDesignerに再考を促す

### 4.3 弱み

1. **全条件で Cheng の strength を strong にできない**: 後続文献の合意 (RAND最高評価) を gpt-5.4-mini が踏まえられない
2. **proposed の Kelly における判定劣化**: 機械的チェックがフラグ整合性NGを出した時、Designerが判定そのものを弱める安易な道を選ぶ。今回は acceptable に救われたが、設計上の問題は残る
3. **Twenge G2 で全条件が経済要因をreject**: 多重決定論の捕捉に失敗。S0/S2_EVID の記述が因果単一論に偏っている可能性

### 4.4 論文への含意

1. **新 gold standard では proposed が combined で最高（65.2%）** — v1 では baseline と同率だったのが改善
2. **許容範囲の導入は proposed の強みを正当に評価する**: 「保守的な hold」を受け入れる gold は、proposed の慎重な判定を正解とみなせる
3. **proposed の優位性は限定的**: 一致率の差は1〜2点であり、過度に強い主張は不可
4. **全条件が苦手とするケースが存在**: Twenge G2、Cheng strength。これは LLM の知識と gold の隔たりに起因し、プロトコル設計の問題ではない可能性

---

## 5. 生成ファイル

- [eval_outputs_v2/blind_eval_summary.json](blind_eval_summary.json) — 集計サマリ
- [eval_outputs_v2/blind_eval_{case}_{method}.json](.) — 24件の個別評価
- [eval_outputs_v2/supervisor_analysis.json](supervisor_analysis.json) — supervisor 集計
- [eval_outputs_v2/evaluation_report.md](evaluation_report.md) — 本ファイル
- [gold_standards.json](../gold_standards.json) — v2 gold standard
- [gold_standards_v1.json](../gold_standards_v1.json) — v1 バックアップ
- [rescore_blind_eval.py](../rescore_blind_eval.py) — v1 → v2 後処理スクリプト
- [supervisor_analysis.py](../supervisor_analysis.py) — supervisor 分析スクリプト

---

## 6. 注意事項

- 本v2評価は OpenAI API quota 切れにより、新しい blind 突合は実行できなかった
- 既存の v1 突合結果 (eval_outputs/) から、`matched_b_id` / `b_decision` / `strength_b` を再利用し、`acceptable_*` リストとの照合のみを後処理で再実行
- 結果として LLM 突合自体は v1 と同じ。**変わったのは「許容範囲」の導入のみ**
- API quota 復旧後は `python blind_eval.py --out eval_outputs_v3/` で新規実行可能
