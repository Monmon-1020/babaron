"""
Prompt templates for baseline and proposed conditions.
Based on prompt_design.md sections 1-4.
"""

# --- Common input template (Section 1) ---
COMMON_INPUT = """\
あなたは研究分析アシスタントです。
以下の研究課題とデータに基づいて因果分析を行ってください。

## 研究課題
{research_question}

## データの説明
{data_description}

## 変数リスト
{variable_list}

## 要約統計量
{summary_statistics}

## データのサンプル（先頭5行）
{sample_rows}

## 利用可能な分析ツール
以下のツールを使用できます。ツールを指定すると自動的に分析が実行され結果が返されます。

- DiD (差の差法): 処置変数・結果変数・グループ変数・時間変数を指定
- IV (操作変数法): 処置変数・結果変数・操作変数を指定
- RDD (回帰不連続デザイン): 結果変数・running variable・カットオフを指定
- マッチング (傾向スコアマッチング): 処置変数・結果変数・共変量リストを指定
- IPW (逆確率重み付け): 処置変数・結果変数・共変量リストを指定
- OLS (線形回帰): 結果変数・説明変数リストを指定

各ツールは推定値・標準誤差・p値に加え、手法固有の診断検定結果も自動出力します。

以下のフォーマットに従って回答してください。
"""

# --- Common output format (Section 2) ---
COMMON_OUTPUT_FORMAT = """\
## S0: 推定対象
- 処置変数:
- 結果変数:
- 比較対象:
- 対象集団:
- 時間枠:
- 推定対象の種類（ATE/ATT/LATE等）:

## S1: 分析上の脅威
この推定を狂わせうる要因を列挙してください。
- 脅威1:
- 脅威2:
- 脅威3:
（必要に応じて追加）

## S2a: 手法選択と識別仮定
- 選択した手法:
- 手法選択の根拠:
- 識別仮定1:
  - 内容:
  - この仮定が対処する脅威（S1のどれか）:
  - この仮定が崩れた場合の帰結:
- 識別仮定2:
  - 内容:
  - この仮定が対処する脅威:
  - この仮定が崩れた場合の帰結:
（必要に応じて追加）
- 判定基準: どのような結果が出たら因果効果あり/なし/判断保留と判定するか

## S2b: モデリング選択
分析にあたって行った選択とその根拠を記述してください。
- 選択1:
  - 何を選んだか:
  - なぜそれを選んだか:
  - 考慮した代替選択肢:
  - 代替を選んだ場合の予想される影響:
- 選択2:
  - 何を選んだか:
  - なぜそれを選んだか:
  - 考慮した代替選択肢:
  - 代替を選んだ場合の予想される影響:
（必要に応じて追加）

## S2-EVID: 分析結果
[ここにツール実行結果が自動挿入される]

## S3: 結論
- 推定結果の要約:
- 識別仮定の状態:
  - 識別仮定1: satisfied / uncertain / violated — 根拠:
  - 識別仮定2: satisfied / uncertain / violated — 根拠:
  （必要に応じて追加）
- モデリング選択の感度:
  - 選択1: 結論への影響が 大きい / 中程度 / 小さい — 根拠:
  （必要に応じて追加）
- 結論の強さ: strong / moderate / weak / hold
- 強さの根拠:
- 残存する懸念:
"""

# --- Baseline instructions (Section 3) ---
BASELINE_INSTRUCTIONS = """\
## 分析の指示

上記のフォーマットの各セクションを埋めてください。

S0では、このデータと研究課題から何を推定すべきかを定義してください。

S1では、この分析で考慮すべき懸念点を挙げてください。

S2aでは、適切な分析手法を選び、その手法を使う上での仮定と、
仮定が成り立たない場合の影響を記述してください。

S2bでは、分析にあたって行った選択と、
別の選択をした場合にどうなるかを記述してください。

S3では、分析結果を踏まえた結論と、その結論の信頼性を評価してください。
"""

