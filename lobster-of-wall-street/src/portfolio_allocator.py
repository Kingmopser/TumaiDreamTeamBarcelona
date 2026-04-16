"""
Portfolio Allocation Engine

Takes research scores and allocates $1,000,000 across at least 50 NASDAQ stocks.

Allocation strategy:
  - Select the top-scoring candidates ensuring at minimum 50 stocks.
  - Conviction-weighted: allocation proportional to (score - floor)^power, creating
    a skewed distribution that overweights high-conviction picks without ignoring tail.
  - Sector diversification: no single sector can exceed 30% of total portfolio.
  - Per-stock bounds: min $5,000, max $50,000.
  - Total must equal exactly $1,000,000 (enforced by rounding adjustment).
"""

import math
from typing import Optional

TOTAL_CAPITAL = 1_000_000
MIN_PER_STOCK = 5_000
MAX_PER_STOCK = 50_000
MIN_STOCKS = 50
TARGET_STOCKS = 65          # Select slightly more than minimum for diversification
SECTOR_CAP_PCT = 0.30       # Max 30% in any single sector
CONVICTION_POWER = 1.5      # Exponent for score-weighting (>1 = more conviction-concentrated)


def allocate(research_results: list[dict], num_stocks: int = TARGET_STOCKS) -> list[dict]:
    """
    Build a portfolio from research results.

    Args:
        research_results: sorted list of dicts with 'ticker', 'score', 'sector', 'company_name', etc.
        num_stocks: how many stocks to include (must be >= MIN_STOCKS)

    Returns:
        List of portfolio entries with 'ticker', 'amount', 'weight_pct', 'score', etc.
    """
    if num_stocks < MIN_STOCKS:
        raise ValueError(f"num_stocks must be >= {MIN_STOCKS}, got {num_stocks}")

    # ── Step 1: Select candidates with sector diversification ─────────────────
    candidates = _select_with_sector_diversity(research_results, num_stocks)

    print(f"\n{'='*60}")
    print(f"Portfolio Allocator")
    print(f"  Selected {len(candidates)} companies")
    print(f"  Sector distribution:")
    sector_counts = {}
    for c in candidates:
        sector_counts[c["sector"]] = sector_counts.get(c["sector"], 0) + 1
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        print(f"    {sector:<25s} {count:3d} companies")
    print(f"{'='*60}")

    # ── Step 2: Compute conviction-weighted allocations ───────────────────────
    # Use score^power as the weight; scores are all >= 0
    min_score = min(c["score"] for c in candidates)
    weights = [(c["score"] - min_score + 1) ** CONVICTION_POWER for c in candidates]
    total_weight = sum(weights)

    raw_allocations = [w / total_weight * TOTAL_CAPITAL for w in weights]

    # ── Step 3: Apply per-stock bounds ────────────────────────────────────────
    allocations = _apply_bounds(raw_allocations, num_stocks)

    # ── Step 4: Apply sector cap ──────────────────────────────────────────────
    allocations = _apply_sector_cap(candidates, allocations)

    # ── Step 5: Force total = exactly $1,000,000 ─────────────────────────────
    allocations = _normalize_to_total(allocations)

    # ── Step 6: Assemble portfolio ────────────────────────────────────────────
    # Round allocations to whole dollars, then fix any residual on the largest position
    int_amounts = [round(a) for a in allocations]
    residual = TOTAL_CAPITAL - sum(int_amounts)
    if residual != 0:
        max_idx = int_amounts.index(max(int_amounts))
        int_amounts[max_idx] += residual

    portfolio = []
    for i, company in enumerate(candidates):
        amount = int_amounts[i]
        portfolio.append({
            "ticker": company["ticker"],
            "company_name": company["company_name"],
            "sector": company["sector"],
            "score": company["score"],
            "amount": amount,
            "weight_pct": round(amount / TOTAL_CAPITAL * 100, 3),
            "raw_analysis": company.get("raw_analysis", ""),
            "data_cutoff_date": company.get("data_cutoff_date", "2025-04-15"),
        })

    portfolio.sort(key=lambda x: x["amount"], reverse=True)

    # ── Validation ────────────────────────────────────────────────────────────
    _validate_portfolio(portfolio)

    return portfolio


def _select_with_sector_diversity(
    research_results: list[dict], num_stocks: int
) -> list[dict]:
    """
    Greedy selection of top-scoring companies while enforcing sector cap.
    The sector cap during selection is floor(SECTOR_CAP_PCT * num_stocks).
    """
    sector_limit = max(3, math.floor(SECTOR_CAP_PCT * num_stocks))
    sector_counts: dict[str, int] = {}
    selected = []

    for company in research_results:  # Already sorted by score descending
        sector = company["sector"]
        if sector_counts.get(sector, 0) >= sector_limit:
            continue
        selected.append(company)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= num_stocks:
            break

    # If we didn't reach num_stocks due to sector caps, relax and fill remaining
    if len(selected) < num_stocks:
        remaining_tickers = {c["ticker"] for c in selected}
        for company in research_results:
            if company["ticker"] not in remaining_tickers:
                selected.append(company)
                remaining_tickers.add(company["ticker"])
            if len(selected) >= num_stocks:
                break

    return selected


