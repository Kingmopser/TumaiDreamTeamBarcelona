# Formulas Cheatsheet

---

## The Big Picture

Every stock gets a single number — its **Final Score**. The stock with the highest score in the AI semiconductor sector gets 75% of the money. The formula:

```
Final Score = Convexity × Sector × Quality × Size × Geo Risk
```

Five factors multiplied together. If any factor is weak, the whole score drops. A stock must be strong on ALL dimensions to rank high. Here's each one:

---

## Factor 1: Convexity — "How explosive is this stock?"

This measures tail-event potential from price data. Six signals, each turned into a percentile rank (0 to 1), then combined:

```
Convexity = 0.25 × volatility_rank
          + 0.20 × gap_frequency_rank
          + 0.20 × drawdown_depth_rank
          + 0.15 × momentum_acceleration_rank
          + 0.10 × twelve_month_return_rank
          + 0.10 × volume_expansion_rank
```

**What's a percentile rank?** If a stock's volatility is higher than 90% of other stocks in our universe, its volatility_rank is 0.90. This way we compare apples to apples — every signal is on the same 0-to-1 scale.

**Where do the weights come from?** We compared 15 stocks that historically produced >500% returns after crashes against 15 normal stocks. The features with the biggest separation between winners and losers got the highest weights:

| Signal | Winner avg | Control avg | Separation | Weight |
|--------|-----------|-------------|------------|--------|
| Volatility | 144% | 43% | 3.4x | 25% |
| Gap frequency | 22 days | 4 days | 5.7x | 20% |
| Drawdown depth | -70% | -28% | 2.5x | 20% |
| Mom acceleration | +12% | -10% | sign flip | 15% |
| 12M return | +29% | +10% | 2.9x | 10% |
| Volume expansion | 0.9x | 1.1x | ~none | 10% |

**Why 0.25 for volatility?"** → "Because volatility showed the largest separation between high-return stocks and average stocks in our empirical analysis — 3.4x difference."

---

## Factor 2: Sector — "Is it in the right industry?"

Two components blended together:

```
Sector = 0.40 × volatility_rank_of_sector + 0.60 × thesis_multiplier
```

**Component 1 (40% — data-driven):** We group all stocks by their sector (Technology, Healthcare, etc.), compute the median volatility of each sector, and rank them. Higher-volatility sectors get a higher score. This is purely computed from the price data.

**Component 2 (60% — Cala AI thesis):** Our agent queries Cala and discovers that AI/semiconductor is the strongest growth sector. So Technology gets 1.30, Healthcare gets 1.05, Consumer gets 0.90, etc.

**On top of that**, stocks in specific AI supply chain industries get a tiered boost:

| Tier | Industries | Extra Multiplier | Why |
|------|-----------|-----------------|-----|
| 1 | Semiconductors, Semiconductor Equipment & Materials | ×1.15 | Direct chip fabrication — bottleneck |
| 2 | Electronic Components, Communication Equipment | ×1.05-1.08 | Supporting components |
| 3 | Computer Hardware, Scientific Instruments | ×1.02-1.03 | Adjacent products |

**Why semiconductors?"** → "Our agent queried Cala for 'NASDAQ companies with revenue growth above 30%' and found semiconductors dominated the results. We also queried for AI supply chain bottlenecks and Cala identified semiconductor substrates as capacity-constrained. This matches the public data: NVIDIA reported 122% revenue growth in February 2025, and data center capex hit all-time highs."

---

## Factor 3: Quality — "Is this a real business or junk?"

Three sub-factors, all percentile-ranked, plus an interaction bonus:

```
Base Quality = 0.30 × revenue_rank + 0.35 × value_rank + 0.35 × revenue_value_rank
```

Where:
- **revenue_rank** = percentile rank of total annual revenue (higher = better)
- **value_rank** = percentile rank of inverse P/B ratio (lower P/B = better)
- **revenue_value_rank** = percentile rank of inverse P/S ratio (lower P/S = better)

**How we compute historical P/B and P/S:**
```
Historical P/B = stock price on April 15, 2025 ÷ book value per share
Historical P/S = (stock price × shares outstanding) ÷ annual revenue
```
We use the April 2025 price (from Yahoo Finance) divided by the latest book value and revenue. Book value doesn't change much quarter to quarter, so this is a valid approximation for the valuation as of our decision date.

**The interaction bonus (Greenblatt-inspired):**
```
Interaction = revenue_rank × value_rank × revenue_value_rank
Quality = Base Quality + 0.40 × Interaction
```

This is a multiplicative product. A stock must be top-ranked on ALL THREE dimensions to get a big bonus. Being excellent on just one dimension isn't enough — the product would still be small.

Example: AXTI has revenue_rank ≈ 0.65, value_rank ≈ 0.97, revenue_value_rank ≈ 0.85.
Interaction = 0.65 × 0.97 × 0.85 = 0.54. That's a strong bonus.

A junk stock with no revenue: revenue_rank ≈ 0.05. Even if value_rank is 0.99, the interaction = 0.05 × 0.99 × anything = tiny. Junk gets filtered out.

**Then quality gets amplified:**
```
Quality_Factor = (0.35 + 0.65 × Quality) ^ 1.3
```

The 1.3 exponent makes differences in quality matter MORE. A quality score of 1.0 gives factor 1.0. A quality score of 0.5 gives factor 0.79. A quality score of 0.1 gives factor 0.46. So low-quality stocks get heavily penalised.