# --- Proposed instructions (Section 4) ---
PROPOSED_INSTRUCTIONS = """\
## 分析の指示

上記のフォーマットの各セクションを埋めてください。
以下のガイダンスに従ってください。

### S0について
推定対象を明確に定義してください。特に以下を区別してください:
- ATE（平均処置効果）: 全集団への平均的な因果効果
- ATT（処置群の処置効果）: 実際に処置を受けた集団への効果
- LATE（局所平均処置効果）: 特定のサブグループへの効果
どれを推定するかによって手法の選択と結果の解釈が変わります。

### S1について
以下の観点から、この推定を狂わせうる脅威を体系的に検討してください:
- 逆因果: 結果が処置を引き起こしている可能性はないか
- 交絡: 処置と結果の両方に影響する第三要因はないか
- Spillover: 処置を受けた単位が受けていない単位に影響する可能性はないか
- 測定誤差: 処置や結果の測定に系統的な誤りはないか
- 選択バイアス: 処置を受ける/受けないの選択が結果と関連していないか

### S2aについて
識別仮定とは、推定値を因果効果として解釈するために成り立つ必要がある
条件のことです。

まず、データ構造と研究課題に最も適した手法を選択してください。
以下に各手法の識別仮定・適用条件・OLSとの違いを示します。
OLSが常に最善とは限りません。データと脅威に応じて適切な手法を選んでください。

■ OLS（回帰調整）
  識別仮定: 条件付き交換可能性（無交絡）、関数形の正しさ
  適用条件: 共変量で交絡を十分に統制でき、結果モデルの関数形が正しい場合
  限界: 結果モデルの関数形に強く依存。処置群と対照群のプロファイルが
  大きく異なる場合、外挿に頼った推定になる

■ IPW（逆確率重み付け）
  識別仮定: 条件付き交換可能性、positivity（正値性）、consistency（整合性）
  適用条件: 処置割当が共変量で説明でき、結果モデルの関数形仮定を避けたい場合
  OLSとの違い: 結果モデルの関数形に依存しない。共変量バランスを明示的に達成
  限界: positivity違反時に極端な重みが発生。傾向スコアモデルの誤指定に脆弱

■ マッチング（傾向スコアマッチング）
  識別仮定: CIA（条件付き独立性）、common support（共通台）
  適用条件: 処置群と対照群のプロファイルが大きく異なる場合に特に有効。
  共変量空間で「似た」対照個体を見つけることで、比較の透明性が高い
  OLSとの違い: 関数形仮定が不要。比較対象を明示的に限定するため、
  外挿を避けられる
  限界: common support外の観測は使えない。次元の呪い

■ DiD（差の差法）
  識別仮定: 平行トレンド仮定、SUTVA（干渉なし）
  適用条件: 処置前後の複数時点データがあり、処置群と対照群の時間トレンドが
  共通と仮定できる場合
  限界: 平行トレンド仮定は検証不可能。同時政策変更に脆弱

■ IV（操作変数法）
  識別仮定: 関連性（relevance）、外生性（exogeneity）、排除制約（exclusion restriction）
  適用条件: 内生性が疑われ、処置に影響するが結果には直接影響しない操作変数がある場合
  限界: 排除制約は検証不可能。弱操作変数問題。LATEの局所性

■ RDD（回帰不連続デザイン）
  識別仮定: 連続性仮定、操作不可能性
  適用条件: 処置割当がrunning variableのカットオフで決まる場合
  限界: LATEの局所性（カットオフ付近のみ）。関数形選択への感度

手法を選んだ上で、その手法に固有の識別仮定を全て列挙してください。

各識別仮定について以下を記述してください:
- 仮定の内容: 何が成り立つ必要があるか
- 対処する脅威: S1で挙げたどの脅威にこの仮定が対処するか
- 崩壊時帰結: この仮定が崩れた場合、推定値にどのようなバイアスが
  生じるか（方向と大きさの見通しを含む）

判定基準はデータの分析結果を見る前に固定してください。
結果を見てから基準を変えてはいけません。

### S2bについて
因果推論の結論は、分析者が行ったモデリング選択に依存します。
以下の選択について、それぞれ記述してください:
- 関数形の選択（線形/多項式/ノンパラメトリック等）
- サンプルの制限（対象期間、除外基準、欠損処理）
- 共変量の選択（何を統制変数に含め、何を含めないか）
- 手法固有のパラメータ（バンド幅、カーネル、重みの仕様等）
- 標準誤差の処理（クラスタリングのレベル等）

各選択について、なぜその選択をしたか（正当化）と、
合理的な代替選択肢を挙げてください。代替を選んだ場合に
推定値がどう変わりうるかの見通しも記述してください。

### S3について
結論の強さ（strong/moderate/weak/hold）は以下のルールに従ってください:
- strong: 全ての識別仮定がsatisfied、かつモデリング選択の感度が小さい場合のみ
- moderate: 識別仮定に軽微なuncertainがある、またはモデリング選択への
  感度が中程度の場合
- weak: 識別仮定にuncertainが複数ある、またはモデリング選択で
  結論が大きく変わる場合
- hold: 識別仮定にviolatedがある、またはデータが不十分な場合

識別仮定にuncertainまたはviolatedがある場合、strongとしてはなりません。
モデリング選択を変えると結論が大きく変わる場合も、strongとしてはなりません。

強さの根拠として、具体的にどの識別仮定・どのモデリング選択に
どんな懸念があるかを記述してください。

残存する懸念には、まだ排除できていない脅威、検証が不十分な仮定、
結論に大きく影響するモデリング選択を記述してください。
"""

# --- Continuation prompt (sent with tool results for S3) ---
CONTINUATION_PROMPT = """\
以下がツール実行結果です。この結果を S2-EVID セクションに記入し、
それを踏まえて S3（結論）セクションを完成させてください。

## S2-EVID: 分析結果
{tool_results}

上記の分析結果を踏まえて、S3セクションを記述してください。
S0〜S2bで述べた識別仮定・モデリング選択・判定基準を参照しながら、
結論とその強さを評価してください。
"""


def format_prompt(case_data: dict, condition: str) -> str:
    """
    Format the full initial prompt.

    Args:
        case_data: dict from cases.load() with research_question,
                   data_description, variable_list, summary_statistics,
                   sample_rows
        condition: "baseline" or "proposed"

    Returns:
        Full prompt string (for the first LLM call, S0-S2b)
    """
    if condition not in ("baseline", "proposed"):
        raise ValueError(f"Unknown condition: {condition}. Use 'baseline' or 'proposed'.")

    # Fill common input
    common = COMMON_INPUT.format(
        research_question=case_data["research_question"],
        data_description=case_data["data_description"],
        variable_list=case_data["variable_list"],
        summary_statistics=case_data["summary_statistics"],
        sample_rows=case_data["sample_rows"],
    )

    # Add output format
    output_fmt = COMMON_OUTPUT_FORMAT

    # Add condition-specific instructions
    if condition == "baseline":
        instructions = BASELINE_INSTRUCTIONS
    else:
        instructions = PROPOSED_INSTRUCTIONS

    return common + "\n" + output_fmt + "\n" + instructions


def format_continuation(tool_results: str) -> str:
    """
    Format the continuation prompt with tool results.

    Args:
        tool_results: formatted string of tool execution results

    Returns:
        Continuation prompt string
    """
    return CONTINUATION_PROMPT.format(tool_results=tool_results)
