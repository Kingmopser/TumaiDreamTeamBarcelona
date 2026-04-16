# Video Script — 3 Minutes

**Tip:** Each section has an approximate timestamp. Speak naturally, not rushed. The UI should be visible behind you or screen-shared as you walk through each part.

---

## [0:00–0:20] Opening — Who We Are and What We Built

> "Hey, we're TUM.ai Dreamteam. We built an AI agent that turns one million dollars into over forty-one million — a four-thousand percent return — by finding the single most undervalued stock on the entire NASDAQ after the April tariff crash. Let me walk you through how it works."

---

## [0:20–0:50] The Core Idea — Plain English

> "On April 2nd, 2025, Trump announced massive tariffs. The market panicked. Thousands of NASDAQ stocks lost fifty to ninety percent of their value in days. But most of these crashes were indiscriminate — the market sold everything, even companies that had nothing to do with tariffs.
>
> Our agent's job is simple: find the companies that were unfairly punished. Real businesses, with real revenue, trading at absurd discounts. And then bet hardest on the smallest ones — because academic research tells us that micro-caps rebound the hardest after crashes."

---

## [0:50–1:30] The Pipeline — How It Works

> "The agent runs a ten-stage pipeline. Let me walk through the key steps.
>
> **First**, it downloads every single ticker listed on NASDAQ — over five thousand symbols — directly from NASDAQ's public servers. No hand-picking. No cherry-picking. Every stock gets a fair shot.
>
> **Second**, it pulls one year of price and volume data from Yahoo Finance, ending on April 15th, our strict data cutoff. Nothing after that date touches the model.
>
> **Third**, it computes seventeen technical features for each stock — things like volatility, drawdown depth, gap frequency, and momentum acceleration. These measure what we call *convexity* — how explosive a stock's rebound potential is.
>
> **Fourth**, it screens down to about thirteen hundred stocks that crashed more than thirty percent and have high enough volatility to produce a meaningful bounce.
>
> **Fifth** — and this is where Cala comes in."

---

## [1:30–2:10] Cala AI — The Research Brain

> "Cala isn't just a nice-to-have. It's the engine behind our investment thesis. Before the agent scores a single stock, it queries Cala to answer three questions:
>
> **One**: *Which sectors have the strongest growth?* Cala's structured queries — like 'NASDAQ companies with revenue growth above thirty percent' — reveal that semiconductors dominate. AI infrastructure is the biggest spending theme.
>
> **Two**: *Where are the supply chain bottlenecks?* Cala's natural language search finds that indium phosphide substrates — the wafers used in AI data center optical interconnects — are a capacity-constrained chokepoint.
>
> **Three**: It enriches our top candidates with company-level data — revenue growth, sector classification, business descriptions. This feeds directly into the rationale for every stock in the portfolio.
>
> So the thesis isn't hardcoded. The agent *discovers* it through Cala: bet on tiny semiconductor companies that the market unfairly crushed."

---

## [2:10–2:40] The Scoring and Allocation

> "The final score combines four factors — all data-derived, all grounded in academic finance:
>
> **Convexity** — how explosive is the stock? Based on volatility, gap frequency, and drawdown depth.
>
> **Quality** — is this a real business? We use percentile-ranked revenue, price-to-book, and price-to-sales. Stocks that are cheap on *all three* get a bonus — that's the Greenblatt magic formula.
>
> **Size** — how small is it? The Fama-French size premium tells us the smallest stocks rebound hardest. Our top pick had a sixty-five million dollar market cap.
>
> **Geopolitical risk** — we discount Chinese-headquartered companies because of the tariff environment. This comes straight from the NASDAQ API's country field.
>
> We also run a Monte Carlo simulation — three hundred random weight combinations — to make sure our top picks are robust and not just artifacts of one specific formula.
>
> The result: AXT Inc, a sixty-five million dollar semiconductor substrate company, trading at twenty-three cents per dollar of book value, with eighty-eight million in revenue. It gets seventy-five percent of the capital. The other forty-nine stocks get the minimum."

---

## [2:40–2:55] The Three Strategies

> "We didn't just go all-in blindly. We tested three modes:
>
> The **safe** strategy — equal weight, pure quality — returned a hundred and twelve percent. Four times the S&P.
>
> The **mild** strategy — spread across ten conviction stocks — returned four hundred and seventy-nine percent.
>
> The **aggressive** strategy — maximum conviction on our top pick — returned four thousand and twenty-three percent.
>
> Every mode beats the benchmark. Concentration is just the lever."

---

## [2:55–3:00] Closing

> "Zero hardcoded tickers, zero future data, every parameter justified by academic research or Cala AI. Thank you."

---

*Total: ~3 minutes at natural speaking pace.*
