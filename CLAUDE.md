# babaron プロジェクト構成ガイド

このファイルはClaude Code等のagentがプロジェクトを理解するための構成ガイドです。

## プロジェクト概要

観察的因果推論における科学的主張形成の監督プロトコル（rubric埋め込みプロンプト）の実装と評価。
baseline（汎用プロンプト）vs proposed（因果推論特化rubricプロンプト）の2条件比較。
4つの教科書データセットに対し、LLMが手法選択→統計分析実行→結論導出を行い、教科書ベースのチェックリストで採点する。

## 2条件の設計

| 条件 | プロンプト | 手法選択 | 識別仮定の記述 |
|------|---------|---------|------------|
| `baseline` | 汎用指示（「適切な手法を選び仮定を記述せよ」） | LLM自律 | 自由記述 |
| `proposed` | 因果推論特化rubric（6手法の識別仮定・適用条件・使い分けを明示） | LLM自律（知識付き） | 構造化ガイダンス |

## 4つの評価対象ケース

| ケースID | データセット | 推奨手法 | 教科書 |
|---------|-----------|---------|------|
| `castle` | Cheng & Hoekstra (2013) | DiD (TWFE) | Cunningham §9 |
| `close_elections` | Lee, Moretti & Butler (2004) | RDD (Sharp) | Cunningham §6 |
| `nhefs` | NHEFS禁煙体重データ | IPW | Hernán & Robins Ch.12 |
| `nsw` | LaLonde/NSW職業訓練 | マッチング (PSM) | Cunningham §5 |

## ファイル構成

### ソースコード

```
cases.py              # 4ケースのデータローダー (causaldata パッケージ)
tools.py              # 6つの統計ツール (DiD/IV/RDD/Matching/IPW/OLS)
prompts.py            # baseline/proposed プロンプト定義
run.py                # メインランナー (2フェーズLLMフロー: S0-S2b → ツール実行 → S3)
evaluate.py           # チェックリスト採点スクリプト (gpt-4oブラインド採点)
```

### 設定・定義ファイル

```
evaluation_checklist_final.md  # 4ケース分のGold Standard（教科書引用付き、0/1/2採点基準）
prompt_design.md               # プロンプト設計書（baseline/proposed の全文）
.env                           # OPENAI_API_KEY (gitignore対象)
.gitignore                     # .env, __pycache__, *.pdf
```

### 実行結果

```
outputs/                       # 4ケース×2条件 = 8件の実行ログ (JSON)
  run_{case}_{condition}.json  # 各実行の全出力（metadata, prompt, llm_output, tool）

eval_outputs/                  # チェックリスト採点結果
  eval_{case}_{condition}.json # 各ケース×条件の個別採点結果
  eval_summary.json            # 全体集計
```

## 処理フロー

```
1. cases.py: データ読み込み (causaldata → pandas DataFrame)
   ↓
2. prompts.py: プロンプト生成 (共通入力 + 出力フォーマット + 条件別指示)
   ↓
3. run.py Phase 1: LLM に送信 → S0, S1, S2a, S2b を生成
   ↓
4. run.py: S2a から選択した手法をパース → tools.py の該当ツールを実行
   ↓
5. run.py Phase 2: ツール結果を LLM に返送 → S2-EVID, S3 を生成
   ↓
6. outputs/ に JSON 保存
   ↓
7. evaluate.py: チェックリスト項目ごとに gpt-4o でブラインド採点 (0/1/2)
```

## 統計ツール (tools.py)

| ツール | 関数 | 主要出力 |
|------|------|---------|
| DiD | `did_estimator()` | TWFE推定 + Event Study + クラスターSE |
| IV | `iv_estimator()` | 2SLS + 第一段階F + Sargan検定 |
| RDD | `rdd_estimator()` | rdrobust + バイアス補正CI + 密度検定 |
| Matching | `matching_estimator()` | PSM + 共変量バランス + common support |
| IPW | `ipw_estimator()` | 安定化重み + トリミング + バランス確認 |
| OLS | `ols_estimator()` | HC1ロバストSE |

## 最新の実験結果

### チェックリスト採点（0/1/2スケール、満点はケースにより異なる）

| ケース | baseline | proposed | 差 |
|------|---------|---------|---|
| castle (DiD) | 23/32 (71.9%) | **28/32 (87.5%)** | +15.6 |
| close_elections (RDD) | 17/26 (65.4%) | 17/26 (65.4%) | 0.0 |
| nhefs (IPW) | 13/28 (46.4%) | **26/28 (92.9%)** | +46.4 |
| nsw (Matching) | 22/28 (78.6%) | **23/28 (82.1%)** | +3.6 |
| **合計** | **75/114 (65.8%)** | **94/114 (82.5%)** | **+16.7** |

### 手法選択

| ケース | 教科書推奨 | baseline | proposed |
|------|---------|----------|----------|
| castle | DiD | DiD ✅ | DiD ✅ |
| close_elections | RDD | RDD ✅ | RDD ✅ |
| nhefs | IPW | OLS ❌ | IPW ✅ |
| nsw | Matching | Matching ✅ | Matching ✅ |

## 実行方法

### 実験の実行
```bash
# 単一ケース×単一条件
python run.py --case castle --condition proposed --model gpt-5.4-mini --out outputs/

# 全ケース×全条件（8件）
python run.py --case all --condition all --model gpt-5.4-mini --out outputs/
```

### 評価の実行
```bash
# 単一ケース×単一条件の採点
python evaluate.py --case castle --condition baseline --model gpt-4o --out eval_outputs/

# 全ケース×全条件の採点
python evaluate.py --case all --condition all --model gpt-4o --out eval_outputs/

# 既存結果のサマリ表示
python evaluate.py --summary --out eval_outputs/
```

## 技術的な注意

- 実験: gpt-5.4-mini, temperature=0, max_completion_tokens=8000
- 評価: gpt-4o（実験と異なるモデル）, temperature=0
- 評価プロンプトには研究目的・条件名を含めない（ブラインド）
- strength チェック項目は LLM 不要（機械判定）
- causaldata パッケージからデータ取得（castle, close_elections_lmb, nhefs, nsw_mixtape）
- 手法選択は LLM の自律判断（proposed は知識を与えるが手法を指定しない）
