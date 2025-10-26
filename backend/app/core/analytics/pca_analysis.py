from app.services.data_pipeline import get_sector_data
from app.core.db_utils import save_pca_snapshot
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

async def compute_rolling_pca(window=60, n_components=None, force_refresh=False):
    rets = await get_sector_data(force_refresh=force_refresh)
    sector_tickers = rets.columns.tolist()
    
    if n_components is None:
        n_components = len(sector_tickers)
    
    logger.info(f"PCA: {len(sector_tickers)} sectors, using {n_components} components")

    evr_list, score_list, loadings_list = [], [], []
    idx = rets.index

    for t in range(window - 1, len(idx)):
        X = rets.iloc[t - window + 1 : t + 1]
        X = X - X.mean()
        C = np.corrcoef(X.T)
        vals, vecs = np.linalg.eigh(C)
        order = vals.argsort()[::-1]
        vals, vecs = vals[order], vecs[:, order]
        if "XLK" in sector_tickers and vecs[sector_tickers.index("XLK"), 0] < 0:
            vecs[:, 0] *= -1

        evr_list.append(vals / vals.sum())
        loadings_list.append(vecs)
        score_list.append(vecs.T @ rets.iloc[t].values)

    dates = idx[window - 1 :]
    
    actual_components = len(sector_tickers)
    
    evr = pd.DataFrame(
        evr_list, 
        index=dates, 
        columns=[f"EVR{k}" for k in range(1, actual_components + 1)]
    )
    scores = pd.DataFrame(
        score_list, 
        index=dates, 
        columns=[f"PC{k}_score" for k in range(1, actual_components + 1)]
    )

    pca_signal = (scores["PC1_score"] - scores["PC1_score"].mean()) / scores["PC1_score"].std()
    pca_signal = pca_signal.rolling(20).mean()

    await save_pca_snapshot(evr, scores, loadings_list, window, actual_components, sector_tickers)

    return {
        "explained_variance": evr,
        "scores": scores,
        "signal": pca_signal,
        "loadings": loadings_list
    }