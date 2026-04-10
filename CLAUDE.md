# babaron プロジェクト構成ガイド

このファイルはClaude Code等のagentがプロジェクトを理解するための構成ガイドです。

## プロジェクト概要

観察的因果推論における科学的主張形成の監督プロトコル（3層構造）の実装と評価。
4条件の2×2デザイン（rubric有無 × supervisor有無）で、6つの因果推論ケースを評価。

## 4条件の設計

|  | Supervisorなし | Supervisorあり |
|--|--------------|-------------|
| **Rubricなし** | `baseline` | `scaffold_only` |
| **Rubricあり** | `rubric_only` | `proposed` |

## 6つの評価対象ケース

| ケースID | 論文 | 因果推論手法 |
|---------|------|-----------|
| `orben_przybylski_2019` | Orben & Przybylski (2019) | Specification Curve Analysis |
| `twenge_2018` | Twenge et al. (2018) | 横断+時系列 |
| `cheng_hoekstra` | Cheng & Hoekstra (2013) | staggered TWFE DiD |
| `voight_hdl` | Voight et al. (2012) | Mendelian Randomization |
| `chen_huairiver` | Chen et al. (2013) | 地理的RDD |
| `angrist_krueger_1991` | Angrist & Krueger (1991) | 操作変数法(IV/2SLS) |

Kelly & Sharot (2025) は正式評価からは除外（後続文献なし）。cases.jsonには残存。

## ファイル構成

### ソースコード（メイン）

```
run.py                  # メインランナー。4条件分岐 (--method baseline/scaffold_only/rubric_only/proposed)
schemas.py              # JSONスキーマバリデーション (extended パラメータで rubric版/non-rubric版を切替)
llm_client.py           # OpenAI API クライアント (gpt-5.4-mini用 max_completion_tokens=8000)
prompt_store.py         # 4プロファイルのプロンプトマッピング
rubric.py               # Layer 2 ルーブリック評価 (14項目28点)
```

### 評価スクリプト

```
blind_eval.py           # 評価A: gpt-4oによるブラインド突合 (S3最終判定 vs gold standard)
process_eval.py         # 評価B: gpt-4oによる推論ステップ評価 (後続文献の懸念検出率)
supervisor_analysis.py  # 評価C: Supervisor分析 (NG回数・分類・Designer変更)
metrics.py              # Rubric独立指標 (overclaim抑制率、evidence grounding率)
```

### 設定・定義ファイル

```
cases.json              # 全ケースのS0 (研究概要) + S2_EVID (エビデンス) 定義
gold_standards.json     # 6ケースのgold standard (後続文献ベース、acceptable_decisions付き)
detection_checkpoints.json  # 評価Bの21個のcheckpoint定義 (後続文献の出典付き)
.env                    # OPENAI_API_KEY (gitignore対象)
.gitignore              # .env, __pycache__
```

### プロンプト

```
prompts/
  baseline_designer_s1.txt    # baseline/scaffold_only用 Designer (汎用)
  baseline_designer_s2.txt
  baseline_designer_s3.txt
  rubric_designer_s1.txt      # rubric_only/proposed用 Designer (5仮説カテゴリ必須化、識別仮定3カテゴリ必須化)
  rubric_designer_s2.txt
  rubric_designer_s3.txt
  scaffold_supervisor_s1.txt  # scaffold_only用 Supervisor (汎用、rubric固有チェックなし)
  scaffold_supervisor_s2.txt
  scaffold_supervisor_s3.txt
  rubric_supervisor_s1.txt    # proposed用 Supervisor (rubric固有チェック: 逆因果欠如検出、横断データ限界検出等)
  rubric_supervisor_s2.txt
  rubric_supervisor_s3.txt
  evidence_server.txt         # Evidence Server (prompt_store.pyから参照、実際にはcases.jsonで代替)
```

### Gold Standard

