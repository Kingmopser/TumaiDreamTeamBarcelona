#!/usr/bin/env python3
"""
v1_momentum.py — Momentum + Inverse-Volatility Portfolio

First submission: pure quant, no Cala API, uses only yfinance.

────────────────────────────────────────────────────────────────────
SELECTION  (top 55 NASDAQ stocks, cutoff 2025-04-15)
  Composite score = 0.50 × 12M_sharpe_rank
                  + 0.30 × 12M_return_rank
                  + 0.20 × 6M_return_rank

  All ranks normalised 0→1 across the universe.
  Sector cap during selection: max 16 stocks per sector.

ALLOCATION  (inverse-volatility / risk-parity)
  weight_i  =  (1/σ_i) / Σ_j(1/σ_j)
  σ_i       =  252-day annualised daily return std (ending 2025-04-15)

  Position bounds:  $5 000 ≤ position ≤ $50 000
  Sector cap:       ≤ $300 000 (30 %) per sector
  Total:            exactly $1 000 000

Why inverse-vol?
  Each stock contributes equal risk — classic risk-parity principle.
  Combined with momentum selection this rewards stable compounders and
  naturally down-weights speculative, volatile names.
────────────────────────────────────────────────────────────────────

Usage:
  python src/v1_momentum.py                   # compute + save portfolio.json
  python src/v1_momentum.py --dry-run         # validate payload, no submit
  python src/v1_momentum.py --submit          # compute + submit
  python src/v1_momentum.py --team-id SLUG    # override team id from .env
  python src/v1_momentum.py --num-stocks 60   # change stock count (≥50)
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
CUTOFF_DATE    = date(2025, 4, 15)   # hackathon "today" — no data after this
TOTAL_CAPITAL  = 1_000_000
MIN_PER_STOCK  = 5_000
MAX_PER_STOCK  = 50_000
TARGET_STOCKS  = 55                  # slightly above 50 minimum
SECTOR_CAP_N   = 16                  # max stocks per sector in selection
SECTOR_CAP_USD = 300_000             # max $ per sector in allocation (30 %)
VOL_WINDOW     = 252                 # trading days for volatility calc
TRADING_DAYS   = 252                 # annualisation factor

# ── NASDAQ Universe ────────────────────────────────────────────────────────────
# (ticker, full_name, sector)
# Only NASDAQ-listed stocks. Grouped by sector for readability.
NASDAQ_UNIVERSE = [
    # ── Semiconductors / AI hardware ─────────────────────────────────────────
    ("NVDA",  "NVIDIA",                    "Semiconductors"),
    ("AVGO",  "Broadcom",                  "Semiconductors"),
    ("AMD",   "Advanced Micro Devices",    "Semiconductors"),
    ("QCOM",  "Qualcomm",                  "Semiconductors"),
    ("AMAT",  "Applied Materials",         "Semiconductors"),
    ("LRCX",  "Lam Research",              "Semiconductors"),
    ("KLAC",  "KLA Corporation",           "Semiconductors"),
    ("MU",    "Micron Technology",         "Semiconductors"),
    ("ADI",   "Analog Devices",            "Semiconductors"),
    ("TXN",   "Texas Instruments",         "Semiconductors"),
    ("MRVL",  "Marvell Technology",        "Semiconductors"),
    ("MPWR",  "Monolithic Power Systems",  "Semiconductors"),
    ("ON",    "ON Semiconductor",          "Semiconductors"),
    ("MCHP",  "Microchip Technology",      "Semiconductors"),
    ("NXPI",  "NXP Semiconductors",        "Semiconductors"),
    ("SNPS",  "Synopsys",                  "Semiconductors"),
    ("CDNS",  "Cadence Design Systems",    "Semiconductors"),
    ("SMCI",  "Super Micro Computer",      "Semiconductors"),
    ("INTC",  "Intel",                     "Semiconductors"),

    # ── Large-cap technology ──────────────────────────────────────────────────
    ("AAPL",  "Apple",                     "Technology"),
    ("MSFT",  "Microsoft",                 "Technology"),
    ("GOOGL", "Alphabet",                  "Technology"),
    ("META",  "Meta Platforms",            "Technology"),
    ("AMZN",  "Amazon",                    "Technology"),
    ("CSCO",  "Cisco",                     "Technology"),
    ("ANET",  "Arista Networks",           "Technology"),
    ("ADBE",  "Adobe",                     "Technology"),
    ("INTU",  "Intuit",                    "Technology"),
    ("ANSS",  "ANSYS",                     "Technology"),
    ("VRSK",  "Verisk Analytics",          "Technology"),
    ("CDW",   "CDW Corporation",           "Technology"),

    # ── Cloud & enterprise software ───────────────────────────────────────────
    ("WDAY",  "Workday",                   "Cloud Software"),
    ("DDOG",  "Datadog",                   "Cloud Software"),
    ("OKTA",  "Okta",                      "Cloud Software"),
    ("MDB",   "MongoDB",                   "Cloud Software"),
    ("TEAM",  "Atlassian",                 "Cloud Software"),
    ("MNDY",  "monday.com",                "Cloud Software"),
    ("PAYC",  "Paycom Software",           "Cloud Software"),
    ("PCTY",  "Paylocity",                 "Cloud Software"),
    ("ZM",    "Zoom",                      "Cloud Software"),
    ("DOCU",  "DocuSign",                  "Cloud Software"),

    # ── Cybersecurity ─────────────────────────────────────────────────────────
    ("PANW",  "Palo Alto Networks",        "Cybersecurity"),
    ("CRWD",  "CrowdStrike",               "Cybersecurity"),
    ("FTNT",  "Fortinet",                  "Cybersecurity"),
    ("ZS",    "Zscaler",                   "Cybersecurity"),
    ("CHKP",  "Check Point Software",      "Cybersecurity"),

    # ── Consumer technology & e-commerce ─────────────────────────────────────
    ("TSLA",  "Tesla",                     "Consumer Tech"),
    ("NFLX",  "Netflix",                   "Consumer Tech"),
    ("PYPL",  "PayPal",                    "Consumer Tech"),
    ("MELI",  "MercadoLibre",              "Consumer Tech"),
    ("BKNG",  "Booking Holdings",          "Consumer Tech"),
    ("EXPE",  "Expedia",                   "Consumer Tech"),
    ("EBAY",  "eBay",                      "Consumer Tech"),
    ("ETSY",  "Etsy",                      "Consumer Tech"),
    ("TTD",   "The Trade Desk",            "Consumer Tech"),
    ("ABNB",  "Airbnb",                    "Consumer Tech"),
    ("TTWO",  "Take-Two Interactive",      "Consumer Tech"),

    # ── Biotech / healthcare ──────────────────────────────────────────────────
    ("AMGN",  "Amgen",                     "Biotech/Healthcare"),
    ("GILD",  "Gilead Sciences",           "Biotech/Healthcare"),
    ("REGN",  "Regeneron",                 "Biotech/Healthcare"),
    ("VRTX",  "Vertex Pharmaceuticals",    "Biotech/Healthcare"),
    ("BIIB",  "Biogen",                    "Biotech/Healthcare"),
    ("MRNA",  "Moderna",                   "Biotech/Healthcare"),
    ("IDXX",  "IDEXX Laboratories",        "Biotech/Healthcare"),
    ("ISRG",  "Intuitive Surgical",        "Biotech/Healthcare"),
    ("ALGN",  "Align Technology",          "Biotech/Healthcare"),
    ("DXCM",  "DexCom",                    "Biotech/Healthcare"),
    ("GEHC",  "GE HealthCare",             "Biotech/Healthcare"),
    ("IONS",  "Ionis Pharmaceuticals",     "Biotech/Healthcare"),
    ("INCY",  "Incyte",                    "Biotech/Healthcare"),
    ("ALNY",  "Alnylam Pharmaceuticals",   "Biotech/Healthcare"),

    # ── Consumer & retail ─────────────────────────────────────────────────────
    ("COST",  "Costco",                    "Consumer/Retail"),
    ("SBUX",  "Starbucks",                 "Consumer/Retail"),
    ("MNST",  "Monster Beverage",          "Consumer/Retail"),
    ("PEP",   "PepsiCo",                   "Consumer/Retail"),
    ("DLTR",  "Dollar Tree",               "Consumer/Retail"),
    ("ULTA",  "Ulta Beauty",               "Consumer/Retail"),
    ("KHC",   "Kraft Heinz",               "Consumer/Retail"),
    ("MDLZ",  "Mondelez",                  "Consumer/Retail"),
    ("KDP",   "Keurig Dr Pepper",          "Consumer/Retail"),
    ("ORLY",  "O'Reilly Automotive",       "Consumer/Retail"),

    # ── Financials / fintech ──────────────────────────────────────────────────
    ("NDAQ",  "Nasdaq Inc.",               "Financials/Fintech"),
    ("IBKR",  "Interactive Brokers",       "Financials/Fintech"),
    ("COIN",  "Coinbase",                  "Financials/Fintech"),
    ("HOOD",  "Robinhood",                 "Financials/Fintech"),
    ("MKTX",  "MarketAxess",               "Financials/Fintech"),
    ("LPLA",  "LPL Financial",             "Financials/Fintech"),
    ("AFRM",  "Affirm",                    "Financials/Fintech"),

    # ── Industrials / business services ──────────────────────────────────────
    ("FAST",  "Fastenal",                  "Industrials"),
    ("PAYX",  "Paychex",                   "Industrials"),
    ("ADP",   "ADP",                       "Industrials"),
    ("CTAS",  "Cintas",                    "Industrials"),
    ("ODFL",  "Old Dominion Freight",      "Industrials"),
    ("CPRT",  "Copart",                    "Industrials"),
    ("PCAR",  "PACCAR",                    "Industrials"),
    ("FICO",  "FICO",                      "Industrials"),
    ("AXON",  "Axon Enterprise",           "Industrials"),

    # ── Telecom / media ───────────────────────────────────────────────────────
    ("TMUS",  "T-Mobile US",               "Telecom/Media"),
    ("CMCSA", "Comcast",                   "Telecom/Media"),
    ("CHTR",  "Charter Communications",    "Telecom/Media"),
    ("SIRI",  "Sirius XM",                 "Telecom/Media"),

    # ── Clean energy ──────────────────────────────────────────────────────────
    ("FSLR",  "First Solar",               "Clean Energy"),
    ("ENPH",  "Enphase Energy",            "Clean Energy"),
    ("CEG",   "Constellation Energy",      "Clean Energy"),
    ("EXC",   "Exelon",                    "Clean Energy"),

    # ── AI / data platforms ───────────────────────────────────────────────────
    ("PLTR",  "Palantir",                  "AI/Data"),
    ("APP",   "AppLovin",                  "AI/Data"),
]


# ── Data download ──────────────────────────────────────────────────────────────

def download_prices(tickers: list[str], cutoff: date) -> pd.DataFrame:
    """
    Download adjusted-close prices for all tickers via yfinance.
    End date = cutoff + 1 day (yfinance end is exclusive).
    Start date = 2 years before cutoff (enough for 12M signals + vol window).
    Returns a DataFrame of adjusted close prices, columns = tickers.
    Missing tickers (delisted / no data) are silently dropped.
    """
    start = (cutoff - timedelta(days=730)).isoformat()   # 2 years back
    end   = (cutoff + timedelta(days=1)).isoformat()     # inclusive cutoff

    print(f"  Downloading {len(tickers)} tickers from {start} to {cutoff} ...")

    # Download in batches of 50 to avoid yfinance query limits
    batch_size = 50
    dfs = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        raw = yf.download(
            batch,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if raw.empty:
            continue
        # yfinance returns MultiIndex columns when multiple tickers
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw[["Close"]].rename(columns={"Close": batch[0]})
        dfs.append(closes)
        print(f"  Batch {i//batch_size + 1}: {len(batch)} tickers OK")

    if not dfs:
        raise RuntimeError("No price data downloaded — check internet / yfinance.")

    prices = pd.concat(dfs, axis=1)
    prices = prices.sort_index()

    # Drop tickers with fewer than 200 valid trading days (insufficient history)
    valid_cols = prices.columns[prices.notna().sum() >= 200].tolist()
    dropped = set(prices.columns) - set(valid_cols)
    if dropped:
        print(f"  Dropped {len(dropped)} tickers with insufficient history: {sorted(dropped)}")
    prices = prices[valid_cols]

    return prices


# ── Signal computation ─────────────────────────────────────────────────────────

def compute_signals(prices: pd.DataFrame, cutoff: date) -> pd.DataFrame:
    """
    For each ticker compute:
      ret12m   — price return April 15 2024 → April 15 2025
      ret6m    — price return Oct 15 2024 → April 15 2025
      vol252   — 252-day annualised daily return std (ending cutoff)
      sharpe12 — ret12m / vol252 (annualised Sharpe, rf=0 for simplicity)

    Returns a DataFrame with one row per ticker and these four columns.
    """
    # Find the nearest available trading days for each anchor date
    cutoff_ts      = pd.Timestamp(cutoff)
    anchor_12m_ts  = pd.Timestamp(cutoff - timedelta(days=365))
    anchor_6m_ts   = pd.Timestamp(cutoff - timedelta(days=183))

    def nearest_prior(ts: pd.Timestamp, index: pd.DatetimeIndex) -> pd.Timestamp:
        """Return the latest index date <= ts."""
        candidates = index[index <= ts]
        if len(candidates) == 0:
            raise ValueError(f"No trading day on or before {ts}")
        return candidates[-1]

    idx = prices.index
    t0  = nearest_prior(cutoff_ts, idx)
    t12 = nearest_prior(anchor_12m_ts, idx)
    t6  = nearest_prior(anchor_6m_ts, idx)

    print(f"  Anchor dates — cutoff: {t0.date()}  12M ago: {t12.date()}  6M ago: {t6.date()}")

    # Daily log returns (last VOL_WINDOW days before cutoff)
    recent = prices[prices.index <= t0].tail(VOL_WINDOW + 1)
    log_rets = np.log(recent / recent.shift(1)).dropna()

    records = []
    for ticker in prices.columns:
        p_end = prices.loc[t0, ticker]
        p_12m = prices.loc[t12, ticker]
        p_6m  = prices.loc[t6, ticker]

        if pd.isna(p_end) or pd.isna(p_12m) or pd.isna(p_6m):
            continue
        if p_12m <= 0 or p_6m <= 0 or p_end <= 0:
            continue

        r12  = (p_end / p_12m) - 1.0
        r6   = (p_end / p_6m) - 1.0
        rets = log_rets[ticker].dropna()
        if len(rets) < 60:
            continue
        vol  = float(rets.std() * np.sqrt(TRADING_DAYS))

        sharpe = r12 / vol if vol > 0 else 0.0

        records.append({
            "ticker":   ticker,
            "ret12m":   r12,
            "ret6m":    r6,
            "vol252":   vol,
            "sharpe12": sharpe,
        })

    signals = pd.DataFrame(records).set_index("ticker")
    print(f"  Computed signals for {len(signals)} tickers")
    return signals


def rank_signals(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise each signal to a 0→1 rank across the universe (percentile rank).
    Composite score = 0.50 × sharpe_rank + 0.30 × ret12m_rank + 0.20 × ret6m_rank
    """
    s = signals.copy()
    # pct_rank: fraction of values ≤ this one → range (0, 1], higher is better
    s["sharpe_rank"]  = s["sharpe12"].rank(pct=True)
    s["ret12m_rank"]  = s["ret12m"].rank(pct=True)
    s["ret6m_rank"]   = s["ret6m"].rank(pct=True)
    s["score"] = (
        0.50 * s["sharpe_rank"]
      + 0.30 * s["ret12m_rank"]
      + 0.20 * s["ret6m_rank"]
    )
    return s.sort_values("score", ascending=False)


