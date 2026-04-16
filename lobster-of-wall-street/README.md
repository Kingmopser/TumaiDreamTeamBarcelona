# 🦞 Lobster of Wall Street

**Hackathon submission for "The Lobster of Wall Street" by Cala AI.**

An AI investment agent that uses the Cala verified knowledge API to research 109 NASDAQ-listed companies and allocate $1,000,000 across at least 50 stocks — targeting returns that beat the S&P 500 benchmark of +29.18%.

---

## Strategy

Grounded in the AAML research project finding that **financial strength text is the #1 predictor of stock outperformance**, the agent applies a 5-factor multi-signal scoring model:

| Factor | Weight | Signal |
|--------|--------|--------|
| Revenue Growth | 30 pts | YoY growth rate extracted from Cala analysis |
| Profitability | 25 pts | Net/operating margin from Cala financial data |
| Financial Strength | 20 pts | Balance sheet health, cash position, debt level |
| Competitive Moat | 15 pts | Market position, switching costs, brand strength |
| Quality Signals | 10 pts | AI/cloud exposure, analyst consensus, momentum |

**Allocation**: Conviction-weighted (score-proportional), with:
- Sector cap: max 30% per sector
- Position bounds: $5,000 – $50,000 per stock
- Total: exactly $1,000,000

---

## Project Structure

```
lobster-of-wall-street/
├── .env                          # CALA_API_KEY, TEAM_ID, DATA_CUTOFF_DATE
├── requirements.txt
├── src/
│   ├── research_agent.py         # Cala API queries + multi-factor scoring
│   ├── portfolio_allocator.py    # Conviction-weighted allocation engine
│   ├── rationale_generator.py    # Per-stock written justifications
│   ├── leaderboard_client.py     # Submission to leaderboard API
│   └── main.py                   # Orchestration pipeline
├── cache/
│   └── research_cache.json       # Cached Cala API research results
└── output/
    ├── portfolio.json             # Final portfolio with rationales
    └── submission_log.json        # Leaderboard API response log
```

---

## Setup

```bash
cd lobster-of-wall-street
pip install -r requirements.txt

# Edit .env:
# CALA_API_KEY=your-key
# TEAM_ID=your-team-slug
# DATA_CUTOFF_DATE=2025-04-15
```

---

## Usage

```bash
# Full pipeline: research → allocate → generate rationales → save
python src/main.py

# Skip research (use cached Cala results from previous run)
python src/main.py --skip-research

# Dry-run submission (validates payload but does not send)
python src/main.py --skip-research --dry-run

# Submit to leaderboard
python src/main.py --skip-research --submit

# Custom settings
python src/main.py --num-stocks 70 --cutoff-date 2025-04-15 --submit --team-id my-team
```

---

## API Reference

- **Cala API**: `POST https://api.cala.ai/v1/knowledge/search`  
  Natural language financial queries returning verified markdown answers + entity citations.
- **Leaderboard**: `POST https://different-cormorant-663.convex.site/api/submit`  
  Payload: `{team_id, model_agent_name, model_agent_version, transactions: [{nasdaq_code, amount}]}`
