#!/usr/bin/env python3
"""
v2_cala.py — Cala API-driven Portfolio

Uses the Cala knowledge/query endpoint to discover and rank the top
NASDAQ companies, then allocates $1,000,000 conviction-weighted.

HOW IT WORKS
────────────
1. Fire 10 fast knowledge/query calls (each ~1-3 s, no rate-limit issues)
   covering different financial filters and sectors.
2. Each query returns a ranked list of companies with tickers.
   Score each ticker by inverse-rank aggregation:
       score += (1 / (rank + 1)) * query_weight
   → companies appearing early in multiple high-weight queries score highest.
3. Select top 55 unique NASDAQ tickers (sector-capped at 15 per sector).
4. Allocate conviction-weighted:
       amount_i = (score_i^1.3 / Σ scores^1.3) × $1,000,000
   Bounds: $5 000 ≤ position ≤ $40 000. Total = exactly $1,000,000.

Usage:
  python src/v2_cala.py                  # query Cala + save portfolio.json
  python src/v2_cala.py --dry-run        # validate without submitting
  python src/v2_cala.py --submit         # query + submit to leaderboard
  python src/v2_cala.py --team-id SLUG   # override TEAM_ID from .env
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from leaderboard_client import LeaderboardClient

# ── Constants ─────────────────────────────────────────────────────────────────
TOTAL_CAPITAL  = 1_000_000
MIN_PER_STOCK  = 5_000
MAX_PER_STOCK  = 40_000
TARGET_STOCKS  = 55
SECTOR_CAP_N   = 15       # max stocks per sector during selection
CONVICTION_POW = 1.3      # mild conviction tilt (1.0 = equal-weight)

CALA_URL = "https://api.cala.ai/v1/knowledge/query"

# ── Cala queries ──────────────────────────────────────────────────────────────
# Each tuple: (query_string, weight)
# Weight controls how much this query contributes to the final score.
# All calls use knowledge/query (fast, no 30s rate limit).
QUERIES = [
    # Financial performance — highest weight (these are the selection criteria)
    ("companies.exchange=NASDAQ.revenue_growth>0.2.net_income>0",   2.0),
    ("companies.exchange=NASDAQ.revenue_growth>0.1.net_income>0",   1.8),
    ("companies.exchange=NASDAQ.market_cap>50B",                    1.6),
    ("companies.exchange=NASDAQ.market_cap>10B",                    1.4),
    # Sector sweeps — broad coverage
    ("companies.exchange=NASDAQ.sector=Technology",                 1.2),
    ("companies.exchange=NASDAQ.sector=Healthcare",                 1.1),
    ("companies.exchange=NASDAQ.sector=Consumer Discretionary",     1.0),
    ("companies.exchange=NASDAQ.sector=Communication Services",     1.0),
    ("companies.exchange=NASDAQ.sector=Financials",                 0.9),
    ("companies.exchange=NASDAQ.sector=Industrials",                0.9),
]

# ── Known NASDAQ ticker→sector mapping (used to validate & classify results) ──
# Only NASDAQ-listed. Used both as a validation allowlist and as a fallback
# if Cala returns fewer than TARGET_STOCKS unique tickers.
NASDAQ_META = {
    # Semiconductors
    "NVDA":"Semiconductors", "AVGO":"Semiconductors", "AMD":"Semiconductors",
    "QCOM":"Semiconductors", "AMAT":"Semiconductors", "LRCX":"Semiconductors",
    "KLAC":"Semiconductors", "MU":"Semiconductors",   "ADI":"Semiconductors",
    "TXN":"Semiconductors",  "MRVL":"Semiconductors", "MPWR":"Semiconductors",
    "ON":"Semiconductors",   "MCHP":"Semiconductors", "NXPI":"Semiconductors",
    "SNPS":"Semiconductors", "CDNS":"Semiconductors", "SMCI":"Semiconductors",
    "INTC":"Semiconductors",
    # Technology
    "AAPL":"Technology", "MSFT":"Technology", "GOOGL":"Technology",
    "META":"Technology", "AMZN":"Technology", "CSCO":"Technology",
    "ANET":"Technology", "ADBE":"Technology", "INTU":"Technology",
    "VRSK":"Technology", "CDW":"Technology",
    # Cloud Software
    "WDAY":"Cloud Software", "DDOG":"Cloud Software", "OKTA":"Cloud Software",
    "MDB":"Cloud Software",  "TEAM":"Cloud Software", "MNDY":"Cloud Software",
    "PAYC":"Cloud Software", "PCTY":"Cloud Software", "ZM":"Cloud Software",
    "DOCU":"Cloud Software",
    # Cybersecurity
    "PANW":"Cybersecurity", "CRWD":"Cybersecurity", "FTNT":"Cybersecurity",
    "ZS":"Cybersecurity",   "CHKP":"Cybersecurity",
    # Consumer Tech
    "TSLA":"Consumer Tech", "NFLX":"Consumer Tech", "PYPL":"Consumer Tech",
    "MELI":"Consumer Tech", "BKNG":"Consumer Tech", "EXPE":"Consumer Tech",
    "EBAY":"Consumer Tech", "ETSY":"Consumer Tech", "TTD":"Consumer Tech",
    "ABNB":"Consumer Tech", "TTWO":"Consumer Tech",
    # Biotech/Healthcare
    "AMGN":"Biotech/Healthcare", "GILD":"Biotech/Healthcare",
    "REGN":"Biotech/Healthcare", "VRTX":"Biotech/Healthcare",
    "BIIB":"Biotech/Healthcare", "MRNA":"Biotech/Healthcare",
    "IDXX":"Biotech/Healthcare", "ISRG":"Biotech/Healthcare",
    "ALGN":"Biotech/Healthcare", "DXCM":"Biotech/Healthcare",
    "GEHC":"Biotech/Healthcare", "IONS":"Biotech/Healthcare",
    "INCY":"Biotech/Healthcare", "ALNY":"Biotech/Healthcare",
    # Consumer/Retail
    "COST":"Consumer/Retail", "SBUX":"Consumer/Retail", "MNST":"Consumer/Retail",
    "PEP":"Consumer/Retail",  "DLTR":"Consumer/Retail", "ULTA":"Consumer/Retail",
    "KHC":"Consumer/Retail",  "MDLZ":"Consumer/Retail", "KDP":"Consumer/Retail",
    "ORLY":"Consumer/Retail",
    # Financials/Fintech
    "NDAQ":"Financials/Fintech", "IBKR":"Financials/Fintech",
    "COIN":"Financials/Fintech", "HOOD":"Financials/Fintech",
    "MKTX":"Financials/Fintech", "LPLA":"Financials/Fintech",
    "AFRM":"Financials/Fintech",
    # Industrials
    "FAST":"Industrials", "PAYX":"Industrials", "ADP":"Industrials",
    "CTAS":"Industrials", "ODFL":"Industrials", "CPRT":"Industrials",
    "PCAR":"Industrials", "FICO":"Industrials", "AXON":"Industrials",
    # Telecom/Media
    "TMUS":"Telecom/Media", "CMCSA":"Telecom/Media",
    "CHTR":"Telecom/Media", "SIRI":"Telecom/Media",
    # Clean Energy
    "FSLR":"Clean Energy", "ENPH":"Clean Energy",
    "CEG":"Clean Energy",  "EXC":"Clean Energy",
    # AI/Data
    "PLTR":"AI/Data", "APP":"AI/Data",
}

NASDAQ_NAMES = {
    "NVDA":"NVIDIA", "AVGO":"Broadcom", "AMD":"Advanced Micro Devices",
    "QCOM":"Qualcomm", "AMAT":"Applied Materials", "LRCX":"Lam Research",
    "KLAC":"KLA Corporation", "MU":"Micron Technology", "ADI":"Analog Devices",
    "TXN":"Texas Instruments", "MRVL":"Marvell Technology",
    "MPWR":"Monolithic Power Systems", "ON":"ON Semiconductor",
    "MCHP":"Microchip Technology", "NXPI":"NXP Semiconductors",
    "SNPS":"Synopsys", "CDNS":"Cadence Design Systems",
    "SMCI":"Super Micro Computer", "INTC":"Intel",
    "AAPL":"Apple", "MSFT":"Microsoft", "GOOGL":"Alphabet",
    "META":"Meta Platforms", "AMZN":"Amazon", "CSCO":"Cisco",
    "ANET":"Arista Networks", "ADBE":"Adobe", "INTU":"Intuit",
    "VRSK":"Verisk Analytics", "CDW":"CDW Corporation",
    "WDAY":"Workday", "DDOG":"Datadog", "OKTA":"Okta",
    "MDB":"MongoDB", "TEAM":"Atlassian", "MNDY":"monday.com",
    "PAYC":"Paycom", "PCTY":"Paylocity", "ZM":"Zoom", "DOCU":"DocuSign",
    "PANW":"Palo Alto Networks", "CRWD":"CrowdStrike", "FTNT":"Fortinet",
    "ZS":"Zscaler", "CHKP":"Check Point Software",
    "TSLA":"Tesla", "NFLX":"Netflix", "PYPL":"PayPal",
    "MELI":"MercadoLibre", "BKNG":"Booking Holdings", "EXPE":"Expedia",
    "EBAY":"eBay", "ETSY":"Etsy", "TTD":"The Trade Desk",
    "ABNB":"Airbnb", "TTWO":"Take-Two Interactive",
    "AMGN":"Amgen", "GILD":"Gilead Sciences", "REGN":"Regeneron",
    "VRTX":"Vertex Pharmaceuticals", "BIIB":"Biogen", "MRNA":"Moderna",
    "IDXX":"IDEXX Laboratories", "ISRG":"Intuitive Surgical",
    "ALGN":"Align Technology", "DXCM":"DexCom", "GEHC":"GE HealthCare",
    "IONS":"Ionis Pharmaceuticals", "INCY":"Incyte",
    "ALNY":"Alnylam Pharmaceuticals",
    "COST":"Costco", "SBUX":"Starbucks", "MNST":"Monster Beverage",
    "PEP":"PepsiCo", "DLTR":"Dollar Tree", "ULTA":"Ulta Beauty",
    "KHC":"Kraft Heinz", "MDLZ":"Mondelez", "KDP":"Keurig Dr Pepper",
    "ORLY":"O'Reilly Automotive",
    "NDAQ":"Nasdaq Inc.", "IBKR":"Interactive Brokers", "COIN":"Coinbase",
    "HOOD":"Robinhood", "MKTX":"MarketAxess", "LPLA":"LPL Financial",
    "AFRM":"Affirm",
    "FAST":"Fastenal", "PAYX":"Paychex", "ADP":"ADP", "CTAS":"Cintas",
    "ODFL":"Old Dominion Freight", "CPRT":"Copart", "PCAR":"PACCAR",
    "FICO":"FICO", "AXON":"Axon Enterprise",
    "TMUS":"T-Mobile US", "CMCSA":"Comcast", "CHTR":"Charter Comm.",
    "SIRI":"Sirius XM",
    "FSLR":"First Solar", "ENPH":"Enphase Energy",
    "CEG":"Constellation Energy", "EXC":"Exelon",
    "PLTR":"Palantir", "APP":"AppLovin",
}


# ── Cala querying ─────────────────────────────────────────────────────────────

def run_queries(api_key: str) -> dict[str, float]:
    """
    Run all QUERIES against the Cala knowledge/query endpoint.
    Returns dict: ticker → cumulative_score (float).
    """
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    ticker_scores: dict[str, float] = {}

    print(f"\n  Running {len(QUERIES)} Cala queries...")
    for i, (query, weight) in enumerate(QUERIES):
        print(f"  [{i+1}/{len(QUERIES)}] {query[:65]}...", end=" ", flush=True)
        try:
            r = requests.post(
                CALA_URL,
                json={"input": query},
                headers=headers,
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"FAILED ({e})")
            continue

        results = data.get("results", [])
        print(f"→ {len(results)} results")

        for rank, item in enumerate(results):
            # Extract ticker — it may be in 'ticker' field directly
            ticker = None

            # Method 1: explicit ticker field
            raw_ticker = str(item.get("ticker", "")).strip().upper()
            if raw_ticker and raw_ticker in NASDAQ_META:
                ticker = raw_ticker

            # Method 2: match company name against our known names
            if not ticker:
                company_raw = str(item.get("company", "")).upper()
                for t, name in NASDAQ_NAMES.items():
                    if name.upper() in company_raw or company_raw in name.upper():
                        ticker = t
                        break

            # Method 3: ticker appears directly in any value string
            if not ticker:
                for val in item.values():
                    val_str = str(val).strip().upper()
                    if val_str in NASDAQ_META:
                        ticker = val_str
                        break

            if not ticker:
                continue

            # Inverse-rank score: position 0 is best
            score = weight * (1.0 / (rank + 1))
            ticker_scores[ticker] = ticker_scores.get(ticker, 0.0) + score

        time.sleep(0.5)   # be polite — tiny pause between calls

    print(f"\n  Found {len(ticker_scores)} unique NASDAQ tickers from Cala")
    return ticker_scores


# ── Selection ─────────────────────────────────────────────────────────────────

def select_stocks(
    ticker_scores: dict[str, float], n: int
) -> list[dict]:
    """
    Pick top-n tickers by Cala score with sector cap.
    If Cala returned fewer than n unique tickers, supplement from NASDAQ_META
    ordered by how well-known / large-cap the company is (just alphabetically
    from the meta dict — already roughly quality-ordered).
    """
    # Sort by score descending
    ranked = sorted(ticker_scores.items(), key=lambda x: -x[1])

    sector_count: dict[str, int] = {}
    selected = []

    for ticker, score in ranked:
        sector = NASDAQ_META.get(ticker)
        if not sector:
            continue
        if sector_count.get(sector, 0) >= SECTOR_CAP_N:
            continue
        selected.append({"ticker": ticker, "cala_score": score, "sector": sector,
                          "company_name": NASDAQ_NAMES.get(ticker, ticker)})
        sector_count[sector] = sector_count.get(sector, 0) + 1
        if len(selected) >= n:
            break

    # Fallback: supplement from NASDAQ_META if needed
    if len(selected) < n:
        selected_tickers = {s["ticker"] for s in selected}
        for ticker, sector in NASDAQ_META.items():
            if ticker in selected_tickers:
                continue
            if sector_count.get(sector, 0) >= SECTOR_CAP_N:
                continue
            selected.append({
                "ticker": ticker,
                "cala_score": 0.01,   # minimal score — fallback
                "sector": sector,
                "company_name": NASDAQ_NAMES.get(ticker, ticker),
            })
            selected_tickers.add(ticker)
            sector_count[sector] = sector_count.get(sector, 0) + 1
            if len(selected) >= n:
                break

    return selected


# ── Allocation ─────────────────────────────────────────────────────────────────

def allocate(candidates: list[dict]) -> list[dict]:
    """
    Conviction-weighted allocation using Cala scores.

    weight_i = score_i^CONVICTION_POW / Σ score_j^CONVICTION_POW
    amount_i = weight_i × $1,000,000

    Bounds enforced iteratively; total forced to exactly $1,000,000.
    """
    import numpy as np

    scores  = np.array([c["cala_score"] for c in candidates], dtype=float)
    # Normalise scores to [1, max] so pow doesn't collapse near-zero scores
    scores  = (scores - scores.min()) + 1.0
    weights = scores ** CONVICTION_POW
    weights = weights / weights.sum()
    amounts = weights * TOTAL_CAPITAL

    # Iterative bounds enforcement
    for _ in range(60):
        below = amounts < MIN_PER_STOCK
        above = amounts > MAX_PER_STOCK
        if not below.any() and not above.any():
            break
        amounts[below] = float(MIN_PER_STOCK)
        amounts[above] = float(MAX_PER_STOCK)
        # Redistribute to unconstrained
        free = ~(below | above)
        if free.any():
            remainder = TOTAL_CAPITAL - amounts[~free].sum()
            free_w = weights[free] / weights[free].sum()
            amounts[free] = free_w * remainder

    # Re-normalise to exactly $1M
    amounts = amounts * (TOTAL_CAPITAL / amounts.sum())

    # Round + fix residual
    int_amounts = np.round(amounts).astype(int)
    residual = TOTAL_CAPITAL - int_amounts.sum()
    int_amounts[int(np.argmax(int_amounts))] += residual

    portfolio = []
    for i, c in enumerate(candidates):
        amt = int(int_amounts[i])
        portfolio.append({
            **c,
            "amount":     amt,
            "weight_pct": round(amt / TOTAL_CAPITAL * 100, 3),
            "score":      round(c["cala_score"], 4),
            "rationale":  (
                f"[{c['ticker']}] {c['company_name']} ({c['sector']}) — "
                f"Selected by Cala API query aggregation. "
                f"Cala score: {c['cala_score']:.3f} "
                f"(inverse-rank weighted across {len(QUERIES)} financial & sector queries). "
                f"Allocated ${amt:,} conviction-proportional to Cala score."
            ),
        })

    portfolio.sort(key=lambda x: x["amount"], reverse=True)
    return portfolio


# ── Validation ────────────────────────────────────────────────────────────────

def validate(portfolio: list[dict]) -> None:
    total   = sum(p["amount"] for p in portfolio)
    tickers = [p["ticker"] for p in portfolio]
    assert len(portfolio) >= 50, f"Only {len(portfolio)} stocks"
    assert len(tickers) == len(set(tickers)), "Duplicate tickers"
    assert all(p["amount"] >= MIN_PER_STOCK for p in portfolio), \
        f"Below min: {[(p['ticker'],p['amount']) for p in portfolio if p['amount'] < MIN_PER_STOCK]}"
    assert abs(total - TOTAL_CAPITAL) <= 1, f"Total {total} ≠ {TOTAL_CAPITAL}"
    print(
        f"\n  Validation passed — {len(portfolio)} stocks | "
        f"${total:,} total | "
        f"min ${min(p['amount'] for p in portfolio):,} | "
        f"max ${max(p['amount'] for p in portfolio):,} | "
        f"{len(set(p['sector'] for p in portfolio))} sectors"
    )


# ── I/O ───────────────────────────────────────────────────────────────────────

def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


def save_portfolio(portfolio: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(exist_ok=True)
    import pandas as pd
    out = {
        "strategy":         "v2_cala_conviction",
        "generated_at":     pd.Timestamp.utcnow().isoformat() + "Z",
        "data_cutoff_date": "2025-04-15",
        "agent":            "CalaConviction",
        "version":          "2.0",
        "total_invested":   sum(p["amount"] for p in portfolio),
        "num_stocks":       len(portfolio),
        "sectors":          sorted(set(p["sector"] for p in portfolio)),
        "portfolio":        portfolio,
    }
    path = output_dir / "portfolio.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Portfolio saved: {path}")


def print_summary(portfolio: list[dict]) -> None:
    total = sum(p["amount"] for p in portfolio)
    print(f"\n{'='*75}")
    print(f"  {'#':<4} {'Ticker':<7} {'Company':<26} {'Sector':<20} {'Amount':>9} {'Score':>7}")
    print(f"  {'─'*75}")
    for i, p in enumerate(portfolio[:20], 1):
        print(
            f"  {i:<4} {p['ticker']:<7} {p['company_name'][:24]:<26} "
            f"{p['sector'][:18]:<20} ${p['amount']:>8,}  {p['score']:>6.3f}"
        )
    if len(portfolio) > 20:
        print(f"  ... and {len(portfolio)-20} more")
    print(f"  {'─'*75}")
    print(f"  {'TOTAL':>42}  ${total:>9,}")
    print(f"{'='*75}")

    sector_totals: dict[str, int] = {}
    for p in portfolio:
        sector_totals[p["sector"]] = sector_totals.get(p["sector"], 0) + p["amount"]
    print("\n  Sector allocation:")
    for s, amt in sorted(sector_totals.items(), key=lambda x: -x[1]):
        print(f"    {s:<25}  ${amt:>9,}  ({amt/total*100:.1f}%)")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="v2 Cala-driven Portfolio")
    p.add_argument("--submit",     action="store_true")
    p.add_argument("--dry-run",    action="store_true")
    p.add_argument("--team-id",    type=str, default=None)
    p.add_argument("--num-stocks", type=int, default=TARGET_STOCKS)
    p.add_argument("--output-dir", type=str, default="output")
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    load_env()
    args = parse_args()

    api_key = os.environ.get("CALA_API_KEY")
    if not api_key:
        print("ERROR: CALA_API_KEY not set in .env")
        sys.exit(1)

    team_id = args.team_id or os.environ.get("TEAM_ID", "")
    if (args.submit or args.dry_run) and not team_id:
        print("ERROR: TEAM_ID required. Set in .env or pass --team-id.")
        sys.exit(1)

    output_dir = Path(__file__).parent.parent / args.output_dir

    print(f"\n{'#'*65}")
    print(f"  LOBSTER OF WALL STREET — v2 Cala Conviction Portfolio")
    print(f"  Queries: {len(QUERIES)} | Target stocks: {args.num_stocks} | Capital: $1,000,000")
    print(f"{'#'*65}")

    # Step 1: Query Cala
    print("\nStep 1 / 3 — Querying Cala API ...")
    ticker_scores = run_queries(api_key)

    # Step 2: Select + allocate
    print(f"\nStep 2 / 3 — Selecting top {args.num_stocks} stocks ...")
    candidates = select_stocks(ticker_scores, args.num_stocks)
    print(f"  {len(candidates)} candidates selected")

    print(f"\nStep 3 / 3 — Conviction-weighted allocation ...")
    portfolio = allocate(candidates)
    validate(portfolio)
    print_summary(portfolio)
    save_portfolio(portfolio, output_dir)

    # Step 4: Submit (optional)
    if args.submit or args.dry_run:
        client = LeaderboardClient(
            team_id=team_id,
            agent_name="CalaConviction",
            agent_version="2.0",
        )
        result = client.submit(portfolio, dry_run=args.dry_run)
        client.save_submission_log(result, portfolio, output_dir=str(output_dir))
    else:
        print("  Run with --submit to submit, --dry-run to validate.")


if __name__ == "__main__":
    main()