# ── Stock selection ────────────────────────────────────────────────────────────

def select_stocks(
    ranked: pd.DataFrame,
    universe_meta: dict[str, tuple],   # ticker → (name, sector)
    n: int,
) -> list[dict]:
    """
    Greedily pick top-n stocks by composite score,
    enforcing a max of SECTOR_CAP_N stocks per sector.
    """
    sector_count: dict[str, int] = {}
    selected = []

    for ticker, row in ranked.iterrows():
        if ticker not in universe_meta:
            continue
        name, sector = universe_meta[ticker]
        count = sector_count.get(sector, 0)
        if count >= SECTOR_CAP_N:
            continue
        selected.append({
            "ticker":       ticker,
            "company_name": name,
            "sector":       sector,
            "score":        round(float(row["score"]), 4),
            "ret12m":       round(float(row["ret12m"]), 4),
            "ret6m":        round(float(row["ret6m"]), 4),
            "vol252":       round(float(row["vol252"]), 4),
            "sharpe12":     round(float(row["sharpe12"]), 4),
        })
        sector_count[sector] = count + 1
        if len(selected) >= n:
            break

    # Safety: if sector caps prevented reaching n, relax and fill remaining
    if len(selected) < n:
        selected_tickers = {s["ticker"] for s in selected}
        for ticker, row in ranked.iterrows():
            if ticker in selected_tickers or ticker not in universe_meta:
                continue
            name, sector = universe_meta[ticker]
            selected.append({
                "ticker":       ticker,
                "company_name": name,
                "sector":       sector,
                "score":        round(float(row["score"]), 4),
                "ret12m":       round(float(row["ret12m"]), 4),
                "ret6m":        round(float(row["ret6m"]), 4),
                "vol252":       round(float(row["vol252"]), 4),
                "sharpe12":     round(float(row["sharpe12"]), 4),
            })
            if len(selected) >= n:
                break

    return selected


