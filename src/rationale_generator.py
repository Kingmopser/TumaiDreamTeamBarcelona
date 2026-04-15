"""
Stage 3: Rationale Generator
For each stock in the portfolio, generates a 3-5 sentence investment rationale
grounded in data retrieved from the Cala API (via knowledge/query and entity search).

Uses Claude (claude-sonnet-4-6) to synthesise Cala data into clear, data-driven prose.

Input:  output/portfolio.json
Output: output/portfolio.json  (enriched with "rationale" field per stock)
"""

import json
import os
import time
from pathlib import Path

import requests

# ── Auth ──────────────────────────────────────────────────────────────────────

def load_api_key(var_names: list[str]) -> str:
    for name in var_names:
        val = os.getenv(name)
        if val:
            return val
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key.strip() in var_names:
                return value.strip().strip('"').strip("'")
    raise ValueError(f"Missing key. Set one of: {var_names}")


CALA_KEY = load_api_key(["API_KEY", "CALA_API_KEY"])
ANTHROPIC_KEY = load_api_key(["ANTHROPIC_API_KEY"])

CALA_HEADERS = {"X-API-KEY": CALA_KEY, "Content-Type": "application/json"}
ANTHROPIC_HEADERS = {
    "x-api-key": ANTHROPIC_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

BASE_CALA = "https://api.cala.ai"
BASE_ANTHROPIC = "https://api.anthropic.com"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


# ── Cala helpers ──────────────────────────────────────────────────────────────

def cala_query(query: str) -> dict:
    try:
        resp = requests.post(
            f"{BASE_CALA}/v1/knowledge/query",
            json={"input": query},
            headers=CALA_HEADERS,
            timeout=45,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"    Cala query error: {e}")
        return {"results": [], "entities": []}


def fetch_company_data(ticker: str, name: str) -> dict:
    """
    Pull structured data about this company from Cala using targeted queries.
    Returns a dict of facts to pass to Claude.
    """
    facts = {"ticker": ticker, "name": name, "cala_data": []}

    queries = [
        f"companies.ticker={ticker}",
        f"companies.exchange=NASDAQ.revenue_growth>0",  # may return this company in results
        f"companies.exchange=NASDAQ.ticker={ticker}",
    ]

    for q in queries:
        data = cala_query(q)
        results = data.get("results", [])
        # Filter to results that mention this company
        for r in results:
            r_str = json.dumps(r, default=str).lower()
            if ticker.lower() in r_str or name.lower().split()[0].lower() in r_str:
                facts["cala_data"].append(r)
        if facts["cala_data"]:
            break
        time.sleep(0.3)

    # Also include the raw data collected during research
    return facts


# ── Claude rationale generation ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are a quantitative equity analyst generating investment rationales
for a portfolio submission. Each rationale must be:
- 3-5 sentences
- Data-driven and specific (cite actual numbers from the provided Cala data)
- Focused on: revenue growth, competitive positioning, sector tailwinds, and why this
  allocation amount makes sense relative to the portfolio
- Professional, concise, third-person tone
- No speculation beyond the data provided
- Reference "Cala data" as the source for any specific metrics cited"""


def generate_rationale(company: dict) -> str:
    """Call Claude to generate a rationale based on Cala data."""
    ticker = company["ticker"]
    name = company["name"]
    score = company.get("score", "N/A")
    amount = company.get("amount", 0)
    sector = company.get("sector", "unspecified sector")
    revenue_growth = company.get("revenue_growth", "not specified")
    market_cap = company.get("market_cap", "not specified")
    cala_data = company.get("cala_data", company.get("_raw", {}))

    prompt = f"""Generate a 3-5 sentence investment rationale for including {name} ({ticker})
in this NASDAQ portfolio.

Available Cala data:
- Ticker: {ticker}
- Company: {name}
- Sector/Industry: {sector}
- Revenue Growth: {revenue_growth}
- Market Cap: {market_cap}
- Investment Score: {score}/100
- Portfolio Allocation: ${amount:,} (out of $1,000,000 total)
- Additional Cala data: {json.dumps(cala_data, default=str)[:800]}

Write the rationale in 3-5 sentences. Be specific about numbers where available.
Start with the key investment thesis for this company."""

    try:
        resp = requests.post(
            f"{BASE_ANTHROPIC}/v1/messages",
            headers=ANTHROPIC_HEADERS,
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"    Claude error for {ticker}: {e}")
        # Fallback: generate a basic rationale without Claude
        return (
            f"{name} ({ticker}) is a {sector} company selected based on Cala data "
            f"showing {revenue_growth} revenue growth and a market capitalisation of "
            f"{market_cap}. The company earned an investment score of {score}/100, "
            f"reflecting its competitive position within the NASDAQ universe. "
            f"An allocation of ${amount:,} represents conviction-weighted exposure "
            f"to this sector opportunity."
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STAGE 3: Rationale Generator")
    print("=" * 60)

    portfolio_path = OUTPUT_DIR / "portfolio.json"
    if not portfolio_path.exists():
        raise FileNotFoundError("Run portfolio_allocator.py first.")

    portfolio = json.loads(portfolio_path.read_text())
    print(f"\n  Generating rationales for {len(portfolio)} stocks...")

    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY") or
                         _check_env_file_for_key("ANTHROPIC_API_KEY"))
    if not has_anthropic:
        print("  WARNING: ANTHROPIC_API_KEY not found. Using fallback rationales.")

    for i, company in enumerate(portfolio, 1):
        ticker = company["ticker"]
        print(f"  [{i:2d}/{len(portfolio)}] {ticker} — {company['name']}")

        # Fetch fresh Cala data for this specific company
        cala_facts = fetch_company_data(ticker, company["name"])
        company["cala_data"] = cala_facts.get("cala_data", [])

        # Generate rationale
        company["rationale"] = generate_rationale(company)
        time.sleep(0.5)  # respect rate limits

    # Save enriched portfolio
    portfolio_path.write_text(json.dumps(portfolio, indent=2, default=str))
    print(f"\n  Rationales added. Portfolio saved to: {portfolio_path}")

    # Print a sample
    print(f"\n  Sample rationale for {portfolio[0]['ticker']}:")
    print(f"  {portfolio[0].get('rationale', 'N/A')[:300]}...")

    return portfolio


def _check_env_file_for_key(key_name: str) -> bool:
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith(key_name):
                return True
    return False


if __name__ == "__main__":
    main()
