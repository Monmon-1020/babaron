# babaron

観察的因果推論における科学的主張形成の監督プロトコル（3層構造）の実装と評価。

## 概要

LLMを用いて因果推論研究の主張形成過程を監査可能な形で記述する。Designer（仮説生成・実験計画・結論導出）とSupervisor（品質チェック）の2エージェント構成に加え、決定論的な機械的整合性チェックとルーブリック評価を統合。

## 4条件の2×2実験デザイン

|  | Supervisorなし | Supervisorあり |
|--|--------------|-------------|
| **Rubricなし** | `baseline` | `scaffold_only` |
| **Rubricあり** | `rubric_only` | `proposed` |

## 評価対象ケース（6つ）

| ケース | 手法 |
|------|------|
| Orben & Przybylski (2019) | Specification Curve Analysis |
| Twenge et al. (2018) | 横断+時系列 |
| Cheng & Hoekstra (2013) | staggered TWFE DiD |
| Voight et al. (2012) | Mendelian Randomization |
| Chen et al. (2013) | 地理的RDD |
| Angrist & Krueger (1991) | 操作変数法(IV/2SLS) |

## 主要結果

**評価B（推論ステップ評価: 後続文献の懸念検出率）**

| 条件 | 検出率 |
|------|-------|
| baseline | 16/21 (76.2%) |
| scaffold_only | 17/21 (81.0%) |
| rubric_only | 19/21 (90.5%) |
| **proposed** | **20/21 (95.2%)** |

## 使い方

```bash
# 実験
python run.py --method proposed --case orben_przybylski_2019 --model gpt-5.4-mini

# 評価
python process_eval.py --model gpt-4o --out eval_outputs_process_v3/
python blind_eval.py --model gpt-4o --out eval_outputs_v3/
```

詳細は [CLAUDE.md](CLAUDE.md) を参照。
