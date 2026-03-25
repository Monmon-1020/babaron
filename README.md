# babaron

LLM を用いた研究ワークフローの自動化フレームワーク。Designer（仮説生成・実験計画・結論導出）と Supervisor（品質チェック・リトライ指示）の 2 エージェント構成で、因果推論ケースの分析品質を検証する。

## 概要

3 段階のパイプライン（S1: 仮説生成 → S2: 実験計画 → S3: 結論導出）を、**Proposed 方式**（Designer + Supervisor ループ）と **Baseline 方式**（Designer のみ）で比較実行できる。各ステージで JSON スキーマのバリデーションと決定論的な整合性チェック（Mechanical Checks）を行い、不整合があればリトライループで自動修正を試みる。

## フォルダ構成

```
babaron/
├── run.py              # メインのワークフローランナー（CLI エントリポイント）
├── llm_client.py       # OpenAI API クライアント（モック対応）
├── schemas.py          # JSON パース・スキーマバリデーション・整合性チェック
├── prompt_store.py     # プロンプトテンプレートのローダー
├── cases.json          # 分析対象ケースの定義（S0 初期情報・S2-EVID エビデンス）
├── prompts/            # プロンプトテンプレート
│   ├── designer_s1.txt / s2.txt / s3.txt        # Proposed 用 Designer プロンプト
│   ├── supervisor_s1.txt / s2.txt / s3.txt      # Supervisor プロンプト
│   ├── baseline_designer_s1.txt / s2.txt / s3.txt  # Baseline 用 Designer プロンプト
│   └── evidence_server.txt                      # Evidence Server プロンプト
├── data/               # ケースごとのゴールドスタンダード・参照テキスト
│   ├── philly/         # フィラデルフィア飲料税
│   ├── chernobyl/      # チェルノブイリ低線量胎内曝露
│   └── weber/          # ウェーバー仮説（宗派と経済成果）
├── outputs/            # 実行ログ（JSONL 形式）
└── results/            # 分析結果・付録資料
```

## 分析ケース

| ケース ID | テーマ | 研究課題 |
|-----------|--------|----------|
| `philly` | フィラデルフィア飲料税 | 飲料税導入が課税飲料消費をどの程度減らすか |
| `chernobyl` | チェルノブイリ胎内曝露 | 低線量の胎内放射線曝露は学業成果を低下させるか |
| `weber` | ウェーバー仮説 | 宗派差と経済成果の関連は労働倫理か人的資本媒介か |

## 使い方

### 前提

- Python 3.10+
- OpenAI API キー（`.env` に `OPENAI_API_KEY` を設定）

### 実行

```bash
# 全ケースを Proposed 方式で実行（GPT-4o-mini）
python run.py

# ケース・手法・モデルを指定
python run.py --case philly --method proposed --model gpt-4o

# Baseline 方式で実行
python run.py --method baseline

# モックモードで動作確認
python run.py --mock

# リトライ回数・出力先を指定
python run.py --max_retry 3 --out outputs/my_run.jsonl
```

### CLI オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--case` | `all` | `philly` / `chernobyl` / `weber` / `all` |
| `--method` | `proposed` | `proposed`（Supervisor あり）/ `baseline`（Designer のみ） |
| `--model` | `gpt-4o-mini` | 使用する OpenAI モデル |
| `--max_retry` | `2` | Supervisor NG 時の最大リトライ回数 |
| `--mock` | `false` | API を呼ばずモックデータで実行 |
| `--out` | `outputs/run_<timestamp>.jsonl` | 出力ファイルパス |

## アーキテクチャ

```
S0 (Evidence: 初期情報)
  ↓
S1 (Designer: 仮説生成) ⇄ S1-CHK (Supervisor: チェック)
  ↓
S2 (Designer: 実験計画) ⇄ S2-CHK (Supervisor: チェック)
  ↓
S2-EVID (Evidence: 実験結果投入)
  ↓
S3 (Designer: 結論導出) ⇄ S3-CHK (Supervisor: チェック)
```

- **Designer**: 各ステージで JSON 構造化出力を生成（仮説・実験計画・結論）
- **Supervisor**: Designer 出力をレビューし、OK/NG 判定と修正指示を返す
- **Mechanical Checks**: Supervisor とは独立した決定論的な整合性検証（仮説 ID の一致、条件フラグの排他性、エビデンス参照の妥当性など）
- **Evidence Server**: ケースごとに事前定義されたエビデンスデータを提供
