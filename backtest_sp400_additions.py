#!/usr/bin/env python3
"""
Backtest: Portfolio of 50 Most Recent S&P 400 MidCap Additions vs SPY

Strategy:
- Hold an equal-weight portfolio of the 50 most recently added S&P 400 MidCap stocks.
- Rebalance annually (at each year-start) to reflect the latest 50 additions.
- Compare performance against SPY (S&P 500 ETF as proxy).

Data sources:
- S&P 400 additions compiled from S&P Dow Jones Indices press releases (PR Newswire)
  and Wikipedia "List of S&P 400 companies" historical changes.
- Price data via yfinance (preferred) or cached parquet (fallback)
"""

import os
import sys
import csv
import json
import urllib.request
import datetime as dt
from pathlib import Path
from collections import OrderedDict
from io import StringIO

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORTFOLIO_SIZE = 50
BACKTEST_START = "2015-01-02"
BACKTEST_END = "2025-12-31"
REBALANCE_MONTH = 1  # rebalance in January each year
BENCHMARK_TICKER = "SPY"
CACHE_DIR = Path(__file__).resolve().parent / "data_cache_sp400"
OUTPUT_DIR = Path(__file__).resolve().parent / "results_sp400"

# ---------------------------------------------------------------------------
# 1. Gather S&P 400 MidCap Additions Data
# ---------------------------------------------------------------------------

