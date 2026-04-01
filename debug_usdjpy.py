#!/usr/bin/env python3
"""Debug USDJPY signal generation."""

import pandas as pd
from strategy import StrategyEngine
from data_handler import OHLCV
from config import BotConfig
from bot_data_pipeline import get_cached_data

data = get_cached_data(['USDJPY'])
df = data['USDJPY']

# Convert to OHLCV
ohlcv_list = []
for idx, row in df.iterrows():
    candle = OHLCV(
        open_=float(row['open']),
        high=float(row['high']),
        low=float(row['low']),
        close=float(row['close']),
        volume=float(row['volume']),
        time=idx
    )
    ohlcv_list.append(candle)

strategy = StrategyEngine(BotConfig())

# Manually test some analysis calls
test_idx = 100
history = ohlcv_list[:test_idx]

print(f"Testing with {len(history)} candles")
print(f"Last candle: O={history[-1].open:.2f} H={history[-1].high:.2f} L={history[-1].low:.2f} C={history[-1].close:.2f}")

# Check if swings are being found
upper, lower = strategy._identify_swings(history)
print(f"\nSwings identified:")
print(f"  Upper high: {upper['high'] if upper else 'None'}")
print(f"  Lower low: {lower['low'] if lower else 'None'}")
print(f"  Current close: {history[-1].close}")

if upper and lower:
    close_vs_up = history[-1].close - upper['high']
    close_vs_lo = lower['low'] - history[-1].close
    print(f"  Close vs upper swing: {close_vs_up:.4f} ({close_vs_up/0.0001:.0f} pips)")
    print(f"  Lower swing vs close: {close_vs_lo:.4f} ({close_vs_lo/0.0001:.0f} pips)")

# Try to analyze
signal = strategy.analyze('USDJPY', history)
print(f"\nSignal: {signal}")

# Test a few more indices
print("\nScanning full dataset...")
signal_count = 0
for i in range(50, len(ohlcv_list), 10):
    history = ohlcv_list[max(0, i-200):i+1]
    signal = strategy.analyze('USDJPY', history)
    if signal:
        signal_count += 1
        print(f"Signal at {i}: {signal.confirmation}")

print(f"\nTotal signals found: {signal_count}")
