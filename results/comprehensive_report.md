# ブラインド評価の再実行指示書（Gold Standard 改訂版）

## 背景

Deep Research による6ケース全ての後続文献調査に基づき、gold standard を全面改訂した。
主要な変更点は以下。

1. Cheng & Hoekstra: strength を weak → **strong** に変更。H3 を hold → **reject** に変更
2. Voight et al.: strength を weak → **strong** に変更
3. Orben: H1 を hold → **reject** に変更
4. 複数ケースで「許容範囲」を導入（survive と hold の両方を正解とする仮説がある）
5. Kelly & Sharot: gold standard の根拠が方法論的原則であることを明記

これに基づき、blind_eval.py と gold_standards.json を更新し、全24件の評価を再実行する。

---

## 手順1: gold_standards.json を以下の内容で上書きする

```json
{
  "web_browsing_mood": {
    "case_label": "Kelly & Sharot (2025)",
    "gold_basis": "methodological_principles",
    "gold_basis_note": "出版後16ヶ月でStudy 3の識別仮定を検討した査読付き後続文献なし。因果推論の方法論的原則に基づいて定義",
    "hypotheses": [
      {
        "id": "G1",
        "statement": "ネガティブなウェブコンテンツの閲覧は気分を悪化させる（コンテンツ→気分の因果効果）",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "Study 2のランダム割付実験により支持。批判的後続文献なし"
      },
      {
        "id": "G2",
        "statement": "気分の悪化はネガティブなウェブコンテンツの閲覧を増加させる（気分→コンテンツの因果効果）",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive", "hold"],
        "source": "Study 3の媒介分析で示唆。ただし識別仮定（処置→結果の直接効果なし）の妥当性が未検証。Pearl (2014), VanderWeele (2015)により媒介分析の識別仮定は一般に強い仮定"
      },
      {
        "id": "G3",
        "statement": "閲覧と気分の関連は第三要因（精神病理傾向等）による見かけの相関であり、直接の因果効果はない",
        "expected_decision": "reject",
        "acceptable_decisions": ["reject"],
        "source": "Study 2-3のランダム割付により短期的な直接効果が確認されている"
      }
    ],
    "expected_strength": "weak",
    "acceptable_strengths": ["weak"],
    "strength_source": "H2の因果方向に識別仮定の懸念が未解消。双方向因果の主張全体としてはweak"
  },
  "orben_przybylski_2019": {
    "case_label": "Orben & Przybylski (2019)",
    "gold_basis": "subsequent_literature",
    "gold_basis_note": "Twenge et al. (2020) Matters Arising、Twenge et al. (2022) 再分析、Orben et al. (2022) 著者修正、Vuorre & Przybylski (2024) 大規模追試",
    "hypotheses": [
      {
        "id": "G1",
        "statement": "デジタルテクノロジー利用は青少年の幸福感に実質的な負の因果効果を持つ",
        "expected_decision": "reject",
        "acceptable_decisions": ["reject"],
        "source": "Vuorre & Przybylski (2024): 168カ国200万人で小さく一貫しない関連。Allcott et al. (2020, AER): Facebook停止実験で0.09SD。全体として実質的な因果効果は否定的"
      },
      {
        "id": "G2",
        "statement": "デジタルテクノロジー利用と幸福感の関連は存在するが、実質的に無視できるほど小さい",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive", "hold"],
        "source": "平均0.4%は再現。しかしTwenge et al. (2022, Acta Psychologica): 女子×SNSでβ=−0.20に上昇。Orben et al. (2022, Nature Communications): 年齢・性別特異的感受性窓を報告。無意味という強い主張は修正が必要"
      },
      {
        "id": "G3",
        "statement": "関連の大きさは分析仕様（変数の操作化、サンプル選択等）に依存する",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "最も頑健に確立された知見。Orben自身のSCA、Twenge et al. (2022)の再分析が直接確認"
      }
    ],
    "expected_strength": "weak",
    "acceptable_strengths": ["weak"],
    "strength_source": "因果方向は横断データで未同定。サブグループ異質性が発見され無意味とは断定できなくなった"
  },
  "twenge_2018": {
    "case_label": "Twenge, Martin & Campbell (2018)",
    "gold_basis": "subsequent_literature",
    "gold_basis_note": "Heffer et al. (2019) 明示的反論、Jensen et al. (2019) 縦断+EMA、Coyne et al. (2020) 8年縦断、Odgers & Jensen (2020) 包括的レビュー、Odgers (2024) Haidt批評",
    "hypotheses": [
      {
        "id": "G1",
        "statement": "スクリーンタイムの増加は青少年の幸福感低下の原因である",
        "expected_decision": "hold",
        "acceptable_decisions": ["survive", "hold"],
        "source": "Heffer et al. (2019): 縦断でSNS→抑うつの前方予測なし。Jensen et al. (2019): 縦断+EMAで関連なし。Coyne et al. (2020): 個人内変化として予測力なし。ただしHaidt (2024)は因果主張を展開し完全棄却はされていない"
      },
      {
        "id": "G2",
        "statement": "幸福感低下は経済的要因や他の時代的変化で説明できる",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive", "hold"],
        "source": "McGorry et al. (2025, Frontiers in Psychiatry): 経済不安定、教育圧力、気候不安等の複合要因。多重決定の見方が支持"
      },
      {
        "id": "G3",
        "statement": "因果は逆方向：幸福感が低い青少年がスクリーンタイムを増やす",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "Heffer et al. (2019): 思春期女子で抑うつ→SNS使用増加を予測。Odgers & Jensen (2020): 逆因果の証拠の方が一貫"
      }
    ],
    "expected_strength": "weak",
    "acceptable_strengths": ["weak"],
    "strength_source": "横断データからの因果推論は方法論的に不十分。大多数のレビューが強い因果主張には証拠不十分と結論。Odgers (2024, Nature)"
  },
  "cheng_hoekstra": {
    "case_label": "Cheng & Hoekstra (2013)",
    "gold_basis": "subsequent_literature",
    "gold_basis_note": "McClellan & Tekin (2017) 独立再現、Humphreys et al. (2017) フロリダ分析、Degli Esposti et al. (2022) 最厳密追試、Yakubovich et al. (2021) 系統的レビュー、RAND (2024) 最高評価、Cunningham (2021) TWFEバイアス検証",
    "hypotheses": [
      {
        "id": "G1",
        "statement": "Castle Doctrine法の採用は殺人・過失致死を増加させる",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "McClellan & Tekin (2017, JHR): 独立データで約8%増再現。Degli Esposti et al. (2022, JAMA Network Open): 23州でIRR=1.08。RAND (2024): 最高評価supportive evidence。6つの高品質研究すべてが増加方向"
      },
      {
        "id": "G2",
        "statement": "Castle Doctrine法は暴力犯罪（窃盗・強盗・加重暴行）を抑止する",
        "expected_decision": "reject",
        "acceptable_decisions": ["reject"],
        "source": "Yakubovich et al. (2021, AJPH): 25研究の系統的レビューで抑止の証拠なし。RAND (2024): 抑止を支持するエビデンスなし"
      },
      {
        "id": "G3",
        "statement": "推定された殺人増加はstaggered TWFE推定量の方法論的問題（負のウェイト、時間的異質性）による見かけの効果である",
        "expected_decision": "reject",
        "acceptable_decisions": ["reject"],
        "source": "Cunningham (2021): このデータで検証し異質性バイアスの証拠はほとんどない。非TWFE手法でも同結果。RAND: バイアスの証拠をほとんど見出さなかった"
      }
    ],
    "expected_strength": "strong",
    "acceptable_strengths": ["strong"],
    "strength_source": "複数の独立チーム、異なるデータ源（UCR, Vital Statistics）、異なる手法（DiD, interrupted time series, 合成コントロール, ベイズ）が約8%増に収束。RAND最高評価。銃政策文献で最も再現された知見の一つ"
  },
  "voight_hdl": {
    "case_label": "Voight et al. (2012)",
    "gold_basis": "subsequent_literature",
    "gold_basis_note": "Holmes et al. (2015) 多面発現分析、Richardson et al. (2020) 多変量MR、Zuber et al. (2021) 確認、CETP阻害薬4剤の臨床試験、Holmes & Davey Smith (2017) Anacetrapib解釈",
    "hypotheses": [
      {
        "id": "G1",
        "statement": "HDL-C上昇は心筋梗塞リスクを因果的に低下させる（HDL仮説）",
        "expected_decision": "reject",
        "acceptable_decisions": ["reject"],
        "source": "Holmes et al. (2015, EHJ): 制限付きスコアでシグナル消失。Richardson et al. (2020, PLOS Medicine): ApoB調整で帰無。CETP阻害薬3剤失敗。パラダイムがHDL-C上昇→ApoB低下に移行済み"
      },
      {
        "id": "G2",
        "statement": "HDL-Cと心筋梗塞の観察的逆相関は、LDL-Cやトリグリセリドとの交差多面発現による見かけの関連である",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "Holmes et al. (2015): 多面発現SNP除外でシグナル消失が直接証拠。Richardson et al. (2020): ApoB調整で帰無。Zuber et al. (2021): 確認"
      }
    ],
    "expected_strength": "strong",
    "acceptable_strengths": ["strong"],
    "strength_source": "単変量MR、多変量MR、臨床試験の3種が収束。MRの最も成功した適用例。教科書的事例として広く引用"
  },
  "chen_huairiver": {
    "case_label": "Chen et al. (2013)",
    "gold_basis": "subsequent_literature",
    "gold_basis_note": "Gelman & Zelizer (2015) 多項式批判、Gelman & Imbens (2019) 一般的方法論批判、Ebenstein et al. (2017) 元著者改訂、Fan et al. (2020) 独立確認、Pope & Dockery (2013) 疫学的評価",
    "hypotheses": [
      {
        "id": "G1",
        "statement": "粒子状大気汚染への長期曝露は平均寿命を短縮する",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "Ebenstein et al. (2017, PNAS): 改訂推定で方向維持（3.1年）。Fan et al. (2020): 時間的RDDで因果連鎖を独立確認。国際疫学と整合"
      },
      {
        "id": "G2",
        "statement": "推定された5.5年という効果の大きさは3次多項式の選択に駆動されたものであり、効果量の信頼性が低い",
        "expected_decision": "survive",
        "acceptable_decisions": ["survive"],
        "source": "Gelman & Zelizer (2015): 線形で1.6年（非有意）。次数で大幅変動。91年の非現実的含意。元著者がEbenstein et al. (2017)で局所線形に切替え3.1年に改訂"
      },
      {
        "id": "G3",
        "statement": "淮河南北の平均寿命差は暖房政策以外の地域差（経済水準、医療アクセス等）で説明できる",
        "expected_decision": "hold",
        "acceptable_decisions": ["hold"],
        "source": "共変量バランス等は実施済みだが淮河は中国の根本的南北境界であり完全統制困難。Pope & Dockery (2013)も効果量が米国推定より大きいことを指摘"
      }
    ],
    "expected_strength": "weak",
    "acceptable_strengths": ["weak"],
    "strength_source": "因果の方向は支持されるが効果量が多項式仕様に大きく依存。改訂推定3.1年も米国推定の1.5-2倍"
  }
}
```

