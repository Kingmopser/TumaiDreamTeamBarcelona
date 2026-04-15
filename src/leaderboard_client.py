"""
Stage 4: Leaderboard Client
Submits the final portfolio to the Cala leaderboard API.

Leaderboard: https://cala-leaderboard.apps.rebolt.ai/
Registration: https://cala-leaderboard.apps.rebolt.ai/register

NOTE: Check the "Hacker Guide" on the leaderboard site for the exact
submission payload format and endpoint before running. Update SUBMIT_URL
and build_payload() below once you have that information.

Input:  output/portfolio.json
Output: output/submission_log.json
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ── Config — update these after reading the Hacker Guide ──────────────────────
LEADERBOARD_BASE = "https://cala-leaderboard.apps.rebolt.ai"
SUBMIT_URL = f"{LEADERBOARD_BASE}/api/submit"   # placeholder — confirm from Hacker Guide
TEAM_NAME = os.getenv("TEAM_NAME", "TumaiDreamTeam")
TEAM_EMAIL = os.getenv("TEAM_EMAIL", "")


# ── Payload builder ───────────────────────────────────────────────────────────

def build_payload(portfolio: list[dict]) -> dict:
    """
    Build the submission payload.
    Adjust the structure once the Hacker Guide format is confirmed.
    Common formats used in hackathon leaderboards:
      - List of {ticker, amount} objects
      - List of {ticker, shares} objects
      - Dict keyed by ticker
    """
    holdings = [
        {
            "ticker": c["ticker"],
            "amount": c["amount"],        # dollar allocation
            "rationale": c.get("rationale", ""),
        }
        for c in portfolio
    ]

    return {
        "team": TEAM_NAME,
        "email": TEAM_EMAIL,
        "portfolio": holdings,
        "total_amount": sum(c["amount"] for c in portfolio),
        "submitted_at": datetime.utcnow().isoformat() + "Z",
    }


# ── Submission ────────────────────────────────────────────────────────────────

def submit(portfolio: list[dict], dry_run: bool = False) -> dict:
    payload = build_payload(portfolio)

    # Validate before sending
    tickers = [c["ticker"] for c in portfolio]
    assert len(tickers) >= 50, f"Need 50+ stocks, have {len(tickers)}"
    assert len(set(tickers)) == len(tickers), "Duplicate tickers found"
    assert all(c["amount"] >= 5000 for c in portfolio), "Some allocation < $5,000"
    assert sum(c["amount"] for c in portfolio) == 1_000_000, "Total != $1,000,000"

    print(f"  Payload validated: {len(portfolio)} stocks, $1,000,000 total")

    if dry_run:
        print("  DRY RUN — not sending. Payload preview:")
        print(json.dumps(payload, indent=2, default=str)[:1000])
        return {"status": "dry_run", "payload": payload}

    print(f"  Submitting to {SUBMIT_URL} ...")
    resp = requests.post(SUBMIT_URL, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    print(f"  Response: {result}")
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main(dry_run: bool = True):
    print("=" * 60)
    print("STAGE 4: Leaderboard Submission")
    print("=" * 60)

    portfolio_path = OUTPUT_DIR / "portfolio.json"
    if not portfolio_path.exists():
        raise FileNotFoundError("Run stages 1-3 first. Missing: output/portfolio.json")

    portfolio = json.loads(portfolio_path.read_text())
    print(f"\n  Loaded portfolio: {len(portfolio)} stocks")

    result = submit(portfolio, dry_run=dry_run)

    # Log the result
    log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "portfolio_size": len(portfolio),
        "total_allocated": sum(c["amount"] for c in portfolio),
        "result": result,
    }
    log_path = OUTPUT_DIR / "submission_log.json"

    # Append to log (keep history of all submissions)
    history = []
    if log_path.exists():
        try:
            history = json.loads(log_path.read_text())
            if not isinstance(history, list):
                history = [history]
        except Exception:
            history = []
    history.append(log)
    log_path.write_text(json.dumps(history, indent=2, default=str))

    print(f"\n  Submission log saved to: {log_path}")
    return result


if __name__ == "__main__":
    import sys
    # Pass --submit to actually send (default is dry run)
    dry = "--submit" not in sys.argv
    if dry:
        print("  (Add --submit flag to actually send to leaderboard)")
    main(dry_run=dry)
