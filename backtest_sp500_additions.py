#!/usr/bin/env python3
"""
Backtest: Portfolio of 50 Most Recent S&P 500 Additions vs S&P 500 Index

Strategy:
- Hold an equal-weight portfolio of the 50 most recently added S&P 500 stocks.
- Rebalance annually (at each year-end) to reflect the latest 50 additions.
- Compare performance against the S&P 500 (SPY ETF as proxy).

Data sources:
- S&P 500 additions derived from historical components (GitHub: hanshof/sp500_constituents)
- Supplemental explicit changes (GitHub: fja05680/sp500)
- Price data via yfinance (preferred) or GitHub-hosted datasets (fallback)
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
CACHE_DIR = Path(__file__).resolve().parent / "data_cache"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"

# ---------------------------------------------------------------------------
# 1. Gather S&P 500 Additions Data
# ---------------------------------------------------------------------------

# Explicit changes from fja05680/sp500 (2019-01 through 2026-01)
EXPLICIT_CHANGES_CSV = """\
date,add,remove
2019-01-18,TFX,PCG
2019-02-15,ATO,NFX
2019-02-27,WAB,GT
2019-04-02,DOW,BHF
2019-06-01,LHX,HRS
2019-06-03,"CTVA,DD","FLR,DWDP"
2019-06-07,AMCR,MAT
2019-07-01,MKTX,LLL
2019-07-15,TMUS,RHT
2019-08-08,GL,TMK
2019-08-09,"IEX,LDOS","FL,APC"
2019-09-23,CDW,TSS
2019-09-26,NVR,JEF
2019-10-03,LVS,NKTR
2019-10-18,BKR,BHGE
2019-11-05,"PEAK,NLOK","HCP,SYMC"
2019-11-21,NOW,CELG
2019-12-05,"WRB,VIAC","VIAB,CBS"
2019-12-09,"ODFL,TFC","STI,BBT"
2019-12-10,J,JEC
2019-12-23,"STE,ZBRA,LYV","MAC,TRIP,AMG"
2020-01-28,PAYC,WCG
2020-03-03,TT,XEC
2020-04-03,"RTX,OTIS,CARR",UTX
2020-04-06,HWM,"ARNC,RTN,M"
2020-05-12,"DXCM,DPZ","AGN,CPRI"
2020-05-22,WST,HP
2020-06-22,"TYL,TDY,BIO","JWN,HOG,ADS"
2020-09-18,LUMN,CTL
2020-09-21,"CTLT,TER,ETSY","COTY,KSS,HRB"
2020-10-07,POOL,ETFC
2020-10-12,VNT,NBL
2020-11-17,VTRS,MYL
2020-12-21,TSLA,AIV
2021-01-07,ENPH,TIF
2021-01-21,TRMB,CXO
2021-02-12,MPWR,FTI
2021-03-22,"CZR,GNRC,PENN,NXPI","VNT,XRX,SLG,FLS"
2021-04-20,PTC,VAR
2021-05-14,CRL,FLIR
2021-06-04,OGN,HFC
2021-07-21,MRNA,ALXN
2021-08-03,BBWI,LB
2021-08-30,TECH,MXIM
2021-09-20,"BRO,CDAY,MTCH","NOV,UNM,PRGO"
2021-10-04,CTRA,COG
2021-12-14,EPAM,KSU
2021-12-20,"SBNY,SEDG,FDS","LEG,HBI,WU"
2022-01-10,WTW,WLTW
2022-02-02,CEG,GPS
2022-02-15,NDSN,XLNX
2022-02-17,PARA,VIAC
2022-03-02,MOH,INFO
2022-04-04,CPT,PBCT
2022-04-11,WBD,"DISCA,DISCK"
2022-05-10,BALL,BLL
2022-06-08,VICI,CERN
2022-06-09,META,FB
2022-06-21,"ON,KDP","IPGP,UA,UAA"
2022-06-28,ELV,ANTM
2022-09-19,"INVH,CSGP","PENN,PVH"
2022-10-03,"EQT,PCG","DRE,CTXS"
2022-10-12,TRGP,NLSN
2022-11-01,ACGL,TWTR
2022-11-08,GEN,NLOK
2022-12-19,FSLR,FBHS
2022-12-22,STLD,ABMD
2023-01-04,GEHC,VNO
2023-03-15,"PODD,BG","SIVB,SBNY"
2023-03-20,FICO,LUMN
2023-05-04,AXON,FRC
2023-05-16,RVTY,PKI
2023-06-07,FI,FISV
2023-06-20,PANW,DISH
2023-07-10,EG,RE
2023-08-25,KVUE,AAP
2023-08-30,COR,ABC
2023-09-18,"ABNB,BX","NWL,LNC"
2023-10-02,VLTO,DXC
2023-10-18,"LULU,HUBB,BLDR,JBL,UBER","ATVI,OGN,SEDG,ALK,SEE"
2024-02-01,DAY,CDAY
2024-03-04,DOC,PEAK
2024-03-18,"DECK,SMCI","ZION,WHR"
2024-03-25,CPAY,FLT
2024-04-03,"SOLV,GEV","VFC,XRAY"
2024-05-08,VST,PXD
2024-06-24,"GDDY,CRWD,KKR","ILMN,CMA,RHI"
2024-07-08,SW,WRK
2024-09-23,"ERIE,DELL,PLTR","BIO,ETSY,AAL"
2024-09-30,AMTM,
2024-10-01,,BBWI
2024-11-26,TPL,MRO
2024-12-23,"APO,WDAY,LII","QRVO,AMTM,CTLT"
2025-03-24,"EXE,WSM,TKO,DASH","FMC,CE,TFX,BWA"
2025-05-19,COIN,DFS
2025-07-09,DDOG,JNPR
2025-07-18,TTD,ANSS
2025-07-23,XYZ,HES
2025-08-08,PSKY,PARA
2025-08-28,IBKR,WBA
2025-09-22,"APP,HOOD,EME","MKTX,CZR,ENPH"
2025-10-30,SOLS,
2025-10-31,,KMX
2025-11-03,Q,
2025-11-04,,EMN
2025-11-11,FISV,FI
2025-11-28,SNDK,IPG
2025-12-11,ARES,K
2025-12-22,"FIX,CVNA,CRH","MHK,SOLS,LKQ"
2026-01-14,MRSH,MMC
"""

# Ticker renames to exclude from "new additions" counting
TICKER_RENAMES_NEW = {
    "GL", "PEAK", "NLOK", "VIAC", "WRB", "TFC", "J", "LUMN", "VTRS",
    "BBWI", "TECH", "CTRA", "WTW", "PARA", "BALL", "META", "ELV",
    "GEN", "COR", "RVTY", "FI", "DAY", "DOC", "CPAY", "BKR", "DOW",
    "FISV", "PSKY",
}


def parse_explicit_changes():
    """Parse the embedded explicit changes CSV into a list of (date, added_tickers)."""
    reader = csv.DictReader(EXPLICIT_CHANGES_CSV.strip().splitlines())
    additions = []
    for row in reader:
        date_str = row["date"]
        added_raw = row["add"].strip().strip('"')
        if not added_raw:
            continue
        tickers = [t.strip() for t in added_raw.split(",") if t.strip()]
        for ticker in tickers:
            additions.append((date_str, ticker))
    return additions


def download_historical_components():
    """Download S&P 500 historical components from GitHub and derive additions."""
    cache_file = CACHE_DIR / "sp500_historical_additions.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    print("Downloading S&P 500 historical components from GitHub...")
    url = "https://raw.githubusercontent.com/hanshof/sp500_constituents/main/sp_500_historical_components.csv"
    try:
        req = urllib.request.urlopen(url, timeout=120)
        data = req.read().decode("utf-8")
    except Exception as e:
        print(f"Warning: Could not download historical components: {e}")
        return []

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
    print(f"  Found {len(additions)} additions from {dates_list[0]} to {dates_list[-1]}")
    return additions


def build_additions_timeline():
    """
    Build a complete, de-duplicated timeline of S&P 500 additions.
    Returns sorted list of (date_str, ticker).
    """
    derived = download_historical_components()
    explicit = parse_explicit_changes()

    cutoff = "2019-01-01"
    combined = [(d, t) for d, t in derived if d < cutoff]
    combined.extend(explicit)

    # Filter out pure renames
    filtered = []
    for date_str, ticker in combined:
        if ticker not in TICKER_RENAMES_NEW:
            filtered.append((date_str, ticker))

    filtered.sort(key=lambda x: x[0])
    return filtered


def get_latest_n_additions(additions, as_of_date, n=PORTFOLIO_SIZE):
    """Get the N most recent additions as of a given date."""
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
# 2. Download Price Data (with GitHub fallback)
# ---------------------------------------------------------------------------

def _download_github_stock_data():
    """
    Fallback: download individual stock data from the Kaggle S&P 500 dataset
    hosted on GitHub (2013-02 to 2018-02).
    """
    url = "https://raw.githubusercontent.com/MarcosBayas95/DEBER-1-U3-all_stocks_5yr.csv/main/all_stocks_5yr.csv"
    print("  Downloading Kaggle S&P 500 stock data from GitHub...")
    try:
        req = urllib.request.urlopen(url, timeout=120)
        raw = req.read().decode("utf-8")
        df = pd.read_csv(StringIO(raw))
        # Pivot to have tickers as columns, dates as rows
        df["date"] = pd.to_datetime(df["date"])
        prices = df.pivot_table(index="date", columns="Name", values="close")
        prices.index.name = None
        return prices
    except Exception as e:
        print(f"    Failed: {e}")
        return pd.DataFrame()


def _download_github_sp500_index():
    """
    Fallback: download S&P 500 daily index data from GitHub (1950-2018).
    Returns as a series named 'SPY' (scaled to approximate SPY ETF prices).
    """
    url = "https://raw.githubusercontent.com/vijinho/sp500/master/csv/sp500.csv"
    print("  Downloading S&P 500 index data from GitHub...")
    try:
        req = urllib.request.urlopen(url, timeout=60)
        raw = req.read().decode("utf-8")
        df = pd.read_csv(StringIO(raw))
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        # Convert S&P 500 index to approximate SPY prices
        # SPY launched 1993-01-29 at ~43.94 when S&P 500 was ~438.78
        # So SPY ~= S&P500 / 10 (approximately)
        spy_approx = df["Close"] / 10.0
        spy_approx.name = "SPY"
        return spy_approx
    except Exception as e:
        print(f"    Failed: {e}")
        return pd.Series(dtype=float)


def _download_yfinance(tickers, start, end):
    """Try to download prices via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame()

    all_tickers = list(set(tickers))
    batch_size = 50
    all_data = []
    any_success = False

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
                any_success = True
        except Exception as e:
            print(f"    Batch failed: {e}")
            break  # If one batch fails, likely all will

    if not all_data:
        return pd.DataFrame()

    prices = pd.concat(all_data, axis=1)
    prices = prices.loc[~prices.index.duplicated(keep="first")]
    prices.sort_index(inplace=True)
    return prices


