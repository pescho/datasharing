#!/usr/bin/env python3
"""
Data fetcher for the S&P 400 MidCap Newest Additions Backtest.

Run this script ONCE before running the backtest to download and cache all
required price data. Requires internet access and yfinance.

Usage:
    python fetch_sp400_data.py
"""

import os
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "data_cache_sp400"
BACKTEST_START = "2015-01-02"
BACKTEST_END = "2025-12-31"
PORTFOLIO_SIZE = 50

# ---------------------------------------------------------------------------
# Embedded S&P 400 MidCap additions timeline
# Compiled from S&P Dow Jones Indices press releases (PR Newswire)
# and Wikipedia "List of S&P 400 companies" historical changes.
# ---------------------------------------------------------------------------
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


def load_additions():
    """Load the embedded S&P 400 additions timeline."""
    import csv
    from io import StringIO

    reader = csv.DictReader(SP400_ADDITIONS_CSV.strip().splitlines())
    additions = []
    for row in reader:
        additions.append((row["date"], row["ticker"]))
    additions.sort(key=lambda x: x[0])
    return additions


def get_required_tickers(additions):
    """Determine which tickers are needed for the backtest."""
    all_tickers = set()
    all_tickers.add("SPY")  # Benchmark

    start_year = int(BACKTEST_START[:4])
    end_year = int(BACKTEST_END[:4])
    for year in range(start_year, end_year + 1):
        as_of = f"{year}-01-15"
        eligible = [(d, t) for d, t in additions if d <= as_of]
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

    cache_file = CACHE_DIR / "sp400_price_data.parquet"
    prices.to_parquet(cache_file)
    print(f"\n  Saved {prices.shape[1]} tickers, {prices.shape[0]} days to {cache_file}")

    if failed:
        print(f"  Failed tickers ({len(failed)}): {', '.join(failed[:20])}")

    return prices


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("S&P 400 MidCap Additions Backtest - Data Fetcher")
    print("=" * 60)

    # Step 1: Load additions data
    print("\n[1/3] Loading S&P 400 MidCap additions timeline...")
    additions = load_additions()
    print(f"  {len(additions)} total additions loaded")
    print(f"  Date range: {additions[0][0]} to {additions[-1][0]}")

    # Save additions to cache
    cache_file = CACHE_DIR / "sp400_historical_additions.json"
    with open(cache_file, "w") as f:
        json.dump(additions, f)

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
    print(f"  python backtest_sp400_additions.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