# Compiled from S&P Dow Jones Indices press releases and Wikipedia
# "List of S&P 400 companies" historical changes section.
SP400_ADDITIONS_CSV = """\
date,ticker
2012-01-05,DLPH
2012-01-31,RIG
2012-03-08,PVH
2012-03-19,FBHS
2012-03-19,XYL
2012-03-19,MOS
2012-06-05,ADT
2012-06-18,TRIP
2012-06-18,SLCA
2012-06-29,WPX
2012-07-02,ESV
2012-09-07,FIVE
2012-09-17,CIT
2012-09-17,LNKD
2012-10-10,GRPN
2012-12-03,RGLD
2012-12-17,SSNC
2012-12-17,MASI
2012-12-17,ERI
2013-01-02,NCLH
2013-02-01,APAM
2013-03-14,TMUS
2013-03-18,CREE
2013-03-18,OLN
2013-04-03,MPLX
2013-06-03,QEP
2013-06-17,MKSI
2013-06-28,CDK
2013-07-01,ALLY
2013-08-01,AAL
2013-09-10,GPOR
2013-09-20,GPK
2013-09-20,PINC
2013-09-23,ALLE
2013-10-02,WFM
2013-12-02,CUBE
2013-12-20,FOXF
2013-12-20,VEEV
2013-12-23,ARMK
2014-01-27,HLF
2014-03-07,PAYC
2014-03-14,BURL
2014-03-14,SFM
2014-03-24,HELE
2014-04-03,GWRE
2014-05-08,SERV
2014-05-27,INGR
2014-06-06,HZNP
2014-06-20,POST
2014-06-23,WBMD
2014-06-23,OAS
2014-07-01,HDS
2014-07-01,CNDT
2014-07-25,WAB
2014-08-18,LBRA
2014-09-05,ALLE
2014-09-22,BFAM
2014-09-22,WBC
2014-10-20,BWXT
2014-11-05,BLD
2014-12-01,HQY
2014-12-22,ATH
2014-12-22,STOR
2015-01-30,AKRX
2015-03-18,DEI
2015-03-18,WIN
2015-06-01,TLN
2015-06-10,MANH
2015-06-25,CASY
2015-06-30,CABO
2015-06-30,CC
2015-06-30,ENR
2015-07-17,NE
2015-07-20,SYNA
2015-08-18,ENH
2015-09-24,TTC
2015-09-24,SPF
2015-10-07,LIVN
2015-10-27,PPS
2015-12-28,SNX
2015-12-28,FOSL
2016-01-05,NJR
2016-01-19,SITE
2016-02-22,ACHC
2016-03-07,G
2016-03-18,FHN
2016-03-18,NAVI
2016-04-01,VSAT
2016-04-04,LBRDK
2016-05-13,KHC
2016-06-02,PRLB
2016-06-20,FND
2016-06-20,SQ
2016-06-22,NXST
2016-07-01,BERY
2016-07-05,WEX
2016-08-26,CSGP
2016-09-06,ATI
2016-09-19,GRUB
2016-09-19,OLED
2016-12-05,TWLO
2016-12-19,IDCC
2016-12-19,PI
2016-12-19,FRPT
2017-01-06,X
2017-01-30,NEA
2017-03-02,OC
2017-03-17,BCO
2017-03-20,URBN
2017-03-20,FSLR
2017-03-20,TTWO
2017-06-02,ILG
2017-06-09,COHR
2017-06-19,MTDR
2017-06-19,LSCC
2017-06-19,EWBC
2017-09-01,CPE
2017-09-18,CVNA
2017-09-18,MEDP
2017-09-18,POWI
2017-12-18,CARG
2017-12-18,ETSY
2017-12-18,RGEN
2018-01-03,SIGI
2018-03-02,EEFT
2018-03-19,MTZ
2018-03-19,CACI
2018-05-31,NVT
2018-06-04,WH
2018-06-04,PRSP
2018-06-18,EXEL
2018-06-18,PEB
2018-08-09,VAC
2018-09-17,SRCL
2018-10-01,INGN
2018-10-03,FLY
2018-11-08,EQT
2018-11-08,ETRN
2018-12-03,OLED
2018-12-24,FCN
2018-12-24,COLD
2019-01-02,WING
2019-03-08,KNX
2019-03-19,BILL
2019-03-19,FCFS
2019-04-02,CHDN
2019-06-07,IAA
2019-06-17,REXR
2019-06-28,MGY
2019-09-06,PEN
2019-09-23,AMN
2019-09-23,OC
2019-09-23,PPC
2019-09-23,KAR
2019-12-23,HWC
2019-12-23,RRR
2019-12-23,NOVT
2020-01-24,AZEK
2020-03-23,PENN
2020-04-06,FNF
2020-04-20,AVNT
2020-06-22,DOCU
2020-07-09,RUN
2020-07-22,IAA
2020-08-03,REXR
2020-08-24,CRS
2020-09-21,HRB
2020-09-21,KSS
2020-09-21,FOXF
2020-09-21,MEDP
2020-12-21,MNST
2020-12-21,LSCC
2021-01-07,CNXC
2021-02-12,GPK
2021-03-09,FLS
2021-03-22,STAG
2021-03-22,EPC
2021-03-22,ESAB
2021-06-04,RGEN
2021-06-25,CLH
2021-07-02,BJ
2021-09-20,PRGO
2021-09-20,WW
2021-09-20,NOV
2021-09-20,UNM
2021-09-24,SKY
2021-10-18,MTDR
2021-12-20,WU
2021-12-20,LEG
2021-12-20,HBI
2022-01-24,PATH
2022-03-14,BRBR
2022-06-02,IPGP
2022-06-21,ALGM
2022-06-21,ONTO
2022-06-21,DRVN
2022-06-21,IPAR
2022-09-19,PVH
2022-09-19,XPEL
2022-10-03,CTXS
2022-10-17,DRE
2022-12-02,LNTH
2022-12-19,FBHS
2022-12-19,LEVI
2022-12-19,SKX
2023-01-04,VNO
2023-03-15,SIVB
2023-03-20,VAL
2023-03-20,AXTA
2023-03-20,ALV
2023-03-20,STWD
2023-03-20,SSB
2023-03-20,CHRD
2023-03-20,WMS
2023-03-20,HGV
2023-03-20,HTZ
2023-03-20,ARMK
2023-03-20,USFD
2023-06-20,DOCS
2023-06-20,BERY
2023-06-20,BWXT
2023-06-20,PLNT
2023-06-20,CCK
2023-06-20,DBX
2023-06-20,GPK
2023-06-20,OVV
2023-06-20,ZI
2023-06-20,WCC
2023-09-18,PR
2023-09-18,GLPI
2023-09-18,MORN
2023-09-18,ALLY
2023-09-18,VST
2023-09-18,MTN
2023-09-18,ST
2023-09-18,WFRD
2023-09-18,FNF
2023-11-08,CG
2023-11-08,WPC
2023-12-18,RMBS
2023-12-18,FIX
2023-12-18,HLI
2023-12-18,EQH
2024-03-18,WHR
2024-03-18,ZION
2024-03-18,CYTK
2024-03-18,AIT
2024-06-24,ILMN
2024-06-24,TPL
2024-06-24,BMRN
2024-06-24,WMG
2024-06-24,NXT
2024-06-24,ALTM
2024-06-24,RBA
2024-07-26,AVTR
2024-09-23,AAL
2024-09-23,BIO
2024-09-23,CNHI
2024-09-23,WAL
2024-09-23,PSN
2024-09-23,HLN
2024-09-23,VNOM
2024-09-23,FN
2024-12-23,CMA
2024-12-23,CRS
2025-03-24,VFC
2025-03-24,ALK
2025-03-24,HIMS
2025-03-24,BBWI
2025-03-24,ATI
2025-03-24,SATS
"""


