#!/usr/bin/env python3
"""
1H BACKTEST - Test if 65% win rate is achievable
"""

import pandas as pd
import yfinance as yf
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from strategy import StrategyEngine, TrendDirection
from data_handler import OHLCV
from config import BotConfig

class BacktestH1:
    """1H backtest engine for aggressive scalping."""

    def __init__(self, pair: str, days_back: int = 60):
        self.pair = pair
        self.days_back = days_back
        self.trades = []
        self.results = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_pips': 0.0,
            'avg_pips_win': 0.0,
            'avg_pips_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'profit_factor': 0.0,
        }

    def fetch_1h_data(self) -> pd.DataFrame:
        """Fetch 1H data from yfinance."""
        ticker = f"{self.pair}=X"
        logger.info(f"Fetching {self.pair} 1H data ({self.days_back} days)...")

        df = yf.download(ticker, period=f"{self.days_back}d", interval="1h", progress=False)

        if df.empty:
            logger.error(f"No data for {self.pair}")
            return None

        logger.info(f"Downloaded {len(df)} candles")
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        return df

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

    def identify_1h_swing(self, candles: List[OHLCV]) -> tuple:
        """Identify swings on 1H (faster detection than 4H)."""
        if len(candles) < 10:
            return None, None

        # Use last 15 candles for 1H swing ID (tighter than 4H)
        recent = candles[-15:]

        upper_swings = []
        lower_swings = []

        for i in range(1, len(recent) - 1):
            if recent[i].high > recent[i-1].high and recent[i].high > recent[i+1].high:
                upper_swings.append({'idx': i, 'high': recent[i].high})

            if recent[i].low < recent[i-1].low and recent[i].low < recent[i+1].low:
                lower_swings.append({'idx': i, 'low': recent[i].low})

        upper = upper_swings[-1] if upper_swings else None
        lower = lower_swings[-1] if lower_swings else None

        return upper, lower

    def check_trend(self, candles: List[OHLCV]) -> tuple:
        """Check trend on 1H (3 candles instead of 20)."""
        if len(candles) < 5:
            return None, False

        recent_5 = candles[-6:-1]
        highs = [c.high for c in recent_5]
        lows = [c.low for c in recent_5]

        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        if hh >= 2:
            return TrendDirection.BULLISH, True
        elif ll >= 2:
            return TrendDirection.BEARISH, True
        else:
            return None, False

    def generate_signal(self, candles: List[OHLCV]) -> Optional[dict]:
        """Generate 1H scalp signal."""
        if len(candles) < 20:
            return None

        current = candles[-1]
        trend, has_trend = self.check_trend(candles)

        if not has_trend:
            return None

        upper, lower = self.identify_1h_swing(candles)

        if not upper or not lower:
            return None

        # LONG: breakout above swing high
        if trend == TrendDirection.BULLISH and current.close > upper['high']:
            breakout_pips = (current.close - upper['high']) / 0.0001

            if breakout_pips >= 3:  # 3+ pips breakout on 1H
                sl = lower['low'] - (20 * 0.0001)  # 20 pip SL
                risk_pips = (current.close - sl) / 0.0001

                if 10 < risk_pips < 100:  # Reasonable risk
                    tp = current.close + (risk_pips * 1.5 * 0.0001)

                    return {
                        'direction': 'LONG',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                        'entry_idx': len(candles) - 1,
                    }

        # SHORT: breakout below swing low
        elif trend == TrendDirection.BEARISH and current.close < lower['low']:
            breakout_pips = (lower['low'] - current.close) / 0.0001

            if breakout_pips >= 3:
                sl = upper['high'] + (20 * 0.0001)
                risk_pips = (sl - current.close) / 0.0001

                if 10 < risk_pips < 100:
                    tp = current.close - (risk_pips * 1.5 * 0.0001)

                    return {
                        'direction': 'SHORT',
                        'entry': current.close,
                        'sl': sl,
                        'tp': tp,
                        'risk_pips': risk_pips,
                        'entry_idx': len(candles) - 1,
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

    def run_backtest(self) -> dict:
        """Run full 1H backtest."""
        df = self.fetch_1h_data()
        if df is None:
            return self.results

        candles = self.df_to_ohlcv(df)
        logger.info(f"Processing {len(candles)} candles...")

        active_trade = None
        lookback_buffer = 20

        for i in range(lookback_buffer, len(candles)):
            current_candle = candles[i]
            history = candles[:i+1]

            # Monitor active trade
            if active_trade:
                result = self.evaluate_trade(active_trade, current_candle)

                if result:
                    # Trade closed
                    if result == 'TP':
                        pips = active_trade['risk_pips'] * 1.5
                    else:  # SL
                        pips = -active_trade['risk_pips']

                    self.trades.append({
                        'entry_idx': active_trade['entry_idx'],
                        'exit_idx': i,
                        'direction': active_trade['direction'],
                        'pips': pips,
                        'result': result,
                    })

                    active_trade = None

            # Look for new signal (only if no active trade)
            if not active_trade and i % 2 == 0:  # Check every 2nd candle
                signal = self.generate_signal(history)

                if signal:
                    active_trade = signal

        # Calculate stats
        if not self.trades:
            logger.warning(f"No completed trades for {self.pair}")
            return self.results

        self.results['total_trades'] = len(self.trades)

        wins = [t for t in self.trades if t['pips'] > 0]
        losses = [t for t in self.trades if t['pips'] <= 0]

        self.results['wins'] = len(wins)
        self.results['losses'] = len(losses)
        self.results['win_rate'] = (len(wins) / len(self.trades)) * 100

        win_pips = [t['pips'] for t in wins]
        loss_pips = [t['pips'] for t in losses]

        self.results['total_pips'] = sum([t['pips'] for t in self.trades])
        self.results['avg_pips_win'] = sum(win_pips) / len(win_pips) if win_pips else 0
        self.results['avg_pips_loss'] = sum(loss_pips) / len(loss_pips) if loss_pips else 0
        self.results['largest_win'] = max(win_pips) if win_pips else 0
        self.results['largest_loss'] = min(loss_pips) if loss_pips else 0

        gross_profit_pips = sum(win_pips)
        gross_loss_pips = abs(sum(loss_pips))

        if gross_loss_pips > 0:
            self.results['profit_factor'] = gross_profit_pips / gross_loss_pips
        else:
            self.results['profit_factor'] = float('inf') if gross_profit_pips > 0 else 0

        return self.results


def main():
    print("\n" + "="*80)
    print("1H BACKTEST - CAN WE GET 65% WIN RATE?")
    print("="*80)

    pairs = ['EURUSD', 'GBPUSD', 'USDJPY']
    all_results = {}

    for pair in pairs:
        print(f"\n📊 Testing {pair}...")
        backtester = BacktestH1(pair, days_back=60)
        result = backtester.run_backtest()
        all_results[pair] = result

        if result['total_trades'] > 0:
            print(f"  Total Trades: {result['total_trades']}")
            print(f"  Wins: {result['wins']} ({result['win_rate']:.1f}%)")
            print(f"  Losses: {result['losses']}")
            print(f"  Total Pips: {result['total_pips']:+.0f}")
            print(f"  Avg Win: {result['avg_pips_win']:+.1f}p")
            print(f"  Avg Loss: {result['avg_pips_loss']:+.1f}p")
            print(f"  Profit Factor: {result['profit_factor']:.2f}")
            print(f"  Status: {'✅ GOOD (+65% target!)' if result['win_rate'] >= 65 else '⚠️ Below 65% target'}")
        else:
            print(f"  ❌ No trades generated")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_trades = sum(r['total_trades'] for r in all_results.values())
    total_wins = sum(r['wins'] for r in all_results.values())
    total_pips = sum(r['total_pips'] for r in all_results.values())

    if total_trades > 0:
        overall_wr = (total_wins / total_trades) * 100
        print(f"\nCombined Results:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Win Rate: {overall_wr:.1f}%")
        print(f"  Total Pips: {total_pips:+.0f}")

        print(f"\n{'='*80}")
        if overall_wr >= 65:
            print(f"✅ WIN RATE {overall_wr:.1f}% >= 65% TARGET")
            print(f"   The $20→$200 in 15 days system is CONFIRMED! 🚀")
        elif overall_wr >= 55:
            print(f"⚠️  WIN RATE {overall_wr:.1f}% - PARTIAL SUCCESS")
            print(f"   You can profit, but not at 65% rate. Expect slower growth.")
        else:
            print(f"❌ WIN RATE {overall_wr:.1f}% - BELOW BREAKEVEN")
            print(f"   This strategy does NOT work for 1H scalping.")
        print(f"{'='*80}")

        # P&L calculation
        print(f"\nProjected Daily P&L ($3 risk per trade):")
        pips_per_trade = total_pips / total_trades
        dollars_per_pip = 0.10  # Micro-lot
        daily_profit_estimate = pips_per_trade * dollars_per_pip * 5  # 5 trades/day
        print(f"  Avg pips/trade: {pips_per_trade:+.1f}p")
        print(f"  5 trades/day: {daily_profit_estimate:+.1f}$ per day")
        print(f"  15 days: {daily_profit_estimate * 15:+.1f}$ total")
        print(f"  Target: $200")
        print(f"  Verdict: {'✅ FEASIBLE' if daily_profit_estimate * 15 >= 180 else '❌ NOT FEASIBLE'}")
    else:
        print("❌ No trades generated across all pairs")
        print("   Strategy needs adjustment for 1H timeframe")

    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
