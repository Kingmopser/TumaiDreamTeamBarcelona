"""
Stage 1: Research Agent
Queries Cala API with multiple structured filters to build a candidate pool of
NASDAQ companies, merges data by ticker, and scores each company for investment.

Output: output/companies_scored.json
"""

import json
import os
import time
from pathlib import Path

import requests

# ── Auth ──────────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    api_key = os.getenv("API_KEY") or os.getenv("CALA_API_KEY")
    if api_key:
        return api_key
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key.strip() in {"API_KEY", "CALA_API_KEY"}:
                return value.strip().strip('"').strip("'")
    raise ValueError("Missing API key. Set API_KEY or CALA_API_KEY in env or .env")


API_KEY = load_api_key()
BASE_URL = "https://api.cala.ai"
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def cala_query(query: str, retries: int = 2) -> dict:
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{BASE_URL}/v1/knowledge/query",
                json={"input": query},
                headers=HEADERS,
                timeout=45,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            if attempt < retries:
                print(f"    Timeout, retrying ({attempt + 1}/{retries})...")
                time.sleep(2)
            else:
                print(f"    Failed after {retries} retries: {query}")
                return {"results": [], "entities": []}
        except requests.HTTPError as e:
            print(f"    HTTP {e.response.status_code}: {query}")
            return {"results": [], "entities": []}


# ── Query catalog ─────────────────────────────────────────────────────────────
# Each query is designed to extract different data dimensions.
# The Cala API returns different fields depending on the query context.

QUERIES = [
    # Broad catches — get ticker + basic info
    "companies.stock_exchange=NASDAQ",
    "public_companies.exchange=NASDAQ",

    # Sector-grouped — returns sector + sub-sector tags
    "companies.exchange=NASDAQ.sector=Technology",
    "companies.exchange=NASDAQ.sector=Healthcare",
    "companies.exchange=NASDAQ.sector=Financials",
    "companies.exchange=NASDAQ.sector=Consumer Discretionary",
    "companies.exchange=NASDAQ.sector=Industrials",
    "companies.exchange=NASDAQ.sector=Communication Services",
    "companies.exchange=NASDAQ.sector=Energy",
    "companies.exchange=NASDAQ.sector=Consumer Staples",
    "companies.exchange=NASDAQ.sector=Utilities",

    # Industry-specific — often returns market cap
    "companies.exchange=NASDAQ.industry=semiconductors",
    "companies.exchange=NASDAQ.industry=biotechnology",
    "companies.exchange=NASDAQ.industry=cloud",
    "companies.exchange=NASDAQ.industry=fintech",
    "companies.exchange=NASDAQ.industry=AI",
    "companies.exchange=NASDAQ.industry=software",
    "companies.exchange=NASDAQ.industry=e-commerce",

    # Financial filters — returns revenue_growth and financial metrics
    "companies.exchange=NASDAQ.revenue_growth>20",
    "companies.exchange=NASDAQ.revenue_growth>10",
    "companies.exchange=NASDAQ.revenue_growth>5",
]

# ── Ticker extraction ─────────────────────────────────────────────────────────
# The Cala API returns different field names depending on which query was run.
# We normalise everything to a common schema.

TICKER_FIELDS = ["ticker", "ticker_symbol", "symbol", "stock_ticker"]
NAME_FIELDS   = ["company", "company_name", "name", "firm"]
SECTOR_FIELDS = ["sector", "industry", "sub_sector", "subSector", "category"]
MCAP_FIELDS   = ["market_cap", "marketCap", "market_capitalization"]
GROWTH_FIELDS = ["revenue_growth", "revenue_growth_rate", "growth_rate", "yoy_growth"]


def _first(d: dict, fields: list) -> str | None:
    for f in fields:
        if d.get(f):
            return str(d[f])
    return None


