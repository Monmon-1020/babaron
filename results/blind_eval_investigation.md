# ブラインド評価の不一致原因の調査

## 質問への回答

> Q: ブラインド突合は仮説のdecision一致だけを見ていて、strengthや仮説間関係を見ていないか？

### A: 部分的にYes

`blind_eval_*.json` には以下が記録されています:
- `matches[].decision_match`: 各仮説の判定一致
- `strength_match`: 結論強度の一致（boolean）
- `unmatched_b_hypotheses`: AIにあるがgoldにない仮説（情報量）
- `match_confidence`: 各マッチの確度（high/medium/low）

しかし `blind_eval_summary.json` の `aggregate` は **`decision_agreed` のみ**を集計していました。`strength_match` は per-row には記録されているが、aggregate に含まれていない。

### strength を含めた厳密集計

| method | (decision一致 + strength一致) / 総点 | rate |
|--------|-----|------|
| baseline | 18/23 | 78.3% |
| scaffold_only | 17/23 | 73.9% |
| rubric_only | 16/22 | 72.7% |
| **proposed** | **18/23** | **78.3%** |

→ **strengthを含めても baseline と proposed は同率（78.3%）**。proposed の優位性は出ない。

---

## より深い原因の調査

### Kelly & Sharot proposedの最終S3を確認

ブラインド評価が gpt-4o に渡したのは:
```
H1: survive
H2: hold       ← Goldはsurvive、不一致
H3: reject     ← Goldはreject、一致
H4: hold
strength: weak
```

しかし `outputs/run_4cond_proposed_web_browsing_mood_v2.jsonl` には3つのS3 designer出力が記録されている:

| attempt | H1 | H2 | H3 | H4 | S3-CHK verdict |
|---------|----|----|----|----|---------------|
| 0 | survive | **survive** | reject | survive | NG |
| 1 | survive | **survive** | reject | survive | NG |
| 2 | survive | **hold** | reject | hold | OK |

**つまり、attempt=0 と 1 では H2=survive で gold と一致していたが、機械的チェックで NG になり、リトライした結果 attempt=2 で H2=hold に「劣化」して通過した。**

### NGの理由

S3-CHK attempt=0 の fatal_issues:
```
- S3: H2 の条件一致フラグはちょうど1つだけ true にしてください。
- S3: H2 は survive なのに条件一致フラグが不整合です。
- S3: H4 の条件一致フラグはちょうど1つだけ true にしてください。
- S3: H4 は survive なのに条件一致フラグが不整合です。
```

機械的チェック (`run_mechanical_checks` in `run.py`) が、`accept_condition_met` / `reject_condition_met` / `hold_condition_met` のうち「厳密に1つだけtrue」を要求している。Designer は H2 で `accept_condition_met=true` と `hold_condition_met=true` の両方をtrueにしていた。

リトライプロンプトを受けた Designer は、フラグ整合性を取るために**判定そのものをsurviveからholdに変更した**。これが意図しない副作用。

---

## 根本原因

### proposed の劣化メカニズム

1. **Designer は正しい結論（survive）を出す**
2. **機械的チェックがフラグの形式整合性で NG**
3. **Designer はフラグを整合させる代わりに、判定を弱める方向（survive→hold）で対応**
4. **結果として、保守的だが誤った判定が最終出力になる**

これは proposed の「rubric + scaffold + mechanical checks」という多層構造が、**Designer に「迷ったら hold」という安易な逃げ道を強制**してしまう副作用です。

### 各ケースで何が起きていたか

| case | gold | proposed最終出力 | 失敗の種類 |
|------|------|---------------|----------|
| Kelly | H2=survive | H2=hold | フラグ整合性NGで判定劣化 |
| Orben | H1=hold | H1=survive | 過剰断定（rubric_designer_s1のガイダンスに従って方向は支持） |
| Twenge | G3=hold | (対応する仮説なし) | proposedはH3を立てなかった |
| Cheng | G1=survive | G1=hold | フラグ整合性NGで判定劣化の可能性 |
| Voight | (両方一致) | (両方一致) | 問題なし |
| Chen | G3=hold | (対応する仮説なし) | proposedはH3を立てなかった |

---

## 私の手動採点が誤っていた可能性

以前のレポートで「proposed = 6ケース全て4/4」と書きましたが、これは:
- attempt=0や1の中間S3を見ていた可能性
- gpt-4oによる厳密な意味的突合ではなく、私の主観的な「H2 surviveの理由が書いてあるからsurvive扱い」という緩い基準

ブラインド評価の方が**より厳密で再現性がある**評価です。

---

## 提案

### 短期: 集計方法の修正

`blind_eval.py` の `aggregate()` で strength_match を集計に含める。
（既に実施した厳密集計でも proposed の優位性は出ないので、根本的な修正にはならない）

### 中期: 機械的チェックの修正

`run.py` の `run_mechanical_checks()` で、フラグ整合性NGの場合の修正指示を改善:
- 現状: 「フラグを排他的に設定してください」
- 改善: 「decision の値（survive/reject/hold）はそのままに、対応する1つのフラグだけをtrueにしてください」

これにより Designer が判定を弱める方向ではなく、フラグだけを修正する方向に誘導される。

### 長期: rubric_supervisor の調整

`rubric_supervisor_s3.txt` に「フラグ整合性のための判定変更を防ぐ」ガイダンスを追加:
- 「decision の値が観察データと整合的なら、フラグの修正のみで対応すること」
- 「フラグ整合性を理由に decision を hold に格下げしないこと」

### 最も重要: 論文での主張の修正

**現状のブラインド評価結果では proposed は baseline に対して有意な優位性を示せていません。** これは:

1. baseline が「Designer単独でも因果推論を概ね適切に扱える」ことの証拠
2. proposed の多層構造が一部のケースで判定を劣化させる副作用を持つ

論文では:
- proposed の優位性を「全ケースで顕著」とは書けない
- 「過剰断定の抑制」（baseline 5/6 vs proposed 6/6）と「rubric項目の構造的明示」では優位性がある
- ただし「最終的な判定の正確性」では baseline と同等

という形で誠実に報告する必要があります。