# ── Allocation engine ──────────────────────────────────────────────────────────

def _inv_vol_weights(vols: np.ndarray) -> np.ndarray:
    """Inverse-volatility weights, normalised to sum to 1."""
    inv = 1.0 / np.maximum(vols, 1e-6)
    return inv / inv.sum()


def _apply_sector_cap(candidates: list[dict], amounts: np.ndarray) -> np.ndarray:
    """
    Scale down any sector whose total allocation > SECTOR_CAP_USD.
    Redistribute excess proportionally to under-weight sectors.
    """
    amounts = amounts.copy()
    sector_indices: dict[str, list[int]] = {}
    for i, c in enumerate(candidates):
        sector_indices.setdefault(c["sector"], []).append(i)

    for sector, idxs in sector_indices.items():
        total = amounts[idxs].sum()
        if total > SECTOR_CAP_USD:
            scale = SECTOR_CAP_USD / total
            amounts[idxs] *= scale
            excess = total - SECTOR_CAP_USD
            other = [i for i in range(len(amounts)) if i not in idxs]
            if other:
                add = excess / len(other)
                amounts[other] = np.minimum(amounts[other] + add, MAX_PER_STOCK)

    return amounts


def _enforce_bounds(
    amounts: np.ndarray, vols: np.ndarray, max_iter: int = 60
) -> np.ndarray:
    """
    Iteratively clip allocations to [MIN, MAX] and redistribute
    the excess/deficit back into unconstrained positions using
    inverse-vol proportions.
    """
    amounts = amounts.copy()
    for _ in range(max_iter):
        below = amounts < MIN_PER_STOCK
        above = amounts > MAX_PER_STOCK
        if not np.any(below) and not np.any(above):
            break

        # Fix out-of-bounds positions
        deficit = np.maximum(MIN_PER_STOCK - amounts, 0.0)[below].sum()
        surplus = np.maximum(amounts - MAX_PER_STOCK, 0.0)[above].sum()
        amounts[below] = float(MIN_PER_STOCK)
        amounts[above] = float(MAX_PER_STOCK)

        net = surplus - deficit
        if abs(net) < 0.01:
            break

        # Redistribute net to unconstrained positions weighted by inv-vol
        free = ~(below | above)
        if not np.any(free):
            break
        free_weights = _inv_vol_weights(vols[free])
        amounts[free] += free_weights * net

    return amounts


