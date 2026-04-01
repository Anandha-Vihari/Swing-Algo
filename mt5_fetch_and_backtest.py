#!/usr/bin/env python3
"""
MT5 DATA FETCH + BACKTEST
Connects to local MT5, fetches real candle data, runs proven strategy backtest.

Usage:
  1. Open MetaTrader 5 on your PC
  2. Run: python mt5_fetch_and_backtest.py
  3. Watch results

Requires: pip install MetaTrader5
"""

import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Try to import MetaTrader5
try:
    import MetaTrader5 as mt5
    print("✅ MetaTrader5 module found\n")
except ImportError:
    print("❌ MetaTrader5 not installed")
    print("   Run: pip install MetaTrader5")
    print("   (Only works on Windows with MT5 installed)")
    sys.exit(1)


class MT5DataFetcher:
    """Fetch real candle data from MT5."""

    PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY']

    def __init__(self):
        self.connected = False
        self.account_info = None

    def connect(self):
        """Connect to MT5."""
        print("=" * 70)
        print("CONNECTING TO METATRADER 5")
        print("=" * 70 + "\n")

        if not mt5.initialize():
            print("❌ Failed to connect to MT5")
            print("   Make sure:")
            print("     • MetaTrader 5 is open")
            print("     • Your trading account is connected")
            print("     • No other app is accessing MT5")
            error = mt5.last_error()
            print(f"   Error: {error}\n")
            return False

        self.account_info = mt5.account_info()
        print(f"✅ Connected to MT5")
        print(f"   Broker: {self.account_info.company}")
        print(f"   Account: {self.account_info.login}")
        print(f"   Currency: {self.account_info.currency}\n")

        self.connected = True
        return True

    def fetch_candles(self, pair: str, timeframe=mt5.TIMEFRAME_H4, bars: int = 2000) -> Optional[List]:
        """Fetch candle data from MT5."""
        print(f"📥 Fetching {pair}...", end=" ", flush=True)

        # Fetch from MT5
        rates = mt5.copy_rates_from_pos(pair, timeframe, 0, bars)

        if rates is None or len(rates) == 0:
            print(f"❌ No data")
            return None

        print(f"✅ {len(rates)} candles\n")
        return rates

    def rates_to_dicts(self, rates) -> List[Dict]:
        """Convert MT5 rates to dict format for strategy."""
        return [
            {
                'time': datetime.fromtimestamp(r['time']),
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'close': r['close'],
                'volume': r['tick_volume'],
            }
            for r in rates
        ]

    def disconnect(self):
        """Disconnect from MT5."""
        mt5.shutdown()
        print("\n✅ Disconnected from MT5")


