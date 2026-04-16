"""
Stage 3 — Cala AI Enrichment
Queries Cala knowledge API with aggressive caching and retry logic.
"""

import json
import os
import time
from pathlib import Path

import requests

CALA_URL = "https://api.cala.ai/v1/knowledge/query"
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"


def _cache_path(query: str) -> Path:
    """Deterministic cache file for a query."""
    CACHE_DIR.mkdir(exist_ok=True)
    safe = query.replace("/", "_").replace(" ", "_").replace(".", "_")[:80]
    return CACHE_DIR / f"cala_{safe}.json"


def _query_cala(query: str, api_key: str, timeout: int = 25, retries: int = 2) -> dict:
    """Single Cala query with caching and retry."""
    cache = _cache_path(query)
    if cache.exists():
        return json.loads(cache.read_text())

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    for attempt in range(retries):
        try:
            r = requests.post(CALA_URL, json={"input": query},
                              headers=headers, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                cache.write_text(json.dumps(data, indent=2))
                return data
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(1)
                continue
        except Exception:
            break
    return {}


def enrich_with_cala(tickers: list, api_key: str, full_mode: bool = False) -> dict:
    """
    Query Cala for batch sector data + individual top picks.
    Returns {ticker: {cala_data}} dict.

    full_mode=True: aggressive Cala usage — more queries, deeper coverage.
    """
    if not api_key:
        print("  No CALA_API_KEY — skipping enrichment")
        return {}

    cala_data = {}

    # ── Batch sector queries (fast, return multiple tickers) ──
    sector_queries = [
        "companies.exchange=NASDAQ.revenue_growth>0.2",
        "companies.exchange=NASDAQ.net_income>0",
        "companies.exchange=NASDAQ.sector=Technology",
        "companies.exchange=NASDAQ.sector=Healthcare",
    ]

    if full_mode:
        sector_queries += [
            "companies.exchange=NASDAQ.sector=Semiconductors",
            "companies.exchange=NASDAQ.sector=Energy",
            "companies.exchange=NASDAQ.sector=Financials",
            "companies.exchange=NASDAQ.sector=Industrials",
            "companies.exchange=NASDAQ.sector=Consumer Discretionary",
            "companies.exchange=NASDAQ.revenue_growth>0.1.market_cap<1B",
            "companies.exchange=NASDAQ.market_cap<500M",
            "companies.exchange=NASDAQ.market_cap>10B",
        ]

    for q in sector_queries:
        print(f"    Cala query: {q[:60]}...")
        result = _query_cala(q, api_key)
        for item in result.get("results", []):
            t = item.get("ticker", "")
            if t:
                cala_data[t] = item
        time.sleep(0.5)

    # ── Individual queries for top picks not yet enriched ──
    n_individual = 30 if full_mode else 10
    missing = [t for t in tickers[:50] if t not in cala_data]
    for t in missing[:n_individual]:
        print(f"    Cala lookup: {t}")
        result = _query_cala(f"companies.ticker={t}", api_key, timeout=15)
        if result.get("results"):
            cala_data[t] = result["results"][0]
        time.sleep(0.3)

    # ── In full mode, also try knowledge/search for sector narratives ──
    if full_mode:
        search_queries = [
            "What are the most promising semiconductor substrate companies for AI data centers?",
            "Which NASDAQ small-cap companies have the strongest revenue growth in 2024?",
            "What companies supply critical components for AI chip manufacturing?",
        ]
        search_url = "https://api.cala.ai/v1/knowledge/search"
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        for sq in search_queries:
            print(f"    Cala search: {sq[:55]}...")
            try:
                r = requests.post(search_url, json={"input": sq},
                                  headers=headers, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    # Extract any tickers mentioned in results
                    for item in data.get("results", []):
                        t = item.get("ticker", "")
                        if t:
                            cala_data.setdefault(t, {}).update(item)
                    print(f"      -> {len(data.get('results', []))} results")
            except Exception as e:
                print(f"      -> timeout/error: {str(e)[:40]}")
            time.sleep(1)

    print(f"  Cala enriched {len(cala_data)} tickers "
          f"({'full' if full_mode else 'standard'} mode)")
    return cala_data
