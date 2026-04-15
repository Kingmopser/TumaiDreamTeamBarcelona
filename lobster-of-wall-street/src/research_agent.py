"""
Research Agent — queries the Cala API to score NASDAQ companies for investment.

Strategy (grounded in prior AAML project findings):
  - Financial strength text was the #1 predictor of future stock performance.
  - Revenue growth + profitability + low leverage → outperformance.

API approach:
  - Uses knowledge/search for a small set of high-value thematic queries.
  - Spaces calls 30s apart to respect Cala's per-minute rate limit.
  - Falls back to fundamental-tier scores when API is unavailable.
  - Uses knowledge/query for structured lookups (sub-second responses).

Scoring model (0–100):
  - Ranking in thematic Cala queries (35 pts): how prominently Cala ranks the company
  - Pre-built fundamental tier (30 pts): based on known financial profile
  - Sector growth factor (20 pts): sector tailwind adjustment
  - Size/quality factor (15 pts): large-cap premium
"""

import json
import time
from pathlib import Path

import requests

# ── Universe of NASDAQ-listed companies ─────────────────────────────────────
# Format: (ticker, company_name, sector, quality_tier)
# Quality tier: 1=top (known market leaders), 2=strong, 3=speculative
NASDAQ_UNIVERSE = [
    # Semiconductors / AI Hardware
    ("NVDA", "NVIDIA Corporation", "Semiconductors", 1),
    ("AMD", "Advanced Micro Devices", "Semiconductors", 1),
    ("AVGO", "Broadcom Inc.", "Semiconductors", 1),
    ("QCOM", "Qualcomm Inc.", "Semiconductors", 1),
    ("AMAT", "Applied Materials Inc.", "Semiconductors", 1),
    ("LRCX", "Lam Research Corporation", "Semiconductors", 1),
    ("KLAC", "KLA Corporation", "Semiconductors", 1),
    ("MRVL", "Marvell Technology Inc.", "Semiconductors", 2),
    ("ON", "ON Semiconductor Corporation", "Semiconductors", 2),
    ("MPWR", "Monolithic Power Systems", "Semiconductors", 2),
    ("ADI", "Analog Devices Inc.", "Semiconductors", 1),
    ("TXN", "Texas Instruments Inc.", "Semiconductors", 1),
    ("NXPI", "NXP Semiconductors NV", "Semiconductors", 2),
    ("MCHP", "Microchip Technology Inc.", "Semiconductors", 2),
    ("INTC", "Intel Corporation", "Semiconductors", 2),
    ("SNPS", "Synopsys Inc.", "Semiconductors", 1),
    ("CDNS", "Cadence Design Systems", "Semiconductors", 1),

    # Large-Cap Technology
    ("AAPL", "Apple Inc.", "Technology", 1),
    ("MSFT", "Microsoft Corporation", "Technology", 1),
    ("GOOGL", "Alphabet Inc. Class A", "Technology", 1),
    ("GOOG", "Alphabet Inc. Class C", "Technology", 1),
    ("META", "Meta Platforms Inc.", "Technology", 1),
    ("AMZN", "Amazon.com Inc.", "Technology", 1),
    ("CSCO", "Cisco Systems Inc.", "Technology", 1),
    ("ANET", "Arista Networks Inc.", "Technology", 1),
    ("ADBE", "Adobe Inc.", "Technology", 1),
    ("INTU", "Intuit Inc.", "Technology", 1),
    ("ANSS", "ANSYS Inc.", "Technology", 2),
    ("VRSK", "Verisk Analytics Inc.", "Technology", 2),

    # Cloud / Enterprise Software
    ("WDAY", "Workday Inc.", "Cloud Software", 1),
    ("DDOG", "Datadog Inc.", "Cloud Software", 1),
    ("MDB", "MongoDB Inc.", "Cloud Software", 2),
    ("MNDY", "monday.com Ltd.", "Cloud Software", 2),
    ("OKTA", "Okta Inc.", "Cloud Software", 2),
    ("ZM", "Zoom Video Communications", "Cloud Software", 2),
    ("DOCU", "DocuSign Inc.", "Cloud Software", 2),
    ("APPN", "Appian Corporation", "Cloud Software", 3),
    ("ESTC", "Elastic NV", "Cloud Software", 2),
    ("SMAR", "Smartsheet Inc.", "Cloud Software", 2),
    ("CDAY", "Ceridian HCM Holding", "Cloud Software", 2),
    ("PCTY", "Paylocity Holding Corporation", "Cloud Software", 2),
    ("PAYC", "Paycom Software Inc.", "Cloud Software", 2),

    # Cybersecurity
    ("PANW", "Palo Alto Networks Inc.", "Cybersecurity", 1),
    ("CRWD", "CrowdStrike Holdings Inc.", "Cybersecurity", 1),
    ("FTNT", "Fortinet Inc.", "Cybersecurity", 1),
    ("ZS", "Zscaler Inc.", "Cybersecurity", 1),
    ("CHKP", "Check Point Software Technologies", "Cybersecurity", 1),
    ("QLYS", "Qualys Inc.", "Cybersecurity", 2),
    ("RPD", "Rapid7 Inc.", "Cybersecurity", 2),
    ("TENB", "Tenable Holdings Inc.", "Cybersecurity", 2),

    # Consumer Technology / E-commerce
    ("TSLA", "Tesla Inc.", "Consumer Technology", 1),
    ("NFLX", "Netflix Inc.", "Consumer Technology", 1),
    ("PYPL", "PayPal Holdings Inc.", "Consumer Technology", 2),
    ("MELI", "MercadoLibre Inc.", "Consumer Technology", 1),
    ("BKNG", "Booking Holdings Inc.", "Consumer Technology", 1),
    ("EXPE", "Expedia Group Inc.", "Consumer Technology", 2),
    ("EBAY", "eBay Inc.", "Consumer Technology", 2),
    ("ETSY", "Etsy Inc.", "Consumer Technology", 2),
    ("TTD", "The Trade Desk Inc.", "Consumer Technology", 2),
    ("ABNB", "Airbnb Inc.", "Consumer Technology", 2),
    ("LYFT", "Lyft Inc.", "Consumer Technology", 3),

    # Biotech / Healthcare
    ("AMGN", "Amgen Inc.", "Biotech/Healthcare", 1),
    ("GILD", "Gilead Sciences Inc.", "Biotech/Healthcare", 1),
    ("REGN", "Regeneron Pharmaceuticals", "Biotech/Healthcare", 1),
    ("VRTX", "Vertex Pharmaceuticals", "Biotech/Healthcare", 1),
    ("BIIB", "Biogen Inc.", "Biotech/Healthcare", 2),
    ("MRNA", "Moderna Inc.", "Biotech/Healthcare", 2),
    ("IDXX", "IDEXX Laboratories Inc.", "Biotech/Healthcare", 1),
    ("ISRG", "Intuitive Surgical Inc.", "Biotech/Healthcare", 1),
    ("ALGN", "Align Technology Inc.", "Biotech/Healthcare", 2),
    ("DXCM", "DexCom Inc.", "Biotech/Healthcare", 2),
    ("PODD", "Insulet Corporation", "Biotech/Healthcare", 2),
    ("EXAS", "Exact Sciences Corporation", "Biotech/Healthcare", 2),
    ("IONS", "Ionis Pharmaceuticals", "Biotech/Healthcare", 2),
    ("INCY", "Incyte Corporation", "Biotech/Healthcare", 2),
    ("BMRN", "BioMarin Pharmaceutical", "Biotech/Healthcare", 2),
    ("ALNY", "Alnylam Pharmaceuticals", "Biotech/Healthcare", 2),

    # Consumer / Retail
    ("COST", "Costco Wholesale Corporation", "Consumer/Retail", 1),
    ("SBUX", "Starbucks Corporation", "Consumer/Retail", 1),
    ("MNST", "Monster Beverage Corporation", "Consumer/Retail", 2),
    ("PEP", "PepsiCo Inc.", "Consumer/Retail", 1),
    ("DLTR", "Dollar Tree Inc.", "Consumer/Retail", 2),
    ("ULTA", "Ulta Beauty Inc.", "Consumer/Retail", 2),
    ("KHC", "Kraft Heinz Company", "Consumer/Retail", 2),

    # Financials / Fintech
    ("NDAQ", "Nasdaq Inc.", "Financials/Fintech", 1),
    ("IBKR", "Interactive Brokers Group", "Financials/Fintech", 2),
    ("COIN", "Coinbase Global Inc.", "Financials/Fintech", 2),
    ("MKTX", "MarketAxess Holdings Inc.", "Financials/Fintech", 2),
    ("SSNC", "SS&C Technologies Holdings", "Financials/Fintech", 2),
    ("LPLA", "LPL Financial Holdings Inc.", "Financials/Fintech", 2),
    ("SEIC", "SEI Investments Company", "Financials/Fintech", 2),

    # Industrials / Business Services
    ("FAST", "Fastenal Company", "Industrials", 2),
    ("PAYX", "Paychex Inc.", "Industrials", 1),
    ("CTAS", "Cintas Corporation", "Industrials", 1),
    ("ODFL", "Old Dominion Freight Line", "Industrials", 1),
    ("EXPD", "Expeditors International", "Industrials", 2),
    ("SAIA", "Saia Inc.", "Industrials", 2),
    ("FICO", "Fair Isaac Corporation", "Industrials", 1),

    # Telecom / Media
    ("TMUS", "T-Mobile US Inc.", "Telecom/Media", 1),
    ("CMCSA", "Comcast Corporation", "Telecom/Media", 1),
    ("CHTR", "Charter Communications Inc.", "Telecom/Media", 2),
    ("SIRI", "Sirius XM Holdings Inc.", "Telecom/Media", 3),

    # Energy / Clean Tech
    ("FSLR", "First Solar Inc.", "Clean Energy", 2),
    ("ENPH", "Enphase Energy Inc.", "Clean Energy", 2),
    ("PLUG", "Plug Power Inc.", "Clean Energy", 3),
    ("RUN", "Sunrun Inc.", "Clean Energy", 3),

    # AI-adjacent / Data
    ("PLTR", "Palantir Technologies Inc.", "AI/Data", 2),
    ("AI", "C3.ai Inc.", "AI/Data", 3),
]

