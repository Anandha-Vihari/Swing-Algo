#!/usr/bin/env python3
"""
HYBRID STRATEGY - SIMPLIFIED
Uses PROVEN strategies:
  - 4H: Use existing strategy.py (+$546 verified)
  - 1H: Simplified tight scalping on best pairs

Result: Combine proven + experimental
"""

import pandas as pd
import yfinance as yf
from typing import List
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

from data_handler import OHLCV
from strategy import StrategyEngine

class SimpleHybrid:
    """Simple hybrid using proven 4H + optimized 1H."""

    H1_PAIRS = ['GBPUSD', 'USDCAD', 'AUDUSD']

    def __init__(self):
        self.pair_data_1h = {}
        self.h1_trades = []
        self.h4_trades = []

    def fetch_data(self):
        """Fetch 1H data only (we'll resample for 4H)."""
        print("📥 Fetching 2 years 1H data for all pairs...\n")

        pairs_all = self.H1_PAIRS + ['EURUSD', 'USDJPY']

        for pair in pairs_all:
            try:
                ticker = f"{pair}=X"
                df = yf.download(ticker, period="730d", interval="1h", progress=False)
                if not df.empty:
                    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                    self.pair_data_1h[pair] = df
                    print(f"  ✅ {pair}: {len(df)} candles")
            except Exception as e:
                print(f"  ❌ {pair}: {str(e)[:40]}")

        print()

    def df_to_ohlcv(self, df: pd.DataFrame) -> List[OHLCV]:
        """Convert DataFrame to OHLCV."""
        return [
            OHLCV(
                open_=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=float(row['Volume']),
                time=idx
            )
            for idx, row in df.iterrows()
        ]

    def identify_swing_tight(self, candles: List[OHLCV]) -> tuple:
        """Tight swing detection for 1H."""
        if len(candles) < 10:
            return None, None

        recent = candles[-12:]
        highs = [c.high for i, c in enumerate(recent)
                if i > 0 and i < len(recent)-1 and c.high > recent[i-1].high and c.high > recent[i+1].high]
        lows = [c.low for i, c in enumerate(recent)
               if i > 0 and i < len(recent)-1 and c.low < recent[i-1].low and c.low < recent[i+1].low]

        return (max(highs) if highs else None, min(lows) if lows else None)

    def generate_h1_signal(self, pair: str, candles: List[OHLCV]) -> dict:
        """1H tight scalping signal."""
        if len(candles) < 15:
            return None

        current = candles[-1]
        recent_5 = candles[-6:-1]

        hh = sum(1 for i in range(1, len(recent_5)) if recent_5[i].high > recent_5[i-1].high)
        ll = sum(1 for i in range(1, len(recent_5)) if recent_5[i].low < recent_5[i-1].low)

        if not (hh >= 2 or ll >= 2):
            return None

        upper, lower = self.identify_swing_tight(candles)
        if not upper or not lower:
            return None

        # LONG: breakout + pullback
        if hh >= 2 and current.close > upper:
            breakout = (current.close - upper) / 0.0001
            if 2 <= breakout <= 25:  # Realistic for 1H
                sl = lower - (8 * 0.0001)  # Tight SL: 8 pips
                risk = (current.close - sl) / 0.0001

                if 5 < risk < 25:  # Keep risk small
                    tp = current.close + (risk * 1.5 * 0.0001)
                    return {'dir': 'L', 'entry': current.close, 'sl': sl, 'tp': tp, 'risk': risk}

        # SHORT
        elif ll >= 2 and current.close < lower:
            breakout = (lower - current.close) / 0.0001
            if 2 <= breakout <= 25:
                sl = upper + (8 * 0.0001)
                risk = (sl - current.close) / 0.0001

                if 5 < risk < 25:
                    tp = current.close - (risk * 1.5 * 0.0001)
                    return {'dir': 'S', 'entry': current.close, 'sl': sl, 'tp': tp, 'risk': risk}

        return None

    def evaluate_trade(self, trade: dict, candle: OHLCV) -> str:
        """Check if hits TP/SL."""
        if trade['dir'] == 'L':
            if candle.high >= trade['tp']:
                return 'TP'
            elif candle.low <= trade['sl']:
                return 'SL'
        else:
            if candle.low <= trade['tp']:
                return 'TP'
            elif candle.high >= trade['sl']:
                return 'SL'
        return None

    def run_backtest(self):
        """Run combined backtest."""
        print("🔄 Running hybrid backtest...\n")

        all_candles = {p: self.df_to_ohlcv(df) for p, df in self.pair_data_1h.items()}
        max_idx = max(len(c) for c in all_candles.values())

        # === 1H Scalping (GBPUSD, USDCAD, AUDUSD) ===
        print("1️⃣  1H Scalping...")
        active_1h = {}

        for idx in range(15, max_idx, 2):  # Every 2 candles
            if idx % 5000 == 0:
                print(f"   {idx/max_idx*100:.0f}%")

            for pair in self.H1_PAIRS:
                if idx >= len(all_candles[pair]):
                    continue

                candle = all_candles[pair][idx]

                # Monitor active trade
                if pair in active_1h:
                    result = self.evaluate_trade(active_1h[pair], candle)
                    if result:
                        pips = active_1h[pair]['risk'] * 1.5 if result == 'TP' else -active_1h[pair]['risk']
                        self.h1_trades.append({'pair': pair, 'pips': pips, 'type': result})
                        del active_1h[pair]

                # Look for new signal
                if pair not in active_1h:
                    history = all_candles[pair][:idx+1]
                    signal = self.generate_h1_signal(pair, history)
                    if signal:
                        active_1h[pair] = signal

        print(f"   ✅ 1H: {len(self.h1_trades)} trades\n")

        # === 4H Using Proven Strategy ===
        print("2️⃣  4H Proven Strategy...")

        h4_pairs = ['EURUSD', 'GBPUSD', 'USDJPY']
        h4_candles = {}

        for pair in h4_pairs:
            # Resample to 4H
            df_1h = self.pair_data_1h[pair]
            df_4h = df_1h.resample('4h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

            h4_candles[pair] = self.df_to_ohlcv(df_4h)
            print(f"   {pair}: {len(h4_candles[pair])} 4H candles")

        print()

        # Run 4H using proven strategy
        from config import BotConfig
        strategy = StrategyEngine(BotConfig())
        active_4h = {}

        max_4h = max(len(c) for c in h4_candles.values())

        for idx in range(50, max_4h, 2):
            if idx % 500 == 0:
                print(f"   {idx/max_4h*100:.0f}%")

            for pair in h4_pairs:
                if idx >= len(h4_candles[pair]):
                    continue

                candle = h4_candles[pair][idx]

                # Monitor active trade
                if pair in active_4h:
                    trade = active_4h[pair]
                    if candle.high >= trade.take_profit:
                        pips = (trade.take_profit - trade.entry_price) / 0.0001
                        self.h4_trades.append({'pair': pair, 'pips': pips, 'type': 'TP'})
                        del active_4h[pair]
                    elif candle.low <= trade.stop_loss:
                        pips = (trade.stop_loss - trade.entry_price) / 0.0001
                        self.h4_trades.append({'pair': pair, 'pips': pips, 'type': 'SL'})
                        del active_4h[pair]

                # Look for new signal
                if pair not in active_4h and idx % 3 == 0:
                    history = h4_candles[pair][:idx+1]
                    signal = strategy.analyze(pair, history)
                    if signal:
                        active_4h[pair] = signal

        print(f"   ✅ 4H: {len(self.h4_trades)} trades\n")

        # Analyze
        print("\n" + "="*80)
        print("HYBRID RESULTS")
        print("="*80)

        h1_wins = len([t for t in self.h1_trades if t['pips'] > 0])
        h1_pips = sum(t['pips'] for t in self.h1_trades)

        h4_wins = len([t for t in self.h4_trades if t['pips'] > 0])
        h4_pips = sum(t['pips'] for t in self.h4_trades)

        print(f"\n1H SCALPING ({len(self.h1_trades)} trades):")
        print(f"  Wins: {h1_wins} ({h1_wins/len(self.h1_trades)*100:.0f}%)")
        print(f"  Pips: {h1_pips:+.0f}")
        print(f"  Avg: {h1_pips/len(self.h1_trades):+.1f}p/trade")

        print(f"\n4H CORE ({len(self.h4_trades)} trades):")
        print(f"  Wins: {h4_wins} ({h4_wins/len(self.h4_trades)*100:.0f}%)" if self.h4_trades else "  No 4H trades")
        if self.h4_trades:
            print(f"  Pips: {h4_pips:+.0f}")
            print(f"  Avg: {h4_pips/len(self.h4_trades):+.1f}p/trade")

        total_pips = h1_pips + h4_pips
        total_trades = len(self.h1_trades) + len(self.h4_trades)

        print(f"\n💰 COMBINED:")
        print(f"  Total trades: {total_trades}")
        print(f"  Total pips: {total_pips:+.0f}")
        print(f"  Avg per trade: {total_pips/total_trades:+.1f}p")

        # Weekly projection
        weeks = 104  # 2 years
        pips_per_week = total_pips / weeks
        profit_per_week = pips_per_week * 0.10

        print(f"\n📈 WEEKLY (on $20 account):")
        print(f"  Pips/week: {pips_per_week:+.1f}")
        print(f"  $/week: {profit_per_week:+.2f}")
        print(f"  Week 1: ${20 + profit_per_week:.2f}")
        print(f"  Week 4: ${20 + profit_per_week*4:.2f}")
        print(f"  Week 13: ${20 + profit_per_week*13:.2f}")
        print(f"  Week 26: ${20 + profit_per_week*26:.2f}")

        print("="*80 + "\n")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SIMPLIFIED HYBRID: 1H SCALPS + 4H PROVEN")
    print("="*80 + "\n")

    hybrid = SimpleHybrid()
    hybrid.fetch_data()
    hybrid.run_backtest()
