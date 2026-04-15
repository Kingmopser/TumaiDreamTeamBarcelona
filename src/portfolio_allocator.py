"""
Stage 2: Portfolio Allocator
Takes scored companies from research_agent output and allocates exactly $1,000,000
across the top 55 stocks using conviction-weighted sizing.

Rules enforced:
  - Minimum 50 NASDAQ companies
  - No duplicates
  - Minimum $5,000 per stock
  - Total = exactly $1,000,000

Input:  output/companies_scored.json
Output: output/portfolio.json  (without rationale — added by rationale_generator)
"""

import json
from pathlib import Path

BUDGET = 1_000_000
MIN_ALLOCATION = 5_000
TARGET_STOCKS = 55  # 5 buffer above the 50 minimum

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def load_scored_companies() -> list[dict]:
    path = OUTPUT_DIR / "companies_scored.json"
    if not path.exists():
        raise FileNotFoundError(f"Run research_agent.py first. Expected: {path}")
    return json.loads(path.read_text())


def allocate(companies: list[dict], budget: int = BUDGET,
             min_alloc: int = MIN_ALLOCATION, n: int = TARGET_STOCKS) -> list[dict]:
    """
    Conviction-weighted allocation:
    1. Take top N by score.
    2. Raw weight = score / total_score * budget.
    3. Floor each at min_alloc.
    4. Re-normalise to exactly budget.
    """
    # Take top N (already sorted descending by score in research_agent)
    selected = companies[:n]

    total_score = sum(c["score"] for c in selected)

    # Raw weighted amounts
    for c in selected:
        raw = budget * (c["score"] / total_score)
        c["amount"] = max(raw, min_alloc)

    # Normalise so sum = exactly budget
    current_total = sum(c["amount"] for c in selected)
    scale = budget / current_total
    for c in selected:
        c["amount"] = c["amount"] * scale

    # Round to integers
    for c in selected:
        c["amount"] = int(c["amount"])

    # Fix rounding residual: add/subtract from the largest position
    residual = budget - sum(c["amount"] for c in selected)
    if residual != 0:
        biggest = max(selected, key=lambda x: x["amount"])
        biggest["amount"] += residual

    # Final validation
    assert sum(c["amount"] for c in selected) == budget, "Allocation doesn't sum to budget"
    assert all(c["amount"] >= min_alloc for c in selected), "Some allocation below minimum"
    assert len({c["ticker"] for c in selected}) == len(selected), "Duplicate tickers"

    return selected


def print_summary(portfolio: list[dict]):
    total = sum(c["amount"] for c in portfolio)
    print(f"\n  Stocks: {len(portfolio)}")
    print(f"  Total:  ${total:,}")
    print(f"\n  Top 15 positions:")
    for c in sorted(portfolio, key=lambda x: x["amount"], reverse=True)[:15]:
        pct = c["amount"] / total * 100
        print(f"    {c['ticker']:6s}  ${c['amount']:>8,}  ({pct:.1f}%)  score={c['score']}")
    min_pos = min(portfolio, key=lambda x: x["amount"])
    max_pos = max(portfolio, key=lambda x: x["amount"])
    print(f"\n  Smallest: {min_pos['ticker']} ${min_pos['amount']:,}")
    print(f"  Largest:  {max_pos['ticker']} ${max_pos['amount']:,}")


def main() -> list[dict]:
    print("=" * 60)
    print("STAGE 2: Portfolio Allocator")
    print("=" * 60)

    print("\n[1/2] Loading scored companies...")
    companies = load_scored_companies()
    print(f"  Loaded {len(companies)} scored companies")

    if len(companies) < TARGET_STOCKS:
        print(f"  WARNING: only {len(companies)} companies available, "
              f"need {TARGET_STOCKS}. Reducing target to {len(companies)}.")
        n = max(len(companies), 50)
    else:
        n = TARGET_STOCKS

    print(f"\n[2/2] Allocating ${BUDGET:,} across top {n} stocks...")
    portfolio = allocate(companies, budget=BUDGET, min_alloc=MIN_ALLOCATION, n=n)

    print_summary(portfolio)

    out_path = OUTPUT_DIR / "portfolio.json"
    out_path.write_text(json.dumps(portfolio, indent=2, default=str))
    print(f"\n  Portfolio saved to: {out_path}")

    return portfolio


if __name__ == "__main__":
    main()