# Quality tier → base score (used as foundation, blended with Cala data)
TIER_BASE_SCORES = {1: 65.0, 2: 45.0, 3: 25.0}

# Sector growth factor (April 2025 context — AI/cloud/semi had strong tailwinds)
SECTOR_GROWTH_FACTORS = {
    "Semiconductors": 18.0,      # AI chip demand explosion
    "Technology": 15.0,          # Cloud + AI infrastructure
    "Cloud Software": 14.0,      # SaaS expansion
    "Cybersecurity": 13.0,       # Structural demand growth
    "AI/Data": 12.0,             # AI deployment wave
    "Consumer Technology": 10.0, # Digital platform strength
    "Biotech/Healthcare": 9.0,   # Drug approval pipeline
    "Financials/Fintech": 8.0,   # Fintech resilience
    "Industrials": 7.0,          # Steady cash flows
    "Consumer/Retail": 6.0,      # Brand stability
    "Telecom/Media": 5.0,        # Subscription revenue
    "Clean Energy": 4.0,         # Policy + volatility
}

# ── Thematic search queries for Cala knowledge/search ────────────────────────
# Each query returns a ranked list of companies. We extract entity mentions
# and use the ranking (position) to score companies.
# ORDER MATTERS: queries are spaced 30s apart to avoid rate limiting.
THEMATIC_QUERIES = [
    # (query_text, sector_focus, weight)
    (
        "Top NASDAQ semiconductor and AI hardware companies by revenue growth in 2024-2025. "
        "Rank by performance with specific revenue growth percentages.",
        ["Semiconductors"],
        1.2,
    ),
    (
        "Top NASDAQ technology companies Microsoft Apple Alphabet Meta Amazon performance "
        "revenue growth profitability 2024-2025.",
        ["Technology"],
        1.1,
    ),
    (
        "Top NASDAQ cloud software cybersecurity companies growth margins 2024-2025. "
        "Include Palo Alto CrowdStrike Fortinet Datadog Workday.",
        ["Cloud Software", "Cybersecurity"],
        1.0,
    ),
    (
        "Top NASDAQ biotech healthcare companies revenue growth pipeline 2024-2025. "
        "Include Amgen Regeneron Vertex Gilead Intuitive Surgical.",
        ["Biotech/Healthcare"],
        0.9,
    ),
    (
        "Top NASDAQ consumer technology e-commerce fintech companies Netflix Tesla "
        "Booking MercadoLibre performance 2024-2025.",
        ["Consumer Technology", "Financials/Fintech"],
        0.9,
    ),
    (
        "Best NASDAQ industrial consumer retail companies Cintas Costco Paychex FICO "
        "growth and financial strength 2024-2025.",
        ["Industrials", "Consumer/Retail", "Telecom/Media"],
        0.8,
    ),
]


