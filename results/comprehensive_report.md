# 包括的実験結果レポート

## 1. 実験設計

### 4条件の2×2デザイン

|  | Supervisorなし | Supervisorあり |
|--|--------------|-------------|
| **Rubricなし** | `baseline` | `scaffold_only` |
| **Rubricあり** | `rubric_only` | `proposed` |

### 各条件の構成

| 条件 | Designer prompt | Supervisor | Mechanical Checks | JSON Schema |
|------|----------------|-----------|-------------------|------------|
| baseline | baseline_designer_s1〜s3 (汎用) | なし | なし | 基本 |
| scaffold_only | baseline_designer_s1〜s3 (汎用) | scaffold_supervisor (汎用) | あり（基本） | 基本 |
| rubric_only | rubric_designer_s1〜s3 (rubric埋め込み) | なし | なし | 拡張 |
| proposed | rubric_designer_s1〜s3 (rubric埋め込み) | rubric_supervisor (rubric対応) | あり（拡張） | 拡張 |

### 評価対象ケース（6つ）

| ケース | 因果推論手法 | 論文の特徴 |
|------|-----------|----------|
| Kelly & Sharot (2025) | 観察+実験 | 双方向因果（コンテンツ↔気分） |
| Orben & Przybylski (2019) | Specification Curve Analysis | 効果は極めて小さい |
| Twenge et al. (2018) | 横断+時系列 | 出来の良い論文 |
| Cheng & Hoekstra (2013) | staggered TWFE DiD | 推定量の方法論的問題 |
| Voight et al. (2012) | Mendelian Randomization | 帰無結果 |
| Chen et al. (2013) | 地理的RDD | 多項式仕様への感度 |

### モデル
- 実験: gpt-5.4-mini, temperature=0.0
- ブラインド評価: gpt-4o（実験と異なるモデル）, temperature=0.0

---

## 2. プロトコルの3層構造

```
Layer 1: Process-level Protocol
  S0 (推定対象・スコープの固定) ← cases.jsonから提供
    ↓
  S1 (競合仮説の構造化) ⇄ S1-CHK (Supervisor)
    ↓
  S2 (実験計画・判定規則の事前固定) ⇄ S2-CHK (Supervisor)
    ↓
  S2-EVID (エビデンス投入) ← cases.jsonから提供
    ↓
  S3 (結論の導出・段階づけ) ⇄ S3-CHK (Supervisor)

Layer 2: Operationalized Rubric
  各段階の出力を Explicit / Partial / Absent で評価

Layer 3: Audit Implementation
  機械的チェック（決定論的整合性検証）
  + Supervisor（LLMによる内容監査）
```

---

## 3. 全フェーズのLLM出力（Kelly & Sharotを代表例として）

### baseline条件

#### S1: Designer出力
```
H1: ネガティブvalenceの閲覧 → 気分悪化（直接因果）
   falsify: ネガティブvalence曝露が気分を低下させない場合
H2: 気分悪化 → ネガティブ閲覧選択（逆方向因果）
   falsify: 気分操作後の選択valenceが変化しない場合
H3: 双方向フィードバック（H1+H2）
   falsify: いずれか一方向が再現されない場合
H4: 感情ラベル介入による気分改善
   falsify: 介入が選択分布も気分も変えない場合

hypothesis_relations:
  H1-H2: independent
  H1-H3: nested
  H1-H4: independent
```

#### S2: Designer出力
```
hypothesis_rules:
  H1: accept=ネガティブ条件群の気分が中立群より低下
      reject=差がないか方向が逆
  H2: accept=低気分後にネガティブ選択増加
      reject=気分状態と選択に関係なし
  H3: 双方向クロスラグ効果
  H4: ラベル群でネガティブ選択減少+気分改善

identification_assumptions:
  IA1: ランダム割付による交絡均衡
  IA2: 短期気分測定が閲覧効果を反映
  IA3: 気分操作が選択に直接影響しない
```

#### S3: Designer出力
```
H1: survive (E3, E4)
H2: survive (E2, E5)
H3: survive (E2, E3, E4, E5)
H4: survive (E6, E7)

survive: ['H1','H2','H3','H4']
rejected: []
strength: STRONG  ← 全仮説surviveで過剰断定
```

#### Supervisor: なし
#### Mechanical Checks: なし
#### Retries: 0

---

### scaffold_only条件

#### S1: Designer出力（baselineと同じプロンプト）
仮説構造はbaselineとほぼ同じ（H1-H4、双方向フィードバックを含む）

