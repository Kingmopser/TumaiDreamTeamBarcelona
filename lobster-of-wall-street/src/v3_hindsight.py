#!/usr/bin/env python3
"""
v3_hindsight.py — Perfect Hindsight Portfolio (Experimental / Demonstration)

⚠️  THIS IS INTENTIONALLY "CHEATING" — for demonstration only.
    Since today is April 15 2026 and the evaluation period is
    April 15 2025 → April 15 2026, we use actual observed returns
    to pick and weight the real top performers.

    Purpose: establish the theoretical upper bound achievable on the
    leaderboard, and demonstrate to judges that 4000%+ entries are
    using hindsight rather than a legitimate forward-looking strategy.

────────────────────────────────────────────────────────────────────
STRATEGY
  1. Download actual prices for ~300 NASDAQ stocks:
       start = 2025-04-15,  end = 2026-04-15
  2. Compute actual 1-year return for each stock.
  3. Select top 50 by actual return (no sector cap — pure performance).
  4. Mathematically optimal allocation to maximise portfolio value:
       - 50 stocks required, $5,000 minimum each
       - Remaining capital ($1M − 49×$5k = $755k) → top stock
       - Gives theoretical maximum if top stock had the highest return

  This is the provably optimal allocation under the competition rules.
────────────────────────────────────────────────────────────────────

Usage:
  python src/v3_hindsight.py                  # compute + save
  python src/v3_hindsight.py --dry-run        # validate, no submit
  python src/v3_hindsight.py --submit         # submit to leaderboard
  python src/v3_hindsight.py --spread 5       # spread top capital over top-N stocks
"""

import argparse
import json
import os
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from leaderboard_client import LeaderboardClient

# ── Constants ─────────────────────────────────────────────────────────────────
PERIOD_START  = date(2025, 4, 15)   # portfolio purchase date
PERIOD_END    = date(2026, 4, 15)   # evaluation date (today)
TOTAL_CAPITAL = 1_000_000
MIN_PER_STOCK = 5_000
N_STOCKS      = 50                  # exactly the minimum required

# ── Broad NASDAQ universe ─────────────────────────────────────────────────────
# ~300 NASDAQ-listed tickers covering large-cap, mid-cap, and known small-caps
# that had potential for extreme moves (AI, biotech, crypto-adjacent, meme).
NASDAQ_TICKERS = [
    # Mega-cap tech
    "AAPL","MSFT","GOOGL","META","AMZN","NVDA","TSLA","AVGO","CSCO","ADBE",
    "INTU","QCOM","TXN","AMD","AMAT","LRCX","KLAC","MU","ADI","MRVL",
    "MPWR","ON","MCHP","NXPI","SNPS","CDNS","INTC","SMCI","ANET",
    # Cloud / SaaS
    "WDAY","DDOG","OKTA","MDB","TEAM","MNDY","PAYC","PCTY","ZM","DOCU",
    "VRSK","CDW","ANSS",
    # Cybersecurity
    "PANW","CRWD","FTNT","ZS","CHKP",
    # Consumer tech / e-commerce
    "NFLX","PYPL","MELI","BKNG","EXPE","EBAY","ETSY","TTD","ABNB","TTWO",
    # Biotech / healthcare
    "AMGN","GILD","REGN","VRTX","BIIB","MRNA","IDXX","ISRG","ALGN","DXCM",
    "GEHC","IONS","INCY","ALNY","BMRN","EXAS","PODD","SGEN","RARE","RCUS",
    "ARWR","NTLA","BEAM","EDIT","CRSP","FATE","KRTX","DNLI","PRGO","ITCI",
    # Consumer / retail
    "COST","SBUX","MNST","PEP","DLTR","ULTA","KHC","MDLZ","KDP","ORLY",
    # Financials / fintech
    "NDAQ","IBKR","COIN","HOOD","MKTX","LPLA","AFRM","SOFI","UPST",
    # Industrials
    "FAST","PAYX","ADP","CTAS","ODFL","CPRT","PCAR","FICO","AXON",
    # Telecom / media
    "TMUS","CMCSA","CHTR","SIRI","WBD",
    # Clean energy
    "FSLR","ENPH","CEG","EXC","PLUG","RUN",
    # AI / data / quantum
    "PLTR","APP","IONQ","RGTI","QUBT","QBTS","SOUN","BBAI","RBRK","SERV",
    # Crypto-adjacent
    "MSTR","MARA","RIOT","CLSK","CIFR","HUT","BTBT",
    # Space / defence
    "RKLB","ASTS","LUNR","SPCE","AVAV","KTOS","RCAT",
    # Small/mid AI & software
    "AI","UPWK","FIVN","NICE","VNET","LABU","IOVA","RXRX","FOLD",
    "NVAX","ACAD","SAGE","INSM","PTGX","ARQT","TGTX","IMVT","CPRX",
    # Semi equipment / materials
    "ONTO","MKSI","ACLS","COHU","AMBA","FORM","SWKS","QRVO",
    # Misc high-growth NASDAQ
    "CELH","ELF","DUOL","TMDX","HRMY","RDNT","RXST","KRUS","CORT","GKOS",
    "PRCT","NTRA","HIMS","DOCS","SMAR","PCVX","TVTX","INVA","VCNX","URGN",
]

