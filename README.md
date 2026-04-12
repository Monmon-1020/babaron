# babaron

観察的因果推論における科学的主張形成の監督プロトコルの実装と評価。

## 概要

LLMに因果推論の分析を行わせ、教科書ベースのチェックリストで出力品質を評価する。
baseline（汎用プロンプト）vs proposed（因果推論特化rubricプロンプト）の2条件比較。

## 4つの評価ケース

| ケース | 手法 | データソース |
|------|------|-----------|
| castle | DiD (TWFE) | Cheng & Hoekstra (2013) |
| close_elections | RDD (Sharp) | Lee, Moretti & Butler (2004) |
| nhefs | IPW | NHEFS禁煙体重データ |
| nsw | マッチング (PSM) | LaLonde/NSW職業訓練 |

## 主要結果

| ケース | baseline | proposed |
|------|---------|---------|
| castle | 23/32 (71.9%) | **28/32 (87.5%)** |
| close_elections | 17/26 (65.4%) | 17/26 (65.4%) |
| nhefs | 13/28 (46.4%) | **26/28 (92.9%)** |
| nsw | 22/28 (78.6%) | **23/28 (82.1%)** |
| **合計** | **75/114 (65.8%)** | **94/114 (82.5%)** |

## 使い方

```bash
# 実験
python run.py --case castle --condition proposed --model gpt-5.4-mini --out outputs/

# 評価
python evaluate.py --case castle --condition proposed --model gpt-4o --out eval_outputs/
```

詳細は [CLAUDE.md](CLAUDE.md) を参照。