---

## 手順2: blind_eval.py の判定ロジックを更新する

現在の blind_eval.py は `expected_decision` との完全一致で判定しているはず。
これを `acceptable_decisions` リストとの一致に変更する。

具体的には、以下の箇所を修正する。

**変更前（想定）:**
```python
decision_match = (b_decision == gold_hyp["expected_decision"])
```

**変更後:**
```python
acceptable = gold_hyp.get("acceptable_decisions", [gold_hyp["expected_decision"]])
decision_match = (b_decision in acceptable)
```

strength についても同様：

**変更前:**
```python
strength_match = (output_strength == gold["expected_strength"])
```

**変更後:**
```python
acceptable_strengths = gold.get("acceptable_strengths", [gold["expected_strength"]])
strength_match = (output_strength in acceptable_strengths)
```

---

## 手順3: 全24件のブラインド評価を再実行する

```bash
python blind_eval.py --model gpt-4o --out eval_outputs_v2/
```

出力ディレクトリを `eval_outputs_v2/` に変更し、旧結果（eval_outputs/）と区別する。

---

## 手順4: 結果のサマリを生成する

```bash
python blind_eval.py --summary eval_outputs_v2/
```

以下の表を出力する。

### 表1: ケース別・条件別の一致率

| ケース | baseline | scaffold_only | rubric_only | proposed |
|--------|----------|---------------|-------------|----------|

