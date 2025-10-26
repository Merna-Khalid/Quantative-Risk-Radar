import pandas as pd
import numpy as np
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

def compute_realized_volatility(returns: pd.Series, window: int = 22):
    return (returns ** 2).rolling(window).sum()

def fit_har_rv(returns: pd.Series):
    """
    Fit HAR-RV model using past daily, weekly, and monthly realized volatilities.
    """
    rv = compute_realized_volatility(returns, window=1)
    data = pd.DataFrame({
        "RV": rv,
        "RV_d": rv.shift(1),
        "RV_w": rv.rolling(5).mean().shift(1),
        "RV_m": rv.rolling(22).mean().shift(1),
    }).dropna()

    X = add_constant(data[["RV_d", "RV_w", "RV_m"]])
    y = data["RV"]
    model = OLS(y, X).fit()

    data["RV_pred"] = model.predict(X)
    return {
        "coefficients": model.params.to_dict(),
        "fitted": data["RV_pred"],
        "residuals": model.resid,
        "r2": model.rsquared
    }
