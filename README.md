# The Lobster of Wall Street — TUM.ai Dreamteam

**Hackathon: Cala AI — Project Barcelona (April 2025)**

An AI-driven stock selection agent that invests $1,000,000 across 50+ NASDAQ stocks. The agent scans the entire NASDAQ, uses Cala AI for thesis discovery, and applies a multi-factor scoring model grounded in academic finance.

**Best result: +4,023% return ($1M → $41.2M)**

---

## Project Structure

```
.
├── lobster-of-wall-street/    ← Main investment agent (Alpha Agent v6)
│   ├── src/alpha/             ← Core scoring pipeline (10 modules)
│   ├── src/                   ← Earlier strategy versions (v1-v5)
│   ├── output/                ← Portfolio JSONs + submission logs
│   ├── cache/                 ← Cached NASDAQ data, Cala responses, yfinance
│   ├── SUBMISSION.md          ← Full write-up for judges
│   ├── FORMULAS-CHEATSHEET.md ← All math explained simply
│   ├── PITCH-STORY.md         ← Science fair walkthrough script
│   └── VIDEO-SCRIPT.md        ← 3-minute demo recording script
│
├── src/                       ← UI & early Cala exploration pipeline
│   ├── main.py                ← Orchestrator for Cala-based approach
│   ├── research_agent.py      ← Cala API research module
│   ├── portfolio_allocator.py ← Allocation logic
│   ├── rationale_generator.py ← Per-stock rationale via Cala + Claude
│   ├── explore_cala.py        ← Cala API schema discovery
│   └── leaderboard_client.py  ← Submission client
│
├── output/                    ← UI pipeline outputs (portfolio iterations)
│
├── .claude/skills/            ← Claude Code financial analysis skills
│   ├── trade-sentiment/       ← News & social sentiment analysis
│   ├── trade-fundamental/     ← Fundamental analysis (DCF, ratios)
│   ├── trade-technical/       ← Technical analysis (patterns, indicators)
│   ├── trade-screen/          ← Stock screener
│   ├── trade-thesis/          ← Investment thesis builder
│   └── ... (15 skills total)  ← See .claude/skills/README.md
│
├── ALPHA-MODE.md              ← System design prompt for the agent
├── cala-api-test.ipynb        ← Jupyter notebook for Cala API exploration
└── .gitignore
```

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r lobster-of-wall-street/requirements.txt
```

### 2. Set up environment

Create `lobster-of-wall-street/.env`:
```
CALA_API_KEY=your_cala_api_key
TEAM_ID=your-team-id
```

### 3. Run the Alpha Agent

```bash
cd lobster-of-wall-street/src

# Full pipeline — aggressive mode (max conviction, ~4000% return)
python -m alpha.run --submit --trials 300

# Mild mode (diversified across top 10, ~479% return)
python -m alpha.run --mild --submit --trials 300

# Safe mode (equal-weight, capital preservation, ~112% return)
python -m alpha.run --safe --submit --trials 300

# With aggressive Cala usage
python -m alpha.run --full-cala --submit --trials 500

# Skip Cala (faster, for testing)
python -m alpha.run --skip-cala --trials 100
```

First run downloads all data from NASDAQ + Yahoo Finance (~5-8 min). Subsequent runs use cache (~2-3 min).

### 4. Run the UI exploration pipeline

```bash
# From project root
python src/main.py              # dry-run
python src/main.py --submit     # submit to leaderboard
```

---

## The Three Strategy Modes

| Mode | Command | Allocation | Return | Risk |
|------|---------|-----------|--------|------|
| **Aggressive** | `--submit` | $755k on #1, $5k on 49 others | +4,023% | High (single-stock) |
| **Mild** | `--mild --submit` | $800k across top 10, $5k on 40 | +479% | Medium |
| **Safe** | `--safe --submit` | $20k equal-weight across 50 | +112% | Low (diversified) |

All three modes use the same scoring pipeline and stock selection. The only difference is capital allocation.

---

## How It Works (Summary)

1. **Download** all 5,419 NASDAQ tickers from public FTP
2. **Filter** to 2,670 by market cap (>$20M)
3. **Compute** 17 technical features from pre-April 2025 price data
4. **Screen** to ~1,300 crash casualties (>30% drawdown)
5. **Fetch** fundamentals from Yahoo Finance for screened stocks
6. **Monte Carlo** search: 300 random weight combos for robustness
7. **Score** with 5 factors: Convexity × Sector × Quality × Size × Geo Risk
8. **Discover** thesis via Cala AI: AI semiconductor supply chain
9. **Allocate** capital with thesis-constrained conviction
10. **Submit** to leaderboard

See `lobster-of-wall-street/SUBMISSION.md` for the full detailed write-up.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| `lobster-of-wall-street/SUBMISSION.md` | Complete write-up for judges — everything about the strategy |
| `lobster-of-wall-street/FORMULAS-CHEATSHEET.md` | All math and formulas explained simply |
| `lobster-of-wall-street/PITCH-STORY.md` | Science fair walkthrough narrative |
| `lobster-of-wall-street/VIDEO-SCRIPT.md` | 3-minute demo video script |
| `lobster-of-wall-street/ALPHA-AGENT-V6.md` | Technical system documentation |
| `ALPHA-MODE.md` | System design prompt that guided the architecture |

---

## Tech Stack

- **Python 3.12** — core language
- **Cala AI API** — thesis discovery, stock enrichment, rationale generation
- **Yahoo Finance (yfinance)** — price data, volume, fundamentals
- **NASDAQ FTP/API** — ticker universe, market caps, country data
- **NumPy / Pandas** — feature engineering, scoring
- **Claude Code Skills** — financial analysis assistant (sentiment, technical, fundamental)

---

## Team

**TUM.ai Dreamteam**
