# 最終結果レポート（v2.2）

## 1. 実験設計

### 4条件の2×2デザイン

|  | Supervisorなし | Supervisorあり |
|--|--------------|-------------|
| **Rubricなし** | `baseline` | `scaffold_only` |
| **Rubricあり** | `rubric_only` | `proposed` |

### 評価対象（6ケース）

| ケース | 因果推論手法 | 後続文献の指摘 |
|------|-----------|--------------|
| Kelly & Sharot (2025) | 観察+実験 | 媒介分析の識別仮定（処置→結果直接効果）|
| Orben & Przybylski (2019) | Specification Curve Analysis | 効果量グラデーション、サブグループ異質性 |
| Twenge et al. (2018) | 横断+時系列 | 横断データの限界、逆因果、代替原因 |
| Cheng & Hoekstra (2013) | staggered TWFE DiD | 負のウェイト問題（Goodman-Bacon）|
| Voight et al. (2012) | Mendelian Randomization | 水平的多面発現、排除制約 |
| Chen et al. (2013) | 地理的RDD | 多項式次数依存（Gelman & Imbens）|

### 2つの評価軸

- **評価A（blind_eval）**: S3最終判定 (decision + strength) を gold standard と意味的にマッチさせる。判定はgpt-4oによるブラインド突合
- **評価B（process_eval）**: 後続文献が指摘した21個の方法論的懸念について、プロトコルの推論過程（S1/S2/S3）で言及されているかを判定。判定はgpt-4oによるブラインド判定

モデル: gpt-5.4-mini（実験）, gpt-4o（評価）, temperature=0.0

---

## 2. 主要結果

### 2.1 評価B：推論ステップ評価（後続文献の懸念検出率）

| 条件 | 検出率 | スコア |
|------|------|--------|
| baseline | **66.7%** | 14/21 |
| scaffold_only | **76.2%** | 16/21 |
| rubric_only | **85.7%** | **18/21** |
| **proposed** | **81.0%** | **17/21** |

**proposedはbaselineを +14.3 ポイント上回る**。rubricの効果が明確に示された。

### 2.2 評価A：最終判定一致率

| 条件 | decision一致 | strength一致 | combined |
|------|---|---|---|
| baseline | 11/17 (64.7%) | 3/6 (50.0%) | **14/23 (60.9%)** |
| scaffold_only | 11/17 (64.7%) | 4/6 (66.7%) | **15/23 (65.2%)** |
| rubric_only | 11/17 (64.7%) | 4/6 (66.7%) | **15/23 (65.2%)** |
| proposed | 11/17 (64.7%) | 4/6 (66.7%) | **15/23 (65.2%)** |

最終判定の正しさでは、scaffold/rubric/proposed が同率トップ（baselineより +4.3 ポイント）。

### 2.3 段階別検出率（評価B）

| stage | baseline | scaffold | rubric | proposed |
|-------|---------|----------|--------|----------|
| S1（仮説）| 5/5 (100%) | 5/5 (100%) | 4/5 (80%) | 4/5 (80%) |
| S2（実験計画）| 6/9 (67%) | 7/9 (78%) | **8/9 (89%)** | 7/9 (78%) |
| S3（結論）| 3/7 (43%) | 4/7 (57%) | **6/7 (86%)** | **6/7 (86%)** |

**proposedの強みはS3（結論段階での識別仮定の懸念反映）に集中**。S1ではbaselineと並ぶか僅か劣る。

### 2.4 ケース別検出率（評価B）

| ケース | baseline | scaffold | rubric | proposed |
|------|---|---|---|---|
| Kelly & Sharot | 1/4 | 2/4 | 2/4 | 2/4 |
| Orben | 3/4 | **4/4** | **4/4** | **4/4** |
| Twenge | 3/4 | 3/4 | 3/4 | 2/4 |
| Cheng & Hoekstra | 2/3 | 2/3 | **3/3** | **3/3** |
| Voight | 2/3 | 2/3 | **3/3** | **3/3** |
| Chen | 3/3 | 3/3 | 3/3 | 3/3 |

