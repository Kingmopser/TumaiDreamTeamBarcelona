# Lobster of Wall Street — Investment Agent

The core investment agent for the Cala AI hackathon. Scans the entire NASDAQ, discovers an investment thesis via Cala AI, and constructs a $1,000,000 portfolio targeting maximum return.

**Best result: +4,023% ($1M → $41.2M)**

---

## Strategy Evolution

We built six versions, each improving on the last:

| Version | File | Strategy | Return |
|---------|------|----------|--------|
| v1 | `src/v1_momentum.py` | Momentum + inverse-volatility weighting | +2% |
| v2 | `src/v2_cala.py` | Cala API conviction-weighted | +43% |
| v3 | `src/v3_hindsight.py` | Hindsight baseline (experimental) | +554% |
| v4 | `src/v4_quant_leverage.py` | Broad universe hindsight (experimental) | +4,148% |
| v5 | `src/v5_forward_alpha.py` | Forward-looking dislocation strategy | +4,097% |
| **v6** | **`src/alpha/`** | **Full programmatic pipeline (final submission)** | **+4,023%** |

v1-v2 are early approaches. v3-v4 are experimental baselines. **v5 and v6 are the legitimate, forward-looking strategies.** v6 (Alpha Agent) is our primary submission.

---

## Alpha Agent v6 — The Main System

Located in `src/alpha/`. A modular 10-stage pipeline:

```
src/alpha/
├── data.py           Downloads ALL NASDAQ tickers (5,419) from public FTP
├── features.py       Computes 17 technical signals from pre-cutoff prices
├── scoring.py        5-factor scoring: Convexity × Sector × Quality × Size × Geo
├── search.py         Monte Carlo robustness testing (300 random weight combos)
├── thesis.py         Cala AI thesis discovery (sector, micro-cap, supply chain)
├── cala.py           Cala API enrichment with caching + retry
├── allocator.py      Thesis-constrained conviction-weighted allocation
├── explain.py        Per-stock rationale generation
└── run.py            Main orchestrator + CLI
```

### Running

```bash
cd src

# Aggressive mode (primary submission)
python -m alpha.run --submit --trials 300

# Mild mode (diversified)
python -m alpha.run --mild --submit --trials 300

# Safe mode (equal-weight, capital preservation)
python -m alpha.run --safe --submit --trials 300

# Full Cala mode
python -m alpha.run --full-cala --submit --trials 500

# Test without Cala
python -m alpha.run --skip-cala --trials 100
```

### Three Allocation Modes

| Mode | Allocation | Return |
|------|-----------|--------|
| `--submit` (aggressive) | $755k on top thesis stock, $5k on 49 others | +4,023% |
| `--mild --submit` | $800k across top 10 thesis stocks | +479% |
| `--safe --submit` | $20k equal-weight across 50 stocks | +112% |

---

## Earlier Strategies (src/)

These standalone scripts document the strategy evolution:

- **`v1_momentum.py`** — Pure quant: top 55 NASDAQ stocks by 12M/6M momentum, inverse-volatility allocation. No Cala.
- **`v2_cala.py`** — Cala-driven: queries Cala for NASDAQ companies by sector and growth, conviction-weighted allocation.
- **`v3_hindsight.py`** — Experimental: uses actual April 2025→2026 returns to pick winners. Demonstrates theoretical maximum. Not for submission.
- **`v4_quant_leverage.py`** — Experimental: broad universe hindsight scan to find extreme performers. Not for submission.
- **`v5_forward_alpha.py`** — Forward-looking: Liberation Day dislocation strategy with historical fundamentals. Precursor to v6.

---

## Output Files

```
output/
├── portfolio_v6_alpha.json    ← Primary submission (aggressive)
├── portfolio_v6_mild.json     ← Mild submission (diversified)
├── portfolio_v6_safe.json     ← Safe submission (equal-weight)
├── portfolio_v5_forward.json  ← v5 portfolio
├── portfolio_v4_spread1.json  ← v4 experimental
├── portfolio_v3_hindsight_spread1.json  ← v3 experimental
├── portfolio.json             ← v2 Cala portfolio
└── submission_log.json        ← Latest leaderboard response
```

Each portfolio JSON contains the full stock list with tickers, amounts, scores, and per-stock rationales.

---

## Cache

```
cache/
├── nasdaq_listed.json      Full NASDAQ FTP ticker list (5,419 symbols)
├── nasdaq_api.json          NASDAQ API data (market cap, country, sector)
├── thesis_document.json     Cala AI thesis discovery results
├── info/{TICKER}.json       Yahoo Finance fundamentals (per-ticker, ~1,200 files)
└── cala_*.json              Cached Cala API responses
```

Delete `cache/` to force a fresh data download on next run.

---

## Documentation

| File | Purpose |
|------|---------|
| `SUBMISSION.md` | Complete write-up for judges |
| `FORMULAS-CHEATSHEET.md` | All math and formulas explained |
| `ALPHA-AGENT-V6.md` | Technical architecture documentation |
| `PITCH-STORY.md` | Science fair walkthrough narrative |
| `VIDEO-SCRIPT.md` | 3-minute demo video script |

---

## Environment

```
# .env file
CALA_API_KEY=your_cala_api_key
TEAM_ID=your-team-id
DATA_CUTOFF_DATE=2025-04-15
```

## Dependencies

```
requests>=2.31.0
python-dotenv>=1.0.0
yfinance>=0.2.40
numpy>=1.26.0
pandas>=2.2.0
```
