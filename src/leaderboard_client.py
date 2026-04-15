"""
Stage 4: Leaderboard Client
Submits the final portfolio to the Cala leaderboard API.

Leaderboard:  https://cala-leaderboard.apps.rebolt.ai/
Submit URL:   https://different-cormorant-663.convex.site/api/submit
Hacker Guide: https://cala-leaderboard.apps.rebolt.ai/guide

Payload format (confirmed from Hacker Guide):
  {
    "team_id": "<slug assigned by Cala>",
    "model_agent_name": "<agent name>",
    "model_agent_version": "<version string>",
    "transactions": [{"nasdaq_code": "AAPL", "amount": 50000}, ...]
  }

Input:  output/portfolio.json
Output: output/submission_log.json
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _load_env_var(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val:
        return val.strip()
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return default


# ── Config ─────────────────────────────────────────────────────────────────────
SUBMIT_URL        = "https://different-cormorant-663.convex.site/api/submit"
TEAM_ID           = _load_env_var("TEAM_ID", "tumai-dreamteam")
MODEL_AGENT_NAME  = _load_env_var("MODEL_AGENT_NAME", "LobsterAgent")
MODEL_VERSION     = _load_env_var("MODEL_VERSION", "1.0")


# ── Payload builder ───────────────────────────────────────────────────────────

def build_payload(portfolio: list[dict]) -> dict:
    transactions = [
        {"nasdaq_code": c["ticker"], "amount": c["amount"]}
        for c in portfolio
    ]
    return {
        "team_id":            TEAM_ID,
        "model_agent_name":   MODEL_AGENT_NAME,
        "model_agent_version": MODEL_VERSION,
        "transactions":       transactions,
    }


# ── Submission ────────────────────────────────────────────────────────────────

def submit(portfolio: list[dict], dry_run: bool = False) -> dict:
    payload = build_payload(portfolio)

    tickers = [c["ticker"] for c in portfolio]
    assert len(tickers) >= 50,                              f"Need 50+ stocks, have {len(tickers)}"
    assert len(set(t.upper() for t in tickers)) == len(tickers), "Duplicate tickers found"
    assert all(c["amount"] >= 5000 for c in portfolio),    "Some allocation < $5,000"
    total = sum(c["amount"] for c in portfolio)
    assert total == 1_000_000,                             f"Total != $1,000,000 (got {total})"

    print(f"  Payload validated: {len(portfolio)} stocks, ${total:,} total")
    print(f"  team_id={TEAM_ID}  model={MODEL_AGENT_NAME} v{MODEL_VERSION}")

    if dry_run:
        print("  DRY RUN — not sending. Payload preview (first 3 transactions):")
        preview = {**payload, "transactions": payload["transactions"][:3]}
        print(json.dumps(preview, indent=2))
        print(f"  ... and {len(payload['transactions']) - 3} more transactions")
        return {"status": "dry_run", "payload": payload}

    print(f"  Submitting to {SUBMIT_URL} ...")
    resp = requests.post(
        SUBMIT_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if not resp.ok:
        print(f"  ERROR {resp.status_code}: {resp.text}")
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

    log = {
        "timestamp":        datetime.now().isoformat() + "Z",
        "portfolio_size":   len(portfolio),
        "total_allocated":  sum(c["amount"] for c in portfolio),
        "result":           result,
    }
    log_path = OUTPUT_DIR / "submission_log.json"
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
    dry = "--submit" not in sys.argv
    if dry:
        print("  (Add --submit flag to actually send to leaderboard)")
    main(dry_run=dry)