各セルに「一致した仮説数/gold仮説数」と strength 一致を記載。

### 表2: 条件別の集計

| 条件 | 仮説一致数/全仮説数 | strength一致数/全ケース数 | 合計一致率 |
|------|-------------------|------------------------|----------|

### 表3: 許容範囲の効果

許容範囲ありの仮説（Kelly H2, Orben H2, Twenge H1, Twenge H2）について、
各条件がsurviveとholdのどちらを出したかの内訳。

---

## 手順5: 評価Cのデータも合わせて集計する

blind_eval とは別に、supervisor のログから以下を集計する。
（新規スクリプト `supervisor_analysis.py` を作成するか、既存の集計に追加）

### 集計するもの

1. **NG回数の条件別・段階別集計**

scaffold_only と proposed のそれぞれについて、
S1-CHK, S2-CHK, S3-CHK でsupervisorがNGを出した回数を集計する。

```
出力形式:
{
  "scaffold_only": {
    "S1-CHK": {"total_ng": 2, "cases": ["web_browsing_mood", "orben"]},
    "S2-CHK": {"total_ng": 1, "cases": ["cheng_hoekstra"]},
    "S3-CHK": {"total_ng": 3, "cases": ["web_browsing_mood", "twenge", "chen"]}
  },
  "proposed": {
    "S1-CHK": {"total_ng": 4, "cases": [...]},
    "S2-CHK": {"total_ng": 3, "cases": [...]},
    "S3-CHK": {"total_ng": 5, "cases": [...]}
  }
}
```

