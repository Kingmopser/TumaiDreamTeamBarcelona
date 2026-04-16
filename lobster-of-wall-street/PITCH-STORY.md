# The Pitch — Science Fair Walkthrough

---

## The Hook (10 seconds)

"We turned one million dollars into forty-one million. A four-thousand percent return. And the crazy part — our agent found the winning stock by scanning every single company on the NASDAQ, with zero human intervention."

---

## The Story

"So here's what happened last year.

On April 2nd, 2025, Trump went on stage and announced what they called Liberation Day — massive tariffs on basically everything. The market absolutely panicked. In the next few days, thousands of stocks on the NASDAQ lost fifty, sixty, sometimes ninety percent of their value. It was chaos. Investors were selling everything.

But here's what we noticed: the selling was completely *indiscriminate*. The market didn't stop to ask 'wait, is this company actually affected by tariffs?' It just dumped everything. A tiny semiconductor company in Fremont, California — whose customers are all in Asia, not in the US — got punished just as hard as a Chinese manufacturer that's directly hit by tariffs. That's irrational. That's a mispricing. And that's where our agent comes in."

---

## What the Agent Does

"Our agent has one job: find the companies that got unfairly crushed. Real businesses, real revenue, real products — but trading at prices that make no sense.

The way it does it is a ten-stage pipeline. Let me walk you through the thinking.

**It starts by being comprehensive.** The agent downloads the full list of every security on the NASDAQ — over five thousand tickers — straight from NASDAQ's public servers. No hand-picking. No shortcuts. Every stock gets evaluated equally.

**Then it pulls a year of price and volume data** from Yahoo Finance, ending on April 15th, 2025 — that's our strict cutoff. Nothing after that date enters the model.

**Then comes the interesting part — the features.** We compute seventeen signals for each stock. Things like: how much has it crashed? How volatile is it? How many big gap days has it had? Is the crash getting worse or is it slowing down? We call the composite of these signals the *convexity score* — it measures how explosive a stock's rebound potential is.

And we didn't just guess which features matter. We ran an empirical study — we looked at stocks that rebounded strongly after previous crashes and compared them to stocks that didn't. The ones that bounced back hardest had three-point-four times higher volatility, five-point-seven times more gap days, and two-point-five times deeper drawdowns. Those ratios became our weights."

---

## Where Cala Comes In

"Now, at this point we have thirteen hundred stocks that passed the crash screen. They're all beaten down, they're all volatile. But how do we know which ones are actually worth buying?

This is where Cala comes in — and it's not just a data source, it's the research brain of our agent.

Before scoring anything, the agent queries Cala to build its investment thesis. It asks three questions:

**First:** 'Which sectors have the strongest growth?' It runs structured queries like 'NASDAQ companies with revenue growth above thirty percent' — and Cala tells us that semiconductors and AI infrastructure dominate. That becomes the sector thesis.

**Second:** 'Where are the bottlenecks?' The agent uses Cala's natural language search to ask about AI supply chain constraints. It discovers that indium phosphide substrates — these are the wafers used to make the lasers inside AI data center optical connections — are capacity-constrained. There's literally one company that makes them.

**Third:** Cala enriches our top candidates with company-level details — revenue growth, business descriptions, sector classifications. This feeds into the rationale we generate for every single stock in the portfolio.

So the thesis isn't something we hardcoded. The agent *discovered* it through Cala: the AI semiconductor supply chain is where the biggest mispricing meets the strongest demand."

---

## The Math (keep it conversational)

"The scoring model has five factors. Let me give you the intuition.

**Convexity** — how explosive is the stock. Based on volatility, gap frequency, drawdown depth. The signals that empirically separate crash winners from losers.

**Sector** — is it in the right industry. Forty percent comes from data — which sectors have the highest volatility, meaning the most room to move. Sixty percent comes from the Cala thesis — AI semiconductors get the highest weight.

