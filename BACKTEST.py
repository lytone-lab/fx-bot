#!/usr/bin/env python3
"""
STEP 1 - Backtest engine for crypto strategies, using ccxt for data.

Usage:
  pip install ccxt pandas numpy

  # 1) download and cache history (public data, no API keys needed)
  python backtest.py fetch BTC/USDT 1h 2022-01-01T00:00:00Z

  # 2) test a strategy on the saved file
  python backtest.py run data/BTC_USDT_1h.csv --tf 1h --strategy sma
  python backtest.py run data/BTC_USDT_1h.csv --tf 1h --strategy rsi

  # sanity check of the engine with fake data (no internet needed)
  python backtest.py run --synthetic --tf 1h --strategy sma
"""
import argparse
import itertools
import math
import os

import numpy as np
import pandas as pd

TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
         "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def periods_per_year(tf):
    return 365 * 24 * 3600 * 1000 / TF_MS[tf]


# --------------------------------------------------------------- DATA
def fetch_all(symbol, tf, since_iso, exchange_id="binance"):
    """Download full candle history in pages of 1000 and cache it as CSV."""
    import ccxt  # imported here so the rest works without ccxt installed

    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    since = ex.parse8601(since_iso)
    rows = []
    while True:
        batch = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
        if not batch:
            break
        rows += batch
        last = batch[-1][0]
        if last >= ex.milliseconds() - TF_MS[tf]:
            break  # reached the present
        if last + TF_MS[tf] <= since:
            break  # no progress, avoid infinite loop
        since = last + TF_MS[tf]
        print(f"  fetched {len(rows)} candles, up to {ex.iso8601(last)}")

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates("ts").sort_values("ts")
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    os.makedirs("data", exist_ok=True)
    path = f"data/{symbol.replace('/', '_')}_{tf}.csv"
    df.to_csv(path, index=False)
    print(f"saved {len(df)} candles -> {path}")
    return path


def load(path):
    df = pd.read_csv(path, parse_dates=["dt"]).set_index("dt").sort_index()
    return df


def check_data(df, tf):
    """Find missing candles, which silently corrupt backtests."""
    expected = TF_MS[tf]
    gaps = df["ts"].diff().dropna() if "ts" in df else None
    if gaps is not None:
        bad = (gaps > expected * 1.5).sum()
        print(f"data check: {len(df)} candles, {bad} gaps larger than 1.5 candles")


