"""
Portfolio Construction — Conviction-Weighted Allocation
Layer 1: constraint stocks at $5k minimum
Layer 2: conviction stocks with exponential-decay weighting
"""

import numpy as np
import pandas as pd

TOTAL_CAPITAL = 1_000_000
MIN_PER_STOCK = 5_000
N_STOCKS      = 50


def allocate(
    ranked: pd.DataFrame,
    n_stocks: int = N_STOCKS,
    conviction_decay: float = 2.0,
    n_conviction: int = 10,
) -> list[dict]:
    """
    Two-layer allocation:
      Layer 2 (conviction): top n_conviction stocks, exponential-decay weighting
      Layer 1 (constraint): remaining stocks at $5k each

    conviction_decay controls concentration steepness:
      decay=1.0 → mild spread
      decay=2.0 → moderate concentration
      decay=3.0 → aggressive concentration
    """
    top = ranked.head(n_stocks)
    n_constraint = n_stocks - n_conviction

    # Layer 1: constraint stocks
    constraint_total = n_constraint * MIN_PER_STOCK

    # Layer 2: conviction stocks with exponential decay
    conviction_pool = TOTAL_CAPITAL - constraint_total
    ranks = np.arange(n_conviction, dtype=float)
    raw_weights = np.exp(-conviction_decay * ranks / n_conviction)
    raw_weights /= raw_weights.sum()
    conviction_amounts = (raw_weights * conviction_pool).astype(int)

    # Ensure minimum $5k for conviction stocks too
    conviction_amounts = np.maximum(conviction_amounts, MIN_PER_STOCK)

    # Fix total
    amounts = list(conviction_amounts) + [MIN_PER_STOCK] * n_constraint
    diff = TOTAL_CAPITAL - sum(amounts)
    amounts[0] += diff

    # Build portfolio
    portfolio = []
    for i, (_, row) in enumerate(top.iterrows()):
        portfolio.append({
            "ticker":       row["ticker"],
            "sector":       row["sector"],
            "amount":       int(amounts[i]),
            "score":        round(float(row["final_score"]), 4),
            "convexity":    round(float(row["convexity"]), 4),
            "quality":      round(float(row.get("quality", 0)), 4),
            "price_apr15":  round(float(row["price"]), 4),
            "drawdown_pct": round(float(row["cur_dd"]) * 100, 1),
            "vol_60d_pct":  round(float(row["vol_60d"]) * 100, 1),
            "layer":        "conviction" if i < n_conviction else "constraint",
        })

    return portfolio


def search_best_allocation(
    ranked: pd.DataFrame,
    n_stocks: int = N_STOCKS,
) -> list[dict]:
    """
    Search over allocation parameters to find optimal portfolio.
    Tests different conviction_decay and n_conviction values.
    Selects the allocation that maximises total conviction exposure.
    """
    best_portfolio = None
    best_metric = -1

    for n_conv in [1, 3, 5, 8, 10]:
        for decay in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 10.0]:
            portfolio = allocate(ranked, n_stocks, decay, n_conv)
            # Metric: weighted sum of (amount × score) — maximises conviction exposure
            metric = sum(p["amount"] * p["score"] for p in portfolio)
            if metric > best_metric:
                best_metric = metric
                best_portfolio = portfolio

    # Report what was selected
    top = best_portfolio[0]
    print(f"  Optimal allocation: #{top['ticker']} gets ${top['amount']:,}")
    print(f"  Conviction metric: {best_metric:,.0f}")
    return best_portfolio