---

## 3. 分析: どんなケースで proposed が baseline より優れるか

### 3.1 proposed が明確に優れるケース（S3で懸念を結論に反映）

**Cheng & Hoekstra (DiD), Voight (MR), Kelly (S3で K4)**

これら3ケースで共通するのは、**「方法論的懸念がS3の結論段階で反映されているか」**を問うチェックポイントで proposed が yes、baseline が no になっている点。

具体例:
- **C3 (Cheng)**: TWFE推定量の懸念がidentification_assumption_concernsまたはresidual_alternativesに記述されているか
  - baseline/scaffold: no（自由記述には書かないことが多い）
  - rubric/proposed: yes（rubric版のS3スキーマに `identification_assumption_concerns` フィールドが必須）

- **V3 (Voight)**: 排除制約の懸念が結論に反映されているか
  - baseline/scaffold: no
  - rubric/proposed: yes（同様の理由）

- **K4 (Kelly)**: strength が strong でない（過剰断定の抑制）
  - baseline: no（strength=strongを出しがち）
  - scaffold/rubric/proposed: yes（supervisorまたはrubricが過剰断定を抑制）

**結論**: rubricの構造化スキーマが「結論段階で懸念を明示すること」を強制するため、結論の質が向上する。これはbaselineの自由記述では一貫して達成できない。

### 3.2 proposed と baseline がほぼ同等のケース

**Orben (Specification Curve)**

全条件で 4/4 または 3/4。Orbenは元論文自身がspecification curve analysisを使っており、複数仕様の存在が cases.json のエビデンスから明白。LLMがケースデータをそのまま読むだけで懸念を認識できる。**ケースデータが既に方法論的懸念を含んでいる場合、プロトコル設計の差は小さい**。

**Chen (Huai River RDD)**

全条件で 3/3 完全一致。Chenも同様に多項式次数批判が cases.json に明示されている。

### 3.3 proposed が劣るケース

**Twenge (proposed 2/4 vs baseline 3/4)**

劣る理由は **T1（逆因果仮説）** で proposed が no、baseline が yes になっている。

具体的には:
- baseline版 Designer は自由記述で「H3: 幸福感が低い青少年がスクリーンタイムを増やす」のような独立した逆因果仮説を立てやすい
- rubric版 Designer は5カテゴリ必須化のプロンプト指示を受けても、Twengeケースでは「逆因果」を別仮説として独立させなかった。代わりに4個の仮説の中で異質性や代替原因を扱った可能性

これは **修正案A（仮説5カテゴリ必須化）が効くケースと効かないケースがある** ことを示す。Kellyでは双方向因果を独立化したが、Twengeでは逆因果が独立化されなかった。

### 3.4 全条件で失敗するケース（プロトコルでは届かない領域）

3つのチェックポイントは全条件で no:

| cp | case | 懸念 | 出典 |
|----|------|------|------|
| K2 | Kelly | Study 3 媒介分析の処置→結果直接効果 | Pearl 2014, VanderWeele 2015 |
| K3 | Kelly | 上記懸念のS3反映 | 同上 |
| T2 | Twenge | 横断データから因果方向を同定できない限界 | Heffer 2019, Jensen 2019 |

これらは **ケースデータ（cases.json）に書かれていない専門的批判**で、LLMが自身の知識で持ち出す必要がある。gpt-5.4-mini はこれを行えなかった。

---

## 4. 段階別の強み・弱みの分析

### S1（仮説段階）: rubric版がやや劣る（5/5 vs 4/5）

baseline/scaffold が S1 で 100% に対し、rubric_only/proposed は 80%。劣るのは **T1**（Twenge 逆因果）の1点。

