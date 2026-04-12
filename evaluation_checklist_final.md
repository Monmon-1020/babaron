# 評価チェックリスト確定版

各項目を0/1/2で採点する。0=言及なし、1=言及あるが不正確/不完全、2=正確かつ十分。

---

## 1. castle（DiD）

| # | 評価項目 | Gold Standard | 引用元 | 引用原文 |
|---|---|---|---|---|
| a | 手法選択がDiD（TWFE）か | DiD / Two-Way Fixed Effects | Cunningham §9.6.6 + bacondecomp vignette | `lm(l_homicide ~ post + factor(state) + factor(year))` → TWFE estimate = 0.0818 |
| b | 識別仮定: 平行トレンド仮定を述べているか | 処置がなかった場合の処置群と対照群のアウトカムの時間変化が同一であること | Cunningham §9.2.1 | "We are assuming that there is no time-variant company specific unobservables. Nothing unobserved in Lambeth households that is changing between these two periods that also determines cholera deaths. This is equivalent to assuming that T is the same for all units. And we call this the *parallel trends* assumption." |
| c | 平行トレンドの重要性を認識しているか | DiDの最も重要な仮定である | Cunningham §9.2.1 | "it is the most important assumption in the design's engine. If you can buy off on the parallel trends assumption, then DD will identify the causal effect." |
| d | 平行トレンドが崩れた場合の帰結を述べているか | ATTが識別不能になる。非平行トレンドバイアス項が残存する | Cunningham §9.2.2 | "This bottom line is often called the parallel trends assumption and it is by definition untestable since we cannot observe this counterfactual conditional expectation." |
| e | 平行トレンドの検証不可能性を認識しているか | 定義上検証不可能（反事実が観察できないため） | Cunningham §9.2.2 | 同上 |
| f | OLSが常に対照群の傾きを反事実として使うことを認識しているか | OLSは対照群の傾きが正しいかどうかに関わらず、それを反事実として推定する | Cunningham §9.2.3 | "OLS always estimates an effect size using the slope of the untreated group as the counterfactual, regardless of whether that slope is in fact the correct one." |
| g | SUTVA/spilloverへの言及があるか | 他州へのspilloverがないこと | Cunningham §9.5.3 | "We chose the 25- to 29-year-olds in the same states as within-state comparison groups instead of 20- to 24-year-olds after a lot of thought. Our reasoning was that we needed an age group that was close enough to capture common trends but far enough so as not to violate SUTVA." |
| h | 同時政策変更の懸念への言及があるか | 同時期の他の政策変更がないこと（州固有の時間ショックがないこと） | Cunningham §9.5.1 | "But what if there were state-specific time shocks such as NJ_t or PA_t? Then even DD cannot recover the treatment effect." |
| i | クラスター標準誤差の必要性を述べているか | 通常のSEは過小評価する。州レベルのクラスタリングが必要 | Cunningham §9.3 | Bertrand, Duflo & Mullainathan (2004): "conventional standard errors often severely understate the standard deviation of the estimators" 解決策: ブロックブートストラップ、データ集約、クラスター標準誤差 |
| j | Staggered adoptionでのTWFE問題への言及があるか | 異なるタイミングの処置群間比較で、すでに処置を受けた群が「対照群」として使われうる | Cunningham §9.6 + bacondecomp vignette | Bacon Decomposition結果: Earlier vs Later Treated (weight=0.060, est=-0.006), Later vs Earlier (weight=0.032, est=0.070), Treated vs Untreated (weight=0.908, est=0.088). 問題ある比較は~9%のみ |
| j2 | モデリング選択: 共変量の選択が結果に影響することを認識しているか | コントロール変数の有無で推定値が変わる | bacondecomp vignette | コントロール変数なし: TWFE=0.0818。コントロール変数あり(l_pop, l_income): TWFE=0.0906。共変量選択により推定が約10%変動 |
| j3 | モデリング選択: 回帰の関数形やコントロール変数の正当化があるか | どの共変量を含めるか、どの関数形を用いるかは解析者の自由度であり、正当化が必要 | Cunningham §9.2.3 | "if you need to avoid omitted variable bias through controlling for endogenous covariates that vary over time, then you may want to use regression. Such strategies are another way of saying that you will need to close some known critical backdoor." |
| k | 診断検定: Event study / lead検定への言及があるか | 処置前期間のDiD係数がゼロであることを確認 | Cunningham §9.4.1 | "If DD coefficients in the pre-treatment periods are statistically zero, then the difference-in-differences between treatment and control groups followed a similar trend prior to treatment." |
| l | Event study検定の限界を認識しているか | 事前の類似性は事後の平行性を保証しない | Cunningham §9.4.1 | "Just because they were similar before does not logically require they be the same after." / "pre-treatment similarities are neither necessary nor sufficient to guarantee parallel counterfactual trends (Kahn-Lang and Lang 2019)." |
| m | strengthが≠ strongか | moderate（TWFE問題は限定的だが平行トレンドの検証不可能性は残存） | §9.2.2 + §9.4.1 + bacondecomp | 上記d, e, l, jの根拠の組合せ |
| n | strengthの根拠が識別仮定の状態と連動しているか | 根拠が平行トレンドの検証不可能性やTWFE問題と結びついているか | — | — |

