"""
Search & Optimisation Layer
Explores 500+ weight combinations to find robust stock rankings.
Stocks that consistently rank high across many weight combos are the most
reliable picks — resistant to overfitting any single scoring formula.
"""

import numpy as np
import pandas as pd
from collections import defaultdict
from .scoring import compute_convexity_scores, compute_final_scores, derive_sector_multipliers


def run_search(
    features: pd.DataFrame,
    n_trials: int = 500,
    top_k: int = 50,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Monte Carlo search over scoring weight space.

    For each trial:
      1. Sample random weights for the convexity score components
      2. Compute scores and rank all tickers
      3. Record top-K tickers and their ranks

    Returns a DataFrame with:
      - appearance_count: how many trials the ticker appeared in top-K
      - avg_rank: average rank across trials where it appeared
      - rank_std: std of rank (high = volatile/outlier-prone)
      - best_rank: best rank achieved in any trial
    """
    rng = np.random.RandomState(seed)

    # Weight ranges for each component (Dirichlet-like sampling)
    appearances = defaultdict(list)  # ticker → list of ranks

    print(f"  Running {n_trials} scoring trials ...")
    for trial in range(n_trials):
        # Sample weights from Dirichlet (ensures they sum to 1)
        raw = rng.dirichlet([2, 2, 2, 1.5, 1, 1])
        w_vol, w_gaps, w_dd, w_accel, w_r12m, w_vexp = raw

        scored = compute_convexity_scores(
            features,
            w_vol=w_vol, w_gaps=w_gaps, w_drawdown=w_dd,
            w_mom_accel=w_accel, w_r12m=w_r12m, w_vol_expand=w_vexp,
        )
        sect_mult = derive_sector_multipliers(scored)
        final = compute_final_scores(scored, sect_mult)

        for rank, ticker in enumerate(final["ticker"].head(top_k)):
            appearances[ticker].append(rank)

    # Aggregate
    records = []
    for ticker, ranks in appearances.items():
        records.append({
            "ticker":           ticker,
            "appearance_count": len(ranks),
            "avg_rank":         np.mean(ranks),
            "rank_std":         np.std(ranks),
            "best_rank":        min(ranks),
        })

    result = pd.DataFrame(records)
    result = result.sort_values(
        ["appearance_count", "avg_rank"],
        ascending=[False, True],
    ).reset_index(drop=True)

    n_consistent = (result["appearance_count"] >= n_trials * 0.8).sum()
    print(f"  {len(result)} unique tickers appeared in top-{top_k}")
    print(f"  {n_consistent} tickers appeared in >80% of trials (robust picks)")

    return result