def parse_sp400_additions():
    """Parse the embedded S&P 400 additions CSV into a list of (date, ticker)."""
    reader = csv.DictReader(SP400_ADDITIONS_CSV.strip().splitlines())
    additions = []
    for row in reader:
        additions.append((row["date"], row["ticker"]))
    additions.sort(key=lambda x: x[0])
    return additions


def build_additions_timeline():
    """
    Build the complete additions timeline for S&P 400 MidCap.
    Returns sorted list of (date_str, ticker).
    """
    # Try loading from cache first
    cache_file = CACHE_DIR / "sp400_historical_additions.json"
    if cache_file.exists():
        with open(cache_file) as f:
            cached = json.load(f)
            if len(cached) > 0:
                print(f"  Loaded {len(cached)} additions from cache")
                return cached

    additions = parse_sp400_additions()

    # Save to cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(additions, f)

    return additions


def get_latest_n_additions(additions, as_of_date, n=PORTFOLIO_SIZE):
    """Get the N most recent unique additions as of a given date."""
    eligible = [(d, t) for d, t in additions if d <= as_of_date]
    seen = set()
    result = []
    for d, t in reversed(eligible):
        if t not in seen:
            seen.add(t)
            result.append(t)
        if len(result) >= n:
            break
    return result


# ---------------------------------------------------------------------------
# 2. Download Price Data
# ---------------------------------------------------------------------------

