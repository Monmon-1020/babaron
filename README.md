# babaron

観察的因果推論における科学的主張形成の監督プロトコル（3層構造）の実装。

LLM を用いて因果推論研究の主張形成過程を、監査可能で再検査可能な形で記述する。Designer（仮説生成・実験計画・結論導出）と Supervisor（品質チェック・リトライ指示）の 2 エージェント構成に加え、決定論的な機械的整合性チェックとルーブリック評価を統合した。

## 3層プロトコル

```
Layer 1: Process-level Protocol
  S0 (推定対象・スコープの固定)
    ↓
  S1 (競合仮説の構造化) ⇄ S1-CHK (Supervisor)
    ↓
  S2 (実験計画・判定規則の事前固定) ⇄ S2-CHK (Supervisor)
    ↓
  S2-EVID (エビデンス投入)
    ↓
  S3 (結論の導出・段階づけ) ⇄ S3-CHK (Supervisor)

Layer 2: Operationalized Rubric
  各段階の出力を Explicit / Partial / Absent で評価

Layer 3: Audit Implementation
  機械的チェック（整合性検証） + Supervisor（内容監査）
```

## 各ステージの構成要素

| Stage | 構成要素 |
|-------|--------|
| S0 | 推定対象（estimand）、主要/副次アウトカム、主張の境界条件 |
| S1 | 競合仮説（≥2）、反証条件（falsify）、弁別予測（distinctive prediction）|
| S2 | 識別仮定（identification assumptions）、判定規則（accept/reject/hold）、分析分岐 |
| S3 | エビデンス突合、反証条件発火確認、結論強度（strong/weak/hold）、残存代替説明 |

## フォルダ構成

```
babaron/
├── run.py              # メインランナー（CLI）
├── llm_client.py       # OpenAI API クライアント（モック対応）
├── schemas.py          # JSONパース・スキーマバリデーション
├── rubric.py           # Layer 2 ルーブリック評価
├── prompt_store.py     # プロンプトテンプレートローダー
├── cases.json          # 評価対象ケース定義
├── prompts/            # プロンプトテンプレート
│   ├── designer_s1~s3.txt      # Proposed用 Designer
│   ├── supervisor_s1~s3.txt    # Supervisor
│   └── baseline_designer_s1~s3.txt  # Baseline用
├── data/               # 参照テキスト
├── outputs/            # 実行ログ（JSONL）
└── results/            # 分析結果
```

## 評価対象ケース

| ケースID | 論文 | テーマ |
|---------|------|-------|
| `web_browsing_mood` | Kelly & Sharot (2025) Nature Human Behaviour | ウェブ閲覧パターンと気分・メンタルヘルスの双方向因果関係 |

## 使い方

### 前提

- Python 3.10+
- OpenAI API キー（`.env` に `OPENAI_API_KEY` を設定）

### 実行

```bash
# Proposed方式（Designer + Supervisor ループ）
python run.py --mock --rubric

# Baseline方式（Designer のみ）
python run.py --mock --method baseline --rubric

# 実APIで実行
python run.py --model gpt-4o --rubric

# ケース・出力先を指定
python run.py --case web_browsing_mood --out outputs/my_run.jsonl
```

### CLI オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--case` | `all` | ケースID or `all` |
| `--method` | `proposed` | `proposed` / `baseline` |
| `--model` | `gpt-4o-mini` | OpenAI モデル |
| `--max_retry` | `2` | Supervisor NG 時の最大リトライ回数 |
| `--mock` | `false` | モックモード |
| `--rubric` | `false` | Layer 2 ルーブリック評価を実行 |
| `--out` | `outputs/run_<timestamp>.jsonl` | 出力ファイルパス |