```
data/
  orben_przybylski_2019/gold.json
  twenge_2018/gold.json
  cheng_hoekstra/gold.json
  voight_hdl/gold.json
  chen_huairiver/gold.json
```

### 実行結果（最新版 v3）

```
outputs/                         # 4条件×6ケース = 24件の実行ログ
  run_4cond_{method}_{case}_v3.jsonl

eval_outputs_v3/                 # 評価A: ブラインド突合結果
  blind_eval_{case}_{method}.json  # 24件の個別結果
  blind_eval_summary.json          # 集計
  blind_eval_prompts.json          # gpt-4oに送った全プロンプト（再現性）
  supervisor_analysis.json         # 評価C: Supervisor分析
  evaluation_report.md             # レポート（旧版、更新必要）

eval_outputs_process_v3/         # 評価B: 推論ステップ評価結果
  process_eval_{case}_{method}.json  # 24件の個別結果
  process_eval_summary.json          # 集計 (主要結果)
  process_eval_prompts.json          # gpt-4oに送った全プロンプト（再現性）
```

## 最新の実験結果（v3）

### 評価B（推論ステップ評価）— 主要結果

| 条件 | 検出率 | S1 | S2 | S3 |
|------|-------|---|---|---|
| baseline | 16/21 (76.2%) | 4/5 | 8/10 | 4/6 |
| scaffold_only | 17/21 (81.0%) | 4/5 | 9/10 | 4/6 |
| rubric_only | 19/21 (90.5%) | 3/5 | 10/10 | 6/6 |
| **proposed** | **20/21 (95.2%)** | **4/5** | **10/10** | **6/6** |

### 評価A（最終判定一致率）

| 条件 | combined |
|------|---------|
| baseline | 14/23 (60.9%) |
| scaffold_only | 13/23 (56.5%) |
| rubric_only | 14/23 (60.9%) |
| proposed | 13/23 (56.5%) |

### 評価C（Supervisor分析）

- scaffold_only NGs: 0
- proposed NGs: 9 (chen_huairiver: S1×1 S3×1, angrist_krueger: S1×3 S3×5)

## 主要な知見

1. **評価Bで proposed が baseline より +19.0 ポイント**（95.2% vs 76.2%）
2. 期待されたパターン baseline < scaffold < rubric < proposed が完全成立
3. rubricの構造化スキーマ（識別仮定の3カテゴリ、仮説の5カテゴリ必須化）が効果の本体
4. 評価Aでは4条件で大差なし（揺らぎ範囲内）
5. proposed の優位性は「推論過程の質（後続文献の懸念検出）」に集中

## 実行方法

### 実験の実行
```bash
python run.py --method proposed --case orben_przybylski_2019 --model gpt-5.4-mini --max_retry 7 --out outputs/test.jsonl
```

### 評価の実行
```bash
# 評価A
python blind_eval.py --model gpt-4o --case orben_przybylski_2019 --method proposed --out eval_outputs_v3
python blind_eval.py --summary --out eval_outputs_v3

# 評価B
python process_eval.py --model gpt-4o --case orben_przybylski_2019 --method proposed --out eval_outputs_process_v3
python process_eval.py --summary --out eval_outputs_process_v3

# 評価C
python supervisor_analysis.py --out eval_outputs_v3/supervisor_analysis.json

# Rubric独立指標
python metrics.py --outputs outputs/ --out eval_outputs_v3/metrics_summary.json
```

## 技術的な注意

- 実験: gpt-5.4-mini, temperature=0.0, max_completion_tokens=8000
- 評価: gpt-4o (実験と異なるモデル), temperature=0.0
- ブラインド突合/検出のプロンプトには研究目的・条件名を含めない
- strength チェックポイントはLLM不要（strength != "strong" で機械判定）
- `find_run_file()` は v3 > v2 > 無印 の優先順位で実行ログを探索
- Kelly (web_browsing_mood) はCASESリストから除外済み（formal evaluation 対象外）
