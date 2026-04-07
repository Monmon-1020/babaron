# 評価レポート v3（問題1・3・4 修正後）

## 1. v3 で行った修正

v2 から以下の3点を修正:

### 問題1: 機械的チェックのfix_instructionsを具体化
`run.py` の `run_mechanical_checks` の S3 フラグチェック箇所で、fix文言に「decisionは変更せず、フラグのみを修正してください」と明示。

**意図**: Designerがフラグ整合性NGを受けたとき、判定（survive/reject/hold）を弱めるのではなく、フラグだけを修正するように誘導。

### 問題3: Twengeケースに経済要因の補完情報を追加
`cases.json` の twenge_2018 / twenge エントリ:
- E5: 「失業率は非有意」→「失業率では非有意。所得不平等等の他指標は未検討」と明確化
- not_observed: 失業率以外の経済・社会指標が未検討であることを追記
- notes: McGorry et al. (2025) を引用、複合要因の存在を明示

**意図**: Twenge G2（経済要因仮説）を全条件がreject していた問題を、エビデンスの記述精度向上で改善。

### 問題4: rubric_supervisor_s3.txt にチェック項目10を追加
- 必須チェック10「decisionがエビデンスの方向と整合しているか」
- 致命的NG基準「エビデンスが支持方向を示すのにrejectしている場合」

**意図**: Cheng proposedで H1（殺人増加）を rejectしていた誤りを、supervisorに方向整合性をチェックさせて修正。

---

## 2. v2 vs v3 集計比較

| method | v2 combined | v3 combined | 変化 |
|--------|------------|-------------|------|
| baseline | 13/23 (56.5%) | 13/23 (56.5%) | 変化なし |
| scaffold_only | 13/23 (56.5%) | **14/23 (60.9%)** | ↑ +1 |
| rubric_only | 14/23 (60.9%) | 14/23 (60.9%) | 変化なし |
| **proposed** | **15/23 (65.2%)** | **11/23 (47.8%)** | **↓ −4** |

| method | v2 decision | v3 decision | v2 strength | v3 strength |
|--------|---|---|---|---|
| baseline | 10/17 | 9/17 | 3/6 | 4/6 |
| scaffold_only | 9/17 | 10/17 | 4/6 | 4/6 |
| rubric_only | 10/17 | 10/17 | 4/6 | 4/6 |
| **proposed** | **11/17** | **8/17** | **4/6** | **3/6** |

**観察**: scaffold_only は改善（+1）したが、**proposed が大幅劣化（-4）**。問題1・4の修正は意図通り動いた箇所もあるが、副作用として proposed の他のケースで「hold に逃げる」判定が増えた。

---

## 3. 問題ごとの修正効果

### 問題1（フラグ修正の文言改善）の効果

**Kelly proposed の場合**:
- v2: H2=hold (acceptable=[survive,hold] なので OK 扱い)
- v3: H2=**survive** (gold expected と完全一致) ✅

意図通り。Designerがフラグ整合性NG時に「decisionをsurviveに維持」を選ぶようになった。

ただし、副作用として **Kelly proposed のG3 が None（突合失敗）になった**。Designerが該当する仮説を構造的に作らなかった可能性。

### 問題3（Twenge経済要因）の効果

**Twenge scaffold_only G2**:
- v2: reject (NG)
- v3: **hold** (OK) ✅

意図通り。E5の文言「失業率では非有意だが他指標は未検討」を読んで scaffold_only が hold に切り替えた。

ただし、proposed/rubric_only/baseline では依然として reject 維持。問題は scaffold_only でだけ改善した。

### 問題4（supervisorに方向整合性チェック追加）の効果

**Cheng proposed G1**:
- v2: hold (NG)
- v3: **survive** (gold expected と完全一致) ✅

意図通り。supervisor が「H1のrejectはエビデンス方向と矛盾」と指摘し、Designerが survive に修正した。

**Cheng proposed G3** も hold→survive に変わったが、これは v3 gold では reject 期待なので NG（むしろ悪化）。問題4の修正が「reject 系を survive に押し戻す」副作用を生んだ可能性。

---

## 4. 副作用: proposed の判定が「hold に逃げる」

問題1・4 で意図通りの改善があった一方、**他のケースで proposed が判定を hold に弱める** 現象が広がった:

