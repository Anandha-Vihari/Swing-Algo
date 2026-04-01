#!/usr/bin/env python3
"""
1H BACKTEST - ALL MAJOR PAIRS
Trade any setup that triggers, highest frequency approach
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional, Dict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from data_handler import OHLCV

class MultiPairBacktest1H:
    """Backtest across all major pairs simultaneously."""

    MAJOR_PAIRS = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'NZDUSD',
        'USDCHF', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY'
    ]

    def __init__(self, days_back: int = 60):
        self.days_back = days_back
        self.pair_data = {}
        self.all_trades = []
        self.daily_trades = {}  # Track trades per day

    def fetch_all_pairs(self):
        """Fetch 1H data for all major pairs."""
        print("📥 Fetching 1H data for all major pairs...")
        print("-" * 70)

        for pair in self.MAJOR_PAIRS:
            try:
                ticker = f"{pair}=X"
                df = yf.download(ticker, period=f"{self.days_back}d", interval="1h", progress=False)

                if df.empty:
                    logger.warning(f"❌ {pair}: No data")
                    continue

                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                self.pair_data[pair] = df

                candles = len(df)
                logger.info(f"✅ {pair}: {candles} candles loaded")

            except Exception as e:
                logger.warning(f"❌ {pair}: {str(e)[:50]}")

        print("-" * 70)
        print(f"Total pairs loaded: {len(self.pair_data)}\n")

    def df_to_ohlcv(self, df: pd.DataFrame) -> List[OHLCV]:
        """Convert DataFrame to OHLCV objects."""
        ohlcv_list = []
        for idx, row in df.iterrows():
            candle = OHLCV(
                open_=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=float(row['Volume']),
                time=idx
            )
            ohlcv_list.append(candle)
        return ohlcv_list

    def identify_swing(self, candles: List[OHLCV]) -> tuple:
        """Identify swings on 1H."""
        if len(candles) < 10:
            return None, None

        recent = candles[-15:]

        upper_swings = []
        lower_swings = []

        for i in range(1, len(recent) - 1):
            if recent[i].high > recent[i-1].high and recent[i].high > recent[i+1].high:
                upper_swings.append(recent[i].high)

            if recent[i].low < recent[i-1].low and recent[i].low < recent[i+1].low:
                lower_swings.append(recent[i].low)

        upper = max(upper_swings) if upper_swings else None
        lower = min(lower_swings) if lower_swings else None

        return upper, lower

    def check_trend(self, candles: List[OHLCV]) -> Optional[str]:
        """Check trend on 1H."""
        if len(candles) < 5:
            return None

        recent_5 = candles[-6:-1]
        highs = [c.high for c in recent_5]
        lows = [c.low for c in recent_5]

        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        if hh >= 2:
            return 'LONG'
        elif ll >= 2:
            return 'SHORT'

        return None

    def generate_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """Generate 1H scalp signal."""
        if len(candles) < 20:
            return None

        current = candles[-1]
        trend = self.check_trend(candles)

        if not trend:
            return None

        upper, lower = self.identify_swing(candles)

        if not upper or not lower:
            return None

        # LONG setup
        if trend == 'LONG' and current.close > upper:
            breakout_pips = (current.close - upper) / 0.0001

            if breakout_pips >= 2:  # 2+ pips on 1H
                sl = lower - (20 * 0.0001)
                risk_pips = (current.close - sl) / 0.0001

                if 8 < risk_pips < 100:
                    tp = current.close + (risk_pips * 1.5 * 0.0001)

                    return {
                        'pair': pair,
                        'direction': 'LONG',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                    }

        # SHORT setup
        elif trend == 'SHORT' and current.close < lower:
            breakout_pips = (lower - current.close) / 0.0001

            if breakout_pips >= 2:
                sl = upper + (20 * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 8 < risk_pips < 100:
                    tp = current.close - (risk_pips * 1.5 * 0.0001)

                    return {
                        'pair': pair,
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
        else:  # SHORT
            if candle.low <= trade['tp']:
                return 'TP'
            elif candle.high >= trade['sl']:
                return 'SL'

        return None

    def run_backtest(self):
        """Run multi-pair 1H backtest."""
        print("🔄 Running backtest across all pairs...\n")

        # Convert all DataFrames to OHLCV
        pair_candles = {}
        for pair, df in self.pair_data.items():
            pair_candles[pair] = self.df_to_ohlcv(df)

        # Find max length
        max_candles = max(len(candles) for candles in pair_candles.values())

        active_trades = {}  # Track active trades per pair
        lookback = 20

        # Iterate through each candle index
        for candle_idx in range(lookback, max_candles):
            # Check each pair
            for pair, candles in pair_candles.items():
                if candle_idx >= len(candles):
                    continue

                current_candle = candles[candle_idx]
                history = candles[:candle_idx + 1]

                # Monitor active trade for this pair
                if pair in active_trades:
                    trade = active_trades[pair]
                    result = self.evaluate_trade(trade, current_candle)

                    if result:
                        # Trade closed
                        if result == 'TP':
                            pips = trade['risk_pips'] * 1.5
                        else:  # SL
                            pips = -trade['risk_pips']

                        self.all_trades.append({
                            'pair': pair,
                            'direction': trade['direction'],
                            'entry': trade['entry'],
                            'pips': pips,
                            'result': result,
                            'date': current_candle.time,
                        })

                        # Track daily
                        day = str(current_candle.time.date())
                        if day not in self.daily_trades:
                            self.daily_trades[day] = []
                        self.daily_trades[day].append({
                            'pair': pair,
                            'pips': pips,
                        })

                        del active_trades[pair]

                # Look for new signal (only if no active trade)
                if pair not in active_trades and candle_idx % 3 == 0:
                    signal = self.generate_signal(pair, history)

                    if signal:
                        active_trades[pair] = signal

        return self.calculate_stats()

    def calculate_stats(self) -> dict:
        """Calculate backtest statistics."""
        if not self.all_trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'total_pips': 0.0,
                'profit_factor': 0.0,
                'avg_pips': 0.0,
                'trades_per_day': 0.0,
            }

        wins = [t for t in self.all_trades if t['pips'] > 0]
        losses = [t for t in self.all_trades if t['pips'] <= 0]

        win_pips = sum(t['pips'] for t in wins)
        loss_pips = abs(sum(t['pips'] for t in losses))

        stats = {
            'total_trades': len(self.all_trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': (len(wins) / len(self.all_trades)) * 100,
            'total_pips': sum(t['pips'] for t in self.all_trades),
            'profit_factor': win_pips / loss_pips if loss_pips > 0 else float('inf'),
            'avg_pips': sum(t['pips'] for t in self.all_trades) / len(self.all_trades),
            'avg_win_pips': sum(t['pips'] for t in wins) / len(wins) if wins else 0,
            'avg_loss_pips': sum(t['pips'] for t in losses) / len(losses) if losses else 0,
            'trades_per_day': len(self.all_trades) / len(self.daily_trades) if self.daily_trades else 0,
        }

        return stats


def main():
    print("\n" + "="*80)
    print("1H BACKTEST - ALL MAJOR PAIRS (Trade Any Setup)")
    print("="*80 + "\n")

    backtester = MultiPairBacktest1H(days_back=60)
    backtester.fetch_all_pairs()

    stats = backtester.run_backtest()

    if stats['total_trades'] == 0:
        print("❌ No trades generated")
        return

    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    print(f"\n📊 Trade Statistics:")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Winning Trades: {stats['wins']} ({stats['win_rate']:.1f}%)")
    print(f"  Losing Trades: {stats['losses']}")
    print(f"  Profit Factor: {stats['profit_factor']:.2f}")
    print(f"  Total Pips: {stats['total_pips']:+.0f}")
    print(f"  Avg Pips/Trade: {stats['avg_pips']:+.1f}")
    print(f"  Avg Win: {stats['avg_win_pips']:+.1f}p")
    print(f"  Avg Loss: {stats['avg_loss_pips']:+.1f}p")

    print(f"\n📈 Daily Activity:")
    print(f"  Trades/Day: {stats['trades_per_day']:.1f}")
    print(f"  Trading Days: {len(backtester.daily_trades)}")

    # P&L projection
    print(f"\n💰 P&L Projection (1H micro-lot = $0.10/pip):")
    pips_per_trade = stats['avg_pips']
    daily_pips_5trades = pips_per_trade * 5
    daily_profit = daily_pips_5trades * 0.10
    profit_15days = daily_profit * 15
    profit_30days = daily_profit * 30

    print(f"  Avg pips/trade: {pips_per_trade:+.1f}p")
    print(f"  5 trades/day: {daily_pips_5trades:+.1f}p → ${daily_profit:+.2f}")
    print(f"  15 days: ${profit_15days:+.2f}")
    print(f"  30 days: ${profit_30days:+.2f}")

    print(f"\n🎯 $20 Account Projections:")
    print(f"  Day 15: ${20 + profit_15days:.2f} ({(profit_15days/20)*100:+.0f}%)")
    print(f"  Day 30: ${20 + profit_30days:.2f} ({(profit_30days/20)*100:+.0f}%)")

    # Verdict
    print(f"\n📋 Verdict:")
    if stats['win_rate'] >= 60 and profit_15days >= 150:
        print(f"  ✅ CAN HIT $200 IN 15 DAYS (with proper scaling)")
    elif stats['win_rate'] >= 55 and profit_30days >= 150:
        print(f"  ✅ CAN HIT $200 IN 30 DAYS")
    elif stats['win_rate'] >= 50:
        print(f"  ⚠️  PROFITABLE BUT SLOWER ($20 → ${20 + profit_30days:.0f} in 30 days)")
    else:
        print(f"  ❌ NOT PROFITABLE")

    print("="*80 + "\n")

    # Show top performing pairs
    print("📊 Performance by Pair:")
    print("-" * 80)
    pair_stats = {}
    for trade in backtester.all_trades:
        pair = trade['pair']
        if pair not in pair_stats:
            pair_stats[pair] = {'trades': 0, 'wins': 0, 'pips': 0}

        pair_stats[pair]['trades'] += 1
        if trade['pips'] > 0:
            pair_stats[pair]['wins'] += 1
        pair_stats[pair]['pips'] += trade['pips']

    for pair in sorted(pair_stats.keys(), key=lambda p: pair_stats[p]['pips'], reverse=True):
        data = pair_stats[pair]
        wr = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0
        print(f"  {pair}: {data['trades']} trades, {wr:.0f}% WR, {data['pips']:+.0f}p")

    print("-" * 80)


if __name__ == "__main__":
    main()