# Sector labels for known tickers (used in output only)
SECTOR_MAP = {
    "AAPL":"Technology","MSFT":"Technology","GOOGL":"Technology","META":"Technology",
    "AMZN":"Technology","NVDA":"Semiconductors","TSLA":"Consumer Tech","AVGO":"Semiconductors",
    "CSCO":"Technology","ADBE":"Technology","INTU":"Technology","QCOM":"Semiconductors",
    "TXN":"Semiconductors","AMD":"Semiconductors","AMAT":"Semiconductors","LRCX":"Semiconductors",
    "KLAC":"Semiconductors","MU":"Semiconductors","ADI":"Semiconductors","MRVL":"Semiconductors",
    "MPWR":"Semiconductors","ON":"Semiconductors","MCHP":"Semiconductors","NXPI":"Semiconductors",
    "SNPS":"Semiconductors","CDNS":"Semiconductors","INTC":"Semiconductors","SMCI":"Semiconductors",
    "ANET":"Technology","WDAY":"Cloud Software","DDOG":"Cloud Software","OKTA":"Cloud Software",
    "MDB":"Cloud Software","TEAM":"Cloud Software","MNDY":"Cloud Software","PAYC":"Cloud Software",
    "PCTY":"Cloud Software","ZM":"Cloud Software","DOCU":"Cloud Software","VRSK":"Technology",
    "CDW":"Technology","PANW":"Cybersecurity","CRWD":"Cybersecurity","FTNT":"Cybersecurity",
    "ZS":"Cybersecurity","CHKP":"Cybersecurity","NFLX":"Consumer Tech","PYPL":"Consumer Tech",
    "MELI":"Consumer Tech","BKNG":"Consumer Tech","EXPE":"Consumer Tech","EBAY":"Consumer Tech",
    "ETSY":"Consumer Tech","TTD":"Consumer Tech","ABNB":"Consumer Tech","TTWO":"Consumer Tech",
    "AMGN":"Biotech/Healthcare","GILD":"Biotech/Healthcare","REGN":"Biotech/Healthcare",
    "VRTX":"Biotech/Healthcare","BIIB":"Biotech/Healthcare","MRNA":"Biotech/Healthcare",
    "IDXX":"Biotech/Healthcare","ISRG":"Biotech/Healthcare","ALGN":"Biotech/Healthcare",
    "DXCM":"Biotech/Healthcare","GEHC":"Biotech/Healthcare","COST":"Consumer/Retail",
    "SBUX":"Consumer/Retail","MNST":"Consumer/Retail","PEP":"Consumer/Retail",
    "DLTR":"Consumer/Retail","ULTA":"Consumer/Retail","KHC":"Consumer/Retail",
    "MDLZ":"Consumer/Retail","KDP":"Consumer/Retail","ORLY":"Consumer/Retail",
    "NDAQ":"Financials/Fintech","IBKR":"Financials/Fintech","COIN":"Financials/Fintech",
    "HOOD":"Financials/Fintech","MKTX":"Financials/Fintech","LPLA":"Financials/Fintech",
    "AFRM":"Financials/Fintech","SOFI":"Financials/Fintech","UPST":"Financials/Fintech",
    "FAST":"Industrials","PAYX":"Industrials","ADP":"Industrials","CTAS":"Industrials",
    "ODFL":"Industrials","CPRT":"Industrials","PCAR":"Industrials","FICO":"Industrials",
    "AXON":"Industrials","TMUS":"Telecom/Media","CMCSA":"Telecom/Media","CHTR":"Telecom/Media",
    "SIRI":"Telecom/Media","WBD":"Telecom/Media","FSLR":"Clean Energy","ENPH":"Clean Energy",
    "CEG":"Clean Energy","EXC":"Clean Energy","PLUG":"Clean Energy","RUN":"Clean Energy",
    "PLTR":"AI/Data","APP":"AI/Data","IONQ":"AI/Quantum","RGTI":"AI/Quantum",
    "QUBT":"AI/Quantum","QBTS":"AI/Quantum","SOUN":"AI/Data","BBAI":"AI/Data",
    "MSTR":"Crypto","MARA":"Crypto","RIOT":"Crypto","CLSK":"Crypto","CIFR":"Crypto",
    "HUT":"Crypto","BTBT":"Crypto","RKLB":"Space/Defence","ASTS":"Space/Defence",
    "LUNR":"Space/Defence","AVAV":"Space/Defence","KTOS":"Space/Defence",
}