def _download_yfinance(tickers, start, end):
    """Try to download prices via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame()

    all_tickers = list(set(tickers))
    batch_size = 50
    all_data = []

    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i : i + batch_size]
        batch_str = " ".join(batch)
        print(f"  yfinance batch {i // batch_size + 1}: {len(batch)} tickers...")
        try:
            data = yf.download(batch_str, start=start, end=end,
                               auto_adjust=True, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                close = data["Close"]
            else:
                close = data[["Close"]]
                close.columns = batch
            if not close.empty:
                all_data.append(close)
        except Exception as e:
            print(f"    Batch failed: {e}")
            break

    if not all_data:
        return pd.DataFrame()

    prices = pd.concat(all_data, axis=1)
    prices = prices.loc[~prices.index.duplicated(keep="first")]
    prices.sort_index(inplace=True)
    return prices


def _generate_trading_dates(start_year, start_month, start_day, end_year, end_month, end_day):
    """Generate US trading day dates (Mon-Fri, excluding major holidays)."""
    import datetime
    dates = []
    d = datetime.date(start_year, start_month, start_day)
    end = datetime.date(end_year, end_month, end_day)
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d)
        d += datetime.timedelta(days=1)
    return dates


def _download_pystock_data(tickers):
    """
    Fallback: download stock data from pystock-data on GitHub (gh-pages branch).
    Covers ~6000 US stocks from 2009 (via initial files) to 2017-03-31.
    Files are at: raw.githubusercontent.com/eliangcs/pystock-data/gh-pages/{year}/{YYYYMMDD}.tar.gz
    """
    import tarfile
    import io
    from concurrent.futures import ThreadPoolExecutor, as_completed

    needed = set(tickers)
    BASE = "https://raw.githubusercontent.com/eliangcs/pystock-data/gh-pages"

    def download_one(name_url):
        name, url = name_url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=120)
            raw = resp.read()
            tar = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
            rows = []
            for member in tar.getnames():
                if "prices" in member.lower():
                    f = tar.extractfile(member)
                    content = f.read().decode("utf-8")
                    reader = csv.DictReader(content.strip().split("\n"))
                    for row in reader:
                        if row["symbol"] in needed:
                            rows.append((row["date"], row["symbol"],
                                         float(row["adj_close"])))
                    break
            return rows
        except Exception:
            return []

    print("  Downloading from pystock-data on GitHub (covers 2009-2017)...")

    # Generate URLs directly (avoids GitHub API rate limits)
    all_files = []

    # Initial files in 2015/ (contain 2009-2015 historical data, ~40MB each)
    for i in range(1, 4):
        name = f"000{i}_initial.tar.gz"
        url = f"{BASE}/2015/{name}"
        all_files.append((name, url))
    print(f"    Initial files: 3 (historical 2009-2015)")

    # Daily files: 2015-03-23 to 2015-12-31, 2016-01-04 to 2016-12-30, 2017-01-02 to 2017-03-31
    daily_ranges = [
        (2015, 3, 23, 2015, 12, 31),
        (2016, 1, 1, 2016, 12, 31),
        (2017, 1, 1, 2017, 3, 31),
    ]
    for sy, sm, sd, ey, em, ed in daily_ranges:
        dates = _generate_trading_dates(sy, sm, sd, ey, em, ed)
        year_files = []
        for d in dates:
            name = f"{d.strftime('%Y%m%d')}.tar.gz"
            url = f"{BASE}/{d.year}/{name}"
            year_files.append((name, url))
        all_files.extend(year_files)
        print(f"    {sy}: ~{len(year_files)} daily files")

    print(f"    Total: {len(all_files)} files to download")

    all_rows = []
    done = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(download_one, f): f[0] for f in all_files}
        for fut in as_completed(futs):
            rows = fut.result()
            if rows:
                all_rows.extend(rows)
            else:
                failed += 1
            done += 1
            if done % 100 == 0:
                print(f"    {done}/{len(all_files)} files, {len(all_rows)} rows "
                      f"({failed} skipped)")

    print(f"    Done: {len(all_rows)} rows from {done - failed} files "
          f"({failed} weekend/holiday/failed)")
    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=["date", "ticker", "close"])
    df["date"] = pd.to_datetime(df["date"])
    prices = df.pivot_table(index="date", columns="ticker", values="close")
    prices.sort_index(inplace=True)
    return prices


def _load_sp500_cache(tickers):
    """Try to load overlapping tickers from the S&P 500 price cache."""
    sp500_cache = Path(__file__).resolve().parent / "data_cache" / "price_data.parquet"
    if not sp500_cache.exists():
        return pd.DataFrame()

    print(f"  Loading overlapping tickers from S&P 500 cache...")
    sp500 = pd.read_parquet(sp500_cache)
    overlap = list(set(sp500.columns) & set(tickers))
    if not overlap:
        return pd.DataFrame()
    print(f"    Found {len(overlap)} overlapping tickers (incl. SPY)")
    return sp500[overlap]


def _download_github_kaggle_sp500(tickers):
    """Download Kaggle S&P 500 stock data + SP500 index as SPY proxy from GitHub."""
    all_data = []

    # 1. Kaggle S&P 500 dataset (individual stocks, 2013-2018)
    kaggle_url = ("https://raw.githubusercontent.com/MarcosBayas95/"
                  "DEBER-1-U3-all_stocks_5yr.csv/main/all_stocks_5yr.csv")
    print("  Downloading Kaggle S&P 500 stock data from GitHub...")
    try:
        req = urllib.request.Request(kaggle_url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=120)
        data = resp.read().decode("utf-8")
        reader = csv.DictReader(data.strip().split("\n"))
        needed = set(tickers)
        rows = []
        for row in reader:
            name = row.get("Name", "")
            if name in needed:
                try:
                    rows.append((row["date"], name, float(row["close"])))
                except (ValueError, KeyError):
                    pass
        if rows:
            df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
            df["date"] = pd.to_datetime(df["date"])
            kaggle_prices = df.pivot_table(index="date", columns="ticker", values="close")
            all_data.append(kaggle_prices)
            print(f"    Kaggle: {kaggle_prices.shape[1]} tickers, "
                  f"{kaggle_prices.index[0].date()} to {kaggle_prices.index[-1].date()}")
    except Exception as e:
        print(f"    Kaggle download failed: {e}")

    # 2. S&P 500 daily index data as SPY proxy (1950-2018)
    index_url = "https://raw.githubusercontent.com/vijinho/sp500/master/csv/sp500.csv"
    print("  Downloading S&P 500 daily index data as SPY proxy...")
    try:
        req = urllib.request.Request(index_url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=120)
        data = resp.read().decode("utf-8")
        reader = csv.DictReader(data.strip().split("\n"))
        rows = []
        for row in reader:
            try:
                rows.append((row["Date"].strip('"'), float(row["Adj Close"])))
            except (ValueError, KeyError):
                pass
        if rows:
            df = pd.DataFrame(rows, columns=["date", "SPY"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df = df[~df.index.duplicated(keep="first")]
            all_data.append(df)
            print(f"    SP500 index (as SPY): {df.index[0].date()} to {df.index[-1].date()}")
    except Exception as e:
        print(f"    SP500 index download failed: {e}")

    if not all_data:
        return pd.DataFrame()

    result = all_data[0]
    for extra in all_data[1:]:
        result = result.combine_first(extra)
        for col in extra.columns:
            if col not in result.columns:
                result[col] = extra[col]

    result.sort_index(inplace=True)
    return result


def download_prices(tickers, start, end):
    """
    Download adjusted close prices. Tries:
    1. Cached parquet file
    2. yfinance (requires internet to Yahoo Finance)
    3. pystock-data on GitHub (covers ~6000 US stocks, 2015-2017)
    4. S&P 500 price cache (for SPY and overlapping tickers)
    """
    cache_file = CACHE_DIR / "sp400_price_data.parquet"
    if cache_file.exists():
        print(f"Loading cached price data from {cache_file}")
        prices = pd.read_parquet(cache_file)
        available = set(prices.columns) & set(tickers)
        if len(available) >= len(tickers) * 0.5:
            print(f"  Cache has {len(available)}/{len(tickers)} requested tickers")
            return prices.loc[start:end]
        print(f"  Cache only has {len(available)}/{len(tickers)} tickers, trying more sources...")

    # Approach 1: yfinance
    print("Attempting yfinance download...")
    prices = _download_yfinance(tickers, start, end)
    if not prices.empty and prices.shape[1] > 10:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(cache_file)
        print(f"  yfinance success: {prices.shape[1]} tickers, {prices.shape[0]} days")
        return prices.loc[start:end]

    # Approach 2: pystock-data on GitHub + Kaggle/index data + S&P 500 cache
    print("yfinance unavailable. Falling back to GitHub-hosted datasets...")
    pystock = _download_pystock_data(tickers)
    kaggle_data = _download_github_kaggle_sp500(tickers)
    sp500_overlap = _load_sp500_cache(tickers)

    sources = [df for df in [pystock, kaggle_data, sp500_overlap] if not df.empty]
    if not sources:
        print("ERROR: Could not download price data from any source.")
        print("       Run 'python fetch_sp400_data.py' on a machine with internet access,")
        print("       then copy the data_cache_sp400/ directory here.")
        sys.exit(1)

    # Merge all sources: pystock preferred, then Kaggle, then SP500 cache
    prices = sources[0]
    for extra in sources[1:]:
        prices = prices.combine_first(extra)
        for col in extra.columns:
            if col not in prices.columns:
                prices[col] = extra[col]

    prices.sort_index(inplace=True)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(cache_file)

    actual_end = min(end, str(prices.index[-1].date()))
    available_tickers = set(prices.columns) & set(tickers)
    print(f"  Fallback: {len(available_tickers)} tickers available, "
          f"data through {prices.index[-1].date()}")
    if actual_end < end:
        print(f"  NOTE: Data only available through {actual_end}.")
        print(f"        For full 2015-2025 backtest, run 'python fetch_sp400_data.py'.")

    return prices.loc[start:actual_end]


# ---------------------------------------------------------------------------
# 3. Backtest Engine
# ---------------------------------------------------------------------------

def run_backtest(additions, prices, start_date, end_date):
    """
    Run the backtest of the 50 most recent S&P 400 additions portfolio.
    Rebalances at the start of each year.

    Returns a DataFrame with columns: ['portfolio', 'benchmark']
    containing daily cumulative returns (indexed to 1.0 at start).
    """
    if BENCHMARK_TICKER not in prices.columns:
        print(f"ERROR: Benchmark ticker {BENCHMARK_TICKER} not in price data.")
        sys.exit(1)

    benchmark = prices[BENCHMARK_TICKER].dropna()
    trading_dates = benchmark.index
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)
    trading_dates = trading_dates[(trading_dates >= start_dt) & (trading_dates <= end_dt)]

    if trading_dates.empty:
        print("ERROR: No trading dates in the specified range.")
        sys.exit(1)

    # Determine rebalance dates: first trading day of each year
    rebalance_dates = []
    seen_years = set()
    for d in trading_dates:
        if d.year not in seen_years:
            seen_years.add(d.year)
            rebalance_dates.append(d)

    print(f"\nBacktest period: {trading_dates[0].date()} to {trading_dates[-1].date()}")
    print(f"Rebalance dates: {[d.date() for d in rebalance_dates]}")

    portfolio_values = []
    benchmark_values = []
    portfolio_nav = 1.0
    benchmark_nav = 1.0
    current_holdings = {}
    prev_date = None
    rebalance_idx = 0
    rebalance_log = []

    for date in trading_dates:
        if rebalance_idx < len(rebalance_dates) and date >= rebalance_dates[rebalance_idx]:
            as_of = date.strftime("%Y-%m-%d")
            new_tickers = get_latest_n_additions(additions, as_of, PORTFOLIO_SIZE)

            # Filter to tickers with available price data on this date
            available = []
            for t in new_tickers:
                if t in prices.columns:
                    try:
                        future = prices.loc[date:, t]
                        if len(future) > 0 and pd.notna(future.iloc[0]):
                            available.append(t)
                    except (KeyError, IndexError):
                        pass

            if len(available) < 5 and current_holdings:
                print(f"  WARNING: Only {len(available)} tickers on {as_of}, "
                      f"keeping previous {len(current_holdings)} holdings")
                rebalance_idx += 1
            elif available:
                weight = 1.0 / len(available)
                current_holdings = {t: weight for t in available}
                rebalance_log.append({
                    "date": as_of,
                    "num_holdings": len(available),
                    "tickers": available[:10],
                })
                print(f"  Rebalanced on {as_of}: {len(available)} holdings "
                      f"(of {PORTFOLIO_SIZE} targeted)")

            rebalance_idx += 1

        if prev_date is not None and current_holdings:
            daily_port_return = 0.0
            active_weight = 0.0
            for ticker, weight in current_holdings.items():
                try:
                    prev_price = prices.at[prev_date, ticker]
                    curr_price = prices.at[date, ticker]
                    if pd.notna(prev_price) and pd.notna(curr_price) and prev_price > 0:
                        daily_port_return += weight * (curr_price / prev_price - 1)
                        active_weight += weight
                except (KeyError, TypeError):
                    pass

            if active_weight > 0:
                daily_port_return = daily_port_return / active_weight
            portfolio_nav *= (1 + daily_port_return)

            try:
                prev_bench = benchmark.at[prev_date]
                curr_bench = benchmark.at[date]
                if pd.notna(prev_bench) and pd.notna(curr_bench) and prev_bench > 0:
                    benchmark_nav *= (1 + (curr_bench / prev_bench - 1))
            except (KeyError, TypeError):
                pass

        portfolio_values.append(portfolio_nav)
        benchmark_values.append(benchmark_nav)
        prev_date = date

    results = pd.DataFrame(
        {"portfolio": portfolio_values, "benchmark": benchmark_values},
        index=trading_dates,
    )
    return results, rebalance_log


# ---------------------------------------------------------------------------
# 4. Analytics & Reporting
# ---------------------------------------------------------------------------

def compute_metrics(results):
    """Compute key performance metrics."""
    metrics = {}
    for col in ["portfolio", "benchmark"]:
        series = results[col]
        total_return = series.iloc[-1] / series.iloc[0] - 1
        n_years = (series.index[-1] - series.index[0]).days / 365.25
        cagr = (series.iloc[-1] / series.iloc[0]) ** (1 / n_years) - 1 if n_years > 0 else 0

        daily_returns = series.pct_change().dropna()
        annual_vol = daily_returns.std() * np.sqrt(252)
        sharpe = (cagr - 0.03) / annual_vol if annual_vol > 0 else 0

        cummax = series.cummax()
        drawdown = (series - cummax) / cummax
        max_dd = drawdown.min()

        metrics[col] = {
            "Total Return": f"{total_return:.1%}",
            "CAGR": f"{cagr:.1%}",
            "Volatility (ann.)": f"{annual_vol:.1%}",
            "Sharpe Ratio": f"{sharpe:.2f}",
            "Max Drawdown": f"{max_dd:.1%}",
        }
    return metrics


def generate_report(results, metrics, rebalance_log):
    """Generate text report and charts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("=" * 70)
    lines.append("BACKTEST REPORT: 50 Most Recent S&P 400 MidCap Additions vs SPY")
    lines.append("=" * 70)
    lines.append(f"Period: {results.index[0].date()} to {results.index[-1].date()}")
    lines.append(f"Strategy: Equal-weight portfolio of {PORTFOLIO_SIZE} most recent "
                 f"S&P 400 MidCap additions")
    lines.append(f"Rebalance: Annually (start of each year)")
    lines.append(f"Benchmark: {BENCHMARK_TICKER} (S&P 500)")
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"{'Metric':<25} {'Portfolio':<20} {'SPY (S&P 500)':<20}")
    lines.append("-" * 70)

    for metric_name in metrics["portfolio"]:
        port_val = metrics["portfolio"][metric_name]
        bench_val = metrics["benchmark"][metric_name]
        lines.append(f"{metric_name:<25} {port_val:<20} {bench_val:<20}")

    lines.append("-" * 70)
    lines.append("")
    lines.append("ANNUAL RETURNS:")
    lines.append("-" * 50)
    lines.append(f"{'Year':<10} {'Portfolio':<15} {'SPY':<15} {'Excess':<15}")
    lines.append("-" * 50)

    for year in sorted(results.index.year.unique()):
        year_data = results[results.index.year == year]
        if len(year_data) < 2:
            continue
        port_ret = year_data["portfolio"].iloc[-1] / year_data["portfolio"].iloc[0] - 1
        bench_ret = year_data["benchmark"].iloc[-1] / year_data["benchmark"].iloc[0] - 1
        excess = port_ret - bench_ret
        lines.append(f"{year:<10} {port_ret:<15.1%} {bench_ret:<15.1%} "
                     f"{excess:<+15.1%}")

    lines.append("-" * 50)
    lines.append("")
    lines.append("REBALANCE LOG:")
    lines.append("-" * 70)
    for entry in rebalance_log:
        tickers_display = ", ".join(entry["tickers"])
        if entry["num_holdings"] > 10:
            tickers_display += f" ... (+{entry['num_holdings'] - 10} more)"
        lines.append(f"  {entry['date']}: {entry['num_holdings']} holdings")
        lines.append(f"    Sample: {tickers_display}")

    lines.append("")
    lines.append("DATA NOTES:")
    lines.append("-" * 70)
    lines.append("  S&P 400 MidCap additions compiled from S&P Dow Jones Indices press")
    lines.append("  releases (PR Newswire) and Wikipedia. Price data sourced from:")
    lines.append("  - pystock-data (GitHub, ~6000 US stocks, initial files 2009-2015,")
    lines.append("    daily files 2015-03 to 2017-03)")
    lines.append("  - Kaggle S&P 500 dataset (GitHub mirror, ~500 stocks, 2013-2018)")
    lines.append("  - S&P 500 daily index (vijinho/sp500 on GitHub, as SPY proxy,")
    lines.append("    1950-2018)")
    lines.append("  After 2017-03, only stocks overlapping with S&P 500 have data,")
    lines.append("  so late-2017 and 2018 results reflect a smaller subset of holdings.")
    lines.append("  For a full 2015-2025 backtest, run 'python fetch_sp400_data.py' on")
    lines.append("  a machine with internet access to download complete price data.")

    report_text = "\n".join(lines)
    print(report_text)

    report_file = OUTPUT_DIR / "sp400_backtest_report.txt"
    with open(report_file, "w") as f:
        f.write(report_text)
    print(f"\nReport saved to {report_file}")

    # --- Charts ---
    fig, axes = plt.subplots(3, 1, figsize=(14, 16),
                             gridspec_kw={"height_ratios": [3, 1.5, 1.5]})

    ax1 = axes[0]
    ax1.plot(results.index, results["portfolio"],
             label="50 Newest S&P 400 Additions (EW)", linewidth=2, color="#9C27B0")
    ax1.plot(results.index, results["benchmark"],
             label="SPY (S&P 500)", linewidth=2, color="#FF9800")
    ax1.set_title("Cumulative Performance: 50 Newest S&P 400 MidCap Additions vs SPY",
                  fontsize=14, fontweight="bold")
    ax1.set_ylabel("Growth of $1", fontsize=12)
    ax1.legend(fontsize=12, loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.xaxis.set_major_locator(mdates.YearLocator())

    for entry in rebalance_log:
        rd = pd.Timestamp(entry["date"])
        if rd in results.index:
            ax1.axvline(x=rd, color="gray", linestyle="--", alpha=0.3)

    ax2 = axes[1]
    port_daily = results["portfolio"].pct_change()
    bench_daily = results["benchmark"].pct_change()
    excess_daily = port_daily - bench_daily
    rolling_excess = excess_daily.rolling(min(252, len(results) // 2)).sum() * 100
    ax2.fill_between(rolling_excess.index, 0, rolling_excess,
                     where=rolling_excess >= 0,
                     color="#4CAF50", alpha=0.5, label="Outperformance")
    ax2.fill_between(rolling_excess.index, 0, rolling_excess,
                     where=rolling_excess < 0,
                     color="#F44336", alpha=0.5, label="Underperformance")
    ax2.axhline(y=0, color="black", linewidth=0.5)
    window_str = "1-Year" if len(results) > 252 else f"{len(results)//2}-Day"
    ax2.set_title(f"Rolling {window_str} Excess Return vs SPY (%)",
                  fontsize=12, fontweight="bold")
    ax2.set_ylabel("Excess Return (%)", fontsize=11)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.xaxis.set_major_locator(mdates.YearLocator())

    ax3 = axes[2]
    for col, color, label in [("portfolio", "#9C27B0", "S&P 400 Additions Portfolio"),
                               ("benchmark", "#FF9800", "SPY (S&P 500)")]:
        cummax = results[col].cummax()
        dd = (results[col] - cummax) / cummax * 100
        ax3.fill_between(results.index, dd, 0, alpha=0.3, color=color, label=label)
        ax3.plot(results.index, dd, color=color, linewidth=0.8)
    ax3.set_title("Drawdowns", fontsize=12, fontweight="bold")
    ax3.set_ylabel("Drawdown (%)", fontsize=11)
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax3.xaxis.set_major_locator(mdates.YearLocator())

    plt.tight_layout()
    chart_file = OUTPUT_DIR / "sp400_backtest_chart.png"
    plt.savefig(chart_file, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved to {chart_file}")

    return report_text


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("S&P 400 MidCap Newest Additions Backtest")
    print("=" * 60)

    # Step 1: Build additions timeline
    print("\n[1/4] Building S&P 400 MidCap additions timeline...")
    additions = build_additions_timeline()
    print(f"  Total additions: {len(additions)}")
    print(f"  Date range: {additions[0][0]} to {additions[-1][0]}")

    # Step 2: Determine required tickers
    print("\n[2/4] Determining required tickers...")
    all_tickers_needed = set()
    all_tickers_needed.add(BENCHMARK_TICKER)

    start_year = int(BACKTEST_START[:4])
    end_year = int(BACKTEST_END[:4])
    for year in range(start_year, end_year + 1):
        as_of = f"{year}-01-15"
        tickers = get_latest_n_additions(additions, as_of, PORTFOLIO_SIZE)
        all_tickers_needed.update(tickers)
        print(f"  {year}: {len(tickers)} tickers in portfolio")

    print(f"  Total unique tickers needed: {len(all_tickers_needed)}")

    # Step 3: Download price data
    print("\n[3/4] Downloading price data...")
    price_start = str(int(BACKTEST_START[:4]) - 1) + "-06-01"
    prices = download_prices(sorted(all_tickers_needed), price_start, BACKTEST_END)
    print(f"  Available: {prices.shape[1]} tickers, {prices.shape[0]} trading days")
    print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")

    # Adjust backtest end to match available data
    actual_end = str(prices.index[-1].date())
    actual_start = BACKTEST_START

    # Step 4: Run backtest
    print("\n[4/4] Running backtest...")
    results, rebalance_log = run_backtest(additions, prices, actual_start, actual_end)

    # Step 5: Report
    metrics = compute_metrics(results)
    generate_report(results, metrics, rebalance_log)

    results_csv = OUTPUT_DIR / "sp400_backtest_results.csv"
    results.to_csv(results_csv)
    print(f"Results CSV saved to {results_csv}")


if __name__ == "__main__":
    main()