def allocate(candidates: list[dict]) -> list[dict]:
    """
    Build the final portfolio from selected candidates.

    Steps:
      1. Compute inverse-volatility weights
      2. Scale to TOTAL_CAPITAL
      3. Apply sector dollar cap
      4. Enforce per-stock bounds iteratively
      5. Re-normalise to exactly TOTAL_CAPITAL
      6. Round to whole dollars + fix residual on largest position
    """
    vols    = np.array([c["vol252"] for c in candidates])
    weights = _inv_vol_weights(vols)
    amounts = weights * TOTAL_CAPITAL

    # Apply sector cap
    amounts = _apply_sector_cap(candidates, amounts)

    # Enforce per-stock bounds (iterative)
    amounts = _enforce_bounds(amounts, vols)

    # Final normalisation to exactly $1,000,000
    amounts = amounts * (TOTAL_CAPITAL / amounts.sum())

    # Round to integers and fix residual
    int_amounts = np.round(amounts).astype(int)
    residual = TOTAL_CAPITAL - int_amounts.sum()
    max_idx  = int(np.argmax(int_amounts))
    int_amounts[max_idx] += residual

    # Build output records
    portfolio = []
    for i, c in enumerate(candidates):
        amt = int(int_amounts[i])
        portfolio.append({
            **c,
            "amount":     amt,
            "weight_pct": round(amt / TOTAL_CAPITAL * 100, 3),
            "rationale":  _rationale(c, amt),
        })

    portfolio.sort(key=lambda x: x["amount"], reverse=True)
    return portfolio