---

## 2. close_elections（RDD）

| # | 評価項目 | Gold Standard | 引用元 | 引用原文 |
|---|---|---|---|---|
| a | 手法選択がRDD（Sharp）か | Sharp Regression Discontinuity Design | Cunningham §6.4 + §6.2.1 | causaldata公式: "This data comes from a close-elections regression discontinuity study from Lee, Moretti, and Butler (2004)." / §6.2.1: D_i = 1 if X_i ≥ c_0, 0 if X_i < c_0 |
| b | 識別仮定: 連続性仮定を述べているか | カットオフにおけるポテンシャルアウトカムの条件付き期待値がrunning variableに対して連続であること | Cunningham §6.2.2 | "The key identifying assumption in an RDD is called the continuity assumption. It states that E[Y⁰ᵢ\|X=c₀] and E[Y¹ᵢ\|X=c₀] are continuous (smooth) functions of X even across the c₀ threshold. Absent the treatment, in other words, the expected potential outcomes wouldn't have jumped; they would've remained smooth functions of X." |
| c | 連続性仮定がOVBを排除することを認識しているか | カットオフにおける省略変数バイアスを排除する | Cunningham §6.2.2 | "If the expected potential outcomes are not jumping at c₀, then there necessarily are no competing interventions occurring at c₀. Continuity, in other words, explicitly rules out omitted variable bias at the cutoff itself." |
| d | 識別仮定: 操作不可能性を述べているか | 個体がrunning variableを正確に操作してカットオフの上下を選択できないこと | Cunningham §6.1.4 + McCrary (2008) | §6.1.4: "The validity of an RDD doesn't require that the assignment rule be arbitrary. It only requires that it be known, precise and free of manipulation." / McCrary (2008): "if agents are able to manipulate the running variable... This paper develops a test of manipulation related to continuity of the running variable density function." |
| e | 連続性仮定が崩れた場合の帰結を述べているか | カットオフでのジャンプが処置効果以外の原因と区別不可 → LATE識別不能 | Cunningham §6.2.2 | "Does there exist some omitted variable wherein the outcome would jump at c₀ even if we disregarded the treatment altogether? If so, then the continuity assumption is violated and our methods do not recover the LATE." |
| f | 操作が存在する場合の帰結を述べているか | カットオフ付近で処置群と対照群の構成が異なり、セレクションバイアスが生じる | McCrary (2008) | "we would expect the running variable to be discontinuous at the cutoff, with surprisingly many individuals just barely qualifying for a desirable treatment assignment" |
| g | LATEの局所性の限界を述べているか | RDDはカットオフ付近の局所的効果のみ推定。外的妥当性は限定的 | Cunningham §6.2.1 | "Since identification in an RDD is a limiting case, we are technically only identifying an average causal effect for those units at the cutoff. Insofar as those units have treatment effects that differ from units along the rest of the running variable, then we have only estimated an average treatment effect that is local to the range around the cutoff." |
| h | バンド幅選択への感度を述べているか | 推定結果がバンド幅の選択に敏感でありうる | Cunningham §6.1.3 | Hoekstra (2009)の例: "he experiments with a variety of binning of the data (what he calls the 'bandwidth'), and his estimates when he does so range from 7.4% to 11.1%." |
| i | 関数形選択への懸念を述べているか | 高次多項式の使用は推奨されない | Cunningham §6.2.2 + Gelman & Imbens (2019) | 教科書がシミュレーションで線形近似と多項式の影響を実演。Gelman & Imbens (2019)が高次多項式の問題を確立。 |
| j | 診断検定: McCrary密度検定への言及があるか | running variableの密度がカットオフで不連続でないことを確認 | Cunningham §6.3.1 + McCrary (2008) | McCrary (2008): "The test is based on the intuition that... we would expect the running variable to be discontinuous at the cutoff, with surprisingly many individuals just barely qualifying for a desirable treatment assignment." |
| k | 診断検定: 共変量バランス検定への言及があるか | カットオフ付近で事前共変量にジャンプがないことを確認 | Cunningham §6.3.2 + §6.2.2 | §6.3.2 "Covariate balance and other placebos" / §6.2.2: Carpenter & Dobkin (2009)の例でプラシーボ検定を実演 |
| l | strengthがmoderate〜strongの範囲か | moderate〜strong（RDDは最も信頼性の高い観察研究デザインの一つ。close electionは操作困難。ただしLATEの局所性は残存） | Cunningham §6.1.1, §6.1.2 | §6.1.2: "its ability to convincingly eliminate selection bias. This appeal is partly due to the fact that its underlying identifying assumptions are viewed by many as easier to accept and evaluate." / §6.1.1: "one of the most credible research designs with observational data" |
| m | strengthの根拠が識別仮定の状態と連動しているか | 根拠が連続性仮定・操作不可能性の検証状況と結びついているか | — | — |

