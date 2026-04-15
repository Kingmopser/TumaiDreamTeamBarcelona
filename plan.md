# Lobster of Wall Street — Implementation Plan

## Objective

Simulate being on **April 15, 2025** with **$1,000,000** to invest. Use Cala's verified knowledge API to research NASDAQ-listed companies and allocate capital across at least 50 stocks. Portfolio is evaluated on April 15, 2026.

**Benchmark to beat:** S&P 500 returned **+29.18%** → $1,291,754

**Evaluation date:** Dynamic — TBA from Cala AI during the hackathon (currently expected April 15, 2026)

---

## Submission Rules (Non-Negotiable)

| Rule | Detail |
|------|--------|
| Minimum stocks | 50 NASDAQ-listed companies |
| No duplicates | Each ticker appears only once |
| Minimum per stock | $5,000 per company |
| Total capital | Exactly $1,000,000 |
| Resubmissions | Unlimited — iterate freely |

---

## Scoring

- **50%** — Leaderboard rank (portfolio return vs. S&P 500 and other teams)
- **50%** — Qualitative: data-driven rationale per stock, sourced from Cala data

---

## Cala API — What We Know

### Endpoints

| Endpoint | Method | Use |
|----------|--------|-----|
| `/v1/knowledge/query` | POST | Structured dot-notation filtering — get lists of companies by attributes |
| `/v1/knowledge/search` | POST | Natural language — get researched, sourced narrative answers |
| `/v1/entities` | GET | Fuzzy name search — find entity UUIDs by name |
| `/v1/entities/{id}` | POST | Full entity profile with all properties + sources |
| `/v1/entities/{id}/introspection` | GET | Discover available fields/relationships for a specific entity |

**Auth:** `X-API-KEY` header
**Base URL:** `https://api.cala.ai/`

### Query Syntax (dot-notation)

```
entity_type.attribute=value.attribute>value.attribute<value
```

**Operators:** `=` `!=` `>` `<` `>=` `<=`

**Example queries:**
```
companies.exchange=NASDAQ.sector=Technology
companies.industry=AI.founded_year>=2018
companies.sector=semiconductor.employee_count>1000
startups.location=Spain.funding>10M.funding<50M
```

### Key Fields Available

- `name`, `legal_name`, `sector`, `industry`
- `founded_date`, `founded_year`, `employee_count`
- `funding_amount`, `round_type`
- `cik` (SEC ID — confirms US public company)
- `headquarters_address`
- Financial metrics via `numerical_observations` (retrieved per entity via introspection)

### Supplementary Data Sources (Allowed)

Cala is the **primary** source (required for rationale), but these can supplement scoring:
- **Yahoo Finance** — real-time fundamentals, P/E, EPS, market cap
- **Alpha Vantage** — historical financials, earnings
- **Morningstar** — analyst ratings, moat scores

Use supplementary sources to enrich the scoring model, but always ground the written rationale in Cala data.

### Two Search Modes

1. **`/v1/knowledge/query`** — Structured, deterministic. Use to *filter* companies by attributes. Returns typed results + entity UUIDs.
2. **`/v1/knowledge/search`** — Natural language, sourced. Use to *research* a company ("What is Nvidia's revenue growth trend?"). Returns markdown answer + source citations + reasoning steps.

---

## Project Structure

```
TumaiDreamTeamBarcelona/
├── PLAN.md                        # This file
├── CLAUDE.md                      # Hackathon brief
├── .env                           # CALA_API_KEY
├── main.py                        # Existing Cala API client
├── src/
│   ├── explore_cala.py            # Step 0: probe API fields/entity types
│   ├── research_agent.py          # Step 1: query Cala for NASDAQ companies + scores
│   ├── portfolio_allocator.py     # Step 2: allocate $1M, enforce rules
│   ├── rationale_generator.py     # Step 3: per-stock written justification via Cala
│   └── leaderboard_client.py      # Step 4: submit to leaderboard API
├── output/
│   ├── api_schema_notes.md        # Confirmed Cala field names from exploration
│   ├── companies_raw.json         # Raw Cala query results
│   ├── companies_scored.json      # Scored + ranked companies
│   ├── portfolio.json             # Final: [{ticker, amount, rationale}]
│   └── submission_log.json        # Leaderboard API responses
```

---

## Implementation Pipeline

### Stage 0 — Explore Cala API (15 min)

**File:** `src/explore_cala.py`

Goal: Discover what entity types and field names work for NASDAQ stocks before writing the main pipeline.

Probe queries to run:
```python
# Find the right entity type for listed companies
"companies.exchange=NASDAQ"
"public_companies.exchange=NASDAQ"
"stocks.exchange=NASDAQ"

# Test financial field names
"companies.exchange=NASDAQ.sector=Technology"
"companies.exchange=NASDAQ.revenue_growth>20"
```

Also: pick 2-3 known NASDAQ companies (Apple, Nvidia, Microsoft), run entity search + introspection on them to discover what `numerical_observations` fields exist (revenue, margins, growth rates, etc.).

**Output:** `output/api_schema_notes.md` — confirmed field names.

---

### Stage 1 — Research Agent (45 min)

**File:** `src/research_agent.py`

#### 1a. Bulk Company Discovery
Query Cala for NASDAQ companies grouped by sector to build a candidate pool of ~100-150 companies:

```python
sectors = ["Technology", "Healthcare", "Financials", "Consumer Discretionary",
           "Industrials", "Communication Services", "Energy", "Semiconductors"]

for sector in sectors:
    query = f"companies.exchange=NASDAQ.sector={sector}"
    # collect results → entity UUIDs
```