def synthetic(n=8000, seed=1):
    """Fake random-walk prices, used only to test that the engine works."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.00002, 0.008, n)
    close = 20000 * np.exp(np.cumsum(r))
    idx = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"close": close}, index=idx)


# --------------------------------------------------------- STRATEGIES
# A strategy returns a Series: 1.0 = hold the coin, 0.0 = stay in cash.
def sig_sma(df, fast, slow):
    """Trend following: hold when the fast average is above the slow one."""
    f = df["close"].rolling(fast).mean()
    s = df["close"].rolling(slow).mean()
    return (f > s).astype(float)


def sig_rsi(df, n, low, high):
    """Mean reversion: buy when RSI is low (oversold), sell when high."""
    d = df["close"].diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    pos = pd.Series(np.nan, index=df.index)
    pos[rsi < low] = 1.0
    pos[rsi > high] = 0.0
    return pos.ffill().fillna(0.0)


STRATEGIES = {
    "sma": (sig_sma, [dict(fast=f, slow=s) for f, s in
                      itertools.product([5, 10, 20, 30], [40, 50, 100, 200]) if f < s]),
    "rsi": (sig_rsi, [dict(n=n, low=lo, high=hi) for n, lo, hi in
                      itertools.product([7, 14], [20, 30], [60, 70, 80])]),
}


# ------------------------------------------------------------ ENGINE
def backtest(df, signal, fee=0.001, slip=0.0005):
    """
    Long-only spot backtest.
    - The signal is shifted by one candle: a decision made on a candle's close
      can only be traded on the NEXT candle. This avoids look-ahead cheating.
    - Every change of position pays fee + slippage on the amount traded.
    """
    pos = signal.shift(1).fillna(0.0)
    ret = df["close"].pct_change().fillna(0.0)
    turnover = pos.diff().abs()
    turnover.iloc[0] = abs(pos.iloc[0])
    strat = pos * ret - turnover * (fee + slip)
    equity = (1 + strat).cumprod()
    return pd.DataFrame({"pos": pos, "ret": strat, "equity": equity, "turnover": turnover})


def max_drawdown(equity):
    return float((equity / equity.cummax() - 1).min())


def metrics(bt, df, tf):
    ppy = periods_per_year(tf)
    end = float(bt["equity"].iloc[-1])
    years = len(bt) / ppy
    sd = bt["ret"].std()
    bh = float(df["close"].iloc[-1] / df["close"].iloc[0] - 1)
    return {
        "return_%": round((end - 1) * 100, 1),
        "buy_hold_%": round(bh * 100, 1),
        "max_dd_%": round(max_drawdown(bt["equity"]) * 100, 1),
        "sharpe": round(float(bt["ret"].mean() / sd * math.sqrt(ppy)), 2) if sd > 0 else 0.0,
        "trades": int((bt["turnover"] > 0).sum() / 2),
        "time_in_market_%": round(float((bt["pos"] > 0).mean()) * 100, 0),
        "years": round(years, 2),
    }


def run(df, tf, strategy, split, fee, slip):
    fn, grid = STRATEGIES[strategy]
    cut = int(len(df) * split)
    train, test = df.iloc[:cut], df.iloc[cut:]
    print(f"\ntrain: {train.index[0].date()} -> {train.index[-1].date()} ({len(train)} candles)")
    print(f"test : {test.index[0].date()} -> {test.index[-1].date()} ({len(test)} candles)")
    print(f"costs: fee {fee*100:.2f}% + slippage {slip*100:.3f}% per trade\n")

    results = []
    for params in grid:
        m_train = metrics(backtest(train, fn(train, **params), fee, slip), train, tf)
        results.append((m_train["sharpe"], params, m_train))
    results.sort(key=lambda x: x[0], reverse=True)

    print("TOP 5 settings on TRAIN data, then the same settings on unseen TEST data:")
    print(f"{'settings':<34}{'train ret%':>11}{'train shp':>10}{'test ret%':>11}{'test shp':>9}"
          f"{'test dd%':>9}{'trades':>7}{'test@2x cost%':>14}")
    for _, params, mt in results[:5]:
        sig_full = fn(df, **params)  # indicators computed on all data, then sliced (no leakage of future into past)
        bt_test = backtest(test, sig_full.loc[test.index], fee, slip)
        m = metrics(bt_test, test, tf)
        bt_hard = backtest(test, sig_full.loc[test.index], fee * 2, slip * 2)
        hard = metrics(bt_hard, test, tf)["return_%"]
        print(f"{str(params):<34}{mt['return_%']:>11}{mt['sharpe']:>10}{m['return_%']:>11}"
              f"{m['sharpe']:>9}{m['max_dd_%']:>9}{m['trades']:>7}{hard:>14}")

    bh = metrics(backtest(test, pd.Series(1.0, index=test.index), fee, slip), test, tf)
    print(f"\nBUY & HOLD on TEST: return {bh['buy_hold_%']}%, max drawdown "
          f"{max_drawdown((test['close'] / test['close'].iloc[0])) * 100:.1f}%")
    print("\nHOW TO READ THIS:")
    print(" - If TEST is much worse than TRAIN, the settings were overfitted. Not a real edge.")
    print(" - If TEST does not beat buy & hold (or at least cut the drawdown a lot), it is not worth running.")
    print(" - If the 2x-cost column collapses, the strategy is too fragile to survive real fees.")
    print(" - Fewer than ~30 test trades means the result is mostly luck either way.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("symbol")
    f.add_argument("tf")
    f.add_argument("since")
    f.add_argument("--exchange", default="binance")
    r = sub.add_parser("run")
    r.add_argument("path", nargs="?")
    r.add_argument("--tf", default="1h")
    r.add_argument("--strategy", choices=STRATEGIES, default="sma")
    r.add_argument("--split", type=float, default=0.7)
    r.add_argument("--fee", type=float, default=0.001)
    r.add_argument("--slip", type=float, default=0.0005)
    r.add_argument("--synthetic", action="store_true")
    a = p.parse_args()

    if a.cmd == "fetch":
        fetch_all(a.symbol, a.tf, a.since, a.exchange)
    else:
        df = synthetic() if a.synthetic else load(a.path)
        if not a.synthetic:
            check_data(df, a.tf)
        run(df, a.tf, a.strategy, a.split, a.fee, a.slip)


if __name__ == "__main__":
    main()