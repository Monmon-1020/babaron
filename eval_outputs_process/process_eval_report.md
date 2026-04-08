# 推論ステップ評価レポート（評価B）

## 1. 評価の目的

評価A（ブラインド突合）はS3最終判定だけを gold standard と比較するため、proposed の本来の強み（推論過程で適切な懸念に気づく能力）を捕捉できなかった。

評価Bは、後続文献が指摘した方法論的問題を、プロトコルの**各段階**で検出できたかを判定する。「最終結論が正しいか」ではなく「推論の途中で適切な懸念に気づけているか」を測る。

---

## 2. 評価方法

### detection_checkpoints.json
6ケースについて合計21個の checkpoint を定義。各 checkpoint は:
- `stage`: S1 / S2 / S3 のどこを見るか
- `what_to_check`: hypotheses / identification_assumptions / experiment_plan / identification_assumption_concerns / strength / conclusion のどのフィールドか
- `question`: 検出すべき具体的な問題
- `source`: 後続文献の出典
- `expected`: yes（その問題に言及していることが望ましい）

### process_eval.py
各 (case, method) について:
1. 最後の成功した Designer 出力を抽出
2. 該当フィールドを切り出して gpt-4o に渡す
3. 「この問題への言及があるか yes/no」を判定させる
4. プロンプトには研究の目的・条件名を一切含めない（ブラインド）
5. strength は LLM 不要（strength != "strong" なら yes）

---

## 3. 結果サマリ

### 3.1 by_method（条件別の検出率）

| method | 検出率 | 比率 |
|--------|------|------|
| baseline | **14/21** | 66.7% |
| scaffold_only | **16/21** | 76.2% |
| rubric_only | **16/21** | 76.2% |
| **proposed** | **14/21** | **66.7%** |

**期待されたパターン (baseline ≤ scaffold_only ≤ rubric_only ≤ proposed) は実現せず、proposed と baseline が同率最低**。scaffold_only と rubric_only が同率最高。

### 3.2 by_stage（段階別の検出率）

| stage | baseline | scaffold_only | rubric_only | proposed |
|-------|---------|---------------|-------------|----------|
| S1 (5 cps) | 5/5 | 5/5 | 4/5 | **3/5** |
| S2 (9 cps) | 6/9 | 7/9 | 6/9 | **5/9** |
| S3 (7 cps) | 3/7 | 4/7 | 6/7 | **6/7** |

**段階ごとに違うパターン**:
- **S1（仮説段階）**: baseline/scaffold が最高（5/5）、proposed が最低（3/5）
- **S2（実験計画段階）**: scaffold_only が最高（7/9）、proposed が最低（5/9）
- **S3（結論段階）**: rubric_only/proposed が最高（6/7）、baseline が最低（3/7）

つまり **S3 では proposed が優位だが、S1/S2 で劣る** のがトータルで相殺している。

### 3.3 by_case（ケース別）

| case | baseline | scaffold_only | rubric_only | proposed |
|------|---------|---------------|-------------|----------|
| Kelly | 1/4 | 2/4 | 2/4 | 1/4 |
| Orben | 3/4 | 4/4 | 4/4 | **4/4** |
| Twenge | 3/4 | 3/4 | 2/4 | 2/4 |
| Cheng | 2/3 | 2/3 | **3/3** | 2/3 |
| Voight | 2/3 | 2/3 | **3/3** | **3/3** |
| Chen | **3/3** | **3/3** | 2/3 | 2/3 |

proposed が単独最高なのは **Orben のみ**。他は同率か劣位。

---

## 4. チェックポイント別の検出パターン

| cp | case | stage | baseline | scaffold | rubric | proposed | 観察 |
|----|------|-------|---------|----------|--------|----------|------|
| K1 | Kelly | S1 | yes | yes | yes | **no** | proposed が双方向因果を1仮説にまとめた |
| K2 | Kelly | S2 | no | no | no | no | 全条件失敗（媒介分析の直接効果） |
| K3 | Kelly | S3 | no | no | no | no | 全条件失敗 |
| K4 | Kelly | S3 | no | **yes** | **yes** | **yes** | scaffold/rubric/proposed が strength=weak を出した |
| O1 | Orben | S1 | yes | yes | yes | yes | 全条件で効果量グラデーション認識 |
| O2 | Orben | S2 | yes | yes | yes | yes | 全条件で仕様依存性に言及 |
| O3 | Orben | S2 | no | **yes** | **yes** | **yes** | rubric版で identification_assumptions に横断データの限界 |
| O4 | Orben | S3 | yes | yes | yes | yes | 全条件 strength≠strong |
| T1 | Twenge | S1 | yes | yes | **no** | **no** | rubric版が逆因果仮説を立てなかった |
| T2 | Twenge | S2 | no | no | no | no | 全条件失敗 |
| T3 | Twenge | S1 | yes | yes | yes | yes | 全条件で代替要因仮説 |
| T4 | Twenge | S3 | yes | yes | yes | yes | strength≠strong |
| C1 | Cheng | S2 | yes | yes | yes | **no** | proposed が TWFE 問題を S2 で言及せず |
| C2 | Cheng | S2 | yes | yes | yes | yes | 処置タイミング異質性に言及 |
| C3 | Cheng | S3 | no | no | **yes** | **yes** | rubric/proposed が結論部分に反映 |
| V1 | Voight | S1 | yes | yes | yes | yes | 全条件で多面発現仮説 |
| V2 | Voight | S2 | yes | yes | yes | yes | 排除制約への言及 |
| V3 | Voight | S3 | no | no | **yes** | **yes** | rubric/proposed が結論部分に反映 |
| R1 | Chen | S2 | yes | yes | **no** | **no** | rubric版が多項式次数批判を S2 で言及せず |
| R2 | Chen | S2 | yes | yes | yes | yes | バンド幅問題への言及 |
| R3 | Chen | S3 | yes | yes | yes | yes | 仕様依存性を結論に反映 |

