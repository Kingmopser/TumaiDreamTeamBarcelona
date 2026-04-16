# UI & Early Exploration Pipeline

This directory contains the early Cala-based pipeline used for UI visualization and initial portfolio exploration. Built by Bakir for the dashboard/visualization layer.

---

## What's Here

| File | Purpose |
|------|---------|
| `main.py` | Pipeline orchestrator — runs research → allocate → rationale → submit |
| `research_agent.py` | Queries Cala API to discover and score NASDAQ companies |
| `portfolio_allocator.py` | Allocates $1M across top-scoring stocks |
| `rationale_generator.py` | Generates per-stock written justifications using Cala + Claude |
| `explore_cala.py` | Cala API schema discovery — run this first to understand what Cala returns |
| `leaderboard_client.py` | Submits portfolio to the hackathon leaderboard |

---

## How to Run

```bash
# From project root
python src/main.py              # full pipeline, dry-run
python src/main.py --submit     # full pipeline + submit to leaderboard
python src/main.py --from 2     # start from stage 2 (reuse cached research)
```

Requires `.env` in `lobster-of-wall-street/` with `CALA_API_KEY` and `TEAM_ID`.

---

## Pipeline Stages

1. **Stage 1 — Research** (`research_agent.py`): Queries Cala for NASDAQ companies by sector and financial metrics. Scores each company on revenue growth, profitability, financial strength, competitive moat, and quality signals.

2. **Stage 2 — Allocation** (`portfolio_allocator.py`): Takes scored companies and distributes $1M with conviction weighting. Enforces rules: 50+ stocks, $5k minimum, no duplicates.

3. **Stage 3 — Rationale** (`rationale_generator.py`): For each stock in the portfolio, generates a written explanation of why it was selected, referencing specific Cala data.

4. **Stage 4 — Submit** (`leaderboard_client.py`): Posts the portfolio to the hackathon leaderboard API.

---

## Output

Results go to `../output/`:
- `portfolio_v*.json` — portfolio iterations from UI testing
- `submission_v*.json` — leaderboard submission responses
- `companies_raw.json` — raw Cala research results
- `companies_scored.json` — scored company data
- `api_schema_notes.md` — Cala API schema documentation

---

## Relationship to Alpha Agent

This pipeline was the first approach — using Cala directly for stock selection and scoring. The Alpha Agent (`lobster-of-wall-street/src/alpha/`) evolved from this by adding Yahoo Finance price data, Monte Carlo robustness testing, and a multi-factor scoring model. Both pipelines use the same leaderboard submission client.
