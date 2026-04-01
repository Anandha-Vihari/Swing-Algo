#!/usr/bin/env python3
"""
Aggressive position sizing backtest for $20 account.
Targets $2-5/day by risking $2.50 per trade.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

from strategy import StrategyEngine, SignalContext, TrendDirection
from data_handler import OHLCV
from config import BotConfig
from bot_data_pipeline import get_cached_data
from aggressive_config import (
    RISK_PER_TRADE, ACCOUNT_SIZE, DAILY_TARGET, MAX_DAILY_TRADES,
    BREAKOUT_PIPS, calculate_position_size, DailySession
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class AggressiveTradeSimulator:
    """Aggressive simulator with $2.50 risk per trade."""

    def __init__(self):
        self.account_balance = ACCOUNT_SIZE
        self.trades: List[Dict] = []
        self.daily_sessions: List[DailySession] = []
        self.current_session: Optional[DailySession] = None
        self.current_date = None

    def process_candle(self, pair: str, candle_idx: int, candle: OHLCV):
        """Check for session rollover."""
        candle_date = candle.time.date() if hasattr(candle.time, 'date') else str(candle.time)[:10]

        if candle_date != self.current_date:
            # New day
            if self.current_session:
                self.daily_sessions.append(self.current_session)

            self.current_date = candle_date
            self.current_session = DailySession(str(candle_date))
            self.current_session.starting_balance = self.account_balance

    def can_take_trade(self) -> bool:
        """Check if we can take another trade today."""
        if not self.current_session:
            return False
        return self.current_session.trades_taken < MAX_DAILY_TRADES

    def enter_trade(self, pair: str, signal: SignalContext, candle: OHLCV) -> Dict:
        """Enter a trade with aggressive position sizing."""
        if not self.can_take_trade():
            return None

        # Calculate position size
        micro_lots = calculate_position_size(
            self.account_balance,
            RISK_PER_TRADE,
            signal.entry_price,
            signal.stop_loss,
            pip_value=0.0001
        )

        if micro_lots <= 0:
            return None

        return {
            'pair': pair,
            'direction': signal.direction,
            'entry_price': signal.entry_price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'entry_time': candle.time,
            'micro_lots': micro_lots,
            'risk_amount': RISK_PER_TRADE,
        }

    def evaluate_trade(self, trade: Dict, current_candle: OHLCV) -> Optional[Dict]:
        """Check if trade hit SL or TP."""
        if trade['direction'] == TrendDirection.BULLISH:
            # Check TP first (take profits are priority)
            if current_candle.high >= trade['take_profit']:
                exit_price = trade['take_profit']
                profit = RISK_PER_TRADE * 2.0  # 2:1 RR
                return {
                    'exit_price': exit_price,
                    'profit': profit,
                    'status': 'TP',
                }
            # Check SL
            elif current_candle.low <= trade['stop_loss']:
                exit_price = trade['stop_loss']
                profit = -RISK_PER_TRADE
                return {
                    'exit_price': exit_price,
                    'profit': profit,
                    'status': 'SL',
                }

        else:  # BEARISH
            if current_candle.low <= trade['take_profit']:
                exit_price = trade['take_profit']
                profit = RISK_PER_TRADE * 2.0
                return {
                    'exit_price': exit_price,
                    'profit': profit,
                    'status': 'TP',
                }
            elif current_candle.high >= trade['stop_loss']:
                exit_price = trade['stop_loss']
                profit = -RISK_PER_TRADE
                return {
                    'exit_price': exit_price,
                    'profit': profit,
                    'status': 'SL',
                }

        return None

    def get_daily_stats(self) -> Dict:
        """Get overall daily statistics."""
        if not self.daily_sessions:
            return {}

        total_days = len(self.daily_sessions)
        profitable_days = sum(1 for d in self.daily_sessions if d.daily_profit > 0)
        total_profit = sum(d.daily_profit for d in self.daily_sessions)
        target_hit_days = sum(1 for d in self.daily_sessions if d.daily_profit >= DAILY_TARGET)

        daily_profits = [d.daily_profit for d in self.daily_sessions if d.daily_profit != 0]
        avg_daily_profit = sum(daily_profits) / len(daily_profits) if daily_profits else 0

        return {
            'total_days': total_days,
            'profitable_days': profitable_days,
            'profit_rate': (profitable_days / total_days) * 100 if total_days > 0 else 0,
            'target_hit_days': target_hit_days,
            'total_profit': total_profit,
            'avg_daily_profit': avg_daily_profit,
            'final_balance': self.account_balance,
            'roi': (total_profit / ACCOUNT_SIZE) * 100,
        }


def csv_to_ohlcv(df: pd.DataFrame) -> List[OHLCV]:
    """Convert DataFrame to OHLCV objects."""
    ohlcv_list = []
    for idx, row in df.iterrows():
        candle = OHLCV(
            open_=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume']),
            time=idx
        )
        ohlcv_list.append(candle)
    return ohlcv_list


def backtest_aggressive(pair: str, df: pd.DataFrame) -> Dict:
    """Run aggressive backtest on a pair."""
    logger.info(f"\nBacktesting {pair} (AGGRESSIVE)...")

    candles = csv_to_ohlcv(df)
    strategy = StrategyEngine(BotConfig())
    simulator = AggressiveTradeSimulator()

    active_trades = []  # List of active trades
    lookback = 50

    for i in range(lookback, len(candles)):
        current_candle = candles[i]

        # Check session date
        simulator.process_candle(pair, i, current_candle)

        # Monitor active trades
        closed_trades = []
        for trade in active_trades:
            result = simulator.evaluate_trade(trade, current_candle)
            if result:
                # Close trade
                simulator.current_session.add_trade(
                    pair,
                    trade['direction'].name,
                    trade['entry_price'],
                    trade['stop_loss'],
                    trade['take_profit'],
                    result['exit_price'],
                    result['profit']
                )
                simulator.account_balance += result['profit']
                closed_trades.append(trade)

        for trade in closed_trades:
            active_trades.remove(trade)

        # Look for new signals
        if simulator.can_take_trade() and i % 2 == 0:  # Check every 2 candles
            history = candles[max(0, i-200):i+1]
            signal = strategy.analyze(pair, history)

            if signal:
                # Check breakout threshold for this pair
                pair_breakout = BREAKOUT_PIPS.get(pair, 12)
                if pair == 'EURUSD' or pair == 'GBPUSD':
                    breakout_pips = abs(signal.entry_price - signal.stop_loss) / 0.0001
                else:  # JPY
                    breakout_pips = abs(signal.entry_price - signal.stop_loss) / 0.0001

                # Only enter on quality setups
                if signal.risk_reward >= 1.8:
                    trade = simulator.enter_trade(pair, signal, current_candle)
                    if trade:
                        active_trades.append(trade)
                        logger.debug(f"Entered {signal.direction.name} @ {signal.entry_price}")

    # Close remaining trades at end
    if active_trades:
        last_candle = candles[-1]
        for trade in active_trades:
            result = simulator.evaluate_trade(trade, last_candle)
            if result:
                simulator.current_session.add_trade(
                    pair,
                    trade['direction'].name,
                    trade['entry_price'],
                    trade['stop_loss'],
                    trade['take_profit'],
                    result['exit_price'],
                    result['profit']
                )
                simulator.account_balance += result['profit']

    # Save final session
    if simulator.current_session and simulator.current_session.trades_taken > 0:
        simulator.daily_sessions.append(simulator.current_session)

    return {
        'pair': pair,
        'simulator': simulator,
        'stats': simulator.get_daily_stats(),
    }


def main():
    print("\n" + "="*70)
    print("AGGRESSIVE BACKTEST: $20 Account, Target $2-5/day")
    print("="*70)

    # Load data
    logger.info("Loading data...")
    pairs = ['EURUSD', 'GBPUSD']
    h4_data = get_cached_data(pairs)

    results = {}
    for pair, df in h4_data.items():
        result = backtest_aggressive(pair, df)
        results[pair] = result

    # Print results
    print("\n" + "="*70)
    print("AGGRESSIVE BACKTEST RESULTS")
    print("="*70)

    combined_stats = {
        'total_days': 0,
        'profitable_days': 0,
        'target_hit_days': 0,
        'total_profit': 0.0,
    }

    for pair, result in results.items():
        s = result['stats']
        if s:
            print(f"\n{pair}:")
            print(f"  Trading Days: {s['total_days']}")
            print(f"  Profitable Days: {s['profitable_days']} ({s['profit_rate']:.1f}%)")
            print(f"  Days Hit Target (>${DAILY_TARGET}): {s['target_hit_days']}")
            print(f"  Total Profit: ${s['total_profit']:+.2f}")
            print(f"  Avg Daily Profit: ${s['avg_daily_profit']:+.2f}")
            print(f"  Final Balance: ${s['final_balance']:+.2f}")
            print(f"  ROI: {s['roi']:+.1f}%")

            combined_stats['total_days'] += s['total_days']
            combined_stats['profitable_days'] += s['profitable_days']
            combined_stats['target_hit_days'] += s['target_hit_days']
            combined_stats['total_profit'] += s['total_profit']

    # Overall summary
    if combined_stats['total_days'] > 0:
        print(f"\n{'='*70}")
        print("COMBINED RESULTS")
        print(f"{'='*70}")
        print(f"Total Trading Days: {combined_stats['total_days']}")
        print(f"Profitable Days: {combined_stats['profitable_days']} ({combined_stats['profitable_days']/combined_stats['total_days']*100:.1f}%)")
        print(f"Days Hit Target: {combined_stats['target_hit_days']} ({combined_stats['target_hit_days']/combined_stats['total_days']*100:.1f}%)")
        print(f"Total Profit: ${combined_stats['total_profit']:+.2f}")
        print(f"Final Balance: ${ACCOUNT_SIZE + combined_stats['total_profit']:+.2f}")
        print(f"{'='*70}\n")

    return 0 if combined_stats['total_profit'] > 0 else 1


if __name__ == "__main__":
    exit(main())