def download_prices(tickers, start, end):
    """
    Download adjusted close prices. Tries:
    1. Cached parquet file
    2. yfinance (requires internet to Yahoo Finance)
    3. GitHub-hosted datasets (Kaggle + vijinho, covers 2013-2018)
    """
    cache_file = CACHE_DIR / "price_data.parquet"
    if cache_file.exists():
        print(f"Loading cached price data from {cache_file}")
        prices = pd.read_parquet(cache_file)
        available = set(prices.columns) & set(tickers)
        if len(available) >= len(tickers) * 0.5:
            print(f"  Cache has {len(available)}/{len(tickers)} requested tickers")
            return prices.loc[start:end]
        print(f"  Cache only has {len(available)}/{len(tickers)} tickers, trying to get more...")

    # Approach 1: yfinance
    print("Attempting yfinance download...")
    prices = _download_yfinance(tickers, start, end)
    if not prices.empty and prices.shape[1] > 10:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(cache_file)
        print(f"  yfinance success: {prices.shape[1]} tickers, {prices.shape[0]} days")
        return prices.loc[start:end]

    # Approach 2: GitHub fallback
    print("yfinance unavailable. Falling back to GitHub-hosted datasets...")
    stock_prices = _download_github_stock_data()
    sp500_index = _download_github_sp500_index()

    if stock_prices.empty and sp500_index.empty:
        print("ERROR: Could not download price data from any source.")
        print("       Run 'python fetch_data.py' on a machine with internet access,")
        print("       then copy the data_cache/ directory here.")
        sys.exit(1)

    # Merge stock data with SPY proxy from index data
    if not sp500_index.empty:
        spy_df = sp500_index.to_frame(name="SPY")
        spy_df.index = pd.to_datetime(spy_df.index)
        if not stock_prices.empty:
            stock_prices.index = pd.to_datetime(stock_prices.index)
            prices = stock_prices.join(spy_df, how="outer")
        else:
            prices = spy_df
    else:
        prices = stock_prices

    prices.sort_index(inplace=True)

    # Cache the result
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(cache_file)

    actual_end = min(end, str(prices.index[-1].date()))
    available_tickers = set(prices.columns) & set(tickers)
    print(f"  GitHub fallback: {len(available_tickers)} tickers available, "
          f"data through {prices.index[-1].date()}")
    if actual_end < end:
        print(f"  NOTE: Data only available through {actual_end}.")
        print(f"        For full 2015-2025 backtest, run 'python fetch_data.py' locally.")

    return prices.loc[start:actual_end]


