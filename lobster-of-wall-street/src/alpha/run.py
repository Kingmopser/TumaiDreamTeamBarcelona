#!/usr/bin/env python3
"""
v6 — Alpha Agent: Tail-Event Capture System with Explainability
───────────────────────────────────────────────────────────────

FULLY PROGRAMMATIC — no hardcoded tickers or fundamentals.

Pipeline:
  0. Download ALL NASDAQ tickers from nasdaqtrader.com (~5,400)
  1. Filter to common stocks + leveraged ETFs (~3,500)
  2. Download pre-cutoff price data from yfinance
  3. Compute 17 technical features
  4. Screen for high-convexity candidates
  5. Fetch yfinance .info for sector + fundamentals (~200 tickers)
  6. Monte Carlo search over 500 weight combinations
  7. Score: convexity × sector × quality
  8. Cala AI enrichment
  9. Conviction-weighted allocation
  10. Submit

Usage:
  python -m alpha.run                    # compute + save
  python -m alpha.run --submit           # submit to leaderboard
  python -m alpha.run --full-cala        # aggressive Cala usage
  python -m alpha.run --skip-cala        # skip Cala API
"""

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha.data import build_universe, download_prices, fetch_sector_info, DATA_CUTOFF
from alpha.features import compute_features
from alpha.scoring import compute_convexity_scores, compute_final_scores, derive_sector_multipliers
from alpha.search import run_search
from alpha.cala import enrich_with_cala
from alpha.thesis import discover_thesis, get_thesis_industries
from alpha.allocator import search_best_allocation
from alpha.explain import generate_rationale
from leaderboard_client import LeaderboardClient

TOTAL_CAPITAL = 1_000_000
MIN_PER_STOCK = 5_000

# ── Screening thresholds ──────────────────────────────────────────────────────
MIN_DRAWDOWN  = 0.30    # must be >30% below 52-week high
MAX_PRICE     = 150.0   # focus on small/mid caps
MIN_AVG_VOL   = 5_000   # minimum liquidity


def load_env():
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def validate(portfolio):
    total = sum(p["amount"] for p in portfolio)
    tickers = [p["ticker"] for p in portfolio]
    assert len(portfolio) >= 50
    assert len(tickers) == len(set(tickers))
    assert all(p["amount"] >= MIN_PER_STOCK for p in portfolio)
    assert abs(total - TOTAL_CAPITAL) <= 1
    print(f"\n  Validation OK: {len(portfolio)} stocks, ${total:,}")


def save_portfolio(portfolio, output_dir):
    output_dir.mkdir(exist_ok=True)
    total = sum(p["amount"] for p in portfolio)
    out = {
        "strategy": "v6_alpha_agent",
        "description": (
            "Tail-event capture system. Universe: ALL NASDAQ tickers downloaded "
            "from nasdaqtrader.com (no hand-picking). Screened via convexity "
            "scoring (volatility, gap frequency, drawdown, momentum acceleration). "
            "Monte Carlo search over 500 weight combos. Fundamentals from yfinance. "
            "Cala AI enrichment. Conviction-weighted allocation."
        ),
        "data_cutoff": str(DATA_CUTOFF),
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "total_invested": total,
        "num_stocks": len(portfolio),
        "portfolio": portfolio,
    }
    path = output_dir / "portfolio_v6_alpha.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"\n  Saved: {path}")


def print_summary(portfolio):
    total = sum(p["amount"] for p in portfolio)
    print(f"\n{'=' * 85}")
    print(f"  v6 ALPHA AGENT — Tail-Event Capture Portfolio")
    print(f"  Stocks: {len(portfolio)} | Total: ${total:,}")
    print(f"  {'#':<4} {'Tick':<7} {'Layer':<11} {'Sector':<24} "
          f"{'Amount':>10} {'Score':>6} {'DD':>6}")
    print(f"  {'─' * 75}")
    for i, p in enumerate(portfolio[:20], 1):
        sector = p.get("sector", "?")[:22]
        print(
            f"  {i:<4} {p['ticker']:<7} {p['layer']:<11} "
            f"{sector:<24} ${p['amount']:>9,} "
            f"{p['score']:.3f} {p['drawdown_pct']:>+5.0f}%"
        )
    if len(portfolio) > 20:
        print(f"  ... and {len(portfolio) - 20} more")
    print(f"  {'─' * 75}")
    conv = [p for p in portfolio if p["layer"] == "conviction"]
    print(f"  Conviction: {len(conv)} stocks, ${sum(p['amount'] for p in conv):,}")
    print(f"  Constraint: {len(portfolio) - len(conv)} stocks, "
          f"${sum(p['amount'] for p in portfolio if p['layer'] == 'constraint'):,}")
    print(f"{'=' * 85}\n")


