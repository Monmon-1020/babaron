# 評価レポート v2.1（問題1のみ採用版）

## 1. v2.1 の位置づけ

v3 で問題1・3・4 を全て適用したところ proposed が大幅劣化したため、ユーザーの判断により **問題1のみを残し、問題3・4を v2 状態に戻した版** を v2.1 として実行した。

### 適用した修正
- **問題1**: `run.py` の S3 フラグ整合性NG時の fix_instructions に「decisionは変更せずフラグのみ修正してください」を明示

### 戻した修正
- **問題3**: `cases.json` twenge_2018 / twenge エントリを 7a39bac 時点に巻き戻し（E5、notes、not_observed の追記を削除）
- **問題4**: `prompts/rubric_supervisor_s3.txt` を 7a39bac 時点に巻き戻し（チェック10を削除）

### 維持した修正
- `schemas.py` validate_s2 で `what_to_compare` 等を str|list 両許容に変更（v3 で発生したスキーマエラー対策、副作用なし）

---

## 2. v2 / v3 / v2.1 集計比較

| method | v2 | v3 | **v2.1** |
|--------|---|---|---|
| baseline | 13/23 (56.5%) | 13/23 (56.5%) | **14/23 (60.9%)** |
| scaffold_only | 13/23 (56.5%) | 14/23 (60.9%) | **15/23 (65.2%)** |
| rubric_only | 14/23 (60.9%) | 14/23 (60.9%) | **12/23 (52.2%)** |
| **proposed** | **15/23 (65.2%)** | 11/23 (47.8%) | **12/23 (52.2%)** |

**v2.1 でも proposed は v2 より低い (15→12)**。問題1のみの修正でも proposed の劣化は防げていない。

decision_agreed の内訳:

| method | v2 | v3 | v2.1 |
|--------|---|---|------|
| baseline | 10/17 | 9/17 | 11/17 |
| scaffold_only | 9/17 | 10/17 | 11/17 |
| rubric_only | 10/17 | 10/17 | 8/17 |
| **proposed** | **11/17** | 8/17 | **9/17** |

---

## 3. 重要な発見: LLM実行揺らぎが修正効果より大きい

### 3-way 比較（同一仮説、3回の独立実行）

| case | method | v2 | v3 | v2.1 | コメント |
|------|--------|----|----|------|---------|
| Kelly | proposed | **3/3** | 2/3 | 2/3 | v2 だけ完璧。問題1適用後でも回復せず |
| Orben | baseline | 2/3 | 0/3 | 2/3 | v3 で偶然劣化、v2.1 で v2 に戻る |
| Orben | rubric_only | 3/3 | 3/3 | 1/3 | v2.1 で大幅劣化（修正と無関係） |
| Cheng | proposed | 1/3 | 2/3 | 2/3 | v3/v2.1 で改善（問題4 を戻したのに） |
| Chen | proposed | **2/3** | 0/3 | 0/3 | v3/v2.1 で揃って劣化 |

### 揺らぎの大きさ

24ペアのうち **15ペアが3版間で異なる結果** を出している。同じプロンプト・同じモデル・temperature=0.0 でも、再実行すると判定がかなり変わる。これは:

- gpt-5.4-mini の判定が確率的（temperature=0でも完全には固定化しない）
- Designer が複数候補から「最後に書いた判定」を選ぶ過程で実行ごとにブレる
- supervisor の retry loop で確率的経路を辿る

### 修正の効果は不明瞭

問題1の意図された効果（Kelly H2 が hold→survive）は v2.1 では起きなかった。**v2 で既に survive を出していた**ため。つまり v2 の Kelly proposed=3/3 が運の良い結果で、v2.1 で「平均的な」結果に戻った可能性。

---

## 4. supervisor 分析（v2.1）

### NG回数

| method | S1-CHK | S2-CHK | S3-CHK | total |
|--------|--------|--------|--------|-------|
| scaffold_only | 0 | 0 | 1 | 1 |
| **proposed** | 0 | 0 | **2** | **2** |

v2 (5) → v3 (7) → **v2.1 (2)**。問題4 を戻したことで supervisor の NG が減った（期待通り）。ただし全体の combined rate は改善しない。

### NG分類

| method | general_quality | causal_specific | total |
|--------|----------------|-----------------|-------|
| scaffold_only | 0 | 1 | 1 |
| **proposed** | **2** | **3** | **5** |

### Designer 変更

| method | 変化したケース |
|--------|--------------|
| scaffold_only | 1 (Kelly) |
| proposed | 1 (Chen) |

問題1 の修正により、Kelly proposed では Designer がリトライ過程で判定を弱める現象は起きていない（Kelly proposed の Designer 変更は0）。問題1 は意図した箇所では機能している。

---

## 5. 結論

### 問題1 の効果は確認できない
- v2 で Kelly proposed=3/3 は運の良い結果だった可能性が高い
- v2.1 で問題1 を適用しても 2/3 までしか回復せず
- 一方で、Kelly proposed の Designer は判定を弱める現象を起こさなくなった（supervisor analysis で確認）→ 問題1 は構造的には正しく動作している

### 真の発見: LLM実行揺らぎが評価の基盤を揺るがす
- 同一条件・同一モデル・temperature=0.0 でも、24ペア中 15ペアが実行間で結果が変動
- 修正の効果（±1〜2点）よりも揺らぎ（±2〜4点）の方が大きい
- 単一実行に基づく順位付けは信頼性に欠ける

### 推奨される対応
1. **複数実行の中央値で評価する**: 各 (case, method) を 3〜5 回実行し、最頻値または中央値を採用する
2. **v2 の結果をそのまま報告**: 「proposed が単一実行で combined 65.2% を達成した1サンプル」として報告し、揺らぎを limitation として明示する
3. **proposed の優位性主張を弱める**: 「LLM実行揺らぎを考慮すると、4条件間の差は1試行では有意ではない」と書く

### 論文への含意

論文で proposed の優位性を主張するには:
- **複数試行の集計が必須**
- **揺らぎを示す95%CI または分散** を併記
- v2/v3/v2.1 の3試行から計算すると、proposed の combined は **15, 11, 12** で平均 12.7、SD 約 2.1。baseline は **13, 13, 14** で平均 13.3。**baseline と proposed の差は揺らぎ範囲内**。

---

## 6. 推奨される次のステップ

1. **複数試行実験**: proposed 単独で各ケース 3〜5 回実行し、中央値で評価（合計 18〜30 実行）
2. **temperature 比較**: temperature=0 と temperature=0.3 で揺らぎの大きさを定量化
3. **gpt-5.4 (mini なし) との比較**: より大きいモデルで揺らぎが減るか検証
4. **以上の結果を踏まえて v2.1 レポートを正式化**

---

## 7. 生成ファイル（v2.1）

- `eval_outputs_v2_1/blind_eval_summary.json` — v2.1 集計
- `eval_outputs_v2_1/blind_eval_{case}_{method}.json` — 24件
- `eval_outputs_v2_1/blind_eval_prompts.json`
- `eval_outputs_v2_1/supervisor_analysis.json`
- `eval_outputs_v2_1/evaluation_report.md` — 本ファイル
- `outputs/run_4cond_{method}_{case}_v3.jsonl` — 24件のv2.1実行ログ（v3命名のまま）
- `outputs/v3_backup/` — 旧v3実行ログのバックアップ