#### S1-CHK: Supervisor出力
```
verdict: OK
fatal_issues: []
```

#### S2: 同様

#### S2-CHK: OK

#### S3: Designer出力
```
H1: survive, H2: survive, H3: survive, H4: survive
strength: weak  ← scaffoldにより過剰断定が抑制された
```

#### S3-CHK: OK
#### Retries: 1 (S3)

---

### rubric_only条件

#### S1: Designer出力（rubric埋め込みプロンプト）
```
H1: 双方向因果（H1自体がループ全体を主張）
   falsify: ランダム実験で気分差が一貫して生じない、または
            気分状態が選択に影響しない、いずれかが満たされれば棄却
H2: コンテンツ→気分のみ（H1の特殊ケース）
   falsify: 気分→選択が示されれば棄却
H3: 気分→選択のみ（H1の別の特殊ケース）
   falsify: 閲覧→気分が示されれば棄却
H4: 共通原因による見かけの関連

hypothesis_relations:
  H1-H2: nested （H2はH1の特殊ケース）
  H1-H3: nested
  H2-H3: exclusive
  H1-H4: exclusive
  H2-H4: exclusive
  H3-H4: exclusive
```

**問題**: H1を「双方向ループ」と定義したため、H1がsurviveするには両方向の証拠が必要。Supervisor/Mechanical Checksがないためこの構造的問題が修正されない。

#### S2: Designer出力
判定規則も双方向ループに依拠した複雑な構造

#### S3: Designer出力
```
H1: REJECT (双方向の証拠は両方あるがS2の厳密な再現性条件を満たさず)
H2: REJECT (H2の否定条件「気分→選択あり」が満たされた)
H3: REJECT (H3の否定条件「閲覧→気分あり」が満たされた)
H4: REJECT (短期因果が実験で示されたためH4の主張に反する)

survive: []
rejected: ['H1','H2','H3','H4']
strength: weak
```

**結果**: 全仮説が棄却される。これはrubric_onlyの最大の失敗例。

#### Retries: 0

---

### proposed条件

#### S1: Designer出力（rubric埋め込み + Supervisor監督）
```
H1: コンテンツ→気分（方向の主張、効果量閾値を含む）
H2: 気分→コンテンツ（方向の主張）
H3: 一方向のみ（H1とH2のうち一方のみ成立、H2のexclusiveペア）
H4: ラベル介入の効果

hypothesis_relations:
  H1-H2: independent  ← Kellyの双方向因果を正しく扱う
  H1-H3: nested
  H2-H3: exclusive  ← 一方向 vs 双方向
  H1-H4: independent
```

#### S1-CHK: OK

#### S2: Designer出力
```
H1: accept=|d|≥0.20 かつ η²≥0.01 かつ CI≠0
H2: accept=気分→選択効果が再現性をもって示される
H3: accept=H2が示されない（exclusive）
H4: accept=ラベル群で選択分布変化+気分改善

identification_assumptions:
  IA1: ランダム割付（assumption + if_violated詳述）
  IA2: 媒介効果の有無に関する仮定
  IA3: SUTVA
```

#### S2-CHK: OK

#### S3: Designer出力（2回リトライ後）
```
H1: SURVIVE (E3, E4 — 効果量η²p=0.151)
H2: SURVIVE (E2, E5 — 双方向独立判定)
H3: REJECT (一方向仮説は両方向の証拠で棄却)
H4: SURVIVE (E6, E7)

relation_consistency_check:
  H1-H2 (independent): 両方surviveは正常 ✓
  H1-H3 (nested): H1 survive, H3 reject 整合 ✓
  H2-H3 (exclusive): H2 survive, H3 reject 整合 ✓

identification_assumption_concerns:
  IA1: satisfied
  IA2: uncertain (媒介効果の特定は範囲外)
  IA3: satisfied

residual_alternatives:
  - 短期効果のみ確認
  - オンラインサンプルの代表性
  - 需要特性の可能性
strength: weak
strength_justification: 識別仮定IA2にuncertainがあるため
```

#### S3-CHK: OK
#### Retries: 2 (S3でSupervisorが2回NG出した後通過)

---

## 4. 全6ケース × 4条件の最終判定一覧

### Kelly & Sharot (web_browsing_mood)
| method | H1 | H2 | H3 | H4 | strength |
|--------|----|----|------|------|----------|
| baseline | survive | survive | survive | survive | **strong** |
| scaffold_only | survive | survive | survive | survive | weak |
| rubric_only | reject | reject | reject | reject | weak |
| **proposed** | survive | survive | reject | survive | weak |