def _rationale(c: dict, amount: int) -> str:
    """Short, data-driven rationale for each position."""
    return (
        f"[{c['ticker']}] {c['company_name']} — {c['sector']} | "
        f"12M return: {c['ret12m']:+.1%}, 6M return: {c['ret6m']:+.1%}, "
        f"annualised vol: {c['vol252']:.1%}, Sharpe(12M): {c['sharpe12']:.2f}. "
        f"Momentum composite rank score: {c['score']:.4f}. "
        f"Allocated ${amount:,} via inverse-volatility risk-parity weighting."
    )


# ── Validation ─────────────────────────────────────────────────────────────────

def validate(portfolio: list[dict]) -> None:
    total   = sum(p["amount"] for p in portfolio)
    tickers = [p["ticker"] for p in portfolio]
    assert len(portfolio) >= 50, f"Only {len(portfolio)} stocks (need ≥50)"
    assert len(tickers) == len(set(tickers)), "Duplicate tickers"
    assert all(p["amount"] >= MIN_PER_STOCK for p in portfolio), (
        f"Positions below $5k: {[(p['ticker'], p['amount']) for p in portfolio if p['amount'] < MIN_PER_STOCK]}"
    )
    assert abs(total - TOTAL_CAPITAL) <= 1, f"Total {total:,} ≠ {TOTAL_CAPITAL:,}"
    print(
        f"\n  Validation passed: {len(portfolio)} stocks, "
        f"${total:,} total, "
        f"min=${min(p['amount'] for p in portfolio):,}, "
        f"max=${max(p['amount'] for p in portfolio):,}, "
        f"{len(set(p['sector'] for p in portfolio))} sectors"
    )


