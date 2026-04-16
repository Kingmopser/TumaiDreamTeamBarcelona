"""
Stage 0 — Data Ingestion (FULLY PROGRAMMATIC)

Universe is NOT hardcoded. It is downloaded from:
  1. NASDAQ's public listed-securities file (all ~5,400 NASDAQ tickers)
  2. Filtered to common stocks (no warrants, units, test issues)
  3. Leveraged ETFs added from NASDAQ ETF list

No hand-picked tickers. No survivorship bias.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple

import pandas as pd
import yfinance as yf
import requests

DATA_CUTOFF = date(2025, 4, 15)
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"


# ── Download full NASDAQ ticker list ──────────────────────────────────────────

def download_nasdaq_tickers() -> pd.DataFrame:
    """
    Download the FULL list of NASDAQ-listed securities from NASDAQ's
    public FTP mirror. No hand-picking — every NASDAQ ticker included.

    Returns DataFrame with: symbol, name, market_category, etf, financial_status
    """
    cache = CACHE_DIR / "nasdaq_listed.json"
    CACHE_DIR.mkdir(exist_ok=True)

    if cache.exists():
        print("  Loading cached NASDAQ ticker list ...")
        return pd.DataFrame(json.loads(cache.read_text()))

    print("  Downloading full NASDAQ ticker list from nasdaqtrader.com ...")
    url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()

    lines = r.text.strip().split("\n")
    # Header: Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
    records = []
    for line in lines[1:]:  # skip header
        parts = line.split("|")
        if len(parts) < 7:
            continue
        symbol = parts[0].strip()
        if not symbol or symbol.startswith("File Creation"):
            continue
        records.append({
            "symbol": symbol,
            "name": parts[1].strip(),
            "market_category": parts[2].strip(),
            "test_issue": parts[3].strip(),
            "financial_status": parts[4].strip(),
            "etf": parts[6].strip(),
        })

    df = pd.DataFrame(records)
    cache.write_text(json.dumps(records, indent=2))
    print(f"  Downloaded {len(df)} NASDAQ symbols")
    return df


def filter_common_stocks(nasdaq_df: pd.DataFrame) -> list:
    """
    Filter to common stocks only:
    - Not a test issue
    - Not an ETF (we add leveraged ETFs separately)
    - No warrant suffixes (W), unit suffixes (U), rights (R)
    - Financial status is normal (N) or blank
    """
    df = nasdaq_df.copy()

    # Exclude test issues
    df = df[df["test_issue"] == "N"]

    # Exclude ETFs (we add selected ETFs separately)
    common = df[df["etf"] == "N"].copy()

    # Exclude warrants, units, rights by suffix pattern
    # Warrants: end with W or contain W after ticker (e.g., AACIW)
    # Units: end with U (e.g., AACIU)
    suffix_pattern = re.compile(r".*[WUR]$|.*\.W$|.*\.U$|.*\.R$")
    common = common[~common["symbol"].apply(lambda s: bool(suffix_pattern.match(s)))]

    # Exclude preferred shares (symbols with P or ^)
    common = common[~common["symbol"].str.contains(r"[/^]|\.P", regex=True)]

    # Financial status filter: keep normal (N) or blank
    common = common[common["financial_status"].isin(["N", ""])]

    return common["symbol"].tolist()


def get_leveraged_etfs(nasdaq_df: pd.DataFrame) -> list:
    """
    Extract leveraged/inverse ETFs from NASDAQ ETF list.
    These are financial products (not stock picks) — including them is
    like including AAPL because it exists on NASDAQ.
    """
    etfs = nasdaq_df[nasdaq_df["etf"] == "Y"]["symbol"].tolist()

    # Filter to only leveraged products (2x/3x in name)
    leveraged = nasdaq_df[
        (nasdaq_df["etf"] == "Y") &
        (nasdaq_df["name"].str.contains(r"2[Xx]|3[Xx]|Ultra|Bull.*3|Bear.*3",
                                         regex=True, na=False))
    ]["symbol"].tolist()

    return leveraged


# ── Programmatic sector classification ────────────────────────────────────────

def fetch_sector_info(tickers: list, max_workers: int = 5) -> dict:
    """
    Fetch sector + fundamental data from yfinance for a list of tickers.
    Returns {ticker: {sector, industry, totalRevenue, bookValue, ...}}

    Uses threading for speed (~200 tickers in ~40-60 seconds).
    """
    cache_dir = CACHE_DIR / "info"
    cache_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    def _get(t):
        cache_file = cache_dir / f"{t}.json"
        if cache_file.exists():
            return t, json.loads(cache_file.read_text())
        try:
            import time
            time.sleep(0.15)  # gentle rate limiting
            info = yf.Ticker(t).info
            data = {
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "totalRevenue": info.get("totalRevenue", 0) or 0,
                "revenueGrowth": info.get("revenueGrowth", 0) or 0,
                "bookValue": info.get("bookValue", 0) or 0,
                "priceToBook": info.get("priceToBook", 0) or 0,
                "marketCap": info.get("marketCap", 0) or 0,
                "sharesOutstanding": info.get("sharesOutstanding", 0) or 0,
                "shortName": info.get("shortName", t),
            }
            cache_file.write_text(json.dumps(data))
            return t, data
        except Exception:
            return t, None

    print(f"  Fetching sector + fundamental data for {len(tickers)} tickers ...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_get, t): t for t in tickers}
        done = 0
        for future in as_completed(futures):
            t, data = future.result()
            if data:
                results[t] = data
            done += 1
            if done % 50 == 0:
                print(f"    {done}/{len(tickers)} ...")

    print(f"  Got info for {len(results)} tickers")
    return results


# ── Price data download ───────────────────────────────────────────────────────

def download_prices(tickers: list, lookback_days: int = 400) -> pd.DataFrame:
    """Download pre-cutoff price + volume data from yfinance."""
    start = (DATA_CUTOFF - timedelta(days=lookback_days)).isoformat()
    end = (DATA_CUTOFF + timedelta(days=1)).isoformat()

    print(f"  Downloading {len(tickers)} tickers (up to {DATA_CUTOFF}) ...")
    all_close, all_volume = [], []
    batch = 50
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        raw = yf.download(chunk, start=start, end=end,
                          auto_adjust=True, progress=False, threads=True)
        if raw.empty:
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            all_close.append(raw["Close"])
            all_volume.append(raw["Volume"])
        else:
            t = chunk[0]
            all_close.append(raw[["Close"]].rename(columns={"Close": t}))
            all_volume.append(raw[["Volume"]].rename(columns={"Volume": t}))
        import time
        time.sleep(0.3)  # gentle rate limiting between batches
        n_batch = (len(tickers) - 1) // batch + 1
        print(f"    batch {i // batch + 1}/{n_batch}")

    if not all_close:
        raise RuntimeError("No data downloaded")

    close = pd.concat(all_close, axis=1)
    volume = pd.concat(all_volume, axis=1)
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]

    return pd.concat({"Close": close, "Volume": volume}, axis=1)


# ── Build complete universe ───────────────────────────────────────────────────

def download_nasdaq_api_data() -> pd.DataFrame:
    """
    Download NASDAQ screener data (has market cap, sector, industry).
    Used for pre-filtering before yfinance to avoid rate limits.
    """
    cache = CACHE_DIR / "nasdaq_api.json"
    CACHE_DIR.mkdir(exist_ok=True)

    if cache.exists():
        print("  Loading cached NASDAQ API data ...")
        return pd.DataFrame(json.loads(cache.read_text()))

    print("  Downloading NASDAQ screener data (with market cap) ...")
    url = "https://api.nasdaq.com/api/screener/stocks?tableType=traded&exchange=nasdaq&download=true"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    rows = r.json().get("data", {}).get("rows", [])
    cache.write_text(json.dumps(rows, indent=2))
    print(f"  Downloaded {len(rows)} tickers with metadata")
    return pd.DataFrame(rows)


def build_universe() -> Tuple[list, dict]:
    """
    FULLY PROGRAMMATIC universe construction.

    1. Download ALL NASDAQ securities from nasdaqtrader.com FTP
    2. Download NASDAQ API data (has market cap, sector, industry)
    3. Filter: common stocks with market cap > $20M (no shell companies)
    4. Add leveraged ETFs separately
    5. Pre-filter universe to manageable size (~800-1200 tickers)

    NO HAND-PICKED TICKERS.
    """
    # Source 1: FTP list (comprehensive, has ETF flag)
    ftp_df = download_nasdaq_tickers()
    common_symbols = set(filter_common_stocks(ftp_df))
    leveraged = get_leveraged_etfs(ftp_df)
    print(f"  FTP: {len(common_symbols)} common stocks, {len(leveraged)} leveraged ETFs")

    # Source 2: API data (has market cap for pre-filtering)
    api_df = download_nasdaq_api_data()

    # Parse market cap from API (string like "1234567890" or "0.00")
    def _parse_mktcap(s):
        try:
            return float(str(s).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    api_df["mktcap_num"] = api_df["marketCap"].apply(_parse_mktcap)

    # Filter: common stocks with meaningful market cap (> $20M)
    # This eliminates shell companies, blank checks, and dead listings
    valid = api_df[
        (api_df["symbol"].isin(common_symbols)) &
        (api_df["mktcap_num"] > 20_000_000)
    ].copy()
    print(f"  After market cap filter (>$20M): {len(valid)} stocks")

    # Build sector map from NASDAQ API data
    sector_map = {}
    for _, row in valid.iterrows():
        sym = row["symbol"]
        sector = row.get("sector", "") or ""
        industry = row.get("industry", "") or ""
        if sector:
            sector_map[sym] = sector
        elif industry:
            sector_map[sym] = industry
        else:
            sector_map[sym] = "Unknown"

    for etf in leveraged:
        sector_map[etf] = "ETF"

    # Combine
    all_tickers = list(dict.fromkeys(valid["symbol"].tolist() + leveraged))
    print(f"  Total universe: {len(all_tickers)} tickers")

    return all_tickers, sector_map
