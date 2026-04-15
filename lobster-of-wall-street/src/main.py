"""
Lobster of Wall Street — Main Pipeline

Orchestrates the full investment agent:
  1. Research Agent  → queries Cala API, scores 100+ NASDAQ companies
  2. Portfolio Allocator → selects top 65 stocks, allocates $1,000,000
  3. Rationale Generator → produces per-stock written justifications
  4. Output + Submission → saves portfolio.json, optionally submits to leaderboard

Usage:
  python main.py                        # Full run, no submission
  python main.py --submit               # Full run + submit to leaderboard
  python main.py --dry-run              # Full run + dry-run submission (validate only)
  python main.py --skip-research        # Skip research (use cached scores), go straight to allocation
  python main.py --submit --team-id my-team-slug
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow importing sibling modules
sys.path.insert(0, str(Path(__file__).parent))

from research_agent import ResearchAgent
from portfolio_allocator import allocate
from rationale_generator import generate_all_rationales
from leaderboard_client import LeaderboardClient


def load_env():
    """Load environment variables from .env file if present."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


def parse_args():
    p = argparse.ArgumentParser(description="Lobster of Wall Street Investment Agent")
    p.add_argument("--submit", action="store_true", help="Submit to leaderboard after building portfolio")
    p.add_argument("--dry-run", action="store_true", help="Validate submission payload without sending")
    p.add_argument("--skip-research", action="store_true", help="Skip Cala API research; use cached scores")
    p.add_argument("--team-id", type=str, help="Override TEAM_ID from .env")
    p.add_argument("--cutoff-date", type=str, default=None, help="Data cutoff date (default: 2025-04-15)")
    p.add_argument("--num-stocks", type=int, default=65, help="Number of stocks to select (min 50)")
    p.add_argument("--output-dir", type=str, default="output", help="Output directory")
    return p.parse_args()


def main():
    load_env()
    args = parse_args()

    api_key = os.environ.get("CALA_API_KEY")
    if not api_key:
        print("ERROR: CALA_API_KEY not set. Add it to .env or set as environment variable.")
        sys.exit(1)

    team_id = args.team_id or os.environ.get("TEAM_ID", "")
    if (args.submit or args.dry_run) and not team_id:
        print("ERROR: TEAM_ID required for submission. Set in .env or pass --team-id.")
        sys.exit(1)

    data_cutoff_date = args.cutoff_date or os.environ.get("DATA_CUTOFF_DATE", "2025-04-15")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"\n{'#'*60}")
    print(f"  🦞 LOBSTER OF WALL STREET — Investment Agent")
    print(f"  Data cutoff: {data_cutoff_date}")
    print(f"  Target stocks: {args.num_stocks}")
    print(f"  Capital: $1,000,000")
    print(f"{'#'*60}\n")

    # ── Step 1: Research ──────────────────────────────────────────────────────
    agent = ResearchAgent(
        api_key=api_key,
        cache_dir=str(Path(__file__).parent.parent / "cache"),
        data_cutoff_date=data_cutoff_date,
    )

    if args.skip_research and (Path(__file__).parent.parent / "cache" / "research_cache.json").exists():
        print("Skipping research phase — loading from cache...")
        cache = agent._load_cache()
        from research_agent import NASDAQ_UNIVERSE, TIER_BASE_SCORES
        research_results = []
        for ticker, company_name, sector, tier in NASDAQ_UNIVERSE:
            entry = cache.get(ticker, {})
            research_results.append({
                "ticker": ticker,
                "company_name": company_name,
                "sector": sector,
                "tier": tier,
                "score": entry.get("score", TIER_BASE_SCORES[tier]),
                "raw_analysis": entry.get("raw_analysis", ""),
                "data_cutoff_date": data_cutoff_date,
            })
        research_results.sort(key=lambda x: x["score"], reverse=True)
    else:
        research_results = agent.run()

    # ── Step 2: Portfolio Allocation ──────────────────────────────────────────
    print("\nAllocating portfolio...")
    portfolio = allocate(research_results, num_stocks=args.num_stocks)

    # ── Step 3: Rationale Generation ──────────────────────────────────────────
    portfolio = generate_all_rationales(
        portfolio,
        api_key=api_key,
        data_cutoff_date=data_cutoff_date,
        max_api_calls=20,  # Cap API calls for rationale generation
    )

    # ── Step 4: Save Output ────────────────────────────────────────────────────
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data_cutoff_date": data_cutoff_date,
        "agent": "CookingLobster",
        "version": "1.0",
        "total_invested": sum(p["amount"] for p in portfolio),
        "num_stocks": len(portfolio),
        "sectors": sorted(set(p["sector"] for p in portfolio)),
        "portfolio": portfolio,
    }

    portfolio_path = output_dir / "portfolio.json"
    with open(portfolio_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ Portfolio saved to: {portfolio_path}")

    # Print summary table
    print(f"\n{'='*70}")
    print(f"{'Rank':<5} {'Ticker':<8} {'Sector':<22} {'Amount':>10} {'Score':>7}")
    print(f"{'─'*70}")
    for i, p in enumerate(portfolio[:20], 1):
        print(f"{i:<5} {p['ticker']:<8} {p['sector']:<22} ${p['amount']:>9,} {p['score']:>6.1f}")
    if len(portfolio) > 20:
        print(f"  ... and {len(portfolio)-20} more positions")
    print(f"{'─'*70}")
    print(f"{'TOTAL':>37}  ${sum(p['amount'] for p in portfolio):>9,}")
    print(f"{'='*70}\n")

    # ── Step 5: Submit (optional) ─────────────────────────────────────────────
    if args.submit or args.dry_run:
        client = LeaderboardClient(
            team_id=team_id,
            agent_name="CookingLobster",
            agent_version="1.0",
        )
        result = client.submit(portfolio, dry_run=args.dry_run)
        client.save_submission_log(result, portfolio, output_dir=str(output_dir))
    else:
        print("Run with --submit to submit to the leaderboard.")
        print("Run with --dry-run to validate the payload without submitting.")


if __name__ == "__main__":
    main()
