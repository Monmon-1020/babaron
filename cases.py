"""
Data loader for 4 causal inference cases.
Each case provides research_question, data_description, variable_list,
summary_statistics (auto-computed), and sample_rows (first 5 rows).
"""

import pandas as pd
from causaldata import castle, close_elections_lmb, nhefs, nsw_mixtape


CASES = {
    "castle": {
        "case_id": "castle",
        "research_question": (
            "Castle Doctrine法（Stand Your Ground法）の導入は、暴力犯罪（特に殺人）を"
            "増加させたか。Castle Doctrine法は、自宅以外の場所でも脅威を感じた場合に"
            "退避義務なく自衛のための武力行使を認める法律であり、"
            "米国の複数の州で異なるタイミングで導入された。"
        ),
        "data_description": (
            "米国の州レベルのパネルデータ（2000-2010年）。各行は「州×年」の観測値。"
            "犯罪率（殺人、強盗、暴行等）、法律の導入タイミング、"
            "経済指標（失業率、貧困率等）、人口統計学的変数を含む。\n"
            "出典: Cheng & Hoekstra (2013) \"Does Strengthening Self-Defense Law "
            "Deter Crime or Escalate Violence?\" のデータ。"
            "Cunningham \"Causal Inference: The Mixtape\" の教科書データセット。"
        ),
        "loader": castle,
        "label": "Cheng & Hoekstra (2013)",
        "key_variables": [
            "year: 年（2000-2010）",
            "sid: 州ID",
            "l_homicide: 対数殺人率",
            "l_larceny: 対数窃盗率",
            "l_motor: 対数自動車窃盗率",
            "post: Castle Doctrine法導入後=1（州ごとに異なる年に導入）",
            "lead1〜lead9: 導入の1〜9年前ダミー",
            "lag0〜lag5: 導入の0〜5年後ダミー",
            "unemployrt: 失業率",
            "poverty: 貧困率",
            "blackm_15_24: 黒人男性15-24歳の人口比率",
            "whitem_15_24: 白人男性15-24歳の人口比率",
            "l_police: 対数警察官数",
            "l_income: 対数所得",
            "l_prisoner: 対数囚人数",
            "popwt: 人口ウェイト",
        ],
        "display_columns": [
            "year", "sid", "l_homicide", "post", "unemployrt", "poverty",
            "blackm_15_24", "whitem_15_24", "l_police", "l_income", "l_prisoner",
            "lead1", "lead2", "lead3", "lag0", "lag1", "lag2", "popwt",
        ],
        "default_tool": "did",
        "default_params": {
            "treatment": "post",
            "outcome": "l_homicide",
            "group": "sid",
            "time": "year",
            "covariates": [
                "l_police", "l_income", "l_prisoner",
                "unemployrt", "poverty", "blackm_15_24", "whitem_15_24",
            ],
        },
    },
    "close_elections": {
        "case_id": "close_elections",
        "research_question": (
            "僅差の選挙で勝利した候補者は、次の選挙でも有利になるか。"
            "選挙での勝利は現職効果を通じて得票率を上昇させるか。"
        ),
        "data_description": (
            "米国下院選挙の候補者レベルデータ。各行は候補者×選挙年の観測値。"
            "得票率、政党、ADAスコア（政策的立場の指標）を含む。"
            "Lee, Moretti, Butler (2004) のSharp RDDの例。"
            "Running variableはdemvoteshare（民主党得票率）、カットオフは0.5。"
        ),
        "loader": close_elections_lmb,
        "label": "Lee, Moretti, Butler (2004)",
        "key_variables": [
            "state: 州コード",
            "district: 選挙区",
            "id: 候補者ID",
            "score: ADAスコア（政策的立場の指標、0-100）",
            "year: 選挙年",
            "demvoteshare: 民主党得票率（running variable）",
            "democrat: 民主党勝利=1（処置変数、カットオフ=0.5）",
            "lagdemocrat: 前回選挙での民主党勝利=1",
            "lagdemvoteshare: 前回選挙の民主党得票率（結果変数）",
        ],
        "display_columns": None,  # show all
        "default_tool": "rdd",
        "default_params": {
            "outcome": "lagdemvoteshare",
            "running_var": "demvoteshare",
            "cutoff": 0.5,
        },
    },
    "nhefs": {
        "case_id": "nhefs",
        "research_question": (
            "喫煙をやめることは体重増加を引き起こすか。"
            "禁煙の体重への因果効果はどの程度か。"
        ),
        "data_description": (
            "NHEFS（National Health and Nutrition Examination Survey Epidemiologic "
            "Follow-up Study）のデータ。1971年に25-74歳だった喫煙者のコホートを追跡。"
            "1982年時点での禁煙状況と体重変化を記録。"
            "Hernán & Robins \"Causal Inference: What If\" の教科書データセット。"
        ),
        "loader": nhefs,
        "label": "Hernán & Robins (NHEFS)",
        "key_variables": [
            "qsmk: 禁煙=1（処置変数）",
            "wt82_71: 1982年と1971年の体重差（kg、結果変数）",
            "sex: 性別（0=男性、1=女性）",
            "age: 年齢（1971年時点）",
            "race: 人種（0=白人、1=黒人/その他）",
            "education: 教育水準（1-5）",
            "smokeintensity: 1日の喫煙本数（1971年時点）",
            "smokeyrs: 喫煙年数",
            "exercise: 運動習慣（0=多い、1=中程度、2=少ない）",
            "active: 日常の活動レベル（0=非常に活発、1=中程度、2=不活発）",
            "wt71: 体重（1971年、kg）",
        ],
        "display_columns": [
            "qsmk", "wt82_71", "sex", "age", "race", "education",
            "smokeintensity", "smokeyrs", "exercise", "active", "wt71",
        ],
        "default_tool": "ipw",
        "default_params": {
            "treatment": "qsmk",
            "outcome": "wt82_71",
            "covariates": [
                "sex", "age", "race", "education",
                "smokeintensity", "smokeyrs",
                "exercise", "active", "wt71",
            ],
        },
    },
    "nsw": {
        "case_id": "nsw",
        "research_question": (
            "職業訓練プログラム（NSW）への参加は、参加者の賃金を向上させたか。"
        ),
        "data_description": (
            "National Supported Work (NSW) 職業訓練プログラムのデータ。"
            "処置群はランダムにプログラムに割り当てられた参加者。"
            "対照群は非参加者。1978年の賃金が結果変数。"
            "LaLonde (1986)、Dehejia & Wahba (1999) の教科書的な例。"
            "Cunningham \"Causal Inference: The Mixtape\" の教科書データセット。"
        ),
        "loader": nsw_mixtape,
        "label": "LaLonde (1986) / Dehejia & Wahba (1999)",
        "key_variables": [
            "data_id: データソース",
            "treat: 処置群=1（職業訓練プログラム参加）",
            "age: 年齢",
            "educ: 教育年数",
            "black: 黒人=1",
            "hisp: ヒスパニック=1",
            "marr: 既婚=1",
            "nodegree: 高校卒業なし=1",
            "re74: 1974年の賃金（ドル）",
            "re75: 1975年の賃金（ドル）",
            "re78: 1978年の賃金（ドル、結果変数）",
        ],
        "display_columns": None,  # show all
        "default_tool": "matching",
        "default_params": {
            "treatment": "treat",
            "outcome": "re78",
            "covariates": [
                "age", "educ", "black", "hisp", "marr", "nodegree",
                "re74", "re75",
            ],
        },
    },
}


