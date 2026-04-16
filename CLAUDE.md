You are going to help me build a submission for a hackathon challenge called **"The Lobster of Wall Street"**, run by a company called **Cala AI**.

---

## 🎯 OBJECTIVE

Build an **AI agent** that simulates being back on **April 15th, 2025**, with **$1,000,000** to invest. The agent must use **Cala's verified knowledge API** to research NASDAQ-listed companies and decide how to allocate that capital across **at least 50 stocks**. The portfolio is then evaluated based on what it would be worth on **April 15th, 2026** (today). Results are submitted to a live leaderboard and ranked in real time.

The benchmark to beat is the **S&P 500 passive index**, which returned **+29.18%** over that period (i.e., $1,000,000 → $1,291,754).

We can also include more information from e.g. Yahoo Finance, Alpha Vantage, Morningstar etc. to combine it with the data we can extract from Cala AI.

---

## 🔑 CALA API

Cala provides a **verified knowledge API** — structured, reliable financial data designed specifically for AI agents. It is the **only data source the agent is allowed to use** for its investment reasoning.

- **Documentation:** https://docs.cala.ai/
- **Sign up for API key:** I have it already
- **Unlimited API credits** are provided during the hackathon

Your first task is to **read the Cala API docs thoroughly** at https://docs.cala.ai/ before writing any code. Understand exactly what endpoints are available, what financial data they return, and how to query them.

---

## 📋 SUBMISSION RULES (non-negotiable)

The portfolio submitted to the leaderboard must satisfy ALL of the following:

| Rule | Detail |
|------|--------|
| Minimum stocks | **50 NASDAQ-listed companies** |
| No duplicates | Each ticker appears only once |
| Minimum per stock | **$5,000** allocated per company |
| Total capital | Exactly **$1,000,000** |
| Resubmissions | Allowed unlimited times |

---

## ⚖️ EVALUATION CRITERIA

The submission is scored on two equally weighted dimensions:

**50% — Leaderboard position** (quantitative): Based purely on portfolio return compared to other teams and the S&P 500 benchmark.

**50% — Qualitative evaluation** of the agent, assessed on:
- Clear, **data-driven rationale** for each stock selection, powered by Cala data
- The agent must be able to **articulate why it chose each specific stock**
- Define until which date the information should be extracted (make it dynamic for now and we define it). TBA from Cala AI during the hackathon.

---

## 🏗️ WHAT TO BUILD

Build the following components:

### 1. Research Agent
An AI agent that calls the Cala API to gather fundamental and financial data on NASDAQ-listed companies as they stood in April 2025. It should assess each company based on Cala's available data signals (financials, fundamentals, or whatever Cala exposes — check the docs) and score/rank them for investment potential.

### 2. Portfolio Allocation Engine
Logic that takes the ranked/scored companies from the research agent and allocates the $1,000,000 budget across at least 50 stocks. It must respect all submission rules. The allocation strategy (equal weight, conviction-weighted, sector-diversified, etc.) should be thoughtful and justified by the data.

### 3. Rationale Generator
For each stock selected, generate a clear written explanation of **why the agent chose it**, grounded in Cala API data. This is critical for the qualitative 50% of the score.

### 4. Leaderboard Submission
Submit the final portfolio via the leaderboard API. The leaderboard is at:
- **Leaderboard:** https://cala-leaderboard.apps.rebolt.ai/
- **Registration:** https://cala-leaderboard.apps.rebolt.ai/register

Check the "Hacker Guide" section on the leaderboard site for the exact submission API format (payload structure, authentication, endpoint).

---

## 📁 SUGGESTED PROJECT STRUCTURE

```
lobster-of-wall-street/
├── README.md
├── .env                  # CALA_API_KEY
├── src/
│   ├── research_agent.py       # Queries Cala API, scores companies
│   ├── portfolio_allocator.py  # Allocation logic, enforces rules
│   ├── rationale_generator.py  # Produces per-stock written justifications
│   ├── leaderboard_client.py   # Handles submission API calls
│   └── main.py                 # Orchestrates the full pipeline
├── output/
│   ├── portfolio.json          # Final allocation: [{ticker, amount, rationale}]
│   └── submission_log.json     # Leaderboard API responses
```

---

## ✅ DEFINITION OF DONE

The project is complete when:

1. The agent successfully queries the Cala API and retrieves data on NASDAQ companies
2. It selects at least 50 stocks with no duplicates
3. Each stock has a minimum $5,000 allocation and the total sums to exactly $1,000,000
4. Each stock has a written rationale citing specific Cala data
5. The portfolio has been successfully submitted to the leaderboard API and appears on https://cala-leaderboard.apps.rebolt.ai/
6. The portfolio's projected return beats the S&P 500 benchmark of +29.18%

---

## ⚠️ IMPORTANT REMINDERS

- The agent's reasoning must be **explainable and data-driven**, not arbitrary.
- **Read the Cala docs first** before writing any code. The entire strategy depends on what data Cala actually exposes.
- Start by exploring the Cala API interactively to understand what's available before designing the selection strategy.

---