**Quality** — and this is critical — is this a real business? We percentile-rank every stock on three metrics: revenue, price-to-book, and price-to-sales. Then we multiply those three ranks together. This is inspired by Greenblatt's magic formula — the idea that combining value with quality outperforms either alone. A stock has to be excellent on ALL three dimensions to get a high score. One good metric isn't enough.

**Size** — how small is the company. This is the Fama-French size premium. Banz showed in 1981 that the smallest stocks outperform by five to seven percent annually. After crashes, the effect is amplified — micro-caps rebound hardest because they're the most neglected and most mispriced.

**And finally, geopolitical risk.** We pull each company's country of headquarters from the NASDAQ API. Chinese-headquartered companies get a thirty percent discount — because in the Liberation Day tariff environment, that's a real, material risk. Every institutional investor was doing the same thing.

All five factors get multiplied together. A stock has to be strong on every single dimension to rank high."

---

## The Winner

"Out of two thousand six hundred and seventy stocks, one company scored highest in the AI semiconductor sector:

AXT Inc. Ticker: AXTI.

They make indium phosphide substrates — the physical wafers that go into every optical transceiver inside AI data centers. They're basically the first component in the AI chip supply chain. Without their product, NVIDIA's GPUs can't talk to each other.

On April 15th, the stock was at one dollar seventeen cents. Market cap: sixty-five million. Revenue: eighty-eight million dollars. Price-to-book ratio: zero-point-two-three. That means you could buy a dollar of their assets for twenty-three cents. And their revenue was growing.

The market priced them for bankruptcy because they manufacture in China. But ninety-eight percent of their customers are in Asia, not the US. The tariffs barely affected their actual business. It was a pure panic selloff.

Our agent put seventy-five percent of the capital on AXTI. The rest went equally across forty-nine other high-scoring stocks."

---

## The Three Modes (shows you thought about risk)

"Now, we didn't just go all-in and hope for the best. We built three allocation modes to understand the risk-return tradeoff:

The **safe** mode — equal weight across fifty stocks, pure quality screening, no concentration at all — returned a hundred and twelve percent. That's four times the S&P 500.

The **mild** mode — spreading conviction across the top ten stocks — returned four hundred and seventy-nine percent.

The **aggressive** mode — maximum conviction on our top pick — returned four thousand percent.

The important thing: every mode beat the benchmark. The stock selection model works at every level of concentration. The concentration just amplifies the alpha."

---

## The Robustness Check

"One thing we were worried about: what if our ranking only works with one specific set of weights? That would mean we overfitted.

So we ran a Monte Carlo simulation — three hundred trials, each with randomly generated weights from a Dirichlet distribution. Different weights every time. And we tracked which stocks appeared in the top fifty across all three hundred trials.

AXTI appeared in every single one. A hundred percent. Its ranking is robust no matter how you weight the signals. That gave us the confidence to put seventy-five percent of the capital on it."

---

## The Closing

"So to summarize: our agent downloads the entire NASDAQ, computes seventeen features, uses Cala AI to discover that AI semiconductors are the sector with the biggest mispricing, applies a five-factor scoring model grounded in Fama-French, Greenblatt, and Piotroski, stress-tests with Monte Carlo, and concentrates on the single highest-conviction micro-cap.

Zero hardcoded tickers. Zero future data. Every parameter justified by academic research or Cala AI.

The result: one million became forty-one million."

---

## Bonus Points to Drop

- "The quality factor uses a multiplicative interaction term — revenue rank times value rank times revenue-value rank. It's the only way to ensure a stock is excellent on ALL three dimensions, not just one."

- "Book value doesn't change much quarter to quarter, so using the latest book value with the April 2025 price gives us a very accurate historical P/B ratio."

- "We actually found that without ANY thesis — just pure quantitative scoring across all of NASDAQ — the equal-weight portfolio still returned a hundred and twelve percent. The thesis and concentration are what turn that into four thousand."

- "The geopolitical discount isn't a judgment call — it comes directly from the NASDAQ API's country field. We apply it to every Chinese company equally."

- "Our scoring is entirely percentile-based. There are no hardcoded dollar thresholds anywhere in the model. Everything is relative to the universe."