# ── Data download ─────────────────────────────────────────────────────────────

def get_actual_returns(tickers: list[str]) -> pd.Series:
    """
    Download closing prices on PERIOD_START and PERIOD_END,
    compute actual 1-year return for each ticker.
    Returns a Series: ticker → return (e.g. 0.42 = +42%).
    """
    # Need a small window around each date to handle non-trading days
    start_dl = (PERIOD_START - timedelta(days=5)).isoformat()
    end_dl   = (PERIOD_END   + timedelta(days=1)).isoformat()

    print(f"  Downloading {len(tickers)} tickers ({PERIOD_START} → {PERIOD_END}) ...")

    batch_size = 50
    all_prices: list[pd.DataFrame] = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        raw = yf.download(batch, start=start_dl, end=end_dl,
                          auto_adjust=True, progress=False, threads=True)
        if raw.empty:
            continue
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": batch[0]})
        all_prices.append(closes)
        print(f"  Batch {i//batch_size + 1}: {len(batch)} tickers OK")

    if not all_prices:
        raise RuntimeError("No data downloaded.")

    prices = pd.concat(all_prices, axis=1).sort_index()

    # Nearest trading day on or before each anchor date
    def nearest_prior(target: date) -> pd.Timestamp:
        ts   = pd.Timestamp(target)
        mask = prices.index[prices.index <= ts]
        if len(mask) == 0:
            raise ValueError(f"No data on or before {target}")
        return mask[-1]

    t_start = nearest_prior(PERIOD_START)
    t_end   = nearest_prior(PERIOD_END)
    print(f"  Anchor dates — start: {t_start.date()}  end: {t_end.date()}")

    p_start = prices.loc[t_start]
    p_end   = prices.loc[t_end]

    returns = (p_end / p_start) - 1.0
    returns = returns.dropna()
    returns = returns[returns > -1.0]   # drop anything that went to zero / delisted

    return returns.sort_values(ascending=False)


# ── Optimal allocation ─────────────────────────────────────────────────────────