def normalise_result(raw: dict) -> dict | None:
    """Extract a normalised company record from a raw Cala result row."""
    ticker = _first(raw, TICKER_FIELDS)
    if not ticker:
        return None
    return {
        "ticker":       ticker.upper().strip(),
        "name":         _first(raw, NAME_FIELDS) or ticker,
        "sector":       _first(raw, SECTOR_FIELDS),
        "market_cap":   _first(raw, MCAP_FIELDS),
        "revenue_growth": _first(raw, GROWTH_FIELDS),
        "_raw":         raw,
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect_companies() -> dict[str, dict]:
    """
    Run all queries and merge results by ticker.
    Later queries enrich earlier ones without overwriting existing non-null values.
    """
    companies: dict[str, dict] = {}  # ticker → merged record
    total_hits = 0

    for query in QUERIES:
        print(f"  Querying: {query}")
        data = cala_query(query)
        results = data.get("results", [])
        print(f"    → {len(results)} results")
        total_hits += len(results)

        for raw in results:
            record = normalise_result(raw)
            if not record:
                continue
            ticker = record["ticker"]
            if ticker not in companies:
                companies[ticker] = record
            else:
                # Enrich: fill in nulls from new data
                existing = companies[ticker]
                for key in ["name", "sector", "market_cap", "revenue_growth"]:
                    if not existing.get(key) and record.get(key):
                        existing[key] = record[key]
                # Keep all raw data for rationale generation
                existing.setdefault("_raw_all", []).append(raw)

        time.sleep(0.4)  # rate limit courtesy

    print(f"\n  Total API hits: {total_hits}")
    print(f"  Unique tickers collected: {len(companies)}")
    return companies


# ── Scoring model ─────────────────────────────────────────────────────────────
# Scores each company 0–100 based on available Cala data.
# Criteria and weights match the PLAN.md scoring model.

SECTOR_WEIGHTS = {
    # High growth sectors get a bonus
    "technology": 20,
    "semiconductors": 20,
    "ai": 20,
    "cloud": 18,
    "software": 18,
    "communication services": 15,
    "healthcare": 15,
    "biotechnology": 15,
    "fintech": 14,
    "consumer discretionary": 10,
    "financials": 10,
    "industrials": 8,
    "energy": 8,
    "consumer staples": 6,
    "utilities": 4,
}

# Known high-quality NASDAQ companies to seed the scoring with conviction scores.
# Sourced from publicly known fundamentals as of April 2025.
CONVICTION_OVERRIDES = {
    # AI / Semiconductor leaders
    "NVDA":  92, "TSM":  88, "AVGO": 85, "AMD":  80, "QCOM": 75,
    "MRVL":  78, "AMAT": 74, "KLAC": 73, "LRCX": 72, "ASML": 86,
    # Cloud / SaaS leaders
    "MSFT":  90, "AMZN": 88, "GOOGL": 87, "META": 85, "CRM":  80,
    "SNOW":  74, "DDOG": 76, "MDB":  75, "ZS":   78, "NET":  79,
    "PANW":  80, "CRWD": 82, "FTNT": 74,
    # Consumer Tech
    "AAPL":  88, "NFLX": 78, "SPOT": 70, "UBER": 72, "LYFT": 60,
    # Biotech / Healthcare
    "AMGN":  75, "GILD": 70, "BIIB": 65, "VRTX": 80, "REGN": 78,
    "MRNA":  68, "ILMN": 66,
    # Fintech
    "PYPL":  70, "SQ":   72, "COIN": 65, "HOOD": 58, "AFRM": 60,
    # Other strong NASDAQ names
    "TSLA":  76, "COST": 82, "SBUX": 70, "ABNB": 72, "BKNG": 78,
    "MAR":   74, "EBAY": 62, "ETSY": 60, "MELI": 80, "SE":   72,
}


def parse_growth(value: str | None) -> float | None:
    """Parse strings like '~39%', '30%+', '25' into a float."""
    if not value:
        return None
    import re
    m = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(m.group(1)) if m else None


def parse_market_cap(value: str | None) -> float | None:
    """Parse strings like '~$4.4–4.5 T', '$1,960B', '250M' into billions."""
    if not value:
        return None
    import re
    # Remove ~, $, commas, spaces
    cleaned = re.sub(r"[~$,\s]", "", str(value))
    # Handle range: take average of first and last number
    numbers = re.findall(r"[\d.]+", cleaned)
    if not numbers:
        return None
    val = float(numbers[0])
    # Detect unit
    upper = cleaned.upper()
    if "T" in upper:
        val *= 1000  # trillions → billions
    elif "M" in upper and "B" not in upper:
        val /= 1000  # millions → billions
    return val


def score_company(c: dict) -> int:
    """Score a company 0–100 for investment attractiveness."""
    ticker = c["ticker"]

    # Start with conviction override if available
    if ticker in CONVICTION_OVERRIDES:
        base = CONVICTION_OVERRIDES[ticker]
        # Small adjustment from growth data if available
        growth = parse_growth(c.get("revenue_growth"))
        if growth and growth > 30:
            base = min(base + 3, 100)
        elif growth and growth < 5:
            base = max(base - 5, 0)
        return base

    # For companies without a conviction override, score from available data
    score = 40  # baseline

    # Sector tailwind (up to +20)
    sector_str = (c.get("sector") or "").lower()
    sector_bonus = 0
    for sector_key, weight in SECTOR_WEIGHTS.items():
        if sector_key in sector_str:
            sector_bonus = max(sector_bonus, weight)
    score += sector_bonus

    # Revenue growth (up to +25)
    growth = parse_growth(c.get("revenue_growth"))
    if growth is not None:
        if growth >= 50:
            score += 25
        elif growth >= 30:
            score += 20
        elif growth >= 20:
            score += 15
        elif growth >= 10:
            score += 8
        elif growth >= 5:
            score += 3
        elif growth < 0:
            score -= 10

    # Market cap — prefer mid/large caps (stability)
    mcap = parse_market_cap(c.get("market_cap"))
    if mcap is not None:
        if mcap >= 500:    # mega cap
            score += 5
        elif mcap >= 50:   # large cap
            score += 8
        elif mcap >= 10:   # mid cap
            score += 6
        elif mcap < 1:     # micro cap — risky
            score -= 5

    return max(0, min(100, score))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STAGE 1: Research Agent — Collecting & Scoring Companies")
    print("=" * 60)

    print("\n[1/2] Collecting NASDAQ companies from Cala API...")
    companies = collect_companies()

    print("\n[2/2] Scoring companies...")
    scored = []
    for ticker, c in companies.items():
        c["score"] = score_company(c)
        scored.append(c)

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Save
    raw_path = OUTPUT_DIR / "companies_raw.json"
    scored_path = OUTPUT_DIR / "companies_scored.json"

    raw_path.write_text(json.dumps(list(companies.values()), indent=2, default=str))
    scored_path.write_text(json.dumps(scored, indent=2, default=str))

    print(f"\n  Companies collected: {len(scored)}")
    print(f"  Top 10 by score:")
    for c in scored[:10]:
        growth_str = f", growth={c['revenue_growth']}" if c.get("revenue_growth") else ""
        print(f"    {c['ticker']:6s}  score={c['score']}  {c['name']}{growth_str}")

    print(f"\n  Raw saved to:    {raw_path}")
    print(f"  Scored saved to: {scored_path}")
    return scored


if __name__ == "__main__":
    main()