**Why the interaction term?"** → "It's based on Greenblatt's magic formula and Piotroski's F-Score — the academic finding that combining value with quality outperforms either alone. The multiplicative form ensures a stock must be strong on ALL dimensions simultaneously, not just one."

---

## Factor 4: Size — "How small is this stock?"

```
Size Factor = 0.75 + 0.75 × (1 - market_cap_percentile_rank)
```

The smallest stocks in the universe get 1.50. The largest get 0.75. Everything in between is linear.

**How we compute historical market cap:**
```
Market Cap (April 2025) = stock price on April 15, 2025 × shares outstanding
```

AXTI: $1.17 × 55.6M shares = $65M → nano-cap → Size Factor ≈ 1.47

**Why favor small stocks?"** → "The Fama-French size premium. Banz 1981 showed the smallest decile outperforms by 5-7% annually. After market crashes specifically, micro-caps rebound hardest because they have less institutional coverage, more information asymmetry, and bigger mispricing."

---

## Factor 5: Geopolitical Risk — "Is it exposed to tariffs?"

```
Geo Risk = 0.70  if headquartered in China
         = 0.90  if country is unknown
         = 1.00  otherwise
```

Comes directly from the NASDAQ API's country-of-headquarters field. Not a judgment call — purely data-driven.

**Why penalise China?"** → "On April 2, 2025, the US imposed 145% tariffs on Chinese goods. Chinese-headquartered companies face direct tariff exposure, potential HFCAA delisting risk, and export controls. Every institutional investor was reassessing China exposure. This is a standard country-risk premium."

---

## How AXTI Becomes #1

Putting it all together for AXT Inc:

| Factor | Value | Why |
|--------|-------|-----|
| Convexity | 0.560 | 70% drawdown, 112% volatility, 17 gap days |
| Sector | ~1.35 | Technology group (1.30 thesis) × Tier 1 semiconductor (×1.15) × vol component |
| Quality_Factor | ~1.0 | Revenue $88M, P/B 0.23 (bottom 3%), P/S 0.74 — strong interaction |
| Size | ~1.37 | $65M market cap — nano-cap percentile |
| Geo Risk | 1.00 | US-headquartered (Fremont, CA) |

```
Final Score = 0.560 × 1.35 × 1.0 × 1.37 × 1.00 ≈ 0.96
```

This is the highest score among all Tier 1 semiconductor stocks in a universe of 2,670 NASDAQ tickers. The agent selects it as the conviction pick.

---

## The Three Allocation Modes

All three use the SAME scoring pipeline and stock selection. The only difference is how capital is distributed:

### Aggressive (our primary submission)
```
AXTI (rank #1 in thesis sector): $755,000  (= $1M - 49 × $5,000)
Remaining 49 stocks:              $5,000 each
```
This is mathematically optimal when one stock scores far above the rest. Return: **+4,023%**

### Mild
```
Top 10 thesis stocks: $800,000 total, exponential decay
  amount_i = $800k × exp(-1.5 × i/10) / sum(weights)
  → #1 gets ~$143k, #2 gets ~$123k, ... #10 gets ~$37k
Remaining 40 stocks: $5,000 each
```
Spreads risk across 10 conviction picks. Return: **+479%**

### Safe
```
All 50 stocks: $20,000 each (equal weight)
Ranked by Quality × Size only (convexity ignored)
```
No concentration at all. Pure quality-value screen. Return: **+112%**

**The key insight:** All three beat the S&P 500 (+29%). The stock SELECTION is what generates alpha. Concentration is just the amplifier.

---

## Monte Carlo Robustness — "How do you know the ranking is stable?"

```
For trial = 1 to 300:
    weights = random_dirichlet([2, 2, 2, 1.5, 1, 1])  # 6 random weights
    scores  = compute_convexity(all_stocks, weights)
    top_50  = stocks with highest scores
    record which stocks appear in top_50
```

After 300 trials with different random weights, we count how many times each stock appeared in the top 50. Stocks appearing in >80% of trials are "robust" — their ranking doesn't depend on any specific weight choice.

AXTI appeared in 100% of trials (all 300). It's robust regardless of how you weight the convexity signals.

**Why Monte Carlo?"** → "To avoid overfitting. If a stock only ranks high with one specific set of weights, that's fragile. We test hundreds of weight combinations and only trust stocks that consistently rank well across all of them."

---

## Quick Reference

| Question | Answer |
|----------|--------|
| "Why percentile ranks?" | Standard quant factor construction. Makes different signals comparable. No hardcoded thresholds. |
| "Why multiply factors?" | A stock must be strong on ALL dimensions. Multiplication penalises weakness on any single factor. |
| "Why 1.3 exponent on quality?" | Amplifies quality differences. Based on Lakonishok et al. 1994 — in crash recovery, fundamentals drive which stocks rebound. |
| "Why not use Cala for everything?" | Cala is slow (30s+ per search query). We use it strategically: thesis discovery, top-candidate enrichment, rationale generation. Yahoo Finance handles the bulk price data. |
| "Could you have found AXTI without the thesis?" | Yes — it ranked #3 overall even without the thesis constraint. The thesis just ensures our biggest bet is in the sector we have highest conviction in. |
| "What if AXTI had crashed further?" | That's the risk. The safe mode (+112%) proves the stock selection works even without concentration. We accept single-stock risk in exchange for maximum upside in a competition setting. |
