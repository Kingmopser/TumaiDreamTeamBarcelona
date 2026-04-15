"""
Leaderboard Submission Client

Submits the portfolio to the hackathon leaderboard API.

Endpoint: POST https://different-cormorant-663.convex.site/api/submit
Auth: None (team identified by team_id in payload)

Payload:
  {
    "team_id": "your-team-slug",
    "model_agent_name": "CookingLobster",
    "model_agent_version": "1.0",
    "transactions": [
      {"nasdaq_code": "NVDA", "amount": 45000},
      ...
    ]
  }

Rules enforced server-side (and pre-validated here):
  - Minimum 50 unique NASDAQ companies
  - No duplicate tickers
  - Each amount >= $5,000
  - Total = exactly $1,000,000
"""

import json
from datetime import datetime
from pathlib import Path

import requests

SUBMISSION_URL = "https://different-cormorant-663.convex.site/api/submit"
TOTAL_CAPITAL = 1_000_000
MIN_PER_STOCK = 5_000
MIN_STOCKS = 50


class LeaderboardClient:

    def __init__(self, team_id: str, agent_name: str = "CookingLobster", agent_version: str = "1.0"):
        self.team_id = team_id
        self.agent_name = agent_name
        self.agent_version = agent_version

    def validate_portfolio(self, portfolio: list[dict]) -> list[str]:
        """Return list of validation errors (empty = all good)."""
        errors = []
        tickers = [p["ticker"] for p in portfolio]
        amounts = [p["amount"] for p in portfolio]
        total = sum(amounts)

        if len(portfolio) < MIN_STOCKS:
            errors.append(f"Too few stocks: {len(portfolio)} < {MIN_STOCKS}")

        if len(tickers) != len(set(t.upper() for t in tickers)):
            errors.append("Duplicate tickers detected")

        below_min = [(t, a) for t, a in zip(tickers, amounts) if a < MIN_PER_STOCK]
        if below_min:
            errors.append(f"Stocks below $5,000 minimum: {below_min}")

        if abs(total - TOTAL_CAPITAL) > 1:
            errors.append(f"Total capital {total:,.0f} ≠ {TOTAL_CAPITAL:,}")

        return errors

    def build_payload(self, portfolio: list[dict]) -> dict:
        """Build the submission payload from portfolio."""
        transactions = [
            {"nasdaq_code": p["ticker"].upper(), "amount": p["amount"]}
            for p in portfolio
        ]
        return {
            "team_id": self.team_id,
            "model_agent_name": self.agent_name,
            "model_agent_version": self.agent_version,
            "transactions": transactions,
        }

    def submit(self, portfolio: list[dict], dry_run: bool = False) -> dict:
        """
        Submit portfolio to the leaderboard.

        Args:
            portfolio: list of portfolio dicts with 'ticker' and 'amount'
            dry_run: if True, validate and print payload but do NOT send

        Returns:
            dict with 'success', 'response', and 'payload' keys
        """
        # Validate first
        errors = self.validate_portfolio(portfolio)
        if errors:
            print(f"\n✗ Pre-submission validation FAILED:")
            for e in errors:
                print(f"  - {e}")
            return {"success": False, "errors": errors, "response": None}

        payload = self.build_payload(portfolio)

        total = sum(t["amount"] for t in payload["transactions"])
        print(f"\n{'='*60}")
        print(f"Submission Summary")
        print(f"  Team:         {self.team_id}")
        print(f"  Agent:        {self.agent_name} v{self.agent_version}")
        print(f"  Stocks:       {len(payload['transactions'])}")
        print(f"  Total:        ${total:,.0f}")
        print(f"  Endpoint:     {SUBMISSION_URL}")
        print(f"{'='*60}")

        if dry_run:
            print("\n[DRY RUN] — payload validated but NOT submitted.")
            print(f"Payload preview:\n{json.dumps(payload, indent=2)[:500]}...")
            return {"success": True, "dry_run": True, "payload": payload, "response": None}

        print("\nSubmitting to leaderboard...")
        try:
            r = requests.post(
                SUBMISSION_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response_data = {}
            try:
                response_data = r.json()
            except Exception:
                response_data = {"raw": r.text}

            if r.status_code == 200:
                print(f"✓ Submission accepted! Status: {r.status_code}")
                print(f"  Response: {json.dumps(response_data, indent=2)[:500]}")
                return {"success": True, "response": response_data, "payload": payload, "status_code": r.status_code}
            else:
                print(f"✗ Submission rejected. Status: {r.status_code}")
                print(f"  Response: {json.dumps(response_data, indent=2)[:500]}")
                return {"success": False, "response": response_data, "payload": payload, "status_code": r.status_code}

        except requests.exceptions.RequestException as e:
            print(f"✗ Network error: {e}")
            return {"success": False, "error": str(e), "payload": payload}

    def save_submission_log(
        self,
        result: dict,
        portfolio: list[dict],
        output_dir: str = "output",
    ):
        """Save submission result + portfolio to JSON log."""
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        log = {
            "submitted_at": timestamp,
            "team_id": self.team_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "submission_result": result,
            "portfolio_summary": {
                "num_stocks": len(portfolio),
                "total_invested": sum(p["amount"] for p in portfolio),
                "sectors": sorted(set(p["sector"] for p in portfolio)),
                "top_10": [
                    {"ticker": p["ticker"], "amount": p["amount"], "score": p["score"]}
                    for p in sorted(portfolio, key=lambda x: x["amount"], reverse=True)[:10]
                ],
            },
        }

        log_path = Path(output_dir) / "submission_log.json"
        with open(log_path, "w") as f:
            json.dump(log, f, indent=2)
        print(f"\n  Submission log saved to: {log_path}")