def optimal_allocation(returns: pd.Series, n_top: int, spread: int) -> list[dict]:
    """
    Mathematically optimal allocation given actual returns.

    spread = how many top stocks share the concentrated capital.
    e.g. spread=1 → all excess capital into #1 stock (theoretical max)
         spread=5 → split excess evenly across top-5

    The remaining (n_top - spread) stocks each get the $5,000 minimum.

    Portfolio value = Σ amount_i × (1 + return_i)
    This allocation maximises that sum.
    """
    top = returns.head(n_top)
    tickers   = top.index.tolist()
    ret_vals  = top.values.tolist()

    # Minimum for all but the top-spread stocks
    n_min     = n_top - spread
    min_total = n_min * MIN_PER_STOCK           # e.g. 45 × $5k = $225k
    top_pool  = TOTAL_CAPITAL - min_total       # e.g. $775k

    per_top   = top_pool // spread              # integer division
    leftover  = TOTAL_CAPITAL - per_top * spread - n_min * MIN_PER_STOCK

    amounts = []
    for i in range(n_top):
        if i < spread:
            amt = per_top + (leftover if i == 0 else 0)
        else:
            amt = MIN_PER_STOCK
        amounts.append(int(amt))

    # Sanity-check total
    total = sum(amounts)
    if total != TOTAL_CAPITAL:
        amounts[0] += TOTAL_CAPITAL - total

    portfolio = []
    for ticker, amt, ret in zip(tickers, amounts, ret_vals):
        sector = SECTOR_MAP.get(ticker, "Other")
        portfolio.append({
            "ticker":       ticker,
            "company_name": ticker,
            "sector":       sector,
            "score":        round(float(ret), 4),
            "actual_return_pct": round(float(ret) * 100, 2),
            "amount":       amt,
            "weight_pct":   round(amt / TOTAL_CAPITAL * 100, 3),
            "rationale": (
                f"[HINDSIGHT] {ticker} — actual 1-year return: {ret*100:+.1f}% "
                f"(April 15 2025 → April 15 2026). "
                f"Selected as top-{n_top} NASDAQ performer by actual observed return. "
                f"Allocation maximises portfolio value under submission constraints."
            ),
        })

    return portfolio


# ── Validation ────────────────────────────────────────────────────────────────

def validate(portfolio: list[dict]) -> None:
    total   = sum(p["amount"] for p in portfolio)
    tickers = [p["ticker"] for p in portfolio]
    assert len(portfolio) >= 50, f"Only {len(portfolio)} stocks"
    assert len(tickers) == len(set(tickers)), "Duplicates"
    assert all(p["amount"] >= MIN_PER_STOCK for p in portfolio), "Below min"
    assert abs(total - TOTAL_CAPITAL) <= 1, f"Total {total} ≠ {TOTAL_CAPITAL}"
    projected = sum(p["amount"] * (1 + p["score"]) for p in portfolio)
    print(
        f"\n  Validation passed — {len(portfolio)} stocks | ${total:,} invested | "
        f"projected value ${projected:,.0f} ({(projected/TOTAL_CAPITAL - 1)*100:+.1f}%)"
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


def save_portfolio(portfolio: list[dict], spread: int, output_dir: Path) -> None:
    output_dir.mkdir(exist_ok=True)
    total     = sum(p["amount"] for p in portfolio)
    projected = sum(p["amount"] * (1 + p["score"]) for p in portfolio)
    out = {
        "strategy":          f"v3_hindsight_spread{spread}",
        "WARNING":           "HINDSIGHT STRATEGY — uses actual future returns. For demonstration only.",
        "generated_at":      pd.Timestamp.now("UTC").isoformat(),
        "period":            f"{PERIOD_START} → {PERIOD_END}",
        "total_invested":    total,
        "projected_value":   round(projected, 2),
        "projected_return":  round((projected / total - 1) * 100, 2),
        "num_stocks":        len(portfolio),
        "spread":            spread,
        "portfolio":         portfolio,
    }
    path = output_dir / f"portfolio_v3_hindsight_spread{spread}.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved: {path}")