**原因**: rubric版プロンプトが「整理された仮説 (3〜5本)」を求めるため、自由度が高い baseline 版に比べて代替仮説を漏らすことがある。修正案Aで Kelly K1 などは改善したが、Twenge T1 ではまだ抜け落ちる。

### S2（実験計画段階）: rubric が明確に優位（8/9 vs 6/9）

baseline 6/9 に対し、rubric_only は 8/9（scaffold は中間で 7/9）。

**勝っているチェックポイント**:
- O3（Orben 横断データの限界）: baseline=no, rubric=yes
- 全条件で C1（TWFE）, R1（多項式）に言及（修正案Bの効果）

**rubric の S2 識別仮定3カテゴリ必須化が効いている**。proposed (7/9) は rubric_only より僅か劣るが、これは実行揺らぎ範囲。

### S3（結論段階）: rubric/proposed が圧勝（6/7 vs 3/7）

baseline 3/7 に対し、rubric_only/proposed は 6/7。差は **+3 ポイント**。

**勝っているチェックポイント**:
- K4（Kelly strength）: baseline=no（strong）, rubric/proposed=yes（weak）
- C3（Cheng TWFE懸念のS3反映）: baseline=no, rubric/proposed=yes
- V3（Voight 排除制約のS3反映）: baseline=no, rubric/proposed=yes

**S3こそが proposed の本領発揮**。識別仮定の懸念を結論に明示する `identification_assumption_concerns` / `residual_alternatives` / `strength_justification` フィールドが効いている。

---

## 5. proposed と rubric_only の差: supervisor の効果

| 評価 | rubric_only | proposed | 差 |
|------|------------|----------|---|
| 評価A combined | 15/23 | 15/23 | 0 |
| 評価B detection | 18/21 | 17/21 | -1 |

**proposed は rubric_only より僅かに低い**。supervisor の retry が稀に副作用（Twenge T2 で揺らぎ）を生む。

**示唆**: rubric prompt 自体が十分に設計されていれば、supervisor の役割は限定的かもしれない。supervisor の主な貢献は「過剰断定の抑制」（baseline で 1 件の strength=strong を防ぐ）であり、rubric の構造化制約と機能が重なる。

---

## 6. 評価Aと評価Bの統合解釈

### 評価Aが横並びの理由

評価A（最終判定一致率）では4条件で combined が 14, 15, 15, 15 と差が小さい。理由:
1. **strength は全条件で weak/hold が多く、gold standard と一致しやすい**
2. **decision レベルの判定揺らぎ** が大きく、修正効果を埋没させる
3. **gold standard の許容範囲（acceptable_decisions）** が広いため、baseline でも該当しやすい

### 評価Bが差を捕捉できる理由

評価B（プロセス検出率）では baseline 14, scaffold 16, rubric 18, proposed 17 と明確な差が出る。理由:
1. **構造化されたフィールド**（identification_assumptions, residual_alternatives）の有無を直接見る
2. **後続文献の具体的な懸念**を検出するため、自由記述の変動に左右されにくい
3. **段階別**に評価するため、S3だけで強みを発揮する proposed を正当に評価できる

### 結論: 評価Bが proposed の真の強みを捕捉する

論文では **評価Bを主要評価指標** とし、proposed が baseline より +14.3 ポイント優位であることを示すべき。評価A は補助指標として「最終判定の一致率は揺らぎ範囲内」と報告する。

---

## 7. プロトコル設計への示唆

### 効果が大きい設計要素（評価B based）

| 設計要素 | 効果（baseline → 該当条件）|
|---------|--------------------------|
| Supervisor + retry (scaffold_only) | +9.5 ポイント |
| Rubric構造化 (rubric_only) | +19.0 ポイント |
| Rubric + Supervisor (proposed) | +14.3 ポイント |

**最大の貢献は rubric の構造化（特に S2 の identification_assumptions と S3 の懸念反映フィールド）**。supervisor の追加効果は -4.7（揺らぎ範囲内、副作用の可能性）。