class CalaClient:
    """Thin wrapper around the Cala API with rate-limit-aware retry logic."""

    BASE_URL = "https://api.cala.ai"
    CALL_SPACING_SEC = 32  # Wait between knowledge/search calls to avoid rate limit

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        })
        self._last_search_call = 0.0

    def _wait_for_rate_limit(self):
        """Ensure at least CALL_SPACING_SEC seconds between knowledge/search calls."""
        elapsed = time.time() - self._last_search_call
        if elapsed < self.CALL_SPACING_SEC:
            wait = self.CALL_SPACING_SEC - elapsed
            print(f"    [Rate limit] Waiting {wait:.0f}s before next Cala search call...")
            time.sleep(wait)

    def knowledge_search(self, query: str, timeout: int = 45, max_retries: int = 2) -> dict:
        """POST /v1/knowledge/search — natural language financial question."""
        self._wait_for_rate_limit()
        for attempt in range(max_retries + 1):
            try:
                self._last_search_call = time.time()
                r = self.session.post(
                    f"{self.BASE_URL}/v1/knowledge/search",
                    json={"input": query},
                    timeout=timeout,
                )
                r.raise_for_status()
                return r.json()
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    wait = 35
                    print(f"    Timeout on attempt {attempt+1}, waiting {wait}s before retry...")
                    time.sleep(wait)
                    self._last_search_call = time.time()
                else:
                    print(f"    All retries exhausted.")
                    return {}
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    time.sleep(10)
                else:
                    print(f"    Request error: {e}")
                    return {}

    def knowledge_query(self, query: str, timeout: int = 15) -> dict:
        """POST /v1/knowledge/query — fast structured dot-notation filter (sub-second)."""
        try:
            r = self.session.post(
                f"{self.BASE_URL}/v1/knowledge/query",
                json={"input": query},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    knowledge_query error: {e}")
            return {}

    def entity_search(self, name: str, limit: int = 5) -> list:
        """GET /v1/entities — find entity by name."""
        try:
            r = self.session.get(
                f"{self.BASE_URL}/v1/entities",
                params={"name": name, "entity_types": "Company", "limit": limit},
                timeout=10,
            )
            r.raise_for_status()
            return r.json().get("entities", [])
        except Exception:
            return []


# ── Signal extraction from Cala response text ────────────────────────────────

def extract_mentioned_tickers(content: str, entities: list) -> dict:
    """
    Extract companies mentioned in a Cala response and their relative ranking.
    Returns dict: ticker → rank_score (higher = mentioned earlier/more prominently).

    Uses both the returned entities list (has tickers) and text pattern matching.
    """
    ranking = {}

    # Method 1: Use entities list (has explicit tickers/names)
    for i, entity in enumerate(entities):
        mentions = entity.get("mentions", [])
        # Determine ticker from mentions (usually short uppercase symbols)
        ticker = None
        for m in mentions:
            if m.upper() == m and len(m) <= 5 and m.isalpha():
                ticker = m.upper()
                break
        if ticker:
            # Earlier entity = higher rank; score = 100 - (i * 5), minimum 10
            ranking[ticker] = max(10, 100 - i * 5)

    # Method 2: Scan text for known tickers in our universe
    universe_tickers = {c[0] for c in NASDAQ_UNIVERSE}
    lines = content.split("\n")
    for line_idx, line in enumerate(lines[:60]):  # Only scan first 60 lines (top of response)
        words = line.upper().split()
        for word in words:
            # Clean common punctuation
            clean = word.strip("()[].,:-")
            if clean in universe_tickers and clean not in ranking:
                # Earlier in response = better rank
                line_score = max(5, 80 - line_idx * 2)
                ranking[clean] = line_score

    return ranking


# ── Research Agent ─────────────────────────────────────────────────────────────

class ResearchAgent:
    """
    Queries the Cala API to research and score NASDAQ companies.
    Results are cached to disk so runs are resumable.
    """

    def __init__(self, api_key: str, cache_dir: str = "cache", data_cutoff_date: str = "2025-04-15"):
        self.cala = CalaClient(api_key)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "research_cache.json"
        self.data_cutoff_date = data_cutoff_date
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=2)

    def _compute_base_score(self, ticker: str, sector: str, tier: int) -> float:
        """
        Compute base score from tier + sector growth factor.
        This is the foundation score before Cala API data is applied.
        """
        tier_score = TIER_BASE_SCORES[tier]
        sector_bonus = SECTOR_GROWTH_FACTORS.get(sector, 7.0)
        return tier_score + sector_bonus

    def _run_thematic_queries(self) -> dict:
        """
        Run all thematic knowledge/search queries and aggregate company rankings.
        Returns dict: ticker → aggregated_cala_score (0-35 pts)
        """
        ticker_scores: dict[str, list[float]] = {}

        for i, (query_text, sector_focus, weight) in enumerate(THEMATIC_QUERIES):
            print(f"\nThematic query {i+1}/{len(THEMATIC_QUERIES)}: {query_text[:70]}...")
            result = self.cala.knowledge_search(query_text)
            content = result.get("content", "")
            entities = result.get("entities", [])

            if not content:
                print(f"  No response (API timeout/rate limit). Skipping.")
                continue

            print(f"  Got {len(content)} chars, {len(entities)} entities")

            # Extract ticker mentions and their ranking
            mentions = extract_mentioned_tickers(content, entities)

            # Store raw analysis for cache
            self.cache[f"__query_{i+1}__"] = {
                "query": query_text,
                "content": content[:3000],
                "entities": [e.get("name") for e in entities[:10]],
                "mentions": list(mentions.keys())[:15],
            }

            # Weight rankings by query weight and sector relevance
            for ticker, rank_score in mentions.items():
                weighted_score = rank_score * weight
                ticker_scores.setdefault(ticker, []).append(weighted_score)

        # Aggregate: average of all appearances, scaled to 0-35 pts
        aggregated = {}
        for ticker, scores in ticker_scores.items():
            avg = sum(scores) / len(scores)
            # avg is in range [5, 120], normalize to [0, 35]
            aggregated[ticker] = round(min(35.0, avg * 35.0 / 100.0), 2)

        return aggregated

    def _run_sector_queries(self) -> dict:
        """
        Use fast knowledge/query endpoint to get sector-level company lists.
        These are sub-second calls and don't hit the rate limit.
        Returns dict: ticker → sector_query_score (0-15 pts)
        """
        sector_scores: dict[str, float] = {}

        structured_queries = [
            ("companies.exchange=NASDAQ.sector=Technology.market_cap>50B", 15.0),
            ("companies.exchange=NASDAQ.sector=Technology.market_cap>10B", 12.0),
            ("companies.exchange=NASDAQ.sector=Healthcare", 10.0),
            ("companies.exchange=NASDAQ.sector=Consumer Discretionary", 9.0),
            ("companies.exchange=NASDAQ.sector=Financial Services", 9.0),
            ("companies.exchange=NASDAQ.sector=Industrials", 8.0),
        ]

        print("\nRunning fast sector queries (knowledge/query)...")
        for query, base_score in structured_queries:
            result = self.cala.knowledge_query(query)
            results = result.get("results", [])
            for i, company in enumerate(results):
                ticker = company.get("ticker", "").upper().split("/")[0].strip()
                if ticker and ticker in {c[0] for c in NASDAQ_UNIVERSE}:
                    # Companies listed earlier = stronger (market cap ordered)
                    position_score = base_score * (1.0 - i * 0.04)
                    if ticker not in sector_scores:
                        sector_scores[ticker] = max(5.0, position_score)

        # Scale to 0-15 pts
        if sector_scores:
            max_score = max(sector_scores.values())
            sector_scores = {t: round(s / max_score * 15.0, 2) for t, s in sector_scores.items()}

        print(f"  Found {len(sector_scores)} companies via structured queries")
        return sector_scores

    def run(self) -> list[dict]:
        """
        Full research pipeline:
          1. Fast structured sector queries (knowledge/query, sub-second)
          2. Thematic knowledge/search queries (spaced 30s apart)
          3. Combine Cala signals with fundamental base scores
          4. Return sorted company list
        """
        print(f"\n{'='*60}")
        print(f"Research Agent — Cala API Data Cutoff: {self.data_cutoff_date}")
        print(f"Universe: {len(NASDAQ_UNIVERSE)} NASDAQ companies")
        print(f"{'='*60}\n")

        # ── Phase 1: Fast structured queries ────────────────────────────────
        sector_scores = self._run_sector_queries()
        self._save_cache()

        # ── Phase 2: Thematic knowledge/search queries ────────────────────
        print(f"\nPhase 2: Thematic knowledge/search queries")
        print(f"(Note: 30s spacing between calls to respect Cala rate limits)")
        cala_rankings = self._run_thematic_queries()
        self._save_cache()

        # ── Phase 3: Combine all signals ──────────────────────────────────
        print(f"\nPhase 3: Computing final scores...")
        results = []
        for ticker, company_name, sector, tier in NASDAQ_UNIVERSE:
            base_score = self._compute_base_score(ticker, sector, tier)
            cala_rank_bonus = cala_rankings.get(ticker, 0.0)
            sector_query_bonus = sector_scores.get(ticker, 0.0)

            # Retrieve raw analysis from thematic query cache
            raw_analysis = ""
            for i in range(len(THEMATIC_QUERIES)):
                key = f"__query_{i+1}__"
                if key in self.cache:
                    if ticker in self.cache[key].get("mentions", []):
                        raw_analysis = self.cache[key].get("content", "")[:1500]
                        break

            final_score = round(base_score + cala_rank_bonus + sector_query_bonus, 2)

            entry = {
                "ticker": ticker,
                "company_name": company_name,
                "sector": sector,
                "tier": tier,
                "score": final_score,
                "score_components": {
                    "base": round(base_score, 2),
                    "cala_ranking": cala_rank_bonus,
                    "sector_query": sector_query_bonus,
                },
                "raw_analysis": raw_analysis,
                "data_cutoff_date": self.data_cutoff_date,
            }
            results.append(entry)

            # Cache final result
            self.cache[ticker] = entry

        results.sort(key=lambda x: x["score"], reverse=True)
        self._save_cache()

        print(f"\n{'='*60}")
        print(f"Research complete. Top 20 companies by score:")
        for r in results[:20]:
            comps = r.get("score_components", {})
            print(
                f"  {r['ticker']:6s} | {r['score']:5.1f} "
                f"(base={comps.get('base',0):.0f} "
                f"cala={comps.get('cala_ranking',0):.0f} "
                f"sector={comps.get('sector_query',0):.0f}) "
                f"| {r['company_name'][:35]}"
            )
        print(f"{'='*60}\n")

        return results
