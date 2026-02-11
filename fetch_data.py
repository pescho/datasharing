#!/usr/bin/env python3
"""
Data fetcher for the S&P 500 Newest Additions Backtest.

Run this script ONCE before running the backtest to download and cache all
required price data. Requires internet access and yfinance.

Usage:
    python fetch_data.py
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "data_cache"
BACKTEST_START = "2015-01-02"
BACKTEST_END = "2025-12-31"
PORTFOLIO_SIZE = 50


def download_historical_additions():
    """Download S&P 500 additions from historical components data on GitHub."""
    cache_file = CACHE_DIR / "sp500_historical_additions.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    print("Downloading S&P 500 historical components from GitHub...")
    url = "https://raw.githubusercontent.com/hanshof/sp500_constituents/main/sp_500_historical_components.csv"
    req = urllib.request.urlopen(url, timeout=120)
    data = req.read().decode("utf-8")

    lines = data.strip().split("\n")
    dates_list = []
    components_list = []
    for line in lines[1:]:
        parts = line.split('"')
        if len(parts) >= 2:
            date = parts[0].strip().rstrip(",")
            tickers = set(t.strip() for t in parts[1].split(",") if t.strip())
            dates_list.append(date)
            components_list.append(tickers)

    additions = []
    for i in range(1, len(dates_list)):
        added = components_list[i] - components_list[i - 1]
        if added:
            for ticker in sorted(added):
                additions.append((dates_list[i], ticker))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(additions, f)
    print(f"  Found {len(additions)} additions")
    return additions


def get_required_tickers(additions):
    """Determine which tickers are needed for the backtest."""
    # Renames to exclude
    rename_new = {
        "GL", "PEAK", "NLOK", "VIAC", "WRB", "TFC", "J", "LUMN", "VTRS",
        "BBWI", "TECH", "CTRA", "WTW", "PARA", "BALL", "META", "ELV",
        "GEN", "COR", "RVTY", "FI", "DAY", "DOC", "CPAY", "BKR", "DOW",
        "FISV", "PSKY",
    }

    filtered = [(d, t) for d, t in additions if t not in rename_new]
    filtered.sort(key=lambda x: x[0])

    all_tickers = set()
    all_tickers.add("SPY")  # Benchmark

    start_year = int(BACKTEST_START[:4])
    end_year = int(BACKTEST_END[:4])
    for year in range(start_year, end_year + 1):
        as_of = f"{year}-01-15"
        eligible = [(d, t) for d, t in filtered if d <= as_of]
        seen = set()
        result = []
        for d, t in reversed(eligible):
            if t not in seen:
                seen.add(t)
                result.append(t)
            if len(result) >= PORTFOLIO_SIZE:
                break
        all_tickers.update(result)
        print(f"  {year}: {len(result)} portfolio tickers")

    return sorted(all_tickers)


def download_prices(tickers):
    """Download daily adjusted close prices for all tickers using yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance is required. Install with: pip install yfinance")
        sys.exit(1)

    price_start = "2014-06-01"  # Start a bit earlier for buffer
    price_end = BACKTEST_END

    print(f"\nDownloading prices for {len(tickers)} tickers...")
    print(f"  Period: {price_start} to {price_end}")

    batch_size = 50
    all_data = []
    failed = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        batch_str = " ".join(batch)
        print(f"  Batch {i // batch_size + 1}/{(len(tickers) + batch_size - 1) // batch_size}: "
              f"{len(batch)} tickers...")
        try:
            data = yf.download(
                batch_str,
                start=price_start,
                end=price_end,
                auto_adjust=True,
                progress=False,
            )
            if isinstance(data.columns, pd.MultiIndex):
                close = data["Close"]
            else:
                close = data[["Close"]]
                close.columns = batch
            all_data.append(close)
        except Exception as e:
            print(f"    Failed: {e}")
            failed.extend(batch)

    if not all_data:
        print("ERROR: Could not download any price data.")
        sys.exit(1)

    prices = pd.concat(all_data, axis=1)
    prices = prices.loc[~prices.index.duplicated(keep="first")]
    prices.sort_index(inplace=True)

    # Drop tickers with too much missing data
    threshold = 0.5  # need at least 50% of dates
    valid_cols = prices.columns[prices.notna().mean() > threshold]
    prices = prices[valid_cols]

    cache_file = CACHE_DIR / "price_data.parquet"
    prices.to_parquet(cache_file)
    print(f"\n  Saved {prices.shape[1]} tickers, {prices.shape[0]} days to {cache_file}")

    if failed:
        print(f"  Failed tickers ({len(failed)}): {', '.join(failed[:20])}")

    return prices


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("S&P 500 Additions Backtest - Data Fetcher")
    print("=" * 60)

    # Step 1: Get additions data
    print("\n[1/3] Loading S&P 500 additions timeline...")
    additions = download_historical_additions()
    print(f"  {len(additions)} total additions loaded")

    # Step 2: Determine required tickers
    print("\n[2/3] Computing required tickers...")
    tickers = get_required_tickers(additions)
    print(f"  Total unique tickers needed: {len(tickers)}")

    # Step 3: Download price data
    print("\n[3/3] Downloading price data (this may take a few minutes)...")
    prices = download_prices(tickers)

    print("\n" + "=" * 60)
    print("Data download complete!")
    print(f"  Tickers: {prices.shape[1]}")
    print(f"  Trading days: {prices.shape[0]}")
    print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")
    print(f"\nYou can now run the backtest:")
    print(f"  python backtest_sp500_additions.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
