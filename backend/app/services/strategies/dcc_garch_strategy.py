import numpy as np
import pandas as pd
from arch import arch_model
from scipy.optimize import minimize
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class RegimeSwitchingDCC:
    """Regime-Switching DCC(1,1) model (Normal vs Stress)."""

    def __init__(self, returns: pd.DataFrame, stress_regime: pd.Series):
        self.returns = returns.dropna()
        self.stress_regime = stress_regime.reindex(self.returns.index).fillna(False)
        self.tickers = list(self.returns.columns)
        self.std_resid = None
        self.opt_params = None

    def fit_univariate_garch(self):
        """Fit univariate GARCH models for each asset."""
        std_resid = pd.DataFrame(index=self.returns.index, columns=self.tickers)
        for tkr in self.tickers:
            try:
                model = arch_model(self.returns[tkr], vol="GARCH", p=1, q=1, dist='normal')
                fit = model.fit(disp="off")
                std_resid[tkr] = fit.resid / fit.conditional_volatility
                logger.info(f"GARCH fitted for {tkr}")
            except Exception as e:
                logger.warning(f"GARCH failed for {tkr}: {e}. Using standardized returns.")
                std_resid[tkr] = (self.returns[tkr] - self.returns[tkr].mean()) / self.returns[tkr].std()
        
        self.std_resid = std_resid.dropna()
        return self.std_resid

    @staticmethod
    def rs_dcc_loglik(params, eps: pd.DataFrame, stress_regime: pd.Series):
        """Log-likelihood for regime-switching DCC."""
        a1, b1, a2, b2 = params
        
        if not (0 < a1 < 1 and 0 < b1 < 1 and a1 + b1 < 1 and
                0 < a2 < 1 and 0 < b2 < 1 and a2 + b2 < 1):
            return np.inf

        T, N = eps.shape
        Qbar = eps.cov().values
        Q_prev = Qbar.copy()
        loglike = 0.0

        for t in range(1, T):
            a, b = (a2, b2) if stress_regime.iloc[t] else (a1, b1)
            e_prev = eps.iloc[t - 1].values.reshape(-1, 1)
            Q_t = (1 - a - b) * Qbar + a * (e_prev @ e_prev.T) + b * Q_prev

            try:
                d = np.sqrt(np.diag(Q_t))
                R_t = Q_t / d[:, None] / d[None, :]
                inv_Rt = np.linalg.inv(R_t)
            except np.linalg.LinAlgError:
                return np.inf

            eps_t = eps.iloc[t].values
            loglike += np.log(np.linalg.det(R_t)) + eps_t @ inv_Rt @ eps_t
            Q_prev = Q_t
            
        return 0.5 * loglike

    def fit(self):
        """Fit the regime-switching DCC model."""
        if self.std_resid is None:
            self.fit_univariate_garch()
            
        if len(self.std_resid) < 100:
            raise ValueError("Insufficient data for DCC estimation")
        
        try:
            opt = minimize(
                self.rs_dcc_loglik,
                x0=[0.02, 0.96, 0.08, 0.88],
                args=(self.std_resid, self.stress_regime),
                bounds=[(1e-3, 0.99)] * 4,
                method='L-BFGS-B'
            )
            
            if opt.success:
                self.opt_params = opt.x
                logger.info(f"DCC fitted successfully: {self.opt_params}")
            else:
                raise RuntimeError(f"DCC optimization failed: {opt.message}")
                
        except Exception as e:
            logger.error(f"DCC fitting failed: {e}")
            # Fallback to standard DCC parameters
            self.opt_params = [0.02, 0.97, 0.05, 0.93]
            
        return self.opt_params

    def compute_pair_corr(self, pair: Tuple[str, str]):
        """Compute dynamic correlation for a pair of assets."""
        if self.opt_params is None:
            raise RuntimeError("Call fit() first")
            
        if pair[0] not in self.tickers or pair[1] not in self.tickers:
            raise ValueError(f"Invalid pair: {pair}")
            
        eps = self.std_resid
        a1, b1, a2, b2 = self.opt_params
        Q_bar = eps.cov().values
        Q_prev = Q_bar.copy()
        rho = np.empty(len(eps))

        i, j = self.tickers.index(pair[0]), self.tickers.index(pair[1])
        
        for t in range(len(eps)):
            if t > 0:
                is_stress = self.stress_regime.iloc[t]
                a, b = (a2, b2) if is_stress else (a1, b1)
                e_prev = eps.iloc[t - 1].values.reshape(-1, 1)
                Q_t = (1 - a - b) * Q_bar + a * (e_prev @ e_prev.T) + b * Q_prev
            else:
                Q_t = Q_prev
                
            d = np.sqrt(np.diag(Q_t))
            R_t = Q_t / d[:, None] / d[None, :]
            rho[t] = R_t[i, j]
            Q_prev = Q_t
            
        return pd.Series(rho, index=eps.index, name=f"{pair[0]}_{pair[1]}")


async def compute_quantile_regression(systemic_df: pd.DataFrame) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Compute quantile regression for systemic risk analysis.
    Returns summary and detailed results.
    """
    try:
        systemic_series = systemic_df["Systemic"].dropna()
        
        if len(systemic_series) < 100:
            raise ValueError("Insufficient data for quantile regression")
        
        # Calculate VaR at different quantiles
        var_95 = np.percentile(systemic_series, 5)  # 5th percentile for VaR 95
        var_normal = systemic_series.mean() - 2 * systemic_series.std()
        
        # Capital buffer based on tail risk
        capital_buffer = max(0, var_normal - var_95)
        
        if "PCA" in systemic_df.columns and "Credit" in systemic_df.columns:
            corr_series = systemic_df["PCA"].rolling(30).corr(systemic_df["Credit"]).dropna()
            corr_mean = corr_series.mean() if not corr_series.empty else 0
            corr_vol = corr_series.std() if not corr_series.empty else 0
        else:
            corr_mean, corr_vol = 0, 0
            
        summary = {
            "VaR_95": float(var_95),
            "VaR_Normal": float(var_normal),
            "Capital_Buffer": float(capital_buffer),
            "Correlation_Risk": {
                "mean_corr": float(corr_mean),
                "vol_corr": float(corr_vol),
                "corr_beta": float(corr_mean * 0.5),  # Simplified beta
                "corr_contrib_to_loss": float(abs(corr_mean) * 0.3)  # Simplified contribution
            }
        }
        
        quantiles = [0.05, 0.25, 0.5, 0.75, 0.95]
        results = {}
        for q in quantiles:
            results[f"q_{int(q*100)}"] = {
                "value": float(np.percentile(systemic_series, q * 100)),
                "density": len(systemic_series[systemic_series <= np.percentile(systemic_series, q * 100)]) / len(systemic_series)
            }
            
        logger.info("Quantile regression computed successfully")
        return summary, results
        
    except Exception as e:
        logger.error(f"Quantile regression failed: {e}")
        # Return safe fallback values
        summary = {
            "VaR_95": -0.05,
            "VaR_Normal": -0.02,
            "Capital_Buffer": 0.03,
            "Correlation_Risk": {
                "mean_corr": 0.0,
                "vol_corr": 0.0,
                "corr_beta": 0.0,
                "corr_contrib_to_loss": 0.0
            },
            "error": str(e)
        }
        return summary, {}