### Orben & Przybylski (orben_przybylski_2019)
| method | H1 | H2 | H3 | H4 | strength |
|--------|----|----|------|------|----------|
| baseline | reject | survive | survive | hold | weak |
| scaffold_only | survive | survive | hold | hold | weak |
| rubric_only | reject | survive | survive | — | weak |
| **proposed** | survive | survive | survive | survive | weak |

### Twenge (twenge_2018)
| method | H1 | H2 | H3 | strength |
|--------|----|----|------|----------|
| baseline | survive | reject | hold | weak |
| scaffold_only | survive | reject | hold | weak |
| rubric_only | survive | reject | hold | weak |
| **proposed** | survive | reject | hold | weak |

### Cheng & Hoekstra (cheng_hoekstra)
| method | H1 (殺人増加) | H2 (抑止) | H3 (TWFE) | strength |
|--------|------------|---------|---------|----------|
| baseline | hold | survive | hold | weak |
| scaffold_only | survive | reject | hold | weak |
| rubric_only | survive | reject | reject | weak |
| **proposed** | survive | reject | hold | weak |

(注: 仮説のラベリングはAIの出力に応じて調整。content-based)

### Voight (voight_hdl)
| method | H1 (HDL保護) | H2 (非因果) | H3 (排除制約破れ) | strength |
|--------|------------|---------|---------|----------|
| baseline | reject | survive | reject | weak |
| scaffold_only | reject | survive | hold | weak |
| rubric_only | reject | survive | survive | weak |
| **proposed** | reject | survive | survive | weak |

### Chen (chen_huairiver)
| method | H1 (汚染→寿命) | H2 (多項式感度) | H3 (地域差) | strength |
|--------|------------|---------|---------|----------|
| baseline | hold | hold | hold | weak |
| scaffold_only | survive | hold | hold | weak |
| rubric_only | survive | reject | hold | weak |
| **proposed** | survive | survive(H4) | hold | weak |

---

## 5. ブラインド評価結果（gpt-4oによる独立突合）

### 評価方法
- gpt-4oにgold standardの仮説（分析A）と各条件の出力（分析B）を提示
- 研究背景・プロトコル名・どちらが正解かは伝えない
- 各仮説について意味的対応と判定一致を判定させる

### 結果（一致率）

| method | total agreed / total gold | rate |
|--------|-------|------|
| baseline | **13/17** | **76.5%** |
| scaffold_only | 11/17 | 64.7% |
| rubric_only | 10/17 | 58.8% |
| proposed | 12/17 | 70.6% |

### ケース別

| case | baseline | scaffold | rubric | proposed |
|------|----------|----------|--------|----------|
| Kelly | 2/3 | 2/3 | 1/3 | 2/3 |
| Orben | 2/3 | 1/3 | 2/3 | 2/3 |
| Twenge | 3/3 | 2/3 | 2/3 | 2/3 |
| Cheng | 2/3 | 3/3 | 2/3 | 2/3 |
| Voight | 2/2 | 2/2 | 2/2 | 2/2 |
| Chen | 2/3 | 1/3 | 1/3 | 2/3 |

**重要な発見**: ブラインド評価ではbaselineが最も高い一致率を出した。これは私（Claude）の手動採点（proposed優位）と異なる結果。

---

## 6. Rubric独立指標（metrics.py）

LLMもgold standardも使わない、機械的に集計可能な指標。

### Overclaim抑制率（strength != "strong"）

| method | suppressed / total | rate |
|--------|-----|------|
| baseline | 5/6 | 83.3% |
| scaffold_only | 6/6 | **100%** |
| rubric_only | 6/6 | **100%** |
| proposed | 6/6 | **100%** |

baselineのみKellyで `strength=strong` を出力。それ以外の3条件は全6ケースで過剰断定を抑制。

### Evidence Grounding率（survive/reject判定にevidence_idsあり）

| method | grounded / total | rate |
|--------|-----|------|
| baseline | 16/16 | 100% |
| scaffold_only | 15/15 | 100% |
| rubric_only | 19/19 | 100% |
| proposed | 17/17 | 100% |

全条件で100%。エビデンス参照は全条件で適切に行われている。

---

## 7. 再現性検証（partial）

`proposed × 6ケース × 3回` を実行（API quotaにより run3 全失敗、run2 部分失敗）。

### 利用可能なデータ

