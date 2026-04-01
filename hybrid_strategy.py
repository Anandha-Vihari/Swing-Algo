#!/usr/bin/env python3
"""
HYBRID STRATEGY - 1H Scalping + 4H Core Trades
Combines:
  - 4H: High quality, 50-100p wins (1-2/week) - THE BACKBONE
  - 1H: Micro-scalps, 1-5p wins (5-10/week) - THE BUFFER

Result: Smoother equity curve, more consistent daily P&L
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from data_handler import OHLCV

class HybridStrategy:
    """Combined 1H + 4H strategy."""

    # Only use proven pairs
    H1_PAIRS = ['GBPUSD', 'USDCAD', 'AUDUSD']  # 1H scalping pairs
    H4_PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY']   # 4H core trades (from earlier backtest)

    def __init__(self, years_back: int = 2):
        self.years_back = years_back
        self.pair_data_1h = {}
        self.pair_data_4h = {}
        self.h1_trades = []
        self.h4_trades = []

    def fetch_data(self):
        """Fetch both 1H and 4H data."""
        print("📥 Fetching 2 years of data (1H + 4H)...\n")

        # 1H Data
        print("1H Data:")
        for pair in self.H1_PAIRS:
            try:
                ticker = f"{pair}=X"
                df = yf.download(ticker, period=f"{self.years_back*365}d", interval="1h", progress=False)
                if not df.empty:
                    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                    self.pair_data_1h[pair] = df
                    logger.info(f"  ✅ {pair}: {len(df)} candles")
            except Exception as e:
                logger.warning(f"  ❌ {pair}: {str(e)[:40]}")

        # 4H Data
        print("\n4H Data:")
        for pair in self.H4_PAIRS:
            try:
                ticker = f"{pair}=X"
                df = yf.download(ticker, period=f"{self.years_back*365}d", interval="1h", progress=False)
                if not df.empty:
                    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                    # Resample to 4H
                    df_4h = df.resample('4h').agg({
                        'Open': 'first',
                        'High': 'max',
                        'Low': 'min',
                        'Close': 'last',
                        'Volume': 'sum'
                    }).dropna()
                    self.pair_data_4h[pair] = df_4h
                    logger.info(f"  ✅ {pair}: {len(df_4h)} candles")
            except Exception as e:
                logger.warning(f"  ❌ {pair}: {str(e)[:40]}")

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

    def identify_swing(self, candles: List[OHLCV], lookback: int = 15) -> Tuple[Optional[float], Optional[float]]:
        """Identify swings."""
        if len(candles) < 10:
            return None, None

        recent = candles[-lookback:]
        upper_swings = []
        lower_swings = []

        for i in range(1, len(recent) - 1):
            if recent[i].high > recent[i-1].high and recent[i].high > recent[i+1].high:
                upper_swings.append(recent[i].high)
            if recent[i].low < recent[i-1].low and recent[i].low < recent[i+1].low:
                lower_swings.append(recent[i].low)

        return (max(upper_swings) if upper_swings else None,
                min(lower_swings) if lower_swings else None)

    def check_trend(self, candles: List[OHLCV]) -> Optional[str]:
        """Check trend."""
        if len(candles) < 5:
            return None

        recent_5 = candles[-6:-1]
        highs = [c.high for c in recent_5]
        lows = [c.low for c in recent_5]

        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        return 'LONG' if hh >= 2 else 'SHORT' if ll >= 2 else None

    # ===== 1H STRATEGY (TIGHT SCALPING) =====
    def generate_h1_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """Generate tight 1H signal (25-30p SL, 1.5:1 RR)."""
        if len(candles) < 20:
            return None

        current = candles[-1]
        trend = self.check_trend(candles)

        if not trend:
            return None

        upper, lower = self.identify_swing(candles, lookback=12)  # Shorter lookback for 1H

        if not upper or not lower:
            return None

        # LONG
        if trend == 'LONG' and current.close > upper:
            breakout_pips = (current.close - upper) / 0.0001

            if breakout_pips >= 3:  # Smaller breakout threshold
                # TIGHT SL: Only 25 pips
                sl = lower - (10 * 0.0001)  # Tighter!
                risk_pips = (current.close - sl) / 0.0001

                if 8 < risk_pips < 30:  # 1H is about 8-30p risk
                    # SMALLER RR: 1.5:1 instead of 2:1
                    tp = current.close + (risk_pips * 1.5 * 0.0001)

                    return {
                        'pair': pair,
                        'tf': '1H',
                        'direction': 'LONG',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                    }

        # SHORT
        elif trend == 'SHORT' and current.close < lower:
            breakout_pips = (lower - current.close) / 0.0001

            if breakout_pips >= 3:
                sl = upper + (10 * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 8 < risk_pips < 30:
                    tp = current.close - (risk_pips * 1.5 * 0.0001)

                    return {
                        'pair': pair,
                        'tf': '1H',
                        'direction': 'SHORT',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                    }

        return None

    # ===== 4H STRATEGY (PROVEN CORE) =====
    def generate_h4_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """Generate proven 4H signal (50p SL, 2:1 RR)."""
        if len(candles) < 50:
            return None

        current = candles[-1]
        recent_20 = candles[-21:-1]

        highs = [c.high for c in recent_20]
        lows = [c.low for c in recent_20]

        hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        bullish_trend = hh_count >= 6
        bearish_trend = ll_count >= 6

        if not (bullish_trend or bearish_trend):
            return None

        upper_swing, lower_swing = self.identify_swing(candles, lookback=40)
        if not upper_swing or not lower_swing:
            return None

        # Bullish
        if bullish_trend and current.close > upper_swing:
            breakout_pips = (current.close - upper_swing) / 0.0001
            if breakout_pips >= 12:
                sl = lower_swing - (50 * 0.0001)
                risk_pips = (current.close - sl) / 0.0001

                if 10 < risk_pips < 300:  # Sanity check
                    tp = current.close + (risk_pips * 2.0 * 0.0001)
                    return {
                        'pair': pair,
                        'tf': '4H',
                        'direction': 'LONG',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                    }

        # Bearish
        if bearish_trend and current.close < lower_swing:
            breakout_pips = (lower_swing - current.close) / 0.0001
            if breakout_pips >= 12:
                sl = upper_swing + (50 * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 10 < risk_pips < 300:  # Sanity check
                    tp = current.close - (risk_pips * 2.0 * 0.0001)
                    return {
                        'pair': pair,
                        'tf': '4H',
                        'direction': 'SHORT',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                    }

        return None

    def evaluate_trade(self, trade: dict, candle: OHLCV) -> Optional[str]:
        """Check if trade hits SL or TP."""
        if trade['direction'] == 'LONG':
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

    def run_hybrid_backtest(self):
        """Run combined 1H + 4H backtest."""
        print("🔄 Running HYBRID backtest...\n")

        # Convert data
        pair_candles_1h = {pair: self.df_to_ohlcv(df) for pair, df in self.pair_data_1h.items()}
        pair_candles_4h = {pair: self.df_to_ohlcv(df) for pair, df in self.pair_data_4h.items()}

        max_candles_1h = max(len(c) for c in pair_candles_1h.values()) if pair_candles_1h else 0
        max_candles_4h = max(len(c) for c in pair_candles_4h.values()) if pair_candles_4h else 0

        # ===== 1H BACKTEST =====
        print("1️⃣  Running 1H backtest (GBPUSD, USDCAD, AUDUSD)...")
        active_trades_1h = {}

        for candle_idx in range(20, max_candles_1h):
            if candle_idx % 5000 == 0:
                print(f"   Progress: {candle_idx/max_candles_1h*100:.1f}%")

            for pair, candles in pair_candles_1h.items():
                if candle_idx >= len(candles):
                    continue

                current_candle = candles[candle_idx]
                history = candles[:candle_idx + 1]

                # Monitor active trade
                if pair in active_trades_1h:
                    trade = active_trades_1h[pair]
                    result = self.evaluate_trade(trade, current_candle)

                    if result:
                        pips = trade['risk_pips'] * 1.5 if result == 'TP' else -trade['risk_pips']
                        self.h1_trades.append({
                            'pair': pair,
                            'direction': trade['direction'],
                            'pips': pips,
                            'result': result,
                            'date': current_candle.time,
                        })
                        del active_trades_1h[pair]

                # Look for new signal
                if pair not in active_trades_1h and candle_idx % 2 == 0:
                    signal = self.generate_h1_signal(pair, history)
                    if signal:
                        active_trades_1h[pair] = signal

        print(f"   ✅ 1H trades: {len(self.h1_trades)}\n")

        # ===== 4H BACKTEST =====
        print("2️⃣  Running 4H backtest (EURUSD, GBPUSD, USDJPY)...")
        active_trades_4h = {}

        for candle_idx in range(50, max_candles_4h):
            if candle_idx % 500 == 0:
                print(f"   Progress: {candle_idx/max_candles_4h*100:.1f}%")

            for pair, candles in pair_candles_4h.items():
                if candle_idx >= len(candles):
                    continue

                current_candle = candles[candle_idx]
                history = candles[:candle_idx + 1]

                # Monitor active trade
                if pair in active_trades_4h:
                    trade = active_trades_4h[pair]
                    result = self.evaluate_trade(trade, current_candle)

                    if result:
                        pips = trade['risk_pips'] * 2.0 if result == 'TP' else -trade['risk_pips']
                        self.h4_trades.append({
                            'pair': pair,
                            'direction': trade['direction'],
                            'pips': pips,
                            'result': result,
                            'date': current_candle.time,
                        })
                        del active_trades_4h[pair]

                # Look for new signal
                if pair not in active_trades_4h and candle_idx % 3 == 0:
                    signal = self.generate_h4_signal(pair, history)
                    if signal:
                        active_trades_4h[pair] = signal

        print(f"   ✅ 4H trades: {len(self.h4_trades)}\n")

        return self.analyze_hybrid()

    def analyze_hybrid(self) -> dict:
        """Analyze combined performance."""
        print("\n" + "="*80)
        print("HYBRID STRATEGY RESULTS")
        print("="*80)

        # 1H Analysis
        print("\n📊 1H SCALPING (TIGHT)")
        print("-" * 80)
        if self.h1_trades:
            h1_wins = len([t for t in self.h1_trades if t['pips'] > 0])
            h1_total_pips = sum(t['pips'] for t in self.h1_trades)
            h1_wr = (h1_wins / len(self.h1_trades) * 100) if self.h1_trades else 0
            h1_daily = h1_total_pips / 100  # Approximate daily

            print(f"Total Trades: {len(self.h1_trades)}")
            print(f"Wins: {h1_wins} ({h1_wr:.1f}%)")
            print(f"Total Pips: {h1_total_pips:+.0f}")
            print(f"Avg Pips/Trade: {h1_total_pips/len(self.h1_trades):+.1f}")
            print(f"Est Daily (on $20): ${h1_daily*0.10:+.2f}")
        else:
            print("❌ No trades generated")
            h1_total_pips = 0

        # 4H Analysis
        print("\n📊 4H CORE TRADES (PROVEN)")
        print("-" * 80)
        if self.h4_trades:
            h4_wins = len([t for t in self.h4_trades if t['pips'] > 0])
            h4_total_pips = sum(t['pips'] for t in self.h4_trades)
            h4_wr = (h4_wins / len(self.h4_trades) * 100) if self.h4_trades else 0
            h4_daily = h4_total_pips / 100

            print(f"Total Trades: {len(self.h4_trades)}")
            print(f"Wins: {h4_wins} ({h4_wr:.1f}%)")
            print(f"Total Pips: {h4_total_pips:+.0f}")
            print(f"Avg Pips/Trade: {h4_total_pips/len(self.h4_trades):+.1f}")
            print(f"Est Daily (on $20): ${h4_daily*0.10:+.2f}")
        else:
            print("❌ No trades generated")
            h4_total_pips = 0

        # Combined Analysis
        print("\n🎯 TOTAL HYBRID PERFORMANCE")
        print("-" * 80)
        total_trades = len(self.h1_trades) + len(self.h4_trades)
        total_pips = h1_total_pips + h4_total_pips
        total_wins = len([t for t in self.h1_trades if t['pips'] > 0]) + \
                     len([t for t in self.h4_trades if t['pips'] > 0])

        print(f"Total Trades: {total_trades}")
        print(f"Total Wins: {total_wins} ({total_wins/total_trades*100:.1f}%)")
        print(f"Total Pips: {total_pips:+.0f}")
        print(f"Avg Pips/Trade: {total_pips/total_trades:+.1f}")

        # Project to weekly/monthly
        trades_per_week = total_trades / 145  # 145 weeks in 2 years
        pips_per_week = trades_per_week * (total_pips / total_trades)
        profit_per_week = pips_per_week * 0.10

        print(f"\n💰 PROJECTIONS:")
        print(f"Trades/Week: {trades_per_week:.1f}")
        print(f"Pips/Week: {pips_per_week:+.1f}")
        print(f"Profit/Week: ${profit_per_week:+.2f}")
        print(f"$20 Account:")
        print(f"  After 1 week: ${20 + profit_per_week:.2f}")
        print(f"  After 4 weeks: ${20 + profit_per_week*4:.2f}")
        print(f"  After 13 weeks: ${20 + profit_per_week*13:.2f}")
        print(f"  After 26 weeks: ${20 + profit_per_week*26:.2f}")

        print("\n" + "="*80)

        return {
            'h1_pips': h1_total_pips,
            'h4_pips': h4_total_pips,
            'total_pips': total_pips,
            'trades_per_week': trades_per_week,
            'profit_per_week': profit_per_week,
        }


def main():
    print("\n" + "="*80)
    print("HYBRID STRATEGY: 1H SCALPS + 4H CORE TRADES")
    print("="*80 + "\n")

    hybrid = HybridStrategy(years_back=2)
    hybrid.fetch_data()
    results = hybrid.run_hybrid_backtest()


if __name__ == "__main__":
    main()