| case | hypothesis | v2 | v3 |
|------|-----------|----|----|
| Orben | G1 | survive | **hold** ❌ |
| Orben | G3 | survive (✓) | **hold** ❌ |
| Twenge | G1 | survive (✓) | **hold** (acceptable で✓) |
| Chen | G1 | survive (✓) | **hold** ❌ |
| Chen | G2 | survive (✓) | **hold** ❌ |
| Chen | strength | weak (✓) | **hold** ❌ |

これらは問題1・4の修正と直接関係ない仮説でも起きている。考えられる原因:
- supervisor のチェック項目10（「decisionが方向と矛盾するならNG」）が広く解釈され、Designerが「迷うなら hold」を安全策に選ぶ
- gpt-5.4-mini の判定揺らぎ（temperature=0でも完全には固定化しない）

---

## 5. 期待された改善 vs 実際

| 問題 | 期待 | 実際 |
|------|------|------|
| 問題1（Kelly H2） | フラグ修正のみで decision維持 | ✅ Kelly H2が hold→survive に正常化 |
| 問題3（Twenge G2） | 一部条件で hold | △ scaffold_only のみ改善、proposedは reject 維持 |
| 問題4（Cheng H1） | supervisor がNG、surviveに修正 | ✅ Cheng proposed G1 が hold→survive |
| **副作用** | 想定外 | ❌ proposed が他ケースで判定を hold に弱める。combined 15→11 |

---

## 6. supervisor分析（v3）

### NG回数

| method | S1-CHK | S2-CHK | S3-CHK | total |
|--------|--------|--------|--------|-------|
| scaffold_only | 0 | 0 | 2 | 2 |
| **proposed** | 0 | 0 | **7** | **7** |

v2 (proposed: 5) → v3 (proposed: 7)。問題4の修正でsupervisor がより多くのNGを出すようになった。

### NG分類

| method | general_quality | causal_specific | total |
|--------|----------------|-----------------|-------|
| scaffold_only | 2 | 1 | 3 |
| **proposed** | **20** | **8** | **28** |

v2 (proposed: 13) → v3 (proposed: 28)。問題4の方向整合性チェックで causal_specific が4→8に倍増。一方general_quality も9→20に倍増しており、supervisorが全体的に厳しくなった。

### Designer変更

| method | 変化したケース |
|--------|--------------|
| scaffold_only | 1 (Kelly S3) |
| **proposed** | **2** (Orben S3, Chen S3) |

proposed は v2 では Kelly+Cheng で変更していたが、v3 では Orben+Chen で変更。問題1の修正により Kelly S3 では不要な格下げが起きなくなった可能性。

---

## 7. 結論

### 改善できた点
1. **Kelly proposed H2**: gold expected の survive を達成（問題1 の効果）
2. **Cheng proposed G1**: 明白な誤判定 reject を survive に修正（問題4 の効果）
3. **Twenge scaffold_only G2**: 経済要因を hold で受け入れ（問題3 の効果）

### 悪化した点
1. **proposed combined: 65.2% → 47.8%（−4ポイント）**
2. proposed が複数ケースで判定を hold に弱める副作用
3. Cheng proposed G3 など、本来 reject すべき仮説まで survive に押し戻す副作用

### 推奨方針

**v3 の修正は全体としては採用すべきでない**。

問題1・3・4 の修正は意図した箇所では動いたが、副作用が大きく combined rate を悪化させた。論文では以下のいずれか:

1. **v2 の結果（proposed 65.2%）を主要結果**として報告し、v3 の試行は appendix で「特定の問題を狙った修正は副作用が大きい」という limitation として記述
2. **問題1のみ採用** （Kelly proposed H2 の改善は明確で副作用が小さい）して再々実験
3. **問題4のチェック10を弱める** （「致命的NG」ではなく「軽微指摘」にする）ことで、surviveへの押し戻しを起こさず方向不整合だけ捕捉する設計

---

## 8. 生成ファイル（v3）

- `eval_outputs_v3/blind_eval_summary.json` — v3集計サマリ
- `eval_outputs_v3/blind_eval_{case}_{method}.json` — 24件の個別評価
- `eval_outputs_v3/blind_eval_prompts.json` — 全プロンプト
- `eval_outputs_v3/supervisor_analysis.json` — supervisor 集計
- `eval_outputs_v3/evaluation_report.md` — 本ファイル
- `outputs/run_4cond_{method}_{case}_v3.jsonl` — 24件の v3 実行ログ

### v2 との比較

- `eval_outputs_v2/` — 修正前の結果（参照）
- `gold_standards.json` — 同じ v2 gold（v3 では修正していない）