# ---------------------------------------------------------------------------
# 3. Backtest Engine
# ---------------------------------------------------------------------------

def run_backtest(additions, prices, start_date, end_date):
    """
    Run the backtest of the 50 most recent additions portfolio.
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

            if len(available) < 5:
                if current_holdings:
                    print(f"  WARNING: Only {len(available)} tickers on {as_of}, "
                          f"keeping previous holdings")
                    rebalance_idx += 1
                    # keep existing holdings, fall through
                else:
                    # First rebalance with very few stocks
                    pass

            if available:
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
    lines.append("BACKTEST REPORT: 50 Most Recent S&P 500 Additions vs S&P 500")
    lines.append("=" * 70)
    lines.append(f"Period: {results.index[0].date()} to {results.index[-1].date()}")
    lines.append(f"Strategy: Equal-weight portfolio of {PORTFOLIO_SIZE} most recent "
                 f"S&P 500 additions")
    lines.append(f"Rebalance: Annually (start of each year)")
    lines.append(f"Benchmark: {BENCHMARK_TICKER} (S&P 500)")
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"{'Metric':<25} {'Portfolio':<20} {'S&P 500':<20}")
    lines.append("-" * 70)

    for metric_name in metrics["portfolio"]:
        port_val = metrics["portfolio"][metric_name]
        bench_val = metrics["benchmark"][metric_name]
        lines.append(f"{metric_name:<25} {port_val:<20} {bench_val:<20}")

    lines.append("-" * 70)
    lines.append("")
    lines.append("ANNUAL RETURNS:")
    lines.append("-" * 50)
    lines.append(f"{'Year':<10} {'Portfolio':<15} {'S&P 500':<15} {'Excess':<15}")
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

    report_text = "\n".join(lines)
    print(report_text)

    report_file = OUTPUT_DIR / "backtest_report.txt"
    with open(report_file, "w") as f:
        f.write(report_text)
    print(f"\nReport saved to {report_file}")

    # --- Charts ---
    fig, axes = plt.subplots(3, 1, figsize=(14, 16),
                             gridspec_kw={"height_ratios": [3, 1.5, 1.5]})

    ax1 = axes[0]
    ax1.plot(results.index, results["portfolio"],
             label="50 Newest Additions (EW)", linewidth=2, color="#2196F3")
    ax1.plot(results.index, results["benchmark"],
             label="S&P 500", linewidth=2, color="#FF9800")
    ax1.set_title("Cumulative Performance: 50 Newest S&P 500 Additions vs S&P 500",
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
    ax2.set_title(f"Rolling {window_str} Excess Return vs S&P 500 (%)",
                  fontsize=12, fontweight="bold")
    ax2.set_ylabel("Excess Return (%)", fontsize=11)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.xaxis.set_major_locator(mdates.YearLocator())

    ax3 = axes[2]
    for col, color, label in [("portfolio", "#2196F3", "Additions Portfolio"),
                               ("benchmark", "#FF9800", "S&P 500")]:
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
    chart_file = OUTPUT_DIR / "backtest_chart.png"
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
    print("S&P 500 Newest Additions Backtest")
    print("=" * 60)

    # Step 1: Build additions timeline
    print("\n[1/4] Building S&P 500 additions timeline...")
    additions = build_additions_timeline()
    print(f"  Total genuine additions: {len(additions)}")
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

    results_csv = OUTPUT_DIR / "backtest_results.csv"
    results.to_csv(results_csv)
    print(f"Results CSV saved to {results_csv}")


if __name__ == "__main__":
    main()