---

## 5. 重要な発見

### 5.1 proposed の強み: S3 で識別仮定の懸念を結論に反映する
**K4, C3, V3** で proposed が baseline/scaffold より勝っている。これらはすべて **S3 の identification_assumption_concerns / residual_alternatives / strength** に関する checkpoint。

つまり proposed の rubric_supervisor が「結論段階で識別仮定の懸念を明示せよ」というルールを実際に効かせている。

### 5.2 proposed の弱み 1: S1 で構造化された仮説が代替仮説を排除する

**K1（双方向因果の独立仮説化）と T1（逆因果仮説）** で proposed が baseline より劣る。

これは矛盾した発見:
- K1 の意図: 双方向因果を1仮説にまとめないように、各方向を独立仮説にする
- 実際の出力: rubric版 Designer が「双方向ループ」のような統合的仮説を1つ立て、別方向の独立仮説を立てなかった

baseline は構造化されていない自由記述なので、複数の方向や代替を含めやすい。**rubric版が「整理された仮説」を求めることで、却って柔軟な仮説提示が抑制された**可能性。

### 5.3 proposed の弱み 2: S2 で方法論的批判を明示しない

**C1（TWFE問題）と R1（多項式次数批判）** で proposed が baseline より劣る。

これは rubric_designer_s2 のプロンプトが「識別仮定」を「処置と結果に関する仮定」として狭く解釈させ、**推定量そのものの統計的限界**（負のウェイト、関数形依存）を捕捉しにくくしている可能性。baseline は自由記述なので方法論的批判を含めやすい。

### 5.4 全条件失敗のチェックポイント
**K2, K3, T2** はすべての条件で no:
- K2/K3: Kelly Study 3 の媒介分析の直接効果問題（処置→結果バイパス経路）
- T2: 横断データから因果方向を同定できない限界

これらは「論文を読んで指摘される」種類の専門的批判で、ケースデータ（cases.json）にも書かれていない情報。LLM がケースデータ範囲外の方法論的知識を持ち出すのは現状では難しい。

---

## 6. 評価Aと評価Bの統合

### 評価A（最終判定の正しさ、v2.1）
| method | combined |
|--------|---------|
| baseline | 14/23 (60.9%) |
| scaffold_only | 15/23 (65.2%) |
| rubric_only | 12/23 (52.2%) |
| proposed | 12/23 (52.2%) |

### 評価B（推論過程の検出率）
| method | detection rate |
|--------|---------|
| baseline | 14/21 (66.7%) |
| scaffold_only | 16/21 (76.2%) |
| rubric_only | 16/21 (76.2%) |
| proposed | 14/21 (66.7%) |

**両方の評価で proposed の優位性は確認できなかった**。
**むしろ scaffold_only が両評価で最良または同率最良**。

### 解釈

scaffold_only が好成績の理由:
1. baseline と同じ自由度の高いプロンプトで Designer が代替説明を含めやすい
2. supervisor の修正で過剰断定や論理矛盾は避けられる
3. rubric の構造化制約に縛られないため、ケース固有の論点を扱いやすい

proposed の劣位の理由:
1. rubric版の仮説構造化が「整理しすぎ」て代替仮説や逆因果を抑制（K1, T1）
2. identification_assumptions の枠組みが推定量問題を捉えにくい（C1, R1）
3. supervisor の retry が「保守的なhold」への逃避を促す（前回 v2.1 で確認済）

---

## 7. 論文への含意

### 7.1 当初の主張を見直す必要がある
「proposed は推論過程を改善する」という主張は、評価Bでは実証できなかった。むしろ：
- **proposed は S3 段階で結論に懸念を反映する力は強い** (K4, C3, V3)
- **しかし S1/S2 段階で代替仮説や方法論的批判を抑制している** (K1, T1, C1, R1)

両者が打ち消し合って、トータルでは baseline と同率になっている。

### 7.2 scaffold_only の優位性
scaffold_only は両評価で最良または同率最良。これは「supervisor + retry」という構造のみで、rubric の認識論的中身は不要かもしれないという示唆。

### 7.3 推奨される論文の書き方

**Option A: proposed の優位性主張を放棄**
- "scaffold_only と proposed は同率"
- "rubric の構造化は S3 では効果あり、S1/S2 では逆効果"
- limitation として明示

**Option B: rubric の改良が必要**
- rubric_designer_s1 を「代替仮説を抑制しない」ように改良
- rubric_designer_s2 で「推定量の統計的限界」も識別仮定の範囲に含める
- 改良後に再実行

**Option C: 段階別の分析を主結果にする**
- 「proposed は S3 で結論への反映を改善する」（事実）
- 「ただし S1/S2 では代替仮説の抑制という副作用がある」（事実）
- 質的な違いとして報告

---

## 8. 生成ファイル

- `detection_checkpoints.json` — 21 checkpoint の定義
- `process_eval.py` — 評価B 実装
- `eval_outputs_process/process_eval_{case}_{method}.json` — 24件の個別結果
- `eval_outputs_process/process_eval_summary.json` — by_method / by_case / by_stage 集計
- `eval_outputs_process/process_eval_prompts.json` — 全プロンプトと応答（再現性のため）
- `eval_outputs_process/process_eval_report.md` — 本ファイル
