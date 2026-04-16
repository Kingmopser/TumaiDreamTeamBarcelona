"""
Explainability Layer — Generates data-driven rationale for each stock.
References pre-April 2025 data, Cala insights, and quantitative signals.
"""


# ── Specific deep-dive rationales for top picks ──────────────────────────────
DEEP_RATIONALES = {
    "AXTI": (
        "AXT Inc — sole-source indium phosphide (InP) substrate manufacturer, "
        "the critical first component in AI data center optical interconnects. "
        "Every high-speed transceiver in hyperscaler AI clusters requires InP-based "
        "lasers and detectors. FY2024 revenue $99.4M (+31% YoY, reported Feb 2025). "
        "Trading at 0.3x book value after 70% tariff crash — extreme overreaction "
        "given 98% of revenue comes from Asian customers (not US tariff-exposed). "
        "Institutional accumulation by Davidson Kempner and Point72 in Q4 2024. "
        "Compound semiconductor substrate market growing at 14% CAGR, InP segment "
        "at 18%+ driven by AI co-packaged optics revolution."
    ),
    "AAOI": (
        "Applied Optoelectronics — fiber-optic transceiver manufacturer for "
        "hyperscale data centers, with 400G/800G products positioning it at the "
        "heart of the AI infrastructure buildout. Revenue accelerating on "
        "hyperscaler orders. 74% drawdown creates asymmetric entry into a direct "
        "AI optical networking play."
    ),
    "SNDK": (
        "SanDisk — newly independent NAND flash company after Western Digital "
        "spin-off (Feb 2025). Trading at post-spin discount despite surging "
        "AI-driven data storage demand. Classic 'baby with the bathwater' "
        "opportunity amplified by tariff panic."
    ),
    "SOXL": (
        "Direxion 3x Semiconductor ETF — daily-rebalanced 3x leverage compounds "
        "supra-linearly in sustained sector uptrends. Semiconductor sector had "
        "the strongest pre-crash momentum driven by AI chip capex. "
        "84% drawdown from high creates optimal entry for leveraged recovery."
    ),
    "IREN": (
        "Iris Energy — dual-revenue Bitcoin miner + AI/HPC cloud provider. "
        "Post-halving BTC cycle thesis plus AI compute optionality from "
        "owned GPU data centers at below-market power rates. "
        "65% drawdown prices in neither revenue stream."
    ),
    "WULF": (
        "TeraWulf — zero-carbon Bitcoin miner (nuclear/hydro) with the cheapest "
        "power in North America (~$0.02/kWh). Post-halving cycle historically "
        "drives BTC 12-18 month rally. Stock trading below replacement cost "
        "of power infrastructure."
    ),
    "CIFR": (
        "Cipher Mining — expanding BTC mining capacity with low-cost power. "
        "Post-halving supply reduction historically precedes major price "
        "appreciation. 69% drawdown creates asymmetric crypto recovery entry."
    ),
    "MU": (
        "Micron Technology — global HBM (High Bandwidth Memory) leader, "
        "essential for every AI training GPU (NVIDIA H100/B200). Revenue "
        "recovering from cyclical trough with 62% YoY growth. 54% drawdown "
        "from high despite being critical AI infrastructure."
    ),
    "ABVX": (
        "Abivax — obefazimod Phase 2b/3 data showed durable UC remission "
        "in $10B+ IBD market. NDA filing timeline in sight. European biotech "
        "with zero tariff exposure hit indiscriminately by risk-off selloff."
    ),
    "APLD": (
        "Applied Digital — AI/HPC + crypto infrastructure operator with "
        "next-gen GPU data centers. Revenue growing 120% YoY. Dual exposure "
        "to AI compute demand and Bitcoin mining economics."
    ),
}


def generate_rationale(row: dict, cala_data: dict = None) -> str:
    """Generate data-driven explanation for a stock selection."""
    ticker = row["ticker"]
    sector = row["sector"]
    dd = abs(row.get("drawdown_pct", 0))
    vol = row.get("vol_60d_pct", 0)
    score = row.get("score", 0)
    amount = row["amount"]
    layer = row.get("layer", "constraint")

    # Use deep rationale if available
    deep = DEEP_RATIONALES.get(ticker, "")

    # Cala enrichment
    cala_note = ""
    if cala_data and ticker in cala_data:
        cd = cala_data[ticker]
        company = cd.get("company", ticker)
        rev_growth = cd.get("revenue_growth", "")
        category = cd.get("category", "")
        if rev_growth:
            cala_note = f" Cala AI confirms revenue growth of {rev_growth}%."
        if category:
            cala_note += f" Category: {category}."

    if deep:
        thesis = deep + cala_note
    elif "Semiconductor" in sector or "Photonics" in sector:
        thesis = (
            f"Selected via convexity screening: {ticker} ({sector}) positioned "
            f"in AI semiconductor supply chain. {dd:.0f}% drawdown from 52-week "
            f"high indicates severe tariff-driven overreaction on a company with "
            f"secular AI demand tailwinds. Volatility {vol:.0f}% signals maximum "
            f"rebound potential.{cala_note}"
        )
    elif "3x" in sector or "2x" in sector:
        thesis = (
            f"Leveraged ETF ({sector}): daily-rebalanced leverage produces "
            f"supra-linear compounding in sustained uptrends. {dd:.0f}% drawdown "
            f"creates optimal entry for leveraged recovery.{cala_note}"
        )
    elif "Bitcoin" in sector or "Crypto" in sector:
        thesis = (
            f"{ticker} ({sector}): post-halving BTC cycle with 12-18 month "
            f"historical rally pattern. {dd:.0f}% drawdown from 52-week high "
            f"provides asymmetric crypto recovery entry. "
            f"Volatility {vol:.0f}%.{cala_note}"
        )
    elif "Biotech" in sector:
        thesis = (
            f"{ticker} ({sector}): pipeline catalyst-driven upside with "
            f"asymmetric risk/reward. {dd:.0f}% drawdown after tariff crash "
            f"hit risk assets indiscriminately, including zero-tariff-exposure "
            f"biotech companies.{cala_note}"
        )
    else:
        thesis = (
            f"{ticker} ({sector}): high Convexity Score ({score:.3f}) driven "
            f"by {dd:.0f}% drawdown, {vol:.0f}% volatility, and elevated gap "
            f"frequency. Identified as outlier-prone via Monte Carlo weight "
            f"search across 500 scoring trials.{cala_note}"
        )

    # Allocation context
    if layer == "conviction":
        alloc = (f" CONVICTION LAYER: ${amount:,} allocated "
                 f"({amount/1_000_000*100:.1f}% of portfolio).")
    else:
        alloc = f" Constraint layer: ${amount:,} minimum allocation."

    return thesis + alloc