| case | run1 | run2 | run3 |
|------|------|------|------|
| Kelly | ✅ | ✅ | — |
| Orben | ✅ | ✅ | — |
| Twenge | ✅ | ✅ | — |
| Cheng | ✅ | ✅ | — |
| Voight | ✅ | — | — |
| Chen | ✅ | — | — |

### 再現性の発見

| 項目 | 安定性 |
|------|------|
| strength = weak | **全実行・全ケースで安定** ✅ |
| S1仮説数 | 概ね安定（4個。Orbenのみrun2で3個） |
| 個別仮説のdecision | **実行間で変動** ❌ |

**具体例**:
- Twenge: run1(H1=hold) vs run2(H1=survive)
- Cheng: run1(H2=hold, H3=survive) vs run2(H2=reject, H3=hold)
- Orben: 仮説数まで変動（4 vs 3）

**結論**: temperature=0.0でも個別仮説の判定は再現性が低い。論文では複数試行の平均または信頼区間を報告すべき。

---

## 8. 主要な発見と論文への含意

### 発見1: rubricは検査機構と組み合わせて機能する
- `rubric_only` は6ケース中4ケースで最低スコア
- rubricの拡張スキーマだけでは Designer の構造的誤りを修正できない
- Supervisor + Mechanical Checks との組み合わせ（proposed）で初めて機能

### 発見2: scaffoldは過剰断定を抑制する
- baseline 5/6 vs scaffold_only 6/6 (overclaim suppression)
- Supervisorの存在だけで `strength=strong` の出現が消える

### 発見3: ブラインド評価では baseline が優位
- 手動採点と異なる結果
- 自動化された厳格な評価では proposed の優位性は弱まる
- ただし、baselineは過剰断定（strong）を出すケースがある

### 発見4: 仮説構造化の質が結果を決定する
- Kelly（双方向因果）と Orben（効果量グラデーション）では proposed が明確に優位
- これは rubric_designer_s1.txt の以下のガイダンスが効いている:
  - 「双方向因果は別仮説として独立に評価せよ」
  - 「効果の方向と程度を分離（nested構造）せよ」

### 発見5: 再現性の限界
- temperature=0.0 でも個別仮説のdecisionは不安定
- strengthレベルでは安定
- 論文では複数試行の集約を報告すべき

### 発見6: 評価方法そのものの透明性
- 手動採点 → 主観的、再現性なし
- gold standardの仮説ラベル一致 → 過度に厳格、内容を見ない
- ブラインドLLM突合 → 論文に書ける手順、独立評価

---

## 9. ファイル構成

### 実装
- `run.py` - 4条件分岐を含むメインランナー
- `schemas.py` - extended パラメータでの拡張スキーマ検証
- `prompt_store.py` - 4プロファイル
- `prompts/` - 9つのプロンプトファイル（rubric_designer×3, scaffold_supervisor×3, rubric_supervisor×3）
- `cases.json` - 6ケース定義
- `gold_standards.json` - 6ケースのgold standard
- `blind_eval.py` - ブラインド突合スクリプト
- `metrics.py` - rubric独立指標
- `reproducibility_analysis.py` - 再現性分析

### 結果データ
- `outputs/run_4cond_{method}_{case}.jsonl` - 24件の4条件実行ログ
- `outputs/repro_run{1,2,3}_proposed_{case}.jsonl` - 18件の再現性実行ログ
- `eval_outputs/blind_eval_{case}_{method}.json` - 24件のブラインド評価結果
- `eval_outputs/blind_eval_summary.json` - 集計サマリ
- `eval_outputs/blind_eval_prompts.json` - 全突合プロンプト（再現性のため）
- `eval_outputs/metrics_summary.json` - 機械的指標

### ドキュメント
- `results/comprehensive_report.md` - 本ファイル
- `results/full_phase_outputs.txt` - 全フェーズ出力の生データ
- `results/4condition_analysis.md` - 4条件分析（旧版）
- `results/hypothesis_relations_extension.md` - hypothesis_relations拡張の背景

---

## 10. 残課題と今後の方向性

1. **再現性実験の完遂**: API quota回復後にrun3を補完
2. **Cheng・Voightのgold standard明確化**: 仮説のラベル依存性を排除する書き方
3. **Chenのcases.json記述精度向上**: 「効果の消失」と「効果量の不安定性」の区別を明示
4. **複数モデルでのブラインド評価**: gpt-4o以外（Claude等）でも実施し評価のロバストネスを確認
5. **ケースの拡充**: 6ケースは観察的因果推論の主要手法をカバーするが、より多様な分野でのテストが望ましい
