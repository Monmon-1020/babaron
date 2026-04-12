"""
Statistical analysis tools for causal inference.
Each tool takes a DataFrame and parameters, runs the analysis,
and returns a dict with method, summary, estimates, and diagnostics.
"""

import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.iolib.summary2 import summary_col


def did_estimator(
    data: pd.DataFrame,
    treatment: str,
    outcome: str,
    group: str,
    time: str,
    covariates: list[str] | None = None,
) -> dict:
    """
    Two-Way Fixed Effects (TWFE) DiD estimator.
    Includes event study if lead/lag variables are present in data.
    """
    df = data.dropna(subset=[outcome, treatment]).copy()

    # --- Main TWFE regression ---
    # Create fixed effects dummies
    group_dummies = pd.get_dummies(df[group], prefix="fe_g", drop_first=True, dtype=float)
    time_dummies = pd.get_dummies(df[time], prefix="fe_t", drop_first=True, dtype=float)

    X_vars = [treatment]
    if covariates:
        available_covs = [c for c in covariates if c in df.columns]
        X_vars += available_covs

    X = pd.concat(
        [df[X_vars].reset_index(drop=True),
         group_dummies.reset_index(drop=True),
         time_dummies.reset_index(drop=True)],
        axis=1,
    )
    X = sm.add_constant(X)
    y = df[outcome].reset_index(drop=True)

    # Drop rows with any NaN
    mask = X.notna().all(axis=1) & y.notna()
    X, y = X[mask], y[mask]

    # Cluster standard errors at group level
    groups_for_cluster = df[group].reset_index(drop=True)[mask]

    model = sm.OLS(y, X).fit(
        cov_type="cluster", cov_kwds={"groups": groups_for_cluster}
    )

    treatment_coef = model.params.get(treatment, np.nan)
    treatment_se = model.bse.get(treatment, np.nan)
    treatment_pval = model.pvalues.get(treatment, np.nan)

    summary_lines = [
        "=== TWFE DiD 推定結果 ===",
        f"結果変数: {outcome}",
        f"処置変数: {treatment}",
        f"固定効果: {group}（グループ）, {time}（時間）",
        f"共変量: {covariates if covariates else 'なし'}",
        f"クラスター標準誤差: {group}レベル",
        f"",
        f"処置効果推定値: {treatment_coef:.6f}",
        f"標準誤差: {treatment_se:.6f}",
        f"p値: {treatment_pval:.6f}",
        f"95%信頼区間: [{model.conf_int().loc[treatment, 0]:.6f}, {model.conf_int().loc[treatment, 1]:.6f}]",
        f"",
        f"N = {int(model.nobs)}, R² = {model.rsquared:.4f}",
    ]

    estimates = {
        "treatment_effect": float(treatment_coef),
        "se": float(treatment_se),
        "p_value": float(treatment_pval),
        "ci_lower": float(model.conf_int().loc[treatment, 0]),
        "ci_upper": float(model.conf_int().loc[treatment, 1]),
        "n_obs": int(model.nobs),
        "r_squared": float(model.rsquared),
    }

    diagnostics = {}

    # --- Event study ---
    lead_cols = sorted(
        [c for c in df.columns if c.startswith("lead") and c[4:].isdigit()],
        key=lambda x: int(x[4:]),
    )
    lag_cols = sorted(
        [c for c in df.columns if c.startswith("lag") and c[3:].isdigit()],
        key=lambda x: int(x[3:]),
    )

    if lead_cols or lag_cols:
        event_vars = lead_cols + lag_cols
        available_event = [c for c in event_vars if c in df.columns]

        X_event_vars = available_event[:]
        if covariates:
            X_event_vars += [c for c in covariates if c in df.columns]

        X_ev = pd.concat(
            [df[X_event_vars].reset_index(drop=True),
             group_dummies.reset_index(drop=True),
             time_dummies.reset_index(drop=True)],
            axis=1,
        )
        X_ev = sm.add_constant(X_ev)

        mask_ev = X_ev.notna().all(axis=1) & y.notna()
        X_ev_clean = X_ev[mask_ev]
        y_ev_clean = df[outcome].reset_index(drop=True)[mask_ev]
        groups_ev = df[group].reset_index(drop=True)[mask_ev]

        model_ev = sm.OLS(y_ev_clean, X_ev_clean).fit(
            cov_type="cluster", cov_kwds={"groups": groups_ev}
        )

        summary_lines.append("")
        summary_lines.append("=== Event Study 推定結果 ===")
        summary_lines.append(f"{'変数':<10} {'係数':>10} {'SE':>10} {'p値':>10}")
        summary_lines.append("-" * 45)

        event_study_results = {}
        for var in available_event:
            if var in model_ev.params.index:
                coef = model_ev.params[var]
                se = model_ev.bse[var]
                pval = model_ev.pvalues[var]
                summary_lines.append(f"{var:<10} {coef:>10.4f} {se:>10.4f} {pval:>10.4f}")
                event_study_results[var] = {
                    "coef": float(coef), "se": float(se), "p_value": float(pval)
                }

        # Pre-treatment test: any lead significant at 5%?
        pre_treatment_sig = any(
            event_study_results.get(c, {}).get("p_value", 1.0) < 0.05
            for c in lead_cols if c in event_study_results
        )
        diagnostics["event_study"] = event_study_results
        diagnostics["pre_treatment_significant"] = pre_treatment_sig

        summary_lines.append("")
        if pre_treatment_sig:
            summary_lines.append(
                "警告: 処置前期間に統計的に有意な係数が存在します。"
                "平行トレンド仮定に疑義があります。"
            )
        else:
            summary_lines.append(
                "処置前期間の係数はいずれも統計的に有意ではありません。"
                "平行トレンド仮定と整合的です（ただし検証不可能な仮定です）。"
            )

    return {
        "method": "DiD (TWFE)",
        "summary": "\n".join(summary_lines),
        "estimates": estimates,
        "diagnostics": diagnostics,
    }


