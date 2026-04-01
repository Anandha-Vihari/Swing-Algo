#!/usr/bin/env python3
"""
Full trade simulation backtest with P&L tracking.
Simulates actual trades from signals and calculates performance metrics.
"""

import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import pandas as pd

from strategy import StrategyEngine, SignalContext, TrendDirection
from data_handler import OHLCV
from config import BotConfig
from bot_data_pipeline import get_cached_data, validate_backtest_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class Trade:
    """Represents a completed trade."""

    def __init__(self, signal: SignalContext, entry_idx: int, signal_candle: OHLCV):
        self.signal = signal
        self.entry_idx = entry_idx
        self.entry_price = signal.entry_price
        self.stop_loss = signal.stop_loss
        self.take_profit = signal.take_profit
        self.direction = signal.direction
        self.entry_time = signal_candle.time
        self.entry_candle = signal_candle

        self.exit_idx: Optional[int] = None
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.exit_reason: Optional[str] = None  # "SL", "TP", "END"
        self.profit_loss: float = 0.0
        self.profit_loss_pips: float = 0.0
        self.profit_loss_percent: float = 0.0

    def update_exit(self, exit_price: float, exit_idx: int, exit_time: datetime, reason: str):
        """Mark trade as closed."""
        self.exit_price = exit_price
        self.exit_idx = exit_idx
        self.exit_time = exit_time
        self.exit_reason = reason

        # Calculate P&L
        if self.direction == TrendDirection.BULLISH:
            self.profit_loss_pips = (exit_price - self.entry_price) / 0.0001
            self.profit_loss = exit_price - self.entry_price
        else:  # BEARISH
            self.profit_loss_pips = (self.entry_price - exit_price) / 0.0001
            self.profit_loss = self.entry_price - exit_price

        # Assume 1 micro-lot (0.01 lots) = $1 per pip for majors
        self.profit_loss = self.profit_loss_pips * 1.0

        self.profit_loss_percent = (self.profit_loss / abs(self.entry_price * 0.01)) * 100

    def is_open(self) -> bool:
        return self.exit_price is None

    def days_open(self) -> float:
        if self.exit_time:
            delta = self.exit_time - self.entry_time
            return delta.total_seconds() / (24 * 3600)
        return 0.0

    def __repr__(self) -> str:
        direction = "LONG" if self.direction == TrendDirection.BULLISH else "SHORT"
        status = "OPEN" if self.is_open() else f"CLOSED({self.exit_reason})"
        return f"{direction} @ {self.entry_price:.5f} → {self.exit_price:.5f if self.exit_price else 'N/A'} ({self.profit_loss_pips:.0f}p) [{status}]"