#### 1b. Per-Company Deep Research
For each candidate, call:
1. `GET /v1/entities/{id}/introspection` — discover available financial fields
2. `POST /v1/entities/{id}` — get full profile (financials, metrics, numerical_observations)
3. `POST /v1/knowledge/search` — ask: *"What is [Company]'s revenue growth, competitive moat, and key risks as of April 2025?"*

#### 1c. Scoring Model
Score each company 1–100:

| Criterion | Weight | Source |
|-----------|--------|--------|
| Revenue growth (YoY) | 30% | Cala entity financials |
| Profitability (operating margins) | 20% | Cala numerical_observations |
| Competitive moat / market position | 20% | Cala knowledge search |
| Sector tailwind (AI, biotech, cloud) | 15% | Sector classification |
| Valuation attractiveness | 15% | Cala fundamentals |

**Output:** `output/companies_scored.json`

---

### Stage 2 — Portfolio Allocator (20 min)

**File:** `src/portfolio_allocator.py`

1. Sort scored companies descending
2. Take top 55 (5 buffer above minimum)
3. Allocate $1,000,000 using **conviction-weighted** strategy:

```python
def allocate(companies, budget=1_000_000, min_allocation=5_000):
    # Apply score-based weights
    total_score = sum(c['score'] for c in companies)
    for c in companies:
        raw = budget * (c['score'] / total_score)
        c['amount'] = max(raw, min_allocation)
    # Normalize to exactly $1,000,000
    scale = budget / sum(c['amount'] for c in companies)
    for c in companies:
        c['amount'] = round(c['amount'] * scale)
    # Fix rounding residual on largest position
    ...
```

**Output:** `output/portfolio.json`

---

### Stage 3 — Rationale Generator (30 min)

**File:** `src/rationale_generator.py`

For each stock, generate a 3-5 sentence rationale citing specific Cala data:

```python
search_prompt = f"""What are the key financial strengths and growth drivers for {company_name}
as of April 2025? Include revenue growth rate, operating margins, and competitive position."""

response = cala_search(search_prompt)  # POST /v1/knowledge/search
rationale = format_rationale(response, company, allocation_amount)
```

Format per stock:
```json
{
  "ticker": "NVDA",
  "company": "Nvidia",
  "amount": 42000,
  "score": 94,
  "rationale": "Nvidia reported X% revenue growth YoY driven by surging AI chip demand.
                Cala data shows operating margins of Y%, reflecting strong pricing power.
                The company's CUDA ecosystem creates deep switching costs, supporting
                durable competitive advantage. Allocated $42,000 (4.2% of portfolio)
                reflecting highest conviction among semiconductor holdings."
}
```

**Output:** enriched `output/portfolio.json` with rationale per stock.

---

### Stage 4 — Leaderboard Submission (15 min)

**File:** `src/leaderboard_client.py`

1. Read submission format from https://cala-leaderboard.apps.rebolt.ai/ "Hacker Guide"
2. Register team
3. POST portfolio to leaderboard API
4. Log response to `output/submission_log.json`

Resubmit after each iteration of score model improvements.

---

## Investment Strategy

### Sector Allocation (Target)

| Sector | Target % | Rationale |
|--------|----------|-----------|
| AI / Semiconductors | 25% | Strongest growth driver in 2025 |
| Cloud / SaaS | 20% | Recurring revenue, high margins |
| Biotech / Healthcare | 15% | Defensive + innovation upside |
| Fintech | 10% | Digital payments secular trend |
| Consumer Tech | 10% | Brand moat + ecosystem lock-in |
| Industrials / Energy | 10% | Infrastructure spend diversification |
| Other | 10% | Opportunistic picks from Cala data |

### Allocation Style — Conviction-Weighted

| Tier | Count | Per-Stock Range |
|------|-------|-----------------|
| Top 10 (highest conviction) | 10 | $15,000–$40,000 |
| Mid tier | 30 | $10,000–$15,000 |
| Diversification buffer | 15 | $5,000–$10,000 |

---

## Definition of Done

- [ ] Cala API fields confirmed via exploration script
- [ ] 100+ NASDAQ companies queried and scored
- [ ] 55 companies selected with no duplicates
- [ ] Every company has $5,000+ allocation, total = exactly $1,000,000
- [ ] Every company has a written rationale citing specific Cala data
- [ ] Portfolio submitted to leaderboard: https://cala-leaderboard.apps.rebolt.ai/
- [ ] Portfolio projected to beat S&P 500 +29.18%

---

## Build Order (Fastest Path to MVP)

```
1. src/explore_cala.py         → confirm field names           (15 min)
2. src/research_agent.py       → collect + score 100 companies (45 min)
3. src/portfolio_allocator.py  → allocate $1M                  (20 min)
4. src/rationale_generator.py  → add rationale per stock       (30 min)
5. src/leaderboard_client.py   → submit                        (15 min)
────────────────────────────────────────────────────────────────────────
Total: ~2 hours to first submission
```

---

## Key Links

- Cala API Docs: https://docs.cala.ai/
- Cala Query Reference: https://docs.cala.ai/api-reference/query
- Cala Search Reference: https://docs.cala.ai/api-reference/search
- Leaderboard: https://cala-leaderboard.apps.rebolt.ai/
- Leaderboard Registration: https://cala-leaderboard.apps.rebolt.ai/register
- Cala Console (API keys): https://console.cala.ai/api-keys
