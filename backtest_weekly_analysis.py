#!/usr/bin/env python3
"""
2-YEAR WEEKLY ANALYSIS - Trade each WEEK, measure weekly P&L
104 weeks × 2 years = shows consistency and feasibility
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from data_handler import OHLCV

class WeeklyBacktest1H:
    """Analyze performance by week over 2 years."""

    MAJOR_PAIRS = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'NZDUSD',
        'USDCHF', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY'
    ]

    def __init__(self, years_back: int = 2):
        self.years_back = years_back
        self.pair_data = {}
        self.all_trades = []
        self.weekly_results = []  # Track P&L per week

    def fetch_all_pairs(self):
        """Fetch 1H data for all major pairs (2 years)."""
        print("📥 Fetching 2 YEARS of 1H data...")
        print("-" * 80)

        for pair in self.MAJOR_PAIRS:
            try:
                ticker = f"{pair}=X"
                df = yf.download(ticker, period=f"{self.years_back*365}d", interval="1h", progress=False)

                if df.empty:
                    logger.warning(f"❌ {pair}: No data")
                    continue

                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                self.pair_data[pair] = df

                candles = len(df)
                days = candles / 24
                logger.info(f"✅ {pair}: {candles} candles ({days:.0f} days)")

            except Exception as e:
                logger.warning(f"❌ {pair}: {str(e)[:50]}")

        print("-" * 80)
        print(f"Total pairs: {len(self.pair_data)}\n")

    def df_to_ohlcv(self, df: pd.DataFrame) -> List[OHLCV]:
        """Convert DataFrame to OHLCV objects."""
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

        return (max(upper_swings) if upper_swings else None,
                min(lower_swings) if lower_swings else None)

    def check_trend(self, candles: List[OHLCV]) -> Optional[str]:
        """Check trend on 1H."""
        if len(candles) < 5:
            return None

        recent_5 = candles[-6:-1]
        highs = [c.high for c in recent_5]
        lows = [c.low for c in recent_5]

        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        return 'LONG' if hh >= 2 else 'SHORT' if ll >= 2 else None

    def generate_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """Generate 1H signal."""
        if len(candles) < 20:
            return None

        current = candles[-1]
        trend = self.check_trend(candles)

        if not trend:
            return None

        upper, lower = self.identify_swing(candles)

        if not upper or not lower:
            return None

        # LONG
        if trend == 'LONG' and current.close > upper:
            breakout_pips = (current.close - upper) / 0.0001

            if breakout_pips >= 2:
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

        # SHORT
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

    def run_weekly_backtest(self):
        """Run backtest segmented by weeks."""
        print("🔄 Running WEEKLY analysis...\n")

        # Convert to OHLCV
        pair_candles = {}
        for pair, df in self.pair_data.items():
            pair_candles[pair] = self.df_to_ohlcv(df)

        # Get date range
        first_date = min(df.index[0] for df in self.pair_data.values())
        last_date = max(df.index[-1] for df in self.pair_data.values())

        print(f"Date Range: {first_date.date()} to {last_date.date()}")
        print(f"Total days: {(last_date - first_date).days}\n")

        # Segment into weeks (Monday to Friday)
        current_date = first_date
        week_num = 0

        while current_date < last_date:
            # Find Monday
            while current_date.weekday() != 0:  # Monday = 0
                current_date += timedelta(hours=1)

            monday = current_date
            friday_end = monday + timedelta(days=4, hours=23)

            if friday_end > last_date:
                break

            week_num += 1

            # Run trades for this week only
            week_trades = []
            active_trades = {}
            lookback = 20

            # Get candle indices for this week
            for pair, candles in pair_candles.items():
                for i, candle in enumerate(candles):
                    if monday <= candle.time <= friday_end:
                        if i < lookback:
                            continue

                        history = candles[:i+1]

                        # Monitor active trade
                        if pair in active_trades:
                            trade = active_trades[pair]
                            result = self.evaluate_trade(trade, candle)

                            if result:
                                if result == 'TP':
                                    pips = trade['risk_pips'] * 1.5
                                else:
                                    pips = -trade['risk_pips']

                                week_trades.append({
                                    'pair': pair,
                                    'pips': pips,
                                    'result': result,
                                })

                                del active_trades[pair]

                        # Look for new signal
                        if pair not in active_trades and i % 3 == 0:
                            signal = self.generate_signal(pair, history)
                            if signal:
                                active_trades[pair] = signal

            # Calculate week P&L
            week_pips = sum(t['pips'] for t in week_trades)
            week_profit_dollars = week_pips * 0.10  # Micro-lot

            self.weekly_results.append({
                'week': week_num,
                'start_date': monday.date(),
                'end_date': friday_end.date(),
                'trades': len(week_trades),
                'pips': week_pips,
                'profit': week_profit_dollars,
                'profitable': week_profit_dollars > 0,
            })

            current_date = friday_end + timedelta(hours=1)

        return self.analyze_weekly_stats()

    def analyze_weekly_stats(self) -> dict:
        """Analyze weekly performance."""
        if not self.weekly_results:
            return {}

        profitable_weeks = [w for w in self.weekly_results if w['profitable']]
        losing_weeks = [w for w in self.weekly_results if not w['profitable']]

        total_pips = sum(w['pips'] for w in self.weekly_results)
        total_profit = sum(w['profit'] for w in self.weekly_results)

        stats = {
            'total_weeks': len(self.weekly_results),
            'profitable_weeks': len(profitable_weeks),
            'losing_weeks': len(losing_weeks),
            'win_rate_weeks': (len(profitable_weeks) / len(self.weekly_results) * 100) if self.weekly_results else 0,
            'total_pips': total_pips,
            'total_profit': total_profit,
            'avg_pips_per_week': total_pips / len(self.weekly_results) if self.weekly_results else 0,
            'avg_profit_per_week': total_profit / len(self.weekly_results) if self.weekly_results else 0,
            'best_week': max(self.weekly_results, key=lambda w: w['profit']) if self.weekly_results else None,
            'worst_week': min(self.weekly_results, key=lambda w: w['profit']) if self.weekly_results else None,
            'avg_trades_per_week': sum(w['trades'] for w in self.weekly_results) / len(self.weekly_results) if self.weekly_results else 0,
        }

        return stats


def main():
    print("\n" + "="*80)
    print("2-YEAR WEEKLY ANALYSIS (104 WEEKS)")
    print("="*80 + "\n")

    backtester = WeeklyBacktest1H(years_back=2)
    backtester.fetch_all_pairs()

    stats = backtester.run_weekly_backtest()

    if not stats:
        print("❌ No weekly data")
        return

    print("\n" + "="*80)
    print("WEEKLY PERFORMANCE ANALYSIS")
    print("="*80)

    print(f"\n📊 Weekly Statistics:")
    print(f"  Total Weeks: {stats['total_weeks']}")
    print(f"  Profitable Weeks: {stats['profitable_weeks']} ({stats['win_rate_weeks']:.1f}%)")
    print(f"  Losing Weeks: {stats['losing_weeks']} ({100-stats['win_rate_weeks']:.1f}%)")
    print(f"  Week Win Rate: {stats['win_rate_weeks']:.1f}%")

    print(f"\n📈 Weekly P&L:")
    print(f"  Total Pips: {stats['total_pips']:+,.0f}")
    print(f"  Total Profit: ${stats['total_profit']:+,.2f}")
    print(f"  Avg Pips/Week: {stats['avg_pips_per_week']:+.1f}")
    print(f"  Avg Profit/Week: ${stats['avg_profit_per_week']:+.2f}")
    print(f"  Avg Trades/Week: {stats['avg_trades_per_week']:.1f}")

    print(f"\n🏆 Best Week:")
    best = stats['best_week']
    print(f"  Week {best['week']}: {best['start_date']} → {best['profit']:+.2f}$ ({best['pips']:+.0f}p, {best['trades']} trades)")

    print(f"\n💥 Worst Week:")
    worst = stats['worst_week']
    print(f"  Week {worst['week']}: {worst['start_date']} → {worst['profit']:+.2f}$ ({worst['pips']:+.0f}p, {worst['trades']} trades)")

    # $20 Account Analysis
    print(f"\n💰 $20 ACCOUNT WEEKLY SCALING:")
    print(f"  Starting: $20.00")
    if stats['avg_profit_per_week'] > 0:
        week_1 = 20 + stats['avg_profit_per_week']
        week_4 = 20 + (stats['avg_profit_per_week'] * 4)
        week_13 = 20 + (stats['avg_profit_per_week'] * 13)
        week_26 = 20 + (stats['avg_profit_per_week'] * 26)
        print(f"  After 1 week: ${week_1:.2f} (+{(week_1-20)/20*100:.0f}%)")
        print(f"  After 4 weeks: ${week_4:.2f} (+{(week_4-20)/20*100:.0f}%)")
        print(f"  After 13 weeks (quarter): ${week_13:.2f} (+{(week_13-20)/20*100:.0f}%)")
        print(f"  After 26 weeks (half year): ${week_26:.2f} (+{(week_26-20)/20*100:.0f}%)")
    else:
        print(f"  ❌ Negative weekly returns - cannot scale")

    # Verdict
    print(f"\n📋 VERDICT:")
    print("-" * 80)

    if stats['win_rate_weeks'] >= 60:
        print(f"✅ HIGH CONSISTENCY: {stats['win_rate_weeks']:.0f}% of weeks are profitable")
    elif stats['win_rate_weeks'] >= 50:
        print(f"⚠️  BREAKEVEN: {stats['win_rate_weeks']:.0f}% of weeks are profitable")
    else:
        print(f"❌ LOW CONSISTENCY: Only {stats['win_rate_weeks']:.0f}% of weeks profitable")

    if stats['avg_profit_per_week'] > 10:
        print(f"✅ STRONG WEEKLY RETURNS: ${stats['avg_profit_per_week']:+.2f}/week")
    elif stats['avg_profit_per_week'] > 0:
        print(f"⚠️  WEAK WEEKLY RETURNS: ${stats['avg_profit_per_week']:+.2f}/week (slow growth)")
    else:
        print(f"❌ NEGATIVE WEEKLY RETURNS: ${stats['avg_profit_per_week']:+.2f}/week")

    print("-" * 80)

    # Show sample of weeks
    print(f"\n📋 Sample of Weekly Results (First 10 weeks):")
    print("-" * 80)
    print(f"{'Week':<6} {'Start Date':<12} {'Profit':<10} {'Pips':<8} {'Trades':<8} {'Status':<10}")
    print("-" * 80)

    for week in backtester.weekly_results[:10]:
        status = "✅ PROFIT" if week['profitable'] else "❌ LOSS"
        print(f"{week['week']:<6} {str(week['start_date']):<12} ${week['profit']:>8.2f} {week['pips']:>+7.0f}p {week['trades']:<8} {status:<10}")

    print("-" * 80 + "\n")


if __name__ == "__main__":
    main()