class StrategyBacktester:
    """Run proven swing breakout strategy backtest."""

    def __init__(self):
        self.trades = []
        self.pair_results = {}

    def backtest(self, pair: str, candles: List[Dict]) -> Dict:
        """Run backtest for a pair."""
        print(f"\n{'='*70}")
        print(f"BACKTEST: {pair} (4H)")
        print(f"{'='*70}")
        print(f"Candles: {len(candles)} | Period: {candles[0]['time'].date()} to {candles[-1]['time'].date()}\n")

        trades = []
        active_trade = None

        for i in range(100, len(candles)):
            current = candles[i]

            # Monitor active trade
            if active_trade:
                if active_trade['direction'] == 'UP':
                    if current['high'] >= active_trade['tp']:
                        trades.append({
                            'pair': pair,
                            'direction': 'UP',
                            'result': 'TP',
                            'entry': active_trade['entry'],
                            'exit': active_trade['tp'],
                            'pips': active_trade['risk_pips'] * 2.0,
                            'time': current['time'],
                        })
                        active_trade = None
                    elif current['low'] <= active_trade['sl']:
                        trades.append({
                            'pair': pair,
                            'direction': 'UP',
                            'result': 'SL',
                            'entry': active_trade['entry'],
                            'exit': active_trade['sl'],
                            'pips': -active_trade['risk_pips'],
                            'time': current['time'],
                        })
                        active_trade = None

                elif active_trade['direction'] == 'DOWN':
                    if current['low'] <= active_trade['tp']:
                        trades.append({
                            'pair': pair,
                            'direction': 'DOWN',
                            'result': 'TP',
                            'entry': active_trade['entry'],
                            'exit': active_trade['tp'],
                            'pips': active_trade['risk_pips'] * 2.0,
                            'time': current['time'],
                        })
                        active_trade = None
                    elif current['high'] >= active_trade['sl']:
                        trades.append({
                            'pair': pair,
                            'direction': 'DOWN',
                            'result': 'SL',
                            'entry': active_trade['entry'],
                            'exit': active_trade['sl'],
                            'pips': -active_trade['risk_pips'],
                            'time': current['time'],
                        })
                        active_trade = None

            # Look for new signal
            if not active_trade:
                signal = self._generate_signal(pair, candles[:i+1], current)
                if signal:
                    active_trade = signal

        # Calculate stats
        if trades:
            self.trades.extend(trades)
            wins = len([t for t in trades if t['pips'] > 0])
            total_pips = sum(t['pips'] for t in trades)
            pf = sum(t['pips'] for t in trades if t['pips'] > 0) / abs(sum(t['pips'] for t in trades if t['pips'] < 0)) if any(t['pips'] < 0 for t in trades) else 0

            wr = wins / len(trades) * 100

            print(f"📊 RESULTS:")
            print(f"   Trades: {len(trades)}")
            print(f"   Wins: {wins} | Losses: {len(trades)-wins}")
            print(f"   Win Rate: {wr:.1f}%")
            print(f"   Profit Factor: {pf:.2f}")
            print(f"   Total Pips: {total_pips:+.0f}")
            print(f"   Avg Pips/Trade: {total_pips/len(trades):+.1f}\n")

            result = {
                'pair': pair,
                'trades': len(trades),
                'wins': wins,
                'wr': wr,
                'pips': total_pips,
                'pf': pf,
            }

            self.pair_results[pair] = result
            return result
        else:
            print(f"⚠️  No trades generated\n")
            return None

    def _generate_signal(self, pair: str, candles: List[Dict], current: Dict) -> Optional[Dict]:
        """Generate signal using proven strategy logic."""
        if len(candles) < 50:
            return None

        # Trend detection (last 50 candles)
        recent_50 = candles[-50:]
        highs = [c['high'] for c in recent_50]
        lows = [c['low'] for c in recent_50]

        # Count consecutive HH
        max_hh = 0
        current_hh = 0
        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                current_hh += 1
                max_hh = max(max_hh, current_hh)
            else:
                current_hh = 0

        # Count consecutive LL
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
        else:
            return None

        # Find swings in last 40 candles
        recent_40 = candles[-40:]
        upper_swings = []
        lower_swings = []

        for i in range(1, len(recent_40) - 1):
            if recent_40[i]['high'] > recent_40[i-1]['high'] and recent_40[i]['high'] > recent_40[i+1]['high']:
                upper_swings.append(recent_40[i]['high'])
            if recent_40[i]['low'] < recent_40[i-1]['low'] and recent_40[i]['low'] < recent_40[i+1]['low']:
                lower_swings.append(recent_40[i]['low'])

        if not upper_swings or not lower_swings:
            return None

        sup = min(lower_swings)
        res = max(upper_swings)

        # Breakout thresholds
        breakout_thresh = 8 if "JPY" in pair else 12

        # LONG signal
        if trend == 'UP' and current['close'] > res:
            breakout_pips = (current['close'] - res) / 0.0001
            if breakout_pips >= breakout_thresh:
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

        # SHORT signal
        elif trend == 'DOWN' and current['close'] < sup:
            breakout_pips = (sup - current['close']) / 0.0001
            if breakout_pips >= breakout_thresh:
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

    def print_summary(self):
        """Print backtest summary."""
        if not self.trades:
            print("❌ No trades generated across all pairs")
            return

        print("\n" + "=" * 70)
        print("BACKTEST SUMMARY - ALL PAIRS")
        print("=" * 70 + "\n")

        total_trades = len(self.trades)
        wins = len([t for t in self.trades if t['pips'] > 0])
        total_pips = sum(t['pips'] for t in self.trades)

        win_pips = sum(t['pips'] for t in self.trades if t['pips'] > 0)
        loss_pips = sum(t['pips'] for t in self.trades if t['pips'] < 0)

        pf = win_pips / abs(loss_pips) if loss_pips != 0 else 0
        wr = wins / total_trades * 100

        print(f"Total Trades: {total_trades}")
        print(f"Wins: {wins} | Losses: {total_trades-wins}")
        print(f"Win Rate: {wr:.1f}%")
        print(f"Profit Factor: {pf:.2f}")
        print(f"Total Pips: {total_pips:+.0f}\n")

        # Per-pair breakdown
        print("Per Pair:")
        for pair, result in sorted(self.pair_results.items()):
            print(f"  {pair}: {result['trades']} trades, {result['wr']:.1f}% WR, {result['pips']:+.0f}p (PF: {result['pf']:.2f})")

        # Money projections
        weekly_pips = total_pips / 104  # ~2 years = 104 weeks
        weekly_profit = weekly_pips * 0.10  # 0.10 per pip per micro-lot

        print(f"\n💰 PROJECTIONS ($20 account):")
        print(f"   Weekly: {weekly_profit:+.2f}$")
        print(f"   6 months: ${20 + (weekly_profit * 26):+.2f}")
        print(f"   12 months: ${20 + (weekly_profit * 52):+.2f}\n")

        # Status
        if wr >= 55:
            status = "✅ EXCELLENT - Ready for live trading!"
        elif wr >= 50:
            status = "✅ PROFITABLE - Good to trade"
        elif wr >= 45:
            status = "⚠️  MARGINAL - Needs optimization"
        else:
            status = "❌ LOSING - Needs improvement"

        print(f"Status: {status}\n")
        print("=" * 70 + "\n")


def main():
    """Main execution."""
    print("\n" + "=" * 70)
    print("MT5 FETCH + BACKTEST - PROVE ON REAL BROKER DATA")
    print("=" * 70 + "\n")

    # Connect to MT5
    fetcher = MT5DataFetcher()
    if not fetcher.connect():
        return

    # Fetch and backtest
    backtester = StrategyBacktester()

    for pair in fetcher.PAIRS:
        rates = fetcher.fetch_candles(pair, bars=2000)
        if rates:
            candles = fetcher.rates_to_dicts(rates)
            backtester.backtest(pair, candles)

    # Summary
    backtester.print_summary()

    # Disconnect
    fetcher.disconnect()


if __name__ == "__main__":
    main()