def iv_estimator(
    data: pd.DataFrame,
    endogenous: str,
    outcome: str,
    instruments: list[str],
    covariates: list[str] | None = None,
) -> dict:
    """
    2SLS IV estimator using linearmodels.
    Reports first-stage F statistic and Sargan test if overidentified.
    """
    from linearmodels.iv import IV2SLS

    df = data.dropna(subset=[outcome, endogenous] + instruments).copy()

    dep = df[outcome]
    endog = df[[endogenous]]
    instr = df[instruments]

    if covariates:
        available_covs = [c for c in covariates if c in df.columns]
        exog = sm.add_constant(df[available_covs])
    else:
        exog = sm.add_constant(pd.DataFrame(index=df.index))

    model = IV2SLS(dep, exog, endog, instr).fit(cov_type="robust")

    # First stage
    first_stage = sm.OLS(
        df[endogenous],
        sm.add_constant(pd.concat([df[instruments], exog.drop(columns="const", errors="ignore")], axis=1))
    ).fit()
    # Partial F-stat for instruments
    from statsmodels.stats.anova import anova_lm
    restricted = sm.OLS(
        df[endogenous],
        exog
    ).fit()
    f_stat_num = ((restricted.ssr - first_stage.ssr) / len(instruments))
    f_stat_den = first_stage.ssr / first_stage.df_resid
    first_stage_f = f_stat_num / f_stat_den if f_stat_den > 0 else np.nan

    summary_lines = [
        "=== 2SLS IV 推定結果 ===",
        f"結果変数: {outcome}",
        f"内生変数: {endogenous}",
        f"操作変数: {instruments}",
        f"共変量: {covariates if covariates else 'なし'}",
        f"",
        f"IV推定値: {model.params[endogenous]:.6f}",
        f"標準誤差: {model.std_errors[endogenous]:.6f}",
        f"p値: {model.pvalues[endogenous]:.6f}",
        f"",
        f"第1段階F統計量: {first_stage_f:.2f}",
        f"  （F > 10 なら弱操作変数の懸念は小さい）",
        f"N = {int(model.nobs)}",
    ]

    estimates = {
        "iv_estimate": float(model.params[endogenous]),
        "se": float(model.std_errors[endogenous]),
        "p_value": float(model.pvalues[endogenous]),
        "n_obs": int(model.nobs),
    }

    diagnostics = {
        "first_stage_f": float(first_stage_f),
        "weak_instrument": first_stage_f < 10,
    }

    # Sargan test if overidentified
    if len(instruments) > 1:
        try:
            sargan = model.sargan
            diagnostics["sargan_stat"] = float(sargan.stat)
            diagnostics["sargan_pvalue"] = float(sargan.pval)
            summary_lines.append(
                f"Sargan検定: 統計量={sargan.stat:.4f}, p値={sargan.pval:.4f}"
            )
            summary_lines.append(
                "  （p > 0.05 なら過剰識別制約は棄却されず、操作変数の外生性と整合的）"
            )
        except Exception:
            pass

    return {
        "method": "IV (2SLS)",
        "summary": "\n".join(summary_lines),
        "estimates": estimates,
        "diagnostics": diagnostics,
    }