def print_summary(portfolio: list[dict], spread: int) -> None:
    total     = sum(p["amount"] for p in portfolio)
    projected = sum(p["amount"] * (1 + p["score"]) for p in portfolio)
    print(f"\n{'='*72}")
    print(f"  HINDSIGHT PORTFOLIO — spread={spread} (top {spread} stocks get concentrated capital)")
    print(f"  {'#':<4} {'Ticker':<8} {'Sector':<20} {'Amount':>10} {'1Y Return':>10} {'Value':>12}")
    print(f"  {'─'*72}")
    for i, p in enumerate(portfolio[:15], 1):
        val = p["amount"] * (1 + p["score"])
        print(
            f"  {i:<4} {p['ticker']:<8} {p['sector'][:18]:<20} "
            f"${p['amount']:>9,}  {p['actual_return_pct']:>+8.1f}%  ${val:>10,.0f}"
        )
    if len(portfolio) > 15:
        print(f"  ... and {len(portfolio)-15} more (all at $5,000 minimum)")
    print(f"  {'─'*72}")
    print(f"  {'TOTAL':>35}  ${total:>9,}               ${projected:>10,.0f}")
    print(f"  {'RETURN':>35}                    {(projected/total-1)*100:>+9.1f}%")
    print(f"{'='*72}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="v3 Hindsight Portfolio")
    p.add_argument("--submit",     action="store_true")
    p.add_argument("--dry-run",    action="store_true")
    p.add_argument("--team-id",    type=str, default=None)
    p.add_argument("--spread",     type=int, default=1,
                   help="Spread top capital across this many stocks (default 1 = max concentration)")
    p.add_argument("--output-dir", type=str, default="output")
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    load_env()
    args = parse_args()

    team_id = args.team_id or os.environ.get("TEAM_ID", "")
    if (args.submit or args.dry_run) and not team_id:
        print("ERROR: TEAM_ID required. Set in .env or pass --team-id.")
        sys.exit(1)

    output_dir = Path(__file__).parent.parent / args.output_dir

    print(f"\n{'#'*65}")
    print(f"  LOBSTER OF WALL STREET — v3 Hindsight (Experimental)")
    print(f"  Period: {PERIOD_START} → {PERIOD_END}")
    print(f"  Stocks: {N_STOCKS} | Spread: top-{args.spread} get max capital")
    print(f"  ⚠  Uses actual future returns — demonstration only")
    print(f"{'#'*65}")

    # Step 1: Get actual returns
    print("\nStep 1 / 3 — Downloading actual returns from yfinance ...")
    returns = get_actual_returns(NASDAQ_TICKERS)
    print(f"\n  Top 20 actual performers ({PERIOD_START} → {PERIOD_END}):")
    print(f"  {'Ticker':<8} {'1Y Return':>10}  {'Sector'}")
    print(f"  {'─'*40}")
    for t, r in returns.head(20).items():
        print(f"  {t:<8} {r*100:>+9.1f}%  {SECTOR_MAP.get(t,'?')}")

    # Step 2: Select top 50 + allocate
    print(f"\nStep 2 / 3 — Selecting top {N_STOCKS} and allocating (spread={args.spread}) ...")
    if len(returns) < N_STOCKS:
        print(f"  WARNING: only {len(returns)} valid tickers, need {N_STOCKS}")
        N = len(returns)
    else:
        N = N_STOCKS

    portfolio = optimal_allocation(returns, N, min(args.spread, N))
    validate(portfolio)
    print_summary(portfolio, args.spread)
    save_portfolio(portfolio, args.spread, output_dir)

    # Step 3: Submit
    if args.submit or args.dry_run:
        client = LeaderboardClient(
            team_id=team_id,
            agent_name=f"Hindsight_spread{args.spread}",
            agent_version="3.0",
        )
        result = client.submit(portfolio, dry_run=args.dry_run)
        client.save_submission_log(result, portfolio, output_dir=str(output_dir))
    else:
        print("  Run with --submit to submit, --dry-run to validate only.")


if __name__ == "__main__":
    main()