# ── I/O helpers ────────────────────────────────────────────────────────────────

def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


def save_portfolio(portfolio: list[dict], output_dir: Path) -> Path:
    output_dir.mkdir(exist_ok=True)
    out = {
        "strategy":        "v1_momentum_inverse_vol",
        "generated_at":    pd.Timestamp.utcnow().isoformat() + "Z",
        "data_cutoff_date": CUTOFF_DATE.isoformat(),
        "agent":           "MomentumV1",
        "version":         "1.0",
        "total_invested":  sum(p["amount"] for p in portfolio),
        "num_stocks":      len(portfolio),
        "sectors":         sorted(set(p["sector"] for p in portfolio)),
        "portfolio":       portfolio,
    }
    path = output_dir / "portfolio.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Portfolio saved: {path}")
    return path


def print_summary(portfolio: list[dict]) -> None:
    total = sum(p["amount"] for p in portfolio)
    print(f"\n{'='*80}")
    print(f"  {'Rank':<5}{'Ticker':<8}{'Company':<28}{'Sector':<22}{'Amount':>9}{'Score':>7}{'12M Ret':>9}{'Sharpe':>8}")
    print(f"  {'─'*80}")
    for i, p in enumerate(portfolio[:20], 1):
        print(
            f"  {i:<5}{p['ticker']:<8}{p['company_name'][:26]:<28}"
            f"{p['sector'][:20]:<22}${p['amount']:>8,}"
            f"  {p['score']:.3f}  {p['ret12m']:>+7.1%}  {p['sharpe12']:>5.2f}"
        )
    if len(portfolio) > 20:
        print(f"  ... and {len(portfolio)-20} more positions")
    print(f"  {'─'*80}")
    print(f"  {'TOTAL':>41}  ${total:>9,}")
    print(f"{'='*80}\n")

    # Sector breakdown
    sector_totals: dict[str, int] = {}
    for p in portfolio:
        sector_totals[p["sector"]] = sector_totals.get(p["sector"], 0) + p["amount"]
    print("  Sector allocation:")
    for sector, amt in sorted(sector_totals.items(), key=lambda x: -x[1]):
        pct = amt / total * 100
        print(f"    {sector:<25}  ${amt:>9,}  ({pct:.1f}%)")
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="v1 Momentum Portfolio")
    p.add_argument("--submit",     action="store_true", help="Submit to leaderboard after building")
    p.add_argument("--dry-run",    action="store_true", help="Validate payload but don't submit")
    p.add_argument("--team-id",    type=str, default=None, help="Override TEAM_ID from .env")
    p.add_argument("--num-stocks", type=int, default=TARGET_STOCKS, help="Number of stocks (≥50)")
    p.add_argument("--output-dir", type=str, default="output", help="Output directory")
    return p.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    load_env()
    args = parse_args()

    if args.num_stocks < 50:
        print("ERROR: --num-stocks must be ≥ 50")
        sys.exit(1)

    team_id = args.team_id or os.environ.get("TEAM_ID", "")
    if (args.submit or args.dry_run) and not team_id:
        print("ERROR: TEAM_ID required for submission. Set in .env or pass --team-id.")
        sys.exit(1)

    output_dir = Path(__file__).parent.parent / args.output_dir

    print(f"\n{'#'*70}")
    print(f"  LOBSTER OF WALL STREET — v1 Momentum + Inverse-Vol Portfolio")
    print(f"  Data cutoff:  {CUTOFF_DATE}")
    print(f"  Target stocks: {args.num_stocks}")
    print(f"  Capital:      ${TOTAL_CAPITAL:,}")
    print(f"{'#'*70}\n")

    # ── Step 1: Download prices ───────────────────────────────────────────────
    print("Step 1 / 4 — Downloading price data via yfinance ...")
    tickers       = [t for t, _, _ in NASDAQ_UNIVERSE]
    universe_meta = {t: (n, s) for t, n, s in NASDAQ_UNIVERSE}

    prices = download_prices(tickers, CUTOFF_DATE)

    # ── Step 2: Compute momentum signals ─────────────────────────────────────
    print("\nStep 2 / 4 — Computing momentum signals ...")
    signals = compute_signals(prices, CUTOFF_DATE)
    ranked  = rank_signals(signals)

    print(f"\n  Top 15 by composite score:")
    print(f"  {'Ticker':<8}{'Score':>7}{'12M Ret':>10}{'6M Ret':>9}{'Vol':>8}{'Sharpe':>8}")
    print(f"  {'─'*52}")
    for t, row in ranked.head(15).iterrows():
        meta = universe_meta.get(t, ("?", "?"))
        print(
            f"  {t:<8}{row['score']:>7.3f}"
            f"{row['ret12m']:>+10.1%}{row['ret6m']:>+9.1%}"
            f"{row['vol252']:>8.1%}{row['sharpe12']:>8.2f}"
        )

    # ── Step 3: Select stocks ─────────────────────────────────────────────────
    print(f"\nStep 3 / 4 — Selecting top {args.num_stocks} stocks (sector cap ≤{SECTOR_CAP_N}/sector) ...")
    candidates = select_stocks(ranked, universe_meta, args.num_stocks)
    print(f"  Selected {len(candidates)} companies")

    # ── Step 4: Allocate ──────────────────────────────────────────────────────
    print(f"\nStep 4 / 4 — Inverse-volatility allocation ...")
    portfolio = allocate(candidates)
    validate(portfolio)

    print_summary(portfolio)

    # ── Save ──────────────────────────────────────────────────────────────────
    save_portfolio(portfolio, output_dir)

    # ── Submit (optional) ─────────────────────────────────────────────────────
    if args.submit or args.dry_run:
        client = LeaderboardClient(
            team_id=team_id,
            agent_name="MomentumV1",
            agent_version="1.0",
        )
        result = client.submit(portfolio, dry_run=args.dry_run)
        client.save_submission_log(result, portfolio, output_dir=str(output_dir))
    else:
        print("  Run with --submit to submit to the leaderboard.")
        print("  Run with --dry-run to validate the payload without sending.")


if __name__ == "__main__":
    main()
