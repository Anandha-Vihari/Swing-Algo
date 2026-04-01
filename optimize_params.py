#!/usr/bin/env python3
"""
PARAMETER OPTIMIZATION - Find best settings for 55%+ win rate
Tests different combinations and ranks by win rate
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

from data_handler import OHLCV

class ParameterOptimizer:
    """Test different parameter combinations."""

    PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD']

    def __init__(self):
        self.pair_data = {}
        self.results = []

    def fetch_data(self):
        """Fetch 2 years data."""
        print("📥 Fetching data...\n")

        for pair in self.PAIRS:
            try:
                ticker = f"{pair}=X"
                df_1h = yf.download(ticker, period="730d", interval="1h", progress=False)

                if not df_1h.empty:
                    df_1h.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                    df_4h = df_1h.resample('4h').agg({
                        'Open': 'first',
                        'High': 'max',
                        'Low': 'min',
                        'Close': 'last',
                        'Volume': 'sum'
                    }).dropna()

                    self.pair_data[pair] = df_4h
            except:
                pass

        print(f"✅ Loaded {len(self.pair_data)} pairs\n")

    def df_to_ohlcv(self, df: pd.DataFrame) -> List[OHLCV]:
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

    def identify_swing(self, candles: List[OHLCV], lookback: int = 30) -> tuple:
        if len(candles) < lookback:
            return None, None

        recent = candles[-lookback:]
        upper = max(c.high for c in recent)
        lower = min(c.low for c in recent)
        return upper, lower

    def check_trend(self, candles: List[OHLCV], min_strength: int) -> str:
        if len(candles) < 5:
            return None

        recent_20 = candles[-21:-1]
        highs = [c.high for c in recent_20]
        lows = [c.low for c in recent_20]

        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        if hh >= min_strength:
            return 'UP'
        elif ll >= min_strength:
            return 'DOWN'
        return None

    def generate_signal(self, pair: str, candles: List[OHLCV],
                       trend_strength: int, breakout_pips: int,
                       sl_pips: int, rr_ratio: float) -> Dict:
        if len(candles) < 100:
            return None

        current = candles[-1]
        trend = self.check_trend(candles, trend_strength)

        if not trend:
            return None

        upper, lower = self.identify_swing(candles, lookback=40)
        if not upper or not lower:
            return None

        # LONG
        if trend == 'UP' and current.close > upper:
            bkout = (current.close - upper) / 0.0001
            if bkout >= breakout_pips:
                sl = lower - (sl_pips * 0.0001)
                risk_pips = (current.close - sl) / 0.0001

                if 10 < risk_pips < 300:
                    tp = current.close + (risk_pips * rr_ratio * 0.0001)
                    rr = (tp - current.close) / (current.close - sl)

                    if 1.5 <= rr <= 3.5:
                        return {
                            'direction': 'UP',
                            'entry': current.close,
                            'sl': sl,
                            'tp': tp,
                            'risk_pips': risk_pips,
                        }

        # SHORT
        elif trend == 'DOWN' and current.close < lower:
            bkout = (lower - current.close) / 0.0001
            if bkout >= breakout_pips:
                sl = upper + (sl_pips * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 10 < risk_pips < 300:
                    tp = current.close - (risk_pips * rr_ratio * 0.0001)
                    rr = (current.close - tp) / (sl - current.close)

                    if 1.5 <= rr <= 3.5:
                        return {
                            'direction': 'DOWN',
                            'entry': current.close,
                            'sl': sl,
                            'tp': tp,
                            'risk_pips': risk_pips,
                        }

        return None

    def evaluate_trade(self, trade: Dict, candle: OHLCV) -> str:
        if trade['direction'] == 'UP':
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

    def test_parameter_set(self, trend_strength: int, breakout_pips: int,
                          sl_pips: int, rr_ratio: float) -> Dict:
        """Test a single parameter combination."""
        all_candles = {p: self.df_to_ohlcv(df) for p, df in self.pair_data.items()}
        max_idx = max(len(c) for c in all_candles.values())

        trades = []
        active_trades = {}

        for idx in range(100, max_idx):
            for pair in self.PAIRS:
                if idx >= len(all_candles[pair]):
                    continue

                candle = all_candles[pair][idx]

                # Monitor active trade
                if pair in active_trades:
                    result = self.evaluate_trade(active_trades[pair], candle)
                    if result:
                        trade = active_trades[pair]
                        pips = (trade['risk_pips'] * rr_ratio) if result == 'TP' else -trade['risk_pips']
                        trades.append({'pips': pips, 'result': result})
                        del active_trades[pair]

                # Look for signal
                if pair not in active_trades and idx % 3 == 0:
                    signal = self.generate_signal(pair, all_candles[pair][:idx+1],
                                                 trend_strength, breakout_pips,
                                                 sl_pips, rr_ratio)
                    if signal:
                        active_trades[pair] = signal

        if not trades:
            return None

        wins = len([t for t in trades if t['pips'] > 0])
        wr = wins / len(trades) * 100
        total_pips = sum(t['pips'] for t in trades)

        return {
            'trend_strength': trend_strength,
            'breakout_pips': breakout_pips,
            'sl_pips': sl_pips,
            'rr_ratio': rr_ratio,
            'trades': len(trades),
            'wr': wr,
            'pips': total_pips,
        }

    def run_optimization(self):
        """Test parameter grid."""
        print("="*80)
        print("PARAMETER OPTIMIZATION - Testing 48 combinations")
        print("="*80 + "\n")

        # Parameter ranges to test
        trend_strengths = [5, 6, 7]
        breakout_ranges = [8, 12, 15]
        sl_ranges = [30, 50, 80]
        rr_ratios = [1.8, 2.0, 2.5]

        combo_count = 0
        for ts in trend_strengths:
            for bp in breakout_ranges:
                for sl in sl_ranges:
                    for rr in rr_ratios:
                        combo_count += 1
                        print(f"[{combo_count}/48] Testing TS={ts}, BP={bp}, SL={sl}, RR={rr:.1f}...", end=" ")

                        result = self.test_parameter_set(ts, bp, sl, rr)

                        if result:
                            print(f"✅ {result['trades']:3d} trades, {result['wr']:5.1f}% WR, {result['pips']:+6.0f}p")
                            self.results.append(result)
                        else:
                            print("❌ No trades")

        # Sort by win rate
        self.results.sort(key=lambda x: x['wr'], reverse=True)

        print("\n" + "="*80)
        print("TOP 10 PARAMETER COMBINATIONS")
        print("="*80)
        print(f"\n{'TS':<4} {'BP':<4} {'SL':<4} {'RR':<5} {'Trades':<8} {'WR%':<7} {'Pips':<8}")
        print("-"*80)

        for i, result in enumerate(self.results[:10], 1):
            print(f"{result['trend_strength']:<4} {result['breakout_pips']:<4} "
                  f"{result['sl_pips']:<4} {result['rr_ratio']:<5.1f} "
                  f"{result['trades']:<8} {result['wr']:<7.1f} {result['pips']:>+7.0f}")

        print("-"*80)

        # Best result
        best = self.results[0]
        print(f"\n🏆 BEST: {best['wr']:.1f}% WR")
        print(f"   Settings: TS={best['trend_strength']}, BP={best['breakout_pips']}, "
              f"SL={best['sl_pips']}, RR={best['rr_ratio']}")
        print(f"   Trades: {best['trades']}, Pips: {best['pips']:+.0f}")

        # Project to $20 account
        weekly_pips = best['pips'] / 104
        weekly_profit = weekly_pips * 0.10

        print(f"\n💰 PROJECTION ($20 account):")
        print(f"   $/Week: {weekly_profit:+.2f}")
        print(f"   6 months: ${20 + weekly_profit*26:+.2f}")

        print("="*80 + "\n")


def main():
    optimizer = ParameterOptimizer()
    optimizer.fetch_data()
    optimizer.run_optimization()


if __name__ == "__main__":
    main()