class TradeSimulator:
    """Simulates trades from signals."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.account_balance = config.initial_capital
        self.trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.active_trade: Optional[Trade] = None

    def process_signal(self, signal: SignalContext, candle_idx: int, candle: OHLCV) -> Trade:
        """Enter a new trade from signal."""
        trade = Trade(signal, candle_idx, candle)
        self.active_trade = trade
        self.trades.append(trade)
        return trade

    def monitor_trade(self, candle_idx: int, candle: OHLCV) -> Optional[Trade]:
        """Check if active trade should be closed."""
        if not self.active_trade:
            return None

        trade = self.active_trade
        closed = False
        reason = None
        exit_price = None

        # Check SL/TP hits
        if trade.direction == TrendDirection.BULLISH:
            # Check SL first (more important)
            if candle.low <= trade.stop_loss:
                exit_price = trade.stop_loss
                reason = "SL"
                closed = True
            # Check TP
            elif candle.high >= trade.take_profit:
                exit_price = trade.take_profit
                reason = "TP"
                closed = True

        else:  # BEARISH
            if candle.high >= trade.stop_loss:
                exit_price = trade.stop_loss
                reason = "SL"
                closed = True
            elif candle.low <= trade.take_profit:
                exit_price = trade.take_profit
                reason = "TP"
                closed = True

        if closed:
            trade.update_exit(exit_price, candle_idx, candle.time, reason)
            self.active_trade = None
            self.closed_trades.append(trade)
            self.account_balance += trade.profit_loss
            return trade

        return None

    def get_stats(self) -> Dict:
        """Calculate backtest statistics."""
        stats = {
            'total_trades': len(self.closed_trades),
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'total_pips': 0.0,
            'avg_pips': 0.0,
            'largest_win_pips': 0.0,
            'largest_loss_pips': 0.0,
            'total_profit': 0.0,
            'avg_days_in_trade': 0.0,
            'max_drawdown': 0.0,
        }

        if len(self.closed_trades) == 0:
            return stats

        # Count wins/loses
        winners = [t for t in self.closed_trades if t.profit_loss_pips > 0]
        losers = [t for t in self.closed_trades if t.profit_loss_pips < 0]

        stats['winning_trades'] = len(winners)
        stats['losing_trades'] = len(losers)
        stats['win_rate'] = (len(winners) / len(self.closed_trades)) * 100

        # Pips
        stats['total_pips'] = sum(t.profit_loss_pips for t in self.closed_trades)
        stats['avg_pips'] = stats['total_pips'] / len(self.closed_trades)
        stats['largest_win_pips'] = max((t.profit_loss_pips for t in winners), default=0)
        stats['largest_loss_pips'] = min((t.profit_loss_pips for t in losers), default=0)

        # Profit factor
        gross_profit = sum(t.profit_loss for t in winners)
        gross_loss = abs(sum(t.profit_loss for t in losers))
        if gross_loss > 0:
            stats['profit_factor'] = gross_profit / gross_loss
        else:
            stats['profit_factor'] = float('inf') if gross_profit > 0 else 0.0

        stats['total_profit'] = sum(t.profit_loss for t in self.closed_trades)

        # Avg days
        stats['avg_days_in_trade'] = sum(t.days_open() for t in self.closed_trades) / len(self.closed_trades)

        return stats


def csv_to_ohlcv(df: pd.DataFrame) -> List[OHLCV]:
    """Convert DataFrame rows to OHLCV objects."""
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


def backtest_pair(pair: str, df: pd.DataFrame, config: BotConfig) -> Dict:
    """Run full trade simulation backtest."""
    logger.info(f"\n{'='*70}")
    logger.info(f"BACKTESTING {pair}")
    logger.info(f"{'='*70}")

    candles = csv_to_ohlcv(df)
    logger.info(f"Loaded {len(candles)} candles")

    strategy = StrategyEngine(config)
    simulator = TradeSimulator(config)

    lookback_buffer = 50

    # Main loop
    for i in range(lookback_buffer, len(candles)):
        current_candle = candles[i]

        # Monitor active trade
        if simulator.active_trade:
            closed_trade = simulator.monitor_trade(i, current_candle)
            if closed_trade:
                logger.debug(f"Trade closed: {closed_trade.exit_reason} @ {closed_trade.exit_price}")

        # Look for new signal only if no active trade
        if not simulator.active_trade and i % 2 == 0:  # Reduce signal checks
            history = candles[max(0, i-200):i+1]
            signal = strategy.analyze(pair, history)

            if signal:
                trade = simulator.process_signal(signal, i, current_candle)
                logger.debug(f"Signal: {signal.direction.name} @ {signal.entry_price}")

    # Close any remaining active trade at end
    if simulator.active_trade:
        last_candle = candles[-1]
        simulator.active_trade.update_exit(last_candle.close, len(candles)-1, last_candle.time, "END")
        simulator.closed_trades.append(simulator.active_trade)

    # Get stats
    stats = simulator.get_stats()

    # Print results
    print(f"\n{pair} RESULTS:")
    print(f"  Total Trades: {stats['total_trades']}")
    if stats['total_trades'] > 0:
        print(f"  Winning: {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
        print(f"  Losing: {stats['losing_trades']}")
        print(f"  Profit Factor: {stats['profit_factor']:.2f}")
        print(f"  Total Pips: {stats['total_pips']:+.0f}")
        print(f"  Avg Pips/Trade: {stats['avg_pips']:+.1f}")
        print(f"  Largest Win: {stats['largest_win_pips']:.0f}p ({stats['largest_win_pips']*1:.0f}$)")
        print(f"  Largest Loss: {stats['largest_loss_pips']:.0f}p ({stats['largest_loss_pips']*1:.0f}$)")
        print(f"  Total P&L: ${stats['total_profit']:+.2f}")
        print(f"  Avg Days/Trade: {stats['avg_days_in_trade']:.1f}")

    result = {
        'pair': pair,
        'stats': stats,
        'trades': simulator.closed_trades,
    }

    return result


def main():
    print("\n" + "="*80)
    print("FULL TRADE SIMULATION BACKTEST")
    print("="*80)

    # Load and validate
    logger.info("Loading cached CSV data...")
    pairs = ['EURUSD', 'GBPUSD', 'USDJPY']
    h4_data = get_cached_data(pairs)

    if not h4_data:
        logger.error("No cached data found")
        return 1

    logger.info("Validating data...")
    if not validate_backtest_data(h4_data):
        logger.error("Data validation failed")
        return 1

    # Run backtests
    config = BotConfig(initial_capital=10000)
    results = {}

    for pair, df in h4_data.items():
        result = backtest_pair(pair, df, config)
        results[pair] = result

    # Summary
    print("\n" + "="*80)
    print("BACKTEST SUMMARY")
    print("="*80)

    total_trades = 0
    total_pips = 0.0
    total_profit = 0.0
    total_wins = 0
    total_losses = 0

    for pair, result in results.items():
        s = result['stats']
        total_trades += s['total_trades']
        total_pips += s['total_pips']
        total_profit += s['total_profit']
        total_wins += s['winning_trades']
        total_losses += s['losing_trades']

    if total_trades > 0:
        overall_wr = (total_wins / total_trades) * 100
        print(f"\nCombined Results:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Win Rate: {overall_wr:.1f}%")
        print(f"  Total Pips: {total_pips:+.0f}")
        print(f"  Total P&L: ${total_profit:+.2f}")
        print(f"  Final Balance: ${config.initial_capital + total_profit:,.2f}")
    else:
        print("\nNo completed trades")

    print("="*80 + "\n")

    return 0 if total_trades > 0 else 1


if __name__ == "__main__":
    exit(main())