def rdd_estimator(
    data: pd.DataFrame,
    outcome: str,
    running_var: str,
    cutoff: float,
    bandwidth: float | None = None,
) -> dict:
    """
    RDD estimator using rdrobust package.
    """
    from rdrobust import rdrobust

    df = data.dropna(subset=[outcome, running_var]).copy()
    y = df[outcome].values
    x = df[running_var].values

    kwargs = {"c": cutoff}
    if bandwidth is not None:
        kwargs["h"] = bandwidth

    try:
        result = rdrobust(y, x, **kwargs)
    except Exception as e:
        return {
            "method": "RDD",
            "summary": f"RDD推定でエラーが発生: {e}",
            "estimates": {},
            "diagnostics": {},
        }

    # Extract results - rdrobust returns DataFrames
    # Use "Robust" row (index 2) for bias-corrected robust inference
    coef = float(result.coef.iloc[2, 0])
    se_val = float(result.se.iloc[2, 0])
    pval = float(result.pv.iloc[2, 0])
    ci_l = float(result.ci.iloc[2, 0])
    ci_u = float(result.ci.iloc[2, 1])
    bw = float(result.bws.iloc[0, 0])  # h (main bandwidth)

    # Also extract conventional estimates for comparison
    coef_conv = float(result.coef.iloc[0, 0])
    se_conv = float(result.se.iloc[0, 0])
    pval_conv = float(result.pv.iloc[0, 0])

    n_left = int(np.sum(x < cutoff))
    n_right = int(np.sum(x >= cutoff))

    summary_lines = [
        "=== RDD 推定結果 ===",
        f"結果変数: {outcome}",
        f"Running variable: {running_var}",
        f"カットオフ: {cutoff}",
        f"",
        f"--- ロバスト推定（バイアス補正済み） ---",
        f"LATE推定値: {coef:.6f}",
        f"ロバスト標準誤差: {se_val:.6f}",
        f"p値: {pval:.6f}",
        f"95%ロバスト信頼区間: [{ci_l:.6f}, {ci_u:.6f}]",
        f"",
        f"--- 従来推定 ---",
        f"LATE推定値（従来）: {coef_conv:.6f}",
        f"標準誤差（従来）: {se_conv:.6f}",
        f"p値（従来）: {pval_conv:.6f}",
        f"",
        f"選択バンド幅: {bw:.4f}",
        f"カットオフ左側N: {n_left}, 右側N: {n_right}",
    ]

    estimates = {
        "late": float(coef),
        "se": float(se_val),
        "p_value": float(pval),
        "ci_lower": float(ci_l),
        "ci_upper": float(ci_u),
        "bandwidth": float(bw),
    }

    diagnostics = {
        "n_left": n_left,
        "n_right": n_right,
    }

    # McCrary-like density check (simple binning approach)
    try:
        eps = bw
        n_near_left = int(np.sum((x >= cutoff - eps) & (x < cutoff)))
        n_near_right = int(np.sum((x >= cutoff) & (x < cutoff + eps)))
        ratio = n_near_right / n_near_left if n_near_left > 0 else np.nan
        diagnostics["density_left_of_cutoff"] = n_near_left
        diagnostics["density_right_of_cutoff"] = n_near_right
        diagnostics["density_ratio"] = float(ratio)
        summary_lines.append(f"")
        summary_lines.append(f"=== 密度検定（簡易） ===")
        summary_lines.append(
            f"カットオフ付近（±{eps:.4f}）: 左側 {n_near_left}, 右側 {n_near_right}, "
            f"比率 {ratio:.3f}"
        )
        if 0.8 <= ratio <= 1.2:
            summary_lines.append("密度に大きな不連続は見られません。操作の証拠なし。")
        else:
            summary_lines.append(
                "警告: 密度に不連続がある可能性があります。操作の懸念を検討してください。"
            )
    except Exception:
        pass

    return {
        "method": "RDD",
        "summary": "\n".join(summary_lines),
        "estimates": estimates,
        "diagnostics": diagnostics,
    }