---

## 3. nhefs（IPW）

| # | 評価項目 | Gold Standard | 引用元 | 引用原文 |
|---|---|---|---|---|
| a | 手法選択がIPW（またはg推定/傾向スコア法）か | Inverse Probability Weighting | Hernán & Robins Ch.12 | "To estimate the effect of smoking cessation on weight gain we will use real data from the NHEFS" / "IP weighted least squares. Under our assumptions, association is causation" |
| b | 識別仮定: 条件付き交換可能性を述べているか | 観測された共変量で条件付けた上で、処置割り当てがポテンシャルアウトカムと独立 | Hernán & Robins Ch.3 §3.2 | 数式: Y^a ⊥⊥ A \| L / "conditional exchangeability – there should be no unmeasured confounding, meaning treatment assignment is ignorable conditional on measured confounders" |
| c | 交換可能性の検証不可能性を認識しているか | 一般に交換可能性が成立するかを判定することはできない | Hernán & Robins Ch.3 | "we are generally unable to determine whether exchangeability holds in our study" |
| d | 識別仮定: Positivityを述べているか | 共変量の全ての水準において処置を受ける確率が正であること | Hernán & Robins Ch.3 §3.3 | "positivity – each treatment must have a non-zero probability across all covariates" / 数式: P(A=a\|L=l) > 0 for all l with P(L=l) > 0 |
| e | 識別仮定: Consistencyを述べているか | 観測されるアウトカムが実際に受けた処置水準に対応するポテンシャルアウトカムと一致すること | Hernán & Robins Ch.3 §3.4-3.5 | "causal consistency – outcomes at the treatment levels to be compared must align with their counterfactual counterparts" / E[Y\|A=a] = E[Y^a\|A=a] by consistency |
| f | 交換可能性が崩れた場合の帰結を述べているか | 未観測交絡バイアスが残存し、IPW推定量はATEを一致推定しない | Hernán & Robins Ch.3 §3.2 + Ch.2 | 因果効果の識別にはE[Y^a\|A=a] = E[Y^a]（mean exchangeability）が必要。教科書原文: "E[Y^a\|A=a] = E[Y^a] by mean exchangeability." 交換可能性が崩壊するとこの等式が成立せず、観察された関連（association）が因果効果（causation）と一致しなくなる |
| g | Positivityが崩れた場合の帰結を述べているか | 極端な重みが発生し推定が不安定になる | Hernán & Robins Ch.12 | "In the presence of random violations, we used our parametric model to estimate the probability of treatment in the strata with random zeroes using data from individuals in the other strata. In other words, we use parametric models to smooth over the zeroes." |
| h | 極端な重み / stabilized weightsへの言及があるか | 傾向スコアが0/1に近い場合の対処 | Hernán & Robins Ch.12 | 同上（parametric smoothing） |
| i | 傾向スコアモデルの指定への懸念があるか | モデルが誤指定の場合バイアスが生じる | Hernán & Robins Ch.12 | 教科書はIPW推定にロジスティックモデルを使用: "the logistic model used in Section 12.2 estimated the probability of quitting in white women aged 66 by interpolating from all other individuals in the study." パラメトリックモデルの選択がIPW推定値に直接影響することを示唆 |
| j | 未観測交絡の可能性 / 感度分析への言及があるか | 観察研究のため条件付き交換可能性は検証不可能。感度分析で頑健性を評価すべき | 標準的議論 + Ch.3原文 | Ch.3: "we are generally unable to determine whether exchangeability holds in our study" |
| k | 診断検定: 共変量バランス確認への言及があるか | IPW適用後の処置群・対照群間の共変量バランス改善を確認 | Hernán & Robins Ch.12 | NHEFSデータで実演 |
| l | 診断検定: 重みの分布確認への言及があるか | 極端な重みの有無を検査 | Hernán & Robins Ch.12 | positivity violation時の極端な重み→「parametric models to smooth over the zeroes」 |
| m | strengthが≠ strongか | weak〜moderate（条件付き交換可能性は検証不可能、未観測交絡を排除不可能） | Ch.3原文 | "we are generally unable to determine whether exchangeability holds in our study" |
| n | strengthの根拠が識別仮定の状態と連動しているか | 根拠が交換可能性の検証不可能性やpositivity違反の可能性と結びついているか | — | — |

