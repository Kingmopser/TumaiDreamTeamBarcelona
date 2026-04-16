# Claude Code Financial Analysis Skills

15 specialized financial analysis skills for Claude Code. These turn Claude into an AI trading analyst that can perform fundamental analysis, technical analysis, sentiment analysis, and more — all from the command line.

---

## Available Skills

| Skill | Command | What It Does |
|-------|---------|-------------|
| **Analyze** | `/trade-analyze TICKER` | Full orchestrated analysis (calls other skills) |
| **Fundamental** | `/trade-fundamental TICKER` | DCF valuation, financial ratios, balance sheet |
| **Technical** | `/trade-technical TICKER` | Chart patterns, indicators, support/resistance |
| **Sentiment** | `/trade-sentiment TICKER` | News sentiment, social buzz, analyst ratings (0-100 score) |
| **Earnings** | `/trade-earnings TICKER` | Earnings history, surprises, guidance analysis |
| **Sector** | `/trade-sector SECTOR` | Sector overview, rotation analysis, top picks |
| **Screen** | `/trade-screen CRITERIA` | Stock screener with custom filters |
| **Compare** | `/trade-compare TICK1 TICK2` | Side-by-side comparison of two stocks |
| **Risk** | `/trade-risk TICKER` | Risk metrics: VaR, beta, max drawdown, volatility |
| **Options** | `/trade-options TICKER` | Options chain analysis, unusual activity, strategies |
| **Portfolio** | `/trade-portfolio` | Portfolio analysis, correlation, optimization |
| **Thesis** | `/trade-thesis TICKER` | Build a bull/bear investment thesis |
| **Quick** | `/trade-quick TICKER` | Quick 30-second overview |
| **Watchlist** | `/trade-watchlist` | Manage and monitor a watchlist |
| **Report PDF** | `/trade-report-pdf TICKER` | Generate a PDF research report |

---

## How to Use

These skills work with Claude Code (CLI). Just type the command:

```bash
# In Claude Code
/trade-sentiment AXTI
/trade-fundamental NVDA
/trade-compare AXTI AAOI
/trade-screen "semiconductor, market_cap < 500M, revenue_growth > 20%"
```

---

## Relevance to the Hackathon

These skills were built as part of the financial analysis toolkit. The sentiment analysis skill (`trade-sentiment`) demonstrates how we approach qualitative analysis of stocks — understanding news flow, analyst consensus, and market positioning. This complements the quantitative Alpha Agent pipeline.

The `trade-thesis` and `trade-fundamental` skills show the kind of deep-dive analysis our agent would perform on its top candidates — similar to the Cala AI thesis discovery stage in the main pipeline.

---

## File Structure

Each skill is a markdown file with instructions for Claude:

```
.claude/skills/
├── trade-analyze/SKILL.md
├── trade-compare/SKILL.md
├── trade-earnings/SKILL.md
├── trade-fundamental/SKILL.md
├── trade-options/SKILL.md
├── trade-portfolio/SKILL.md
├── trade-quick/SKILL.md
├── trade-report-pdf/SKILL.md
├── trade-risk/SKILL.md
├── trade-screen/SKILL.md
├── trade-sector/SKILL.md
├── trade-sentiment/SKILL.md
├── trade-technical/SKILL.md
├── trade-thesis/SKILL.md
└── trade-watchlist/SKILL.md
```