def matching_estimator(
    data: pd.DataFrame,
    treatment: str,
    outcome: str,
    covariates: list[str],
) -> dict:
    """
    Propensity score matching using logistic regression + nearest neighbor.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    df = data.dropna(subset=[outcome, treatment] + covariates).copy()

    # Ensure numeric types (handle categorical columns)
    for col in covariates + [treatment, outcome]:
        if df[col].dtype.name == "category":
            df[col] = df[col].astype(float)
        elif not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[outcome, treatment] + covariates)

    X = df[covariates].values
    T = df[treatment].values.astype(int)
    Y = df[outcome].values

    # Fit propensity score model
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    ps_model = LogisticRegression(max_iter=10000, random_state=42)
    ps_model.fit(X_scaled, T)
    ps = ps_model.predict_proba(X_scaled)[:, 1]

    # Check common support
    ps_treated = ps[T == 1]
    ps_control = ps[T == 0]
    common_min = max(ps_treated.min(), ps_control.min())
    common_max = min(ps_treated.max(), ps_control.max())

    # Nearest neighbor matching (1:1 without replacement)
    treated_idx = np.where(T == 1)[0]
    control_idx = np.where(T == 0)[0]

    nn = NearestNeighbors(n_neighbors=1, metric="euclidean")
    nn.fit(ps[control_idx].reshape(-1, 1))
    distances, indices = nn.kneighbors(ps[treated_idx].reshape(-1, 1))

    matched_control_idx = control_idx[indices.flatten()]

    # ATT estimate
    y_treated = Y[treated_idx]
    y_matched_control = Y[matched_control_idx]
    att = np.mean(y_treated - y_matched_control)
    att_se = np.std(y_treated - y_matched_control) / np.sqrt(len(treated_idx))

    # Covariate balance before/after matching
    balance_before = {}
    balance_after = {}
    for i, cov in enumerate(covariates):
        mean_t = X[treated_idx, i].mean()
        mean_c_before = X[control_idx, i].mean()
        mean_c_after = X[matched_control_idx, i].mean()
        std_pooled = np.sqrt(
            (X[treated_idx, i].var() + X[control_idx, i].var()) / 2
        )
        if std_pooled > 0:
            smd_before = (mean_t - mean_c_before) / std_pooled
            smd_after = (mean_t - mean_c_after) / std_pooled
        else:
            smd_before = smd_after = 0.0
        balance_before[cov] = float(smd_before)
        balance_after[cov] = float(smd_after)

    summary_lines = [
        "=== 傾向スコアマッチング推定結果 ===",
        f"結果変数: {outcome}",
        f"処置変数: {treatment}",
        f"共変量: {covariates}",
        f"",
        f"ATT推定値: {att:.4f}",
        f"標準誤差: {att_se:.4f}",
        f"",
        f"処置群N: {len(treated_idx)}, 対照群N: {len(control_idx)}",
        f"マッチング: 1対1最近傍（傾向スコア距離）",
        f"",
        f"=== 傾向スコアの分布 ===",
        f"処置群: mean={ps_treated.mean():.4f}, min={ps_treated.min():.4f}, max={ps_treated.max():.4f}",
        f"対照群: mean={ps_control.mean():.4f}, min={ps_control.min():.4f}, max={ps_control.max():.4f}",
        f"Common support: [{common_min:.4f}, {common_max:.4f}]",
        f"",
        f"=== 共変量バランス（標準化平均差） ===",
        f"{'共変量':<20} {'マッチング前':>12} {'マッチング後':>12}",
        f"{'-'*48}",
    ]

    for cov in covariates:
        summary_lines.append(
            f"{cov:<20} {balance_before[cov]:>12.4f} {balance_after[cov]:>12.4f}"
        )

    max_smd_after = max(abs(v) for v in balance_after.values()) if balance_after else 0
    summary_lines.append(f"")
    if max_smd_after < 0.1:
        summary_lines.append("マッチング後の共変量バランスは良好です（全SMD < 0.1）。")
    elif max_smd_after < 0.25:
        summary_lines.append("マッチング後の共変量バランスは許容範囲です（一部SMD > 0.1）。")
    else:
        summary_lines.append(
            f"警告: マッチング後も共変量バランスに問題があります（最大SMD = {max_smd_after:.4f}）。"
        )

    return {
        "method": "Propensity Score Matching",
        "summary": "\n".join(summary_lines),
        "estimates": {
            "att": float(att),
            "se": float(att_se),
            "n_treated": int(len(treated_idx)),
            "n_control": int(len(control_idx)),
        },
        "diagnostics": {
            "ps_treated_mean": float(ps_treated.mean()),
            "ps_control_mean": float(ps_control.mean()),
            "common_support": [float(common_min), float(common_max)],
            "balance_before": balance_before,
            "balance_after": balance_after,
            "max_smd_after": float(max_smd_after),
            "mean_matching_distance": float(distances.mean()),
        },
    }


def ipw_estimator(
    data: pd.DataFrame,
    treatment: str,
    outcome: str,
    covariates: list[str],
) -> dict:
    """
    Inverse Probability Weighting estimator using statsmodels.
    Reports ATE with stabilized weights.
    """
    df = data.dropna(subset=[outcome, treatment] + covariates).copy()

    # Ensure numeric types (handle categorical columns)
    for col in covariates + [treatment, outcome]:
        if df[col].dtype.name == "category":
            df[col] = df[col].astype(float)
        elif not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[outcome, treatment] + covariates)

    X = df[covariates]
    T = df[treatment].values.astype(int)
    Y = df[outcome].values

    # Fit propensity score model
    X_with_const = sm.add_constant(X)
    ps_model = sm.Logit(T, X_with_const).fit(disp=False)
    ps = ps_model.predict(X_with_const)

    # Stabilized weights
    p_treat = T.mean()
    weights = np.where(
        T == 1,
        p_treat / ps,
        (1 - p_treat) / (1 - ps),
    )

    # Trim extreme weights
    w_p1 = np.percentile(weights, 1)
    w_p99 = np.percentile(weights, 99)
    weights_trimmed = np.clip(weights, w_p1, w_p99)

    # ATE via weighted means
    ate_treated = np.average(Y[T == 1], weights=weights_trimmed[T == 1])
    ate_control = np.average(Y[T == 0], weights=weights_trimmed[T == 0])
    ate = ate_treated - ate_control

    # Weighted OLS for SE
    wls_X = sm.add_constant(pd.DataFrame({"treatment": T}))
    wls_model = sm.WLS(Y, wls_X, weights=weights_trimmed).fit()
    ate_se = wls_model.bse["treatment"]
    ate_pval = wls_model.pvalues["treatment"]

    # Weight diagnostics
    summary_lines = [
        "=== IPW 推定結果 ===",
        f"結果変数: {outcome}",
        f"処置変数: {treatment}",
        f"共変量: {covariates}",
        f"",
        f"ATE推定値: {ate:.4f}",
        f"標準誤差: {ate_se:.4f}",
        f"p値: {ate_pval:.6f}",
        f"",
        f"処置群の加重平均: {ate_treated:.4f}",
        f"対照群の加重平均: {ate_control:.4f}",
        f"",
        f"N = {len(df)} (処置群: {T.sum()}, 対照群: {(1-T).sum()})",
        f"",
        f"=== 傾向スコア診断 ===",
        f"傾向スコア: mean={ps.mean():.4f}, min={ps.min():.4f}, max={ps.max():.4f}",
        f"",
        f"=== 重みの分布 ===",
        f"安定化重み（トリミング前）: mean={weights.mean():.4f}, min={weights.min():.4f}, "
        f"max={weights.max():.4f}",
        f"安定化重み（トリミング後、1-99パーセンタイル）: mean={weights_trimmed.mean():.4f}, "
        f"min={weights_trimmed.min():.4f}, max={weights_trimmed.max():.4f}",
    ]

    # Weighted covariate balance
    summary_lines.append("")
    summary_lines.append("=== IPW後の共変量バランス ===")
    summary_lines.append(f"{'共変量':<20} {'未調整差':>10} {'IPW調整後差':>12}")
    summary_lines.append(f"{'-'*46}")

    balance_raw = {}
    balance_ipw = {}
    for cov in covariates:
        vals = df[cov].values
        raw_diff = vals[T == 1].mean() - vals[T == 0].mean()
        ipw_diff = (
            np.average(vals[T == 1], weights=weights_trimmed[T == 1])
            - np.average(vals[T == 0], weights=weights_trimmed[T == 0])
        )
        balance_raw[cov] = float(raw_diff)
        balance_ipw[cov] = float(ipw_diff)
        summary_lines.append(f"{cov:<20} {raw_diff:>10.4f} {ipw_diff:>12.4f}")

    extreme_weights = np.sum((weights > 10) | (weights < 0.1))
    if extreme_weights > 0:
        summary_lines.append(
            f"\n警告: 極端な重み（>10 or <0.1）が {extreme_weights} 個あります。"
            "Positivity違反の可能性があります。"
        )

    return {
        "method": "IPW",
        "summary": "\n".join(summary_lines),
        "estimates": {
            "ate": float(ate),
            "se": float(ate_se),
            "p_value": float(ate_pval),
            "n_obs": int(len(df)),
        },
        "diagnostics": {
            "ps_min": float(ps.min()),
            "ps_max": float(ps.max()),
            "ps_mean": float(ps.mean()),
            "weight_mean": float(weights.mean()),
            "weight_max": float(weights.max()),
            "extreme_weights_count": int(extreme_weights),
            "balance_raw": balance_raw,
            "balance_ipw": balance_ipw,
        },
    }


def ols_estimator(
    data: pd.DataFrame,
    outcome: str,
    regressors: list[str],
) -> dict:
    """
    Simple OLS regression using statsmodels.
    """
    df = data.dropna(subset=[outcome] + regressors).copy()

    X = sm.add_constant(df[regressors])
    y = df[outcome]

    model = sm.OLS(y, X).fit(cov_type="HC1")

    summary_lines = [
        "=== OLS 推定結果 ===",
        f"結果変数: {outcome}",
        f"説明変数: {regressors}",
        f"標準誤差: ロバスト（HC1）",
        f"",
    ]

    for var in regressors:
        summary_lines.append(
            f"{var}: 係数={model.params[var]:.6f}, "
            f"SE={model.bse[var]:.6f}, "
            f"p={model.pvalues[var]:.6f}"
        )

    summary_lines.extend([
        f"",
        f"N = {int(model.nobs)}, R² = {model.rsquared:.4f}, "
        f"Adj R² = {model.rsquared_adj:.4f}",
    ])

    estimates = {
        "coefficients": {v: float(model.params[v]) for v in regressors},
        "se": {v: float(model.bse[v]) for v in regressors},
        "p_values": {v: float(model.pvalues[v]) for v in regressors},
        "r_squared": float(model.rsquared),
        "n_obs": int(model.nobs),
    }

    return {
        "method": "OLS",
        "summary": "\n".join(summary_lines),
        "estimates": estimates,
        "diagnostics": {},
    }


# Tool registry for easy lookup
TOOLS = {
    "did": did_estimator,
    "iv": iv_estimator,
    "rdd": rdd_estimator,
    "matching": matching_estimator,
    "ipw": ipw_estimator,
    "ols": ols_estimator,
}

# Mapping from Japanese/English method names in LLM output to tool keys
METHOD_ALIASES = {
    "did": "did",
    "diff-in-diff": "did",
    "差の差法": "did",
    "差の差": "did",
    "twfe": "did",
    "two-way fixed effects": "did",
    "iv": "iv",
    "2sls": "iv",
    "操作変数法": "iv",
    "操作変数": "iv",
    "rdd": "rdd",
    "回帰不連続デザイン": "rdd",
    "回帰不連続": "rdd",
    "regression discontinuity": "rdd",
    "sharp rdd": "rdd",
    "fuzzy rdd": "rdd",
    "matching": "matching",
    "マッチング": "matching",
    "傾向スコアマッチング": "matching",
    "propensity score matching": "matching",
    "psm": "matching",
    "ipw": "ipw",
    "逆確率重み付け": "ipw",
    "inverse probability weighting": "ipw",
    "ols": "ols",
    "線形回帰": "ols",
    "回帰分析": "ols",
}


def resolve_method(method_text: str) -> str | None:
    """
    Resolve a method name from LLM output to a tool key.
    Returns None if not found.
    """
    text = method_text.strip().lower()
    for alias, key in METHOD_ALIASES.items():
        if alias in text:
            return key
    return None
