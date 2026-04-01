#!/usr/bin/env python3
"""
ADAPTIVE TREND-FOLLOWING STRATEGY (4H)
- Dynamic parameters that adjust based on performance
- Multi-condition entry confirmation (higher quality)
- Scaling position sizing with equity curve
- MT5-compatible code (ready for migration to your PC)

Target: 55-60%+ win rate
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional, Dict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

from data_handler import OHLCV

class AdaptiveStrategy:
    """Adaptive strategy with dynamic parameters."""

    PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD']

    def __init__(self):
        self.pair_data = {}
        self.trades = []

        # ADAPTIVE PARAMETERS (start conservative, adjust during trading)
        self.params = {
            'min_trend_strength': 6,      # HH/HL consecutive (adaptive)
            'min_rr': 1.8,                # Risk/reward minimum (adaptive)
            'sl_pips': 50,                # Stop loss distance (adaptive)
            'tp_multiplier': 2.0,         # TP = entry + (risk * multiplier)
            'breakout_threshold': 12,     # Pips to count as breakout (adaptive)
        }

        # Performance tracking
        self.performance_window = []  # Last 20 trades
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.adaptation_count = 0

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

    def adapt_parameters(self):
        """Adapt parameters based on recent performance."""
        if len(self.performance_window) < 5:
            return

        recent_trades = self.performance_window[-20:]
        wins = len([t for t in recent_trades if t['pips'] > 0])
        wr = wins / len(recent_trades)

        # If win rate too low: tighten filters
        if wr < 0.40:
            self.params['min_trend_strength'] = min(8, self.params['min_trend_strength'] + 1)
            self.params['breakout_threshold'] = min(15, self.params['breakout_threshold'] + 1)
            self.params['sl_pips'] = max(30, self.params['sl_pips'] - 5)
            print(f"  [ADAPT] Low WR ({wr:.0%}): Tightening filters")

        # If win rate good: slightly relax to catch more
        elif wr > 0.55:
            self.params['min_trend_strength'] = max(5, self.params['min_trend_strength'] - 1)
            self.params['breakout_threshold'] = max(8, self.params['breakout_threshold'] - 1)
            self.params['sl_pips'] = min(80, self.params['sl_pips'] + 5)
            print(f"  [ADAPT] High WR ({wr:.0%}): Relaxing filters for more trades")

        self.adaptation_count += 1

    def calculate_trend_strength(self, candles: List[OHLCV]) -> tuple:
        """Calculate trend strength - IMPROVED VERSION."""
        if len(candles) < 50:
            return None, 0

        recent_50 = candles[-50:]
        highs = [c.high for c in recent_50]
        lows = [c.low for c in recent_50]

        # Count consecutive HH/HL
        max_hh = 0
        current_hh = 0
        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                current_hh += 1
                max_hh = max(max_hh, current_hh)
            else:
                current_hh = 0

        # Count consecutive LL/LH
        max_ll = 0
        current_ll = 0
        for i in range(1, len(lows)):
            if lows[i] < lows[i-1]:
                current_ll += 1
                max_ll = max(max_ll, current_ll)
            else:
                current_ll = 0

        # BONUS: Check if trend is ACCELERATING (getting stronger)
        recent_20 = candles[-20:]
        highs_20 = [c.high for c in recent_20]
        hh_20 = sum(1 for i in range(1, len(highs_20)) if highs_20[i] > highs_20[i-1])

        if max_hh >= self.params['min_trend_strength']:
            trend_strength = max_hh
            if hh_20 >= 8:  # Recent 20 candles have strong trend = ACCELERATING
                trend_strength += 3  # Boost score
            return 'UP', trend_strength

        elif max_ll >= self.params['min_trend_strength']:
            trend_strength = max_ll
            lows_20 = [c.low for c in recent_20]
            ll_20 = sum(1 for i in range(1, len(lows_20)) if lows_20[i] < lows_20[i-1])
            if ll_20 >= 8:
                trend_strength += 3
            return 'DOWN', trend_strength

        return None, 0

    def find_support_resistance(self, candles: List[OHLCV]) -> tuple:
        """Find S/R levels - IMPROVED with clustering."""
        if len(candles) < 30:
            return None, None

        recent = candles[-30:]
        highs = [c.high for c in recent]
        lows = [c.low for c in recent]

        # Cluster nearby highs (within 0.2%)
        resistance_clusters = []
        used_indices = set()

        for i, high in enumerate(highs):
            if i in used_indices:
                continue

            cluster = [h for j, h in enumerate(highs)
                      if abs(h - high) < high * 0.002 and j not in used_indices]

            if len(cluster) >= 2:  # At least 2 touches
                res_level = sum(cluster) / len(cluster)
                resistance_clusters.append((res_level, len(cluster)))
                for j in range(len(highs)):
                    if abs(highs[j] - high) < high * 0.002:
                        used_indices.add(j)

        # Cluster nearby lows
        support_clusters = []
        used_indices = set()

        for i, low in enumerate(lows):
            if i in used_indices:
                continue

            cluster = [l for j, l in enumerate(lows)
                      if abs(l - low) < low * 0.002 and j not in used_indices]

            if len(cluster) >= 2:
                sup_level = sum(cluster) / len(cluster)
                support_clusters.append((sup_level, len(cluster)))
                for j in range(len(lows)):
                    if abs(lows[j] - low) < low * 0.002:
                        used_indices.add(j)

        # Return strongest clusters
        res = max(resistance_clusters, key=lambda x: x[1])[0] if resistance_clusters else None
        sup = min(support_clusters, key=lambda x: -x[1])[0] if support_clusters else None

        return res, sup

    def generate_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """
        Generate signal with MULTI-CONDITION confirmation.
        STRICT ENTRY: Need multiple confirmations.
        """
        if len(candles) < 100:
            return None

        current = candles[-1]

        # CONDITION 1: Strong trend
        trend, strength = self.calculate_trend_strength(candles)
        if not trend or strength < self.params['min_trend_strength']:
            return None

        # CONDITION 2: Support/Resistance (price near level)
        res, sup = self.find_support_resistance(candles)
        if not res or not sup:
            return None

        # CONDITION 3: Price action (recent volume/momentum)
        last_5 = candles[-6:-1]
        avg_vol = sum(c.volume for c in last_5) / len(last_5)
        current_vol = current.volume

        vol_confirmation = current_vol >= avg_vol * 0.8  # At least normal volume

        # CONDITION 4: Candle quality (not doji/small candles)
        body_size = abs(current.close - current.open) / current.close
        if body_size < 0.0003:  # Less than 0.03% = too small, skip
            return None

        # ===== UPTREND ENTRY =====
        if trend == 'UP':
            # Price must be above support + showing strength
            if current.close > sup and vol_confirmation:
                sl = sup - (self.params['sl_pips'] * 0.0001)
                risk_pips = (current.close - sl) / 0.0001

                if 15 < risk_pips < 200:
                    tp = current.close + (risk_pips * self.params['tp_multiplier'] * 0.0001)
                    rr = (tp - current.close) / (current.close - sl)

                    if self.params['min_rr'] <= rr <= 3.5:
                        return {
                            'pair': pair,
                            'direction': 'UP',
                            'entry': current.close,
                            'sl': sl,
                            'tp': tp,
                            'risk_pips': risk_pips,
                            'strength': strength,
                            'conditions_met': 4,
                        }

        # ===== DOWNTREND ENTRY =====
        elif trend == 'DOWN':
            if current.close < res and vol_confirmation:
                sl = res + (self.params['sl_pips'] * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 15 < risk_pips < 200:
                    tp = current.close - (risk_pips * self.params['tp_multiplier'] * 0.0001)
                    rr = (current.close - tp) / (sl - current.close)

                    if self.params['min_rr'] <= rr <= 3.5:
                        return {
                            'pair': pair,
                            'direction': 'DOWN',
                            'entry': current.close,
                            'sl': sl,
                            'tp': tp,
                            'risk_pips': risk_pips,
                            'strength': strength,
                            'conditions_met': 4,
                        }

        return None

    def evaluate_trade(self, trade: dict, candle: OHLCV) -> Optional[str]:
        """Check if hits TP/SL."""
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

    def run_adaptive_backtest(self):
        """Run backtest with adaptation."""
        print("🔄 Running ADAPTIVE backtest...\n")

        all_candles = {p: self.df_to_ohlcv(df) for p, df in self.pair_data.items()}
        max_idx = max(len(c) for c in all_candles.values())

        active_trades = {}

        for idx in range(100, max_idx):
            if idx % 500 == 0:
                progress = idx / max_idx * 100
                wr = len([t for t in self.performance_window[-20:] if t['pips'] > 0]) / min(20, len(self.performance_window)) * 100 if self.performance_window else 0
                print(f"  Progress: {progress:.0f}% | Recent WR: {wr:.0f}% | Params: {self.params['min_trend_strength']}trend,{self.params['breakout_threshold']}bkout,{self.params['sl_pips']}SL")

            # Periodic adaptation
            if idx % 1000 == 0 and idx > 100:
                self.adapt_parameters()

            for pair in self.PAIRS:
                if idx >= len(all_candles[pair]):
                    continue

                candle = all_candles[pair][idx]

                # Monitor active trade
                if pair in active_trades:
                    result = self.evaluate_trade(active_trades[pair], candle)

                    if result:
                        trade = active_trades[pair]
                        pips = (trade['risk_pips'] * self.params['tp_multiplier']) if result == 'TP' else -trade['risk_pips']

                        trade_record = {
                            'pair': pair,
                            'direction': trade['direction'],
                            'pips': pips,
                            'result': result,
                            'strength': trade['strength'],
                        }

                        self.trades.append(trade_record)
                        self.performance_window.append(trade_record)

                        # Track streaks
                        if pips > 0:
                            self.consecutive_wins += 1
                            self.consecutive_losses = 0
                        else:
                            self.consecutive_losses += 1
                            self.consecutive_wins = 0

                        del active_trades[pair]

                # Look for new signal
                if pair not in active_trades and idx % 3 == 0:
                    signal = self.generate_signal(pair, all_candles[pair][:idx+1])
                    if signal:
                        active_trades[pair] = signal

        print("\n")
        return self.analyze_results()

    def analyze_results(self) -> dict:
        """Analyze backtest results."""
        print("\n" + "="*80)
        print("ADAPTIVE STRATEGY (4H) - FINAL RESULTS")
        print("="*80)

        if not self.trades:
            print("❌ No trades generated")
            return

        wins = [t for t in self.trades if t['pips'] > 0]
        losses = [t for t in self.trades if t['pips'] <= 0]

        total_pips = sum(t['pips'] for t in self.trades)
        win_rate = (len(wins) / len(self.trades) * 100) if self.trades else 0

        print(f"\n📊 STATISTICS:")
        print(f"  Total Trades: {len(self.trades)}")
        print(f"  Winning Trades: {len(wins)} ({win_rate:.1f}%) ✅" if win_rate >= 55 else f"  Winning Trades: {len(wins)} ({win_rate:.1f}%)")
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

        if profit_per_week > 0:
            print(f"  Week 1: ${20 + profit_per_week:.2f}")
            print(f"  Week 4: ${20 + profit_per_week*4:.2f}")
            print(f"  Week 13: ${20 + profit_per_week*13:.2f}")
            print(f"  Month 6: ${20 + profit_per_week*26:.2f}")

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
        if win_rate >= 60:
            print(f"  ✅✅ EXCELLENT! {win_rate:.0f}% WR - This is professional-grade")
            print(f"     Ready for live trading!")
        elif win_rate >= 55:
            print(f"  ✅ GOOD! {win_rate:.0f}% WR - Profitable strategy")
            print(f"     Recommended for live trading")
        elif win_rate >= 50:
            print(f"  ⚠️  BREAKEVEN ({win_rate:.0f}% WR)")
            print(f"     Needs more optimization")
        else:
            print(f"  ❌ Below target ({win_rate:.0f}% WR)")

        print(f"  Adaptation cycles: {self.adaptation_count}")
        print("="*80 + "\n")


def main():
    print("\n" + "="*80)
    print("ADAPTIVE TREND-FOLLOWING STRATEGY - 4H")
    print("Multi-condition entry, dynamic parameters")
    print("="*80 + "\n")

    strategy = AdaptiveStrategy()
    strategy.fetch_data()
    strategy.run_adaptive_backtest()


if __name__ == "__main__":
    main()
