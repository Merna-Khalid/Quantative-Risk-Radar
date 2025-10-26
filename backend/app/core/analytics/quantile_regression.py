import io
import base64
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt
from statsmodels.regression.quantile_regression import QuantReg
from app.core.db_utils import save_quantile_results


async def compute_quantile_regression(all_data_for_reg: pd.DataFrame, generate_plots: bool = False):
    """
    Compute quantile regressions of HYG returns on multiple macro/correlation factors.

    Parameters:
        all_data_for_reg: DataFrame with 'HYG' column and predictors.
        generate_plots: if True, returns base64-encoded plot images.

    Returns:
        {
            "results": {q: {"params": ..., "pvalues": ..., "r2": ...}},
            "summaries": {"VaR": ..., "CorrelationRisk": ...},
            "plots": [list of base64 PNG strings]  # if generate_plots=True
        }
    """

    if "HYG" not in all_data_for_reg.columns:
        raise ValueError("DataFrame must contain 'HYG' as target variable.")

    y = all_data_for_reg["HYG"]
    X = all_data_for_reg.drop(columns=["HYG"])

    # Interaction terms
    X["Corr_VIX_Interaction"] = X["HYG_SPY_Corr"] * X["VIX_Change"]
    X["Corr_Spread_Interaction"] = X["HYG_SPY_Corr"] * X["HY_Spread_Change"]
    X["Vol_Corr_Interaction"] = X["SPY_Vol"] * X["HYG_SPY_Corr"]
    X = sm.add_constant(X)

    quantiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    results = {}

    for q in quantiles:
        model = QuantReg(y, X)
        fit = model.fit(q=q)
        ssr = np.sum((y - fit.fittedvalues) ** 2)
        sst = np.sum((y - y.mean()) ** 2)
        r2 = 1 - (ssr / sst)

        results[q] = {
            "params": fit.params.to_dict(),
            "pvalues": fit.pvalues.to_dict(),
            "r2": float(r2),
            "fitted": fit.fittedvalues,
        }

    # Summaries for reporting
    var_95 = results[0.05]["fitted"].mean()
    var_50 = results[0.50]["fitted"].mean()

    summaries = {
        "VaR_95": float(var_95),
        "VaR_Normal": float(var_50),
        "Capital_Buffer": float(var_95 - var_50),
    }

    # Correlation-specific stats
    if "HYG_SPY_Corr" in X.columns:
        corr_beta = results[0.05]["params"].get("HYG_SPY_Corr", np.nan)
        corr_mean = X["HYG_SPY_Corr"].mean()
        corr_std = X["HYG_SPY_Corr"].std()
        summaries["Correlation_Risk"] = {
            "mean_corr": float(corr_mean),
            "vol_corr": float(corr_std),
            "corr_beta": float(corr_beta),
            "corr_contrib_to_loss": float(abs(corr_beta * corr_std))
        }

    output = {
        "results": results,
        "summaries": summaries,
    }

    await save_quantile_results(summaries, results)

    # Optional plotting (convert to base64 for frontend)
    if generate_plots:
        figs_base64 = []
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        # Plot 1: coefficients across quantiles
        coef_df = pd.DataFrame({q: pd.Series(results[q]["params"]) for q in quantiles}).T
        coef_df.plot(ax=axes[0, 0], title="Coefficient Dynamics Across Quantiles")
        axes[0, 0].grid(True, alpha=0.3)

        # Plot 2: pseudo R²
        r2s = [results[q]["r2"] for q in quantiles]
        axes[0, 1].plot(quantiles, r2s, marker="o")
        axes[0, 1].set_title("Pseudo R² Across Quantiles")
        axes[0, 1].grid(True, alpha=0.3)

        # Plot 3: fitted quantiles vs actual
        for q in [0.05, 0.5, 0.95]:
            axes[1, 0].scatter(y, results[q]["fitted"], s=8, alpha=0.3, label=f"{q*100:.0f}th")
        axes[1, 0].legend()
        axes[1, 0].set_title("Actual vs Fitted Quantile Predictions")
        axes[1, 0].grid(True, alpha=0.3)

        # Plot 4: tail amplification
        tail_ampl = pd.Series(results[0.05]["params"]) / pd.Series(results[0.50]["params"])
        tail_ampl.dropna().plot(kind="bar", ax=axes[1, 1], color="crimson", title="Tail Amplification (5th / 50th)")
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        figs_base64.append(base64.b64encode(buf.read()).decode("utf-8"))
        plt.close(fig)

        output["plots"] = figs_base64

    return output
