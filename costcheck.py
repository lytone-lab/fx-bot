#!/usr/bin/env python3
"""
costcheck.py - do fees and slippage leave room for a strategy on this timeframe?

Usage:  python costcheck.py data/BTC_USDT_1h.csv [reward_to_risk]
Reads the CSV made by backtest.py fetch, measures how far price really moves
(ATR as % of price), and prints the win rate a strategy needs just to break even
after costs, if its stop is 1x or 2x ATR and its target is reward_to_risk x the stop.
"""
import sys

import numpy as np
import pandas as pd

path = sys.argv[1]
rr = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
df = pd.read_csv(path)
pc = df["close"].shift(1)
tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
atr_pct = float((tr.ewm(alpha=1 / 14, adjust=False).mean() / df["close"] * 100).median())

# round-trip cost as % of position size (entry + exit)
COSTS = {
    "spot taker      (0.10% fee + 0.05% slip, x2)": 0.30,
    "futures taker   (0.05% fee + 0.03% slip, x2)": 0.16,
    "futures maker   (0.02% fee, assumes you always get filled)": 0.04,
}

print(f"\n{path}: {len(df)} candles, typical ATR(14) = {atr_pct:.3f}% of price, reward:risk = {rr}")
print("Break-even win rate = (stop + cost) / ((rr + 1) * stop).  Above 100% = impossible.\n")
print(f"{'stop size':<16}{'cost scenario':<62}{'break-even win rate'}")
for mult in (1.0, 2.0):
    stop = atr_pct * mult
    for name, cost in COSTS.items():
        be = (stop + cost) / ((rr + 1) * stop) * 100
        shown = f"{be:.0f}%" if be < 100 else "impossible"
        print(f"{mult:.0f}x ATR={stop:.3f}%  {name:<62}{shown}")
    print()
print("Compare with your backtest win rate. Real strategies rarely sustain more than 50-55%.")