def parse_args():
    p = argparse.ArgumentParser(description="v6 Alpha Agent")
    p.add_argument("--submit",    action="store_true")
    p.add_argument("--dry-run",   action="store_true")
    p.add_argument("--skip-cala", action="store_true")
    p.add_argument("--full-cala", action="store_true")
    p.add_argument("--team-id",   type=str, default=None)
    p.add_argument("--trials",    type=int, default=500)
    p.add_argument("--output-dir", type=str, default="output")
    return p.parse_args()


def main():
    load_env()
    args = parse_args()
    team_id = args.team_id or os.environ.get("TEAM_ID", "")
    output_dir = Path(__file__).parent.parent.parent / args.output_dir

    print(f"\n{'#' * 70}")
    print(f"  ALPHA AGENT v6 — Tail-Event Capture System")
    print(f"  Data cutoff: {DATA_CUTOFF} | Trials: {args.trials}")
    print(f"  Universe: FULL NASDAQ (programmatic, no hand-picking)")
    print(f"{'#' * 70}")

    # ── Stage 0: Build universe from NASDAQ ──
    print("\n[Stage 0] Building universe from NASDAQ listed securities ...")
    all_tickers, sector_map = build_universe()

    # ── Stage 1: Download pre-cutoff prices ──
    print(f"\n[Stage 1] Downloading pre-cutoff prices for {len(all_tickers)} tickers ...")
    data = download_prices(all_tickers)

    # ── Stage 2: Feature engineering ──
    print("\n[Stage 2] Computing features ...")
    features = compute_features(data, sector_map)
    print(f"  Raw features: {len(features)} tickers")

    # ── Stage 3: Screening ──
    print("\n[Stage 3] Screening for high-convexity candidates ...")
    mask = (
        (features["cur_dd"].abs() >= MIN_DRAWDOWN) &
        (features["price"] <= MAX_PRICE) &
        (features["avg_vol_20d"] >= MIN_AVG_VOL) &
        (features["vol_60d"] > 0.3)  # must have meaningful volatility
    )
    screened = features[mask].copy()
    print(f"  Passed screen: {len(screened)} / {len(features)}")

    if len(screened) < 50:
        print(f"  WARNING: too few candidates, relaxing filters")
        screened = features.nlargest(200, "vol_60d")

    # ── Stage 4a: Use NASDAQ API sector + country data ──
    print(f"\n[Stage 4a] Applying NASDAQ API sector + country data ...")
    for col in ["yf_sector", "yf_industry", "total_revenue", "book_value", "shares_outstanding"]:
        screened[col] = "" if col.startswith("yf") else 0.0
    screened["country"] = "Unknown"

    # Load country data from NASDAQ API cache
    import json as _json
    from alpha.data import CACHE_DIR
    api_cache = CACHE_DIR / "nasdaq_api.json"
    country_map = {}
    if api_cache.exists():
        for row in _json.loads(api_cache.read_text()):
            country_map[row["symbol"]] = row.get("country", "Unknown") or "Unknown"

    for i, row in screened.iterrows():
        sec = sector_map.get(row["ticker"], "Unknown")
        screened.loc[i, "yf_sector"] = sec
        screened.loc[i, "yf_industry"] = sec
        screened.loc[i, "country"] = country_map.get(row["ticker"], "Unknown")

    # ── Stage 4b: Fetch yfinance .info for all screened candidates ──
    # Reads from cache (pre-populated) — only makes new API calls for misses
    all_screened_tickers = screened["ticker"].tolist()
    print(f"\n[Stage 4b] Loading fundamentals for {len(all_screened_tickers)} screened tickers (from cache) ...")
    info_data = fetch_sector_info(all_screened_tickers, max_workers=3)

    # Merge .info into screened dataframe
    for ticker in screened["ticker"]:
        info = info_data.get(ticker, {})
        if not info:
            continue
        idx = screened.index[screened["ticker"] == ticker]
        if len(idx) == 0:
            continue
        i = idx[0]
        if info.get("sector"):
            screened.loc[i, "yf_sector"] = info["sector"]
        if info.get("industry"):
            screened.loc[i, "yf_industry"] = info["industry"]
        screened.loc[i, "total_revenue"] = info.get("totalRevenue", 0) or 0
        screened.loc[i, "book_value"] = info.get("bookValue", 0) or 0
        screened.loc[i, "shares_outstanding"] = info.get("sharesOutstanding", 0) or 0

    print(f"  Fundamentals enriched for {len(info_data)} tickers")

    # ── Stage 5: Monte Carlo search ──
    print(f"\n[Stage 5] Monte Carlo robustness search ({args.trials} trials) ...")
    search_results = run_search(screened, n_trials=args.trials)
    screened = screened.merge(
        search_results[["ticker", "appearance_count", "avg_rank", "rank_std"]],
        on="ticker", how="left",
    )
    screened["appearance_count"] = screened["appearance_count"].fillna(0)

    # ── Stage 6: Final scoring ──
    print("\n[Stage 6] Final scoring ...")
    scored = compute_convexity_scores(screened)
    sector_mult = derive_sector_multipliers(scored)
    ranked = compute_final_scores(scored, sector_mult)

    print(f"\n  Top 20 by final score:")
    cols = ["ticker", "yf_sector", "yf_industry", "final_score", "convexity",
            "quality", "sector_mult", "cur_dd", "price"]
    for _, r in ranked.head(20).iterrows():
        sect = str(r.get("yf_industry", ""))[:24]
        sz = r.get("size_f", 1.0)
        print(f"    {r['ticker']:<7} {sect:<26} "
              f"F={r['final_score']:.3f} C={r['convexity']:.3f} "
              f"Q={r['quality']:.2f} Sz={sz:.2f} "
              f"DD={r['cur_dd']*100:+.0f}% ${r['price']:.2f}")

    # ── Stage 7: Thesis Discovery via Cala AI ──
    api_key = os.environ.get("CALA_API_KEY", "")
    thesis = {}
    thesis_ind = set()
    if not args.skip_cala:
        print("\n[Stage 7a] Thesis Discovery — Cala AI research ...")
        thesis = discover_thesis(api_key)
        thesis_ind = get_thesis_industries(thesis)
        print(f"\n  Thesis industries: {sorted(thesis_ind)[:8]}")
        print(f"  Summary: {thesis.get('summary', '')[:120]}...")

    # ── Stage 7b: Cala enrichment for top candidates ──
    cala_data = {}
    if not args.skip_cala:
        mode = "FULL" if args.full_cala else "standard"
        print(f"\n[Stage 7b] Cala stock enrichment ({mode}) ...")
        top_tickers = ranked["ticker"].head(100).tolist()
        cala_data = enrich_with_cala(top_tickers, api_key, full_mode=args.full_cala)

    # ── Stage 8: Allocation (thesis-constrained conviction) ──
    print("\n[Stage 8] Portfolio allocation (thesis-constrained conviction) ...")
    if thesis_ind:
        portfolio = search_best_allocation(ranked, n_stocks=50, thesis_industries=thesis_ind)
    else:
        portfolio = search_best_allocation(ranked, n_stocks=50)

    # ── Stage 9: Rationale ──
    print("\n[Stage 9] Generating rationales ...")
    for p in portfolio:
        p["rationale"] = generate_rationale(p, cala_data)

    validate(portfolio)
    print_summary(portfolio)
    save_portfolio(portfolio, output_dir)

    # ── Submit ──
    if args.submit or args.dry_run:
        if not team_id:
            print("ERROR: TEAM_ID required")
            sys.exit(1)
        client = LeaderboardClient(
            team_id=team_id,
            agent_name="AlphaAgent",
            agent_version="6.0",
        )
        result = client.submit(portfolio, dry_run=args.dry_run)
        client.save_submission_log(result, portfolio, output_dir=str(output_dir))


if __name__ == "__main__":
    main()
