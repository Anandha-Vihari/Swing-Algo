#!/usr/bin/env python3
"""
MT5 BACKTESTER - Connect to your PC's MetaTrader 5
Requires: pip install MetaTrader5

Run this on your PC with MT5 installed for accurate backtesting.
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class MT5Backtest:
    """Connect to MT5 and run backtest."""

    PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD']

    def __init__(self):
        self.trades = []
        self.connected = False

    def connect(self):
        """Connect to MT5."""
        print("🔗 Connecting to MetaTrader 5...\n")

        if not mt5.initialize():
            print("❌ MT5 connection failed")
            print("Make sure:")
            print("  1. MetaTrader 5 is open")
            print("  2. Your broker account is connected")
            print("  3. No other EA is running")
            logger.error(mt5.last_error())
            return False

        self.connected = True
        account_info = mt5.account_info()
        print(f"✅ Connected to: {account_info.company}")
        print(f"   Account: {account_info.login}\n")
        return True

    def fetch_data(self, pair: str, timeframe=mt5.TIMEFRAME_H4, bars: int = 2000):
        """Fetch data from MT5."""
        print(f"📊 Fetching {pair} {bars} candles (4H)...")

        # Get rates
        rates = mt5.copy_rates_from_pos(pair, timeframe, 0, bars)

        if rates is None:
            logger.error(f"Failed to fetch {pair}")
            return None

        print(f"   ✅ Got {len(rates)} candles\n")
        return rates

    def backtest_pair(self, pair: str) -> Dict:
        """Backtest a single pair."""
        print(f"\n{'='*70}")
        print(f"BACKTESTING: {pair}")
        print(f"{'='*70}")

        # Fetch data
        rates = self.fetch_data(pair, bars=2000)
        if rates is None:
            return None

        # Convert to OHLCV format
        candles = []
        for rate in rates:
            candles.append({
                'open': rate['open'],
                'high': rate['high'],
                'low': rate['low'],
                'close': rate['close'],
                'volume': rate['tick_volume'],
                'time': datetime.fromtimestamp(rate['time']),
            })

        # Run backtest logic (same as Python)
        pair_trades = self._run_strategy(pair, candles)

        # Analyze
        if pair_trades:
            wins = len([t for t in pair_trades if t['pips'] > 0])
            wr = wins / len(pair_trades) * 100
            total_pips = sum(t['pips'] for t in pair_trades)

            print(f"\nRESULTS:")
            print(f"  Trades: {len(pair_trades)}")
            print(f"  Win Rate: {wr:.1f}%")
            print(f"  Total Pips: {total_pips:+.0f}")
            print(f"  Avg Pips/Trade: {total_pips/len(pair_trades):+.1f}")

            self.trades.extend(pair_trades)

            return {
                'pair': pair,
                'trades': len(pair_trades),
                'wr': wr,
                'pips': total_pips,
            }

        return None

    def _run_strategy(self, pair: str, candles: List[Dict]) -> List[Dict]:
        """Run strategy logic."""
        trades = []
        active_trade = None

        for i in range(100, len(candles)):
            current = candles[i]
            history = candles[:i+1]

            # Monitor active trade
            if active_trade:
                candle_high = current['high']
                candle_low = current['low']

                if active_trade['direction'] == 'UP':
                    if candle_high >= active_trade['tp']:
                        trade = {
                            'pair': pair,
                            'direction': 'UP',
                            'pips': active_trade['risk_pips'] * 2.0,
                            'result': 'TP',
                        }
                        trades.append(trade)
                        active_trade = None

                    elif candle_low <= active_trade['sl']:
                        trade = {
                            'pair': pair,
                            'direction': 'UP',
                            'pips': -active_trade['risk_pips'],
                            'result': 'SL',
                        }
                        trades.append(trade)
                        active_trade = None

            # Look for new signal
            if not active_trade:
                signal = self._generate_signal(pair, history)
                if signal:
                    active_trade = signal

        return trades

    def _generate_signal(self, pair: str, candles: List[Dict]) -> Dict:
        """Generate signal - SAME LOGIC AS PYTHON."""
        if len(candles) < 50:
            return None

        current = candles[-1]

        # Detect trend (last 50 candles)
        recent_50 = candles[-50:]
        highs = [c['high'] for c in recent_50]
        lows = [c['low'] for c in recent_50]

        max_hh = 0
        current_hh = 0
        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                current_hh += 1
                max_hh = max(max_hh, current_hh)
            else:
                current_hh = 0

        max_ll = 0
        current_ll = 0
        for i in range(1, len(lows)):
            if lows[i] < lows[i-1]:
                current_ll += 1
                max_ll = max(max_ll, current_ll)
            else:
                current_ll = 0

        trend = None
        if max_hh >= 6:
            trend = 'UP'
        elif max_ll >= 6:
            trend = 'DOWN'

        if not trend:
            return None

        # Find support/resistance
        res = max(h['high'] for h in candles[-30:])
        sup = min(l['low'] for l in candles[-30:])

        # Entry logic
        if trend == 'UP' and current['close'] > sup:
            sl = sup - (50 * 0.0001)
            risk_pips = (current['close'] - sl) / 0.0001

            if 15 < risk_pips < 200:
                tp = current['close'] + (risk_pips * 2.0 * 0.0001)

                return {
                    'direction': 'UP',
                    'entry': current['close'],
                    'sl': sl,
                    'tp': tp,
                    'risk_pips': risk_pips,
                }

        elif trend == 'DOWN' and current['close'] < res:
            sl = res + (50 * 0.0001)
            risk_pips = (sl - current['close']) / 0.0001

            if 15 < risk_pips < 200:
                tp = current['close'] - (risk_pips * 2.0 * 0.0001)

                return {
                    'direction': 'DOWN',
                    'entry': current['close'],
                    'sl': sl,
                    'tp': tp,
                    'risk_pips': risk_pips,
                }

        return None

    def run_full_backtest(self):
        """Run backtest for all pairs."""
        if not self.connected:
            return

        results = []

        for pair in self.PAIRS:
            result = self.backtest_pair(pair)
            if result:
                results.append(result)

        # Summary
        print(f"\n{'='*70}")
        print("BACKTEST SUMMARY")
        print(f"{'='*70}")

        total_trades = sum(r['trades'] for r in results)
        total_wins = sum(r['trades'] * r['wr'] / 100 for r in results)
        overall_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        total_pips = sum(r['pips'] for r in results)

        print(f"\nTotal Trades: {total_trades}")
        print(f"Overall Win Rate: {overall_wr:.1f}%")
        print(f"Total Pips: {total_pips:+.0f}")
        print(f"\nProfit Per Week: ${total_pips * 0.10 / 104:.2f}")
        print(f"$20 Account Projection (6 months): ${20 + (total_pips * 0.10 / 104 * 26):.2f}")

        if overall_wr >= 55:
            print(f"\n✅ PROFITABLE - Ready for live trading!")
        elif overall_wr >= 50:
            print(f"\n⚠️  BREAKEVEN - Needs tweaks")
        else:
            print(f"\n❌ LOSING - Needs optimization")

        print(f"{'='*70}\n")

    def disconnect(self):
        """Disconnect from MT5."""
        mt5.shutdown()
        print("Disconnected from MT5")


def main():
    print("\n" + "="*70)
    print("MT5 BACKTEST CONNECTOR - Run on Your PC")
    print("="*70 + "\n")

    backtester = MT5Backtest()

    if backtester.connect():
        backtester.run_full_backtest()
        backtester.disconnect()
    else:
        print("\n❌ Could not connect to MT5")
        print("Make sure MT5 is open and an account is connected")


if __name__ == "__main__":
    main()