def load(case_id: str) -> dict:
    """
    Load a case and return a dict with:
    - data: pandas DataFrame
    - research_question: str
    - data_description: str
    - variable_list: str (formatted)
    - summary_statistics: str (formatted from df.describe())
    - sample_rows: str (formatted first 5 rows)
    - default_tool: str
    - default_params: dict
    - label: str
    """
    if case_id not in CASES:
        raise ValueError(
            f"Unknown case_id: {case_id}. Available: {list(CASES.keys())}"
        )

    case = CASES[case_id]
    df = case["loader"].load_pandas().data

    # Drop rows with missing outcome for nhefs
    if case_id == "nhefs":
        df = df.dropna(subset=["wt82_71"]).copy()

    # Select display columns
    display_cols = case.get("display_columns")
    if display_cols:
        available = [c for c in display_cols if c in df.columns]
    else:
        available = df.columns.tolist()

    # Variable list
    variable_list = "\n".join(f"- {v}" for v in case["key_variables"])

    # Summary statistics
    desc = df[available].describe().round(3)
    summary_statistics = (
        f"行数: {len(df)}, 列数: {len(df.columns)}\n\n"
        f"{desc.to_string()}"
    )

    # Sample rows
    sample_rows = df[available].head(5).to_string()

    return {
        "case_id": case_id,
        "data": df,
        "research_question": case["research_question"],
        "data_description": case["data_description"],
        "variable_list": variable_list,
        "summary_statistics": summary_statistics,
        "sample_rows": sample_rows,
        "default_tool": case["default_tool"],
        "default_params": case["default_params"],
        "label": case["label"],
    }


def list_cases() -> list[str]:
    """Return list of available case IDs."""
    return list(CASES.keys())


if __name__ == "__main__":
    for cid in list_cases():
        print(f"\n{'='*60}")
        print(f"Case: {cid}")
        print(f"{'='*60}")
        info = load(cid)
        print(f"Label: {info['label']}")
        print(f"Data shape: {info['data'].shape}")
        print(f"Research question: {info['research_question'][:80]}...")
        print(f"Default tool: {info['default_tool']}")
