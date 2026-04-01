#!/usr/bin/env python3
"""
STRATEGY DIAGNOSTIC - Why Swing Trading Fails
Deep analysis of:
- Pair-by-pair performance
- Entry quality (RR distribution)
- Trade outcome patterns (TP vs SL hit rate)
- Market conditions (trending vs ranging)
- Slippage impact
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from data_handler import OHLCV

class StrategyDiagnostics:
    """Diagnostic engine for swing trading strategy."""

    MAJOR_PAIRS = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'NZDUSD',
        'USDCHF', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY'
    ]

    def __init__(self, years_back: int = 2):
        self.years_back = years_back
        self.pair_data = {}
        self.all_trades = []
        self.diagnostics = {}

    def fetch_all_pairs(self):
        """Fetch 2 years of data."""
        print("📥 Fetching 2 years of 1H data...\n")

        for pair in self.MAJOR_PAIRS:
            try:
                ticker = f"{pair}=X"
                df = yf.download(ticker, period=f"{self.years_back*365}d", interval="1h", progress=False)

                if not df.empty:
                    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                    self.pair_data[pair] = df
                    logger.info(f"✅ {pair}: {len(df)} candles")

            except Exception as e:
                logger.warning(f"❌ {pair}: {str(e)[:50]}")

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

    def identify_swing(self, candles: List[OHLCV]) -> tuple:
        """Identify swings."""
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
        """Check trend."""
        if len(candles) < 5:
            return None

        recent_5 = candles[-6:-1]
        highs = [c.high for c in recent_5]
        lows = [c.low for c in recent_5]

        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        return 'LONG' if hh >= 2 else 'SHORT' if ll >= 2 else None

    def generate_signal(self, pair: str, candles: List[OHLCV]) -> Optional[dict]:
        """Generate signal with diagnostic info."""
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
                        'swing_high': upper,
                        'swing_low': lower,
                        'breakout_pips': breakout_pips,
                        'volatility': (current.high - current.low) / 0.0001,  # Current candle size
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
                        'swing_high': upper,
                        'swing_low': lower,
                        'breakout_pips': breakout_pips,
                        'volatility': (current.high - current.low) / 0.0001,
                    }

        return None

    def evaluate_trade(self, trade: dict, candle: OHLCV) -> Optional[dict]:
        """Check if trade hits SL or TP, with diagnostic info."""
        if trade['direction'] == 'LONG':
            if candle.high >= trade['tp']:
                return {'result': 'TP', 'exit_price': trade['tp']}
            elif candle.low <= trade['sl']:
                return {'result': 'SL', 'exit_price': trade['sl']}
        else:
            if candle.low <= trade['tp']:
                return {'result': 'TP', 'exit_price': trade['tp']}
            elif candle.high >= trade['sl']:
                return {'result': 'SL', 'exit_price': trade['sl']}

        return None

    def run_diagnostic_backtest(self):
        """Run backtest with full diagnostics."""
        print("🔍 Running diagnostic backtest...\n")

        pair_candles = {}
        for pair, df in self.pair_data.items():
            pair_candles[pair] = self.df_to_ohlcv(df)

        max_candles = max(len(candles) for candles in pair_candles.values())

        active_trades = {}
        lookback = 20

        for candle_idx in range(lookback, max_candles):
            if candle_idx % 5000 == 0:
                print(f"  Progress: {candle_idx/max_candles*100:.1f}%")

            for pair, candles in pair_candles.items():
                if candle_idx >= len(candles):
                    continue

                current_candle = candles[candle_idx]
                history = candles[:candle_idx + 1]

                # Monitor active trade
                if pair in active_trades:
                    trade = active_trades[pair]
                    evaluation = self.evaluate_trade(trade, current_candle)

                    if evaluation:
                        if evaluation['result'] == 'TP':
                            pips = trade['risk_pips'] * 1.5
                        else:
                            pips = -trade['risk_pips']

                        self.all_trades.append({
                            'pair': pair,
                            'direction': trade['direction'],
                            'entry': trade['entry'],
                            'exit': evaluation['exit_price'],
                            'pips': pips,
                            'result': evaluation['result'],
                            'risk_pips': trade['risk_pips'],
                            'breakout_pips': trade['breakout_pips'],
                            'volatility': trade['volatility'],
                            'swing_range': (trade['swing_high'] - trade['swing_low']) / 0.0001,
                            'date': current_candle.time,
                        })

                        del active_trades[pair]

                # Look for new signal
                if pair not in active_trades and candle_idx % 3 == 0:
                    signal = self.generate_signal(pair, history)
                    if signal:
                        active_trades[pair] = signal

        print("\n")
        return self.analyze_diagnostics()

    def analyze_diagnostics(self) -> dict:
        """Deep analysis of why strategy fails."""
        if not self.all_trades:
            return {}

        print("="*80)
        print("DIAGNOSTIC ANALYSIS")
        print("="*80)

        # ===== PAIR-BY-PAIR ANALYSIS =====
        print("\n1️⃣  PAIR-BY-PAIR PERFORMANCE")
        print("-" * 80)

        pair_stats = {}
        for trade in self.all_trades:
            pair = trade['pair']
            if pair not in pair_stats:
                pair_stats[pair] = {
                    'trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_pips': 0,
                    'tp_hit_rate': 0,
                    'sl_hit_rate': 0,
                    'tp_hits': 0,
                    'sl_hits': 0,
                }

            pair_stats[pair]['trades'] += 1
            pair_stats[pair]['total_pips'] += trade['pips']

            if trade['result'] == 'TP':
                pair_stats[pair]['wins'] += 1
                pair_stats[pair]['tp_hits'] += 1
            else:
                pair_stats[pair]['losses'] += 1
                pair_stats[pair]['sl_hits'] += 1

        print(f"{'Pair':<10} {'Trades':<8} {'Wins':<8} {'WR%':<8} {'Pips':<10} {'TP%':<8} {'SL%':<8}")
        print("-" * 80)

        for pair in sorted(pair_stats.keys(), key=lambda p: pair_stats[p]['total_pips'], reverse=True):
            data = pair_stats[pair]
            wr = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0
            tp_rate = (data['tp_hits'] / data['trades'] * 100) if data['trades'] > 0 else 0
            sl_rate = (data['sl_hits'] / data['trades'] * 100) if data['trades'] > 0 else 0

            profit_emoji = "✅" if data['total_pips'] > 0 else "❌"
            print(f"{pair:<10} {data['trades']:<8} {data['wins']:<8} {wr:<7.0f}% {data['total_pips']:>+8.0f}p {tp_rate:<7.0f}% {sl_rate:<7.0f}%  {profit_emoji}")

        # ===== TP vs SL HIT RATE =====
        print("\n\n2️⃣  WHY ARE WE LOSING?")
        print("-" * 80)

        tp_hits = sum(1 for t in self.all_trades if t['result'] == 'TP')
        sl_hits = sum(1 for t in self.all_trades if t['result'] == 'SL')
        total = len(self.all_trades)

        tp_rate = (tp_hits / total * 100) if total > 0 else 0
        sl_rate = (sl_hits / total * 100) if total > 0 else 0

        print(f"Trades hitting TP: {tp_hits}/{total} ({tp_rate:.1f}%)")
        print(f"Trades hitting SL: {sl_hits}/{total} ({sl_rate:.1f}%)")

        if tp_rate < 50:
            print(f"\n❌ PROBLEM FOUND: Only {tp_rate:.0f}% of trades reach TP")
            print(f"   This means SL is hit more often than TP")
            print(f"   → Entry point is TOO LATE (price already moved)")
            print(f"   → TP is TOO FAR (unrealistic in 1H timeframe)")
        else:
            print(f"\n✓ TP hit rate is good ({tp_rate:.1f}%)")

        # ===== BREAKOUT QUALITY =====
        print("\n\n3️⃣  ENTRY QUALITY ANALYSIS")
        print("-" * 80)

        avg_breakout = sum(t['breakout_pips'] for t in self.all_trades) / len(self.all_trades)
        avg_risk = sum(t['risk_pips'] for t in self.all_trades) / len(self.all_trades)
        avg_swing_range = sum(t['swing_range'] for t in self.all_trades) / len(self.all_trades)

        print(f"Avg breakout size: {avg_breakout:.1f}p")
        print(f"Avg risk per trade: {avg_risk:.1f}p")
        print(f"Avg swing range: {avg_swing_range:.1f}p")

        if avg_breakout < 5:
            print(f"\n❌ PROBLEM: Breakouts too small ({avg_breakout:.1f}p)")
            print(f"   Small breakouts often fail (false breaks)")
            print(f"   → Increase minimum breakout to 10+ pips")

        if avg_risk > 50:
            print(f"\n⚠️  WARNING: Average risk is large ({avg_risk:.1f}p)")
            print(f"   Big risks need big swings to justify")

        # ===== WIN TRADES vs LOSS TRADES =====
        print("\n\n4️⃣  TRADE ANALYSIS: WINNERS vs LOSERS")
        print("-" * 80)

        winners = [t for t in self.all_trades if t['result'] == 'TP']
        losers = [t for t in self.all_trades if t['result'] == 'SL']

        if winners:
            avg_win_breakout = sum(t['breakout_pips'] for t in winners) / len(winners)
            avg_win_volatility = sum(t['volatility'] for t in winners) / len(winners)
            print(f"Winning trades:")
            print(f"  Avg breakout: {avg_win_breakout:.1f}p (entry distance)")
            print(f"  Avg candle vol: {avg_win_volatility:.1f}p")

        if losers:
            avg_loss_breakout = sum(t['breakout_pips'] for t in losers) / len(losers)
            avg_loss_volatility = sum(t['volatility'] for t in losers) / len(losers)
            print(f"\nLosing trades:")
            print(f"  Avg breakout: {avg_loss_breakout:.1f}p (entry distance)")
            print(f"  Avg candle vol: {avg_loss_volatility:.1f}p")

        if winners and losers and avg_loss_breakout > avg_win_breakout:
            print(f"\n❌ KEY PROBLEM FOUND:")
            print(f"   Losing trades have LARGER breakouts ({avg_loss_breakout:.1f}p vs {avg_win_breakout:.1f}p)")
            print(f"   → We're entering TOO LATE in the move")
            print(f"   → By the time we enter, the swing is already partially complete")
            print(f"   → Price then pulls back and hits our SL")

        # ===== SLIPPAGE IMPACT =====
        print("\n\n5️⃣  SLIPPAGE & SPREAD IMPACT")
        print("-" * 80)

        backtest_tp_rate = tp_rate
        realistic_tp_rate = backtest_tp_rate - 8  # 2-3 pips slippage on entry/exit = ~10% hit rate loss

        print(f"Backtest TP rate: {backtest_tp_rate:.1f}%")
        print(f"With 2-3p slippage: ~{realistic_tp_rate:.1f}% (estimated)")

        if realistic_tp_rate < 50:
            print(f"\n❌ SLIPPAGE WILL KILL THIS STRATEGY")
            print(f"   Backtest: {backtest_tp_rate:.1f}% profitable")
            print(f"   Real world: ~{realistic_tp_rate:.1f}% (losing zone)")

        # ===== RECOMMENDATIONS =====
        print("\n\n6️⃣  ROOT CAUSES & FIXES")
        print("-" * 80)

        issues = []

        if tp_rate < 50:
            issues.append("1. LATE ENTRY - Entering after swing is already breaking")
            issues.append("   FIX: Enter BEFORE the break, not after (momentum entry too late)")

        if avg_breakout < 5:
            issues.append("2. FALSE BREAKS - Small breakouts often fail")
            issues.append("   FIX: Only trade breakouts of 10+ pips (higher quality)")

        if avg_risk > 50:
            issues.append("3. LARGE SL - 50+ pip stops are too big for 1H scalping")
            issues.append("   FIX: Reduce SL to 25-30 pips OR trade longer timeframe (4H)")

        if backtest_tp_rate - realistic_tp_rate > 5:
            issues.append("4. SLIPPAGE - Real trading will be 5-10% worse than backtest")
            issues.append("   FIX: Either accept smaller profits or use tighter TP")

        if not issues:
            issues.append("✅ Strategy appears sound in theory")
            issues.append("   But real-world execution differs from backtest")

        for issue in issues:
            print(issue)

        print("\n" + "="*80)

        return {
            'tp_rate': tp_rate,
            'pair_stats': pair_stats,
            'avg_breakout': avg_breakout,
            'avg_risk': avg_risk,
            'issues': issues,
        }


def main():
    print("\n" + "="*80)
    print("SWING TRADING STRATEGY - DIAGNOSTIC REPORT")
    print("="*80 + "\n")

    diag = StrategyDiagnostics(years_back=2)
    diag.fetch_all_pairs()
    results = diag.run_diagnostic_backtest()

    print("\n" + "="*80)
    print("END OF DIAGNOSTIC REPORT")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