---

## 4. nsw（マッチング）

| # | 評価項目 | Gold Standard | 引用元 | 引用原文 |
|---|---|---|---|---|
| a | 手法選択がマッチング（PSM/subclassification等）か | Propensity Score Matching / Subclassification | Cunningham §5.3.4 + §5.3.3 | §5.3.3: "The propensity score is similar in many respects to both nearest-neighbor covariate matching by Abadie and Imbens (2006) and subclassification." |
| b | 識別仮定: CIA（条件付き独立性仮定）を述べているか | 観測された共変量Xで条件付けた上で、処置割り当てがポテンシャルアウトカムと独立 | Cunningham §5.1 | 数式: (Y¹, Y⁰) ⊥ D \| X / "What this means is that the expected values of Y¹ and Y⁰ are equal for treatment and control group *for each value of X*." |
| c | CIAとbackdoor criterionの関係を認識しているか | CIAが成立すればbackdoor criterionが満たされる | Cunningham §5.1 | "insofar as CIA is credible, then CIA means you have found a conditioning strategy that satisfies the backdoor criterion. Second, when treatment assignment had been conditional on observable variables, it is a situation of *selection on observables*." |
| d | 識別仮定: Common Support / Overlapを述べているか | 処置群と対照群の傾向スコア分布に十分な重なりがあること | Cunningham §5.3.4 | "This process of checking whether there are units in both treatment and control for intervals of the propensity score is called checking for common support." |
| e | CIAが崩れた場合の帰結を述べているか | 深刻な選択バイアスが残存する | Cunningham §5.3.4 | "Without controls, both PSID and CPS estimates are extremely negative and precise. This, again, is because the selection bias is so severe with respect to the NSW program." |
| f | Common Supportが崩れた場合の帰結を述べているか | 比較可能な対照単位がなく、推定が信頼できなくなる | Cunningham §5.3.4 | "The overlap was so bad that they opted to drop 12,611 observations in the control group because their propensity scores were outside the treatment group range." / "We learn, for one, that the selection bias on observables is probably extreme if for no other reason than the fact that there are so few units in both treatment and control for given values of the propensity score." |
| g | バランスの概念を正しく理解しているか | 共変量のバランスが達成 = 2群が交換可能 | Cunningham §5.1 | "This connection between the independence assumption and the characteristics of the groups is called *balance*. If the means of the covariates are the same for each group, then we say those covariates are balanced and the two groups are exchangeable with respect to those covariates." |
| h | LaLonde (1986)の教訓への言及があるか | 観察研究の推定値はRCT結果と大きく乖離しうる | Cunningham §5.3.4 | 実験推定値: $1,672〜$1,794の賃金増加。観察データ（CPS/PSID）: "extremely negative and precise" |
| i | PSMの限界への言及があるか | PSMは当初の期待ほど万能ではない | Cunningham §5.3.3 | "Despite some early excitement caused by Dehejia and Wahba (2002), subsequent enthusiasm was more tempered (Smith and Todd 2001, 2005; King and Nielsen 2019). As such, propensity score matching has not seen as wide adoption among economists as in other nonexperimental methods like regression discontinuity" |
| j | 診断検定: 共変量バランス確認への言及があるか | マッチング前後での共変量バランスの改善を確認 | Cunningham §5.1 | バランス概念の定義（上記g） |
| k | 診断検定: Common Support確認への言及があるか | 傾向スコアの分布の重なりをヒストグラム等で確認 | Cunningham §5.3.4 | "One easy way to check for common support is to plot the number of treatment and control group observations separately across the propensity score with a histogram." |
| l | RCTデータとの比較可能性への言及があるか | NSWデータはRCTの結果を持ち、実験結果と観察研究を比較できる | Cunningham §5.3.4 + LaLonde (1986) | Dehejia & Wahba (1999): "Following LaLonde (1986), we pair the experimental treated units with nonexperimental comparison units from the CPS and PSID, and compare the estimates of the treatment effect obtained using our methods to the benchmark results from the experiment." |
| m | strengthが分析アプローチに依存することを認識しているか | RCTデータ→strong。観察データでマッチング→≠ strong | Cunningham §5.3.4 | LaLondeの教訓: 観察研究の推定が実験結果と大きく乖離しうることがNSWデータで実証 |
| n | strengthの根拠が識別仮定の状態と連動しているか | 根拠がCIA/Common Supportの状態と結びついているか | — | — |
