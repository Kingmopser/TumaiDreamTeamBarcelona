"""
Main orchestrator — runs the full pipeline end to end:

  Stage 1: research_agent     → collect + score NASDAQ companies from Cala
  Stage 2: portfolio_allocator → allocate $1M across top 55 stocks
  Stage 3: rationale_generator → generate per-stock rationale using Cala + Claude
  Stage 4: leaderboard_client  → submit (dry run by default)

Usage:
  python src/main.py              # full pipeline, dry-run submission
  python src/main.py --submit     # full pipeline + actually submit
  python src/main.py --from 2     # start from stage 2 (reuse existing research)
"""

import argparse
import sys
from pathlib import Path

# Make sure sibling modules are importable
sys.path.insert(0, str(Path(__file__).parent))

import research_agent
import portfolio_allocator
import rationale_generator
import leaderboard_client


def main():
    parser = argparse.ArgumentParser(description="Lobster of Wall Street — full pipeline")
    parser.add_argument("--from", dest="from_stage", type=int, default=1,
                        help="Start from stage N (1-4). Default: 1")
    parser.add_argument("--submit", action="store_true",
                        help="Actually submit to leaderboard (default: dry run)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  LOBSTER OF WALL STREET — Full Pipeline")
    print("=" * 60 + "\n")

    if args.from_stage <= 1:
        print("Running Stage 1: Research Agent")
        research_agent.main()
        print()

    if args.from_stage <= 2:
        print("Running Stage 2: Portfolio Allocator")
        portfolio_allocator.main()
        print()

    if args.from_stage <= 3:
        print("Running Stage 3: Rationale Generator")
        rationale_generator.main()
        print()

    print("Running Stage 4: Leaderboard Submission")
    leaderboard_client.main(dry_run=not args.submit)

    print("\n" + "=" * 60)
    print("  Pipeline complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
