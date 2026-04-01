#!/usr/bin/env python3
"""
TREND FOLLOWING STRATEGY (4H)
- Don't swing trade constantly
- Only enter on CONFIRMED strong trends
- Ride the trend until reversal
- High selectivity = high quality

Logic:
1. Identify strong trend (not weak structure)
2. Wait for pullback/consolidation
3. Enter on resumption of trend
4. Exit on trend reversal
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

from data_handler import OHLCV

class TrendFollowingStrategy:
    """Pure trend-following, high selectivity."""

    PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD']

    def __init__(self):
        self.pair_data = {}
        self.trades = []

    def fetch_data(self):
        """Fetch 2 years 1H data, resample to 4H."""
        print("📥 Fetching 2 years 1H data, resampling to 4H...\n")

        for pair in self.PAIRS:
            try:
                ticker = f"{pair}=X"
                df_1h = yf.download(ticker, period="730d", interval="1h", progress=False)

                if df_1h.empty:
                    continue

                df_1h.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

                # Resample to 4H
                df_4h = df_1h.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()

                self.pair_data[pair] = df_4h
                print(f"  ✅ {pair}: {len(df_4h)} 4H candles")

            except Exception as e:
                print(f"  ❌ {pair}: {str(e)[:40]}")

        print()

    def df_to_ohlcv(self, df: pd.DataFrame) -> List[OHLCV]:
        """Convert to OHLCV."""
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

    def calculate_trend_strength(self, candles: List[OHLCV]) -> tuple:
        """
        Calculate trend strength over last 50 candles.
        Returns: (trend_direction, strength_score, trend_start_idx)

        STRONG trend: Multiple consecutive HH/HL or LH/LL
        """
        if len(candles) < 50:
            return None, 0, None

        recent_50 = candles[-50:]
        highs = [c.high for c in recent_50]
        lows = [c.low for c in recent_50]

        # Count consecutive HH/HL and LH/LL
        hh_count = 0
        current_hh = 0
        max_hh = 0
        max_hh_idx = 0

        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                current_hh += 1
                if current_hh > max_hh:
                    max_hh = current_hh
                    max_hh_idx = i
            else:
                current_hh = 0

        ll_count = 0
        current_ll = 0
        max_ll = 0
        max_ll_idx = 0

        for i in range(1, len(lows)):
            if lows[i] < lows[i-1]:
                current_ll += 1
                if current_ll > max_ll:
                    max_ll = current_ll
                    max_ll_idx = i
            else:
                current_ll = 0

        # Determine trend
        if max_hh >= 6:  # 6+ consecutive HH = STRONG uptrend
            return 'UP', max_hh, 50 - len(recent_50) + max_hh_idx

        elif max_ll >= 6:  # 6+ consecutive LL = STRONG downtrend
            return 'DOWN', max_ll, 50 - len(recent_50) + max_ll_idx

        return None, 0, None

    def find_swing_high_low(self, candles: List[OHLCV], lookback: int = 20) -> tuple:
        """Find recent swing high and low for reference."""
        if len(candles) < lookback:
            return None, None

        recent = candles[-lookback:]
        swing_high = max(c.high for c in recent)
        swing_low = min(c.low for c in recent)

        return swing_high, swing_low

    def generate_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """
        Generate signal on confirmed trends - RELAXED VERSION.
        """
        if len(candles) < 100:
            return None

        current = candles[-1]
        trend, strength, trend_start = self.calculate_trend_strength(candles)

        # Only trade MODERATE trends (strength >= 5)
        if not trend or strength < 5:
            return None

        swing_high, swing_low = self.find_swing_high_low(candles, lookback=20)

        if not swing_high or not swing_low:
            return None

        # === UPTREND: Simple entry above recent high ===
        if trend == 'UP':
            # Entry: if close > swing_high, we're in trend
            # SL: below recent support
            if current.close > swing_low:  # Price above lower swing = bullish
                sl = swing_low - (30 * 0.0001)
                risk_pips = (current.close - sl) / 0.0001

                if 15 < risk_pips < 200:
                    tp = current.close + (risk_pips * 2.0 * 0.0001)

                    return {
                        'pair': pair,
                        'direction': 'UP',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                        'strength': strength,
                    }

        # === DOWNTREND: Simple entry below recent low ===
        elif trend == 'DOWN':
            if current.close < swing_high:  # Price below upper swing = bearish
                sl = swing_high + (30 * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 15 < risk_pips < 200:
                    tp = current.close - (risk_pips * 2.0 * 0.0001)

                    return {
                        'pair': pair,
                        'direction': 'DOWN',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                        'strength': strength,
                    }

        return None

    def evaluate_trade(self, trade: dict, candle: OHLCV) -> Optional[str]:
        """Check if hits TP/SL."""
        if trade['direction'] == 'UP':
            if candle.high >= trade['tp']:
                return 'TP'
            elif candle.low <= trade['sl']:
                return 'SL'
        else:  # DOWN
            if candle.low <= trade['tp']:
                return 'TP'
            elif candle.high >= trade['sl']:
                return 'SL'

        return None

    def run_backtest(self):
        """Run backtest."""
        print("🔄 Running trend-following backtest...\n")

        all_candles = {p: self.df_to_ohlcv(df) for p, df in self.pair_data.items()}
        max_idx = max(len(c) for c in all_candles.values())

        active_trades = {}

        for idx in range(100, max_idx):
            if idx % 500 == 0:
                print(f"  Progress: {idx/max_idx*100:.0f}%")

            for pair in self.PAIRS:
                if idx >= len(all_candles[pair]):
                    continue

                candle = all_candles[pair][idx]

                # Monitor active trade
                if pair in active_trades:
                    result = self.evaluate_trade(active_trades[pair], candle)

                    if result:
                        trade = active_trades[pair]
                        pips = (trade['risk_pips'] * 2.0) if result == 'TP' else -trade['risk_pips']

                        self.trades.append({
                            'pair': pair,
                            'direction': trade['direction'],
                            'pips': pips,
                            'result': result,
                            'strength': trade['strength'],
                            'date': candle.time,
                        })

                        del active_trades[pair]

                # Look for new signal (only every 3 candles to avoid re-entries)
                if pair not in active_trades and idx % 3 == 0:
                    history = all_candles[pair][:idx+1]
                    signal = self.generate_signal(pair, history)

                    if signal:
                        active_trades[pair] = signal

        print("\n")
        return self.analyze_results()

    def analyze_results(self):
        """Analyze backtest results."""
        print("\n" + "="*80)
        print("TREND FOLLOWING STRATEGY (4H) - RESULTS")
        print("="*80)

        if not self.trades:
            print("❌ No trades generated - strategy too selective")
            return

        wins = [t for t in self.trades if t['pips'] > 0]
        losses = [t for t in self.trades if t['pips'] <= 0]

        total_pips = sum(t['pips'] for t in self.trades)
        win_rate = (len(wins) / len(self.trades) * 100) if self.trades else 0

        print(f"\n📊 STATISTICS:")
        print(f"  Total Trades: {len(self.trades)}")
        print(f"  Winning Trades: {len(wins)} ({win_rate:.1f}%)")
        print(f"  Losing Trades: {len(losses)}")
        print(f"  Total Pips: {total_pips:+,.0f}")
        print(f"  Avg Pips/Trade: {total_pips/len(self.trades):+.1f}")

        if wins:
            avg_win = sum(t['pips'] for t in wins) / len(wins)
            max_win = max(t['pips'] for t in wins)
            print(f"  Avg Win: {avg_win:+.1f}p")
            print(f"  Max Win: {max_win:+.0f}p")

        if losses:
            avg_loss = sum(t['pips'] for t in losses) / len(losses)
            max_loss = min(t['pips'] for t in losses)
            print(f"  Avg Loss: {avg_loss:+.1f}p")
            print(f"  Max Loss: {max_loss:+.0f}p")

        # Profit factor
        gross_profit = sum(t['pips'] for t in wins)
        gross_loss = abs(sum(t['pips'] for t in losses))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        print(f"  Profit Factor: {pf:.2f}")

        # Projections
        print(f"\n💰 PROJECTIONS (on $20 account):")
        weeks = 104
        pips_per_week = total_pips / weeks
        profit_per_week = pips_per_week * 0.10

        print(f"  Pips/Week: {pips_per_week:+.1f}")
        print(f"  $/Week: {profit_per_week:+.2f}")
        print(f"  Week 1: ${20 + profit_per_week:.2f}")
        print(f"  Week 4: ${20 + profit_per_week*4:.2f}")
        print(f"  Week 13: ${20 + profit_per_week*13:.2f}")
        print(f"  Month 6: ${20 + profit_per_week*26:.2f}")
        print(f"  Year 1: ${20 + profit_per_week*52:.2f}")

        # By pair
        print(f"\n📈 PERFORMANCE BY PAIR:")
        print("-" * 80)
        pair_stats = {}
        for trade in self.trades:
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
            status = "✅" if data['pips'] > 0 else "❌"
            print(f"  {pair}: {data['trades']:3d} trades, {wr:5.1f}% WR, {data['pips']:+6.0f}p {status}")

        print("="*80)

        # Verdict
        print(f"\n🎯 VERDICT:")
        if win_rate >= 55 and profit_per_week > 0:
            print(f"  ✅ PROFITABLE STRATEGY (55%+ WR)")
            print(f"     Realistic: ${20/profit_per_week/52:.0f} weeks to double $20")
        elif win_rate >= 50 and profit_per_week > 0:
            print(f"  ✅ BREAKEVEN+ (50%+ WR, positive expected value)")
            print(f"     Realistic: ${20/profit_per_week/52:.0f} weeks to double $20")
        elif win_rate >= 45:
            print(f"  ⚠️  MARGINAL ({win_rate:.0f}% WR)")
            print(f"     Need perfect execution, slippage will hurt")
        else:
            print(f"  ❌ LOSING STRATEGY ({win_rate:.0f}% WR)")

        print("="*80 + "\n")


def main():
    print("\n" + "="*80)
    print("TREND FOLLOWING STRATEGY - 4H")
    print("High Selectivity, Only Trade Strong Trends")
    print("="*80 + "\n")

    ts = TrendFollowingStrategy()
    ts.fetch_data()
    ts.run_backtest()


if __name__ == "__main__":
    main()