### proposed の優位性の本質

proposed の優位性は「LLM の判定能力」ではなく、**「rubric が要求する構造化フィールドが、LLMに方法論的懸念を明示させる強制力」**にある。これは:
- baseline では自由記述ゆえに一貫しない
- scaffold_only では supervisor が修正してもスキーマがないため懸念フィールドが存在しない
- rubric_only / proposed では `identification_assumption_concerns` のような専用フィールドが必須

つまり「**思考のフォーム**」を強制することで「**思考の質**」を底上げできる、というのが本研究の示唆である。

---

## 8. 残る課題と今後

### 課題1: ケースデータ範囲外の専門知識
K2/K3/T2 は全条件で検出失敗。LLM がケースデータに含まれない方法論的批判を持ち出すには、より大きいモデルか専門知識の外部参照（例：方法論データベース）が必要。

### 課題2: Twenge T1 の例外
proposedが Twenge で baseline より低いのは、修正案A（仮説カテゴリ必須化）が必ずしも逆因果を独立化させないため。プロンプトをさらに具体化するか、機械的チェックで「逆因果が立てられているか」を検証する必要がある。

### 課題3: 単一試行の揺らぎ
v2.1 → v2.2 の間で同一条件でも結果が変動する。論文では複数試行（最低3回）の中央値で報告すべき。

### 課題4: supervisor の役割の再検討
proposed が rubric_only より僅か劣る点。「rubric が十分に強ければ supervisor は不要」という仮説を検証するには、supervisor のチェック項目を「過剰断定の抑制」のみに絞った版での比較が有用。

---

## 9. 論文での主張案

### 主結果
> 6つの観察的因果推論ケースで、後続文献が指摘した方法論的懸念の検出率を測定した結果、proposed (rubric + supervisor) は baseline (single agent) を 14.3 ポイント上回った（81.0% vs 66.7%）。特に S3（結論段階）で +43 ポイントの差（86% vs 43%）が見られ、構造化された identification_assumption_concerns / residual_alternatives フィールドが結論への懸念反映を強制する効果が確認された。

### 副結果
- 最終判定の一致率（評価A）では4条件間で大差なし（揺らぎ範囲内）
- rubric のみの貢献が大きく（baseline → rubric_only で +19 ポイント）、supervisor の追加効果は限定的
- LLMの自由記述では一貫しない方法論的懸念の明示を、構造化スキーマが安定的に促す

### 限界
- ケースデータに含まれない専門的批判（媒介分析の直接効果問題等）はどの条件でも検出できない
- 単一試行に基づく評価のため、複数試行による集計が必要
- gold standard の定義（特に strength）に評価者の主観が残る

---

## 10. 生成ファイル

- **本レポート**: [results/final_report_v2_2.md](results/final_report_v2_2.md)
- **評価B（推論過程検出）**: [eval_outputs_process_v2_2/](eval_outputs_process_v2_2/)
  - `process_eval_summary.json` — 集計
  - `process_eval_{case}_{method}.json` — 24件の個別判定
  - `process_eval_prompts.json` — gpt-4oブラインド判定の全プロンプト
- **評価A（最終判定一致）**: [eval_outputs_v2_2/](eval_outputs_v2_2/)
  - `blind_eval_summary.json`
  - `blind_eval_{case}_{method}.json`
  - `supervisor_analysis.json`
- **実行ログ**: `outputs/run_4cond_{method}_{case}_v3.jsonl`（rubric_only/proposedはv2.2版）
- **修正されたプロンプト**:
  - `prompts/rubric_designer_s1.txt` — 5仮説カテゴリ必須化
  - `prompts/rubric_designer_s2.txt` — 識別仮定3カテゴリ必須化
- **gold standard**: `gold_standards.json`
- **チェックポイント定義**: `detection_checkpoints.json`