2. **NG理由の分類**

各NGについて、supervisorが出した `fatal_issues` のテキストを抽出し、
以下の2カテゴリに分類する。

- **一般的品質問題**: 文章の曖昧さ、論理矛盾、形式不備
  （キーワード例: 曖昧、不明確、矛盾、形式、スキーマ）
- **因果推論固有の問題**: 仮説間関係の誤り、識別仮定の不足、結論の過大評価、反証条件の不備
  （キーワード例: hypothesis_relations, exclusive, independent, identification, 
   識別仮定, 排他, 独立, strength, strong, 過剰断定, 反証）

分類はキーワードマッチで自動化してよい。完全な正確性は不要で、
大まかな傾向が見えればよい。

```
出力形式:
{
  "scaffold_only": {
    "general_quality": 4,
    "causal_specific": 1,
    "examples": [
      {"case": "web_browsing_mood", "stage": "S3-CHK", "category": "general_quality",
       "issue": "reasoning が冗長で簡潔性が不足"}
    ]
  },
  "proposed": {
    "general_quality": 3,
    "causal_specific": 8,
    "examples": [
      {"case": "web_browsing_mood", "stage": "S1-CHK", "category": "causal_specific",
       "issue": "hypothesis_relationsの宣言が不合理：独立であるべき仮説ペアがexclusiveと宣言されている"},
      {"case": "web_browsing_mood", "stage": "S3-CHK", "category": "causal_specific",
       "issue": "識別仮定にuncertainがあるのにstrength=strongは不可"}
    ]
  }
}
```

3. **修正前後の差の記録**

supervisorがNGを出したケースについて、
Designer の最初の出力（attempt=0）と最終出力（最後のsuccessful attempt）を比較し、
何が変わったかを記録する。

具体的には以下を比較する：
- S1: 仮説数の変化、hypothesis_relations の変化
- S2: identification_assumptions の数の変化
- S3: strength の変化、各仮説のdecisionの変化

```
出力形式:
{
  "proposed": {
    "web_browsing_mood": {
      "S3": {
        "retries": 2,
        "changes": [
          {"field": "strength", "before": "strong", "after": "weak"},
          {"field": "H2.decision", "before": "survive", "after": "hold"}
        ]
      }
    }
  }
}
```

---

## 手順6: 全結果を一つのレポートにまとめる

以下の構成で `eval_outputs_v2/evaluation_report.md` を作成する。

1. 評価方法の説明
   - gold standard の定義方法（後続文献の合意 + Kelly のみ方法論的原則）
   - ブラインドLLM突合の手順
   - supervisor分析の手順

2. 評価A の結果（ブラインド突合による結論の妥当性）
   - 表1, 表2, 表3

3. 評価C の結果（supervisorの修正記録）
   - NG回数の比較
   - NG理由の分類
   - 修正前後の変化の具体例

4. 2つの評価の統合的解釈

---

## 注意事項

- ブラインド突合のモデルは gpt-4o を使う（実験のgpt-5.4-miniと異なるモデル）
- temperature=0.0
- ブラインド突合プロンプトに研究の目的を入れない（これは変更なし）
- 旧結果（eval_outputs/）は保存したまま、新結果を eval_outputs_v2/ に出力する
- gold_standards.json の旧版もバックアップとして保存する（gold_standards_v1.json にリネーム）