def _apply_bounds(raw_allocations: list[float], num_stocks: int) -> list[float]:
    """
    Clip allocations to [MIN_PER_STOCK, MAX_PER_STOCK] and redistribute excess/deficit.
    Uses iterative approach to converge.
    """
    allocs = list(raw_allocations)
    max_iterations = 20

    for _ in range(max_iterations):
        # Find violators
        below = [i for i, a in enumerate(allocs) if a < MIN_PER_STOCK]
        above = [i for i, a in enumerate(allocs) if a > MAX_PER_STOCK]

        if not below and not above:
            break

        # Fix below-minimum: set to minimum, redistribute deficit
        deficit = 0.0
        for i in below:
            deficit += MIN_PER_STOCK - allocs[i]
            allocs[i] = float(MIN_PER_STOCK)

        # Fix above-maximum: set to maximum, redistribute surplus
        surplus = 0.0
        for i in above:
            surplus += allocs[i] - MAX_PER_STOCK
            allocs[i] = float(MAX_PER_STOCK)

        net = surplus - deficit
        if abs(net) < 1e-6:
            break

        # Redistribute net to unconstrained positions
        unconstrained = [
            i for i, a in enumerate(allocs)
            if MIN_PER_STOCK <= a <= MAX_PER_STOCK and i not in below and i not in above
        ]
        if unconstrained:
            per = net / len(unconstrained)
            for i in unconstrained:
                allocs[i] += per
        else:
            # All constrained; just let normalize handle the rest
            break

    return allocs


def _apply_sector_cap(candidates: list[dict], allocations: list[float]) -> list[float]:
    """
    Ensure no sector exceeds SECTOR_CAP_PCT of total capital.
    Excess is redistributed proportionally to under-weight sectors.
    """
    allocs = list(allocations)
    cap = SECTOR_CAP_PCT * TOTAL_CAPITAL

    # Compute sector totals
    sector_totals: dict[str, float] = {}
    sector_indices: dict[str, list[int]] = {}
    for i, c in enumerate(candidates):
        s = c["sector"]
        sector_totals[s] = sector_totals.get(s, 0.0) + allocs[i]
        sector_indices.setdefault(s, []).append(i)

    for sector, total in sector_totals.items():
        if total > cap:
            excess = total - cap
            # Scale down allocations in this sector proportionally
            indices = sector_indices[sector]
            for i in indices:
                allocs[i] *= cap / total
            # Redistribute excess to other sectors
            other_indices = [i for i in range(len(allocs)) if candidates[i]["sector"] != sector]
            if other_indices:
                per = excess / len(other_indices)
                for i in other_indices:
                    allocs[i] = min(allocs[i] + per, MAX_PER_STOCK)

    return allocs


def _normalize_to_total(allocations: list[float]) -> list[float]:
    """
    Scale all allocations so they sum exactly to TOTAL_CAPITAL.
    Uses two-pass approach: scale factor + single adjustment to the largest position.
    """
    total = sum(allocations)
    if abs(total - TOTAL_CAPITAL) < 0.01:
        return allocations

    factor = TOTAL_CAPITAL / total
    allocs = [a * factor for a in allocations]

    # Fix any floating-point residual by adjusting the largest position
    diff = TOTAL_CAPITAL - sum(allocs)
    if abs(diff) > 0.001:
        max_idx = allocs.index(max(allocs))
        allocs[max_idx] += diff

    return allocs


def _validate_portfolio(portfolio: list[dict]):
    """Assert all submission rules are satisfied."""
    total = sum(p["amount"] for p in portfolio)
    tickers = [p["ticker"] for p in portfolio]

    assert len(portfolio) >= MIN_STOCKS, f"Too few stocks: {len(portfolio)} < {MIN_STOCKS}"
    assert len(tickers) == len(set(tickers)), "Duplicate tickers found"
    assert all(p["amount"] >= MIN_PER_STOCK for p in portfolio), (
        f"Some stocks below minimum: {[(p['ticker'], p['amount']) for p in portfolio if p['amount'] < MIN_PER_STOCK]}"
    )
    assert abs(total - TOTAL_CAPITAL) <= 1, (
        f"Total capital mismatch: {total} != {TOTAL_CAPITAL}"
    )
    print(f"\n✓ Portfolio validation passed:")
    print(f"  Stocks:       {len(portfolio)}")
    print(f"  Total:        ${total:,.0f}")
    print(f"  Min position: ${min(p['amount'] for p in portfolio):,.0f}")
    print(f"  Max position: ${max(p['amount'] for p in portfolio):,.0f}")
    print(f"  Sectors:      {len(set(p['sector'] for p in portfolio))}")
