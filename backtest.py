"""
Backtesting module for historical performance evaluation.
Runs the strategy on historical data and calculates performance metrics.
"""

import logging
from typing import List, Dict, Tuple
from datetime import datetime
import pandas as pd

from config import BotConfig, TimeFrame
from data_handler import DataHandler, OHLCV
from strategy import StrategyEngine, SignalContext
from risk_manager import RiskManager, Trade
from execution import ExecutionEngine

logger = logging.getLogger(__name__)


class BacktestResult:
    """Container for backtest results."""

    def __init__(self):
        self.trades: List[Trade] = []
        self.initial_capital: float = 0.0
        self.final_capital: float = 0.0
        self.total_return_percent: float = 0.0
        self.net_profit: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.win_rate: float = 0.0
        self.profit_factor: float = 0.0
        self.max_drawdown: float = 0.0
        self.largest_win: float = 0.0
        self.largest_loss: float = 0.0
        self.avg_win: float = 0.0
        self.avg_loss: float = 0.0
        self.avg_bars_in_trade: float = 0.0
        self.backtest_period: Tuple[datetime, datetime] = (None, None)
        self.equity_curve: List[float] = []

    def print_summary(self):
        """Print formatted backtest summary."""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Period: {self.backtest_period[0]} to {self.backtest_period[1]}")
        print(f"\nCapital:")
        print(f"  Initial:      ${self.initial_capital:,.2f}")
        print(f"  Final:        ${self.final_capital:,.2f}")
        print(f"  Net Profit:   ${self.net_profit:,.2f}")
        print(f"  Return:       {self.total_return_percent:+.2f}%")

        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {self.total_trades}")
        print(f"  Winning:      {self.winning_trades} ({self.win_rate:.1f}%)")
        print(f"  Losing:       {self.losing_trades} ({100-self.win_rate:.1f}%)")
        print(f"  Profit Factor: {self.profit_factor:.2f}")

        print(f"\nDrawdown & Risk:")
        print(f"  Max Drawdown: {self.max_drawdown:.2f}%")
        print(f"  Largest Win:  ${self.largest_win:,.2f}")
        print(f"  Largest Loss: ${self.largest_loss:,.2f}")
        print(f"  Avg Win:      ${self.avg_win:,.2f}")
        print(f"  Avg Loss:     ${self.avg_loss:,.2f}")

        if self.avg_bars_in_trade > 0:
            print(f"\nTrade Duration:")
            print(f"  Avg Bars:     {self.avg_bars_in_trade:.1f} (4H candles)")

        print("=" * 60 + "\n")


class Backtester:
    """Main backtesting engine."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.data_handler = DataHandler(config)
        self.strategy_engine = StrategyEngine(config)
        self.risk_manager = RiskManager(config)
        self.execution_engine = ExecutionEngine(config, self.risk_manager,
                                               self.data_handler)

    def run_backtest(self, symbol: str, start_date: datetime = None,
                     end_date: datetime = None) -> BacktestResult:
        """
        Run backtest for a single symbol.

        Args:
            symbol: Symbol to backtest
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            BacktestResult object with all metrics
        """
        logger.info(f"Starting backtest for {symbol}")

        # Fetch historical data
        try:
            candles = self.data_handler.get_ohlcv_objects(
                symbol,
                self.config.trade_config.timeframe,
                periods=500
            )
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            result = BacktestResult()
            result.initial_capital = self.config.initial_capital
            result.final_capital = self.config.initial_capital
            return result

        if not candles:
            logger.error(f"No data available for {symbol}")
            result = BacktestResult()
            result.initial_capital = self.config.initial_capital
            result.final_capital = self.config.initial_capital
            return result

        # Reset managers for fresh backtest
        self.risk_manager = RiskManager(self.config)
        self.execution_engine = ExecutionEngine(self.config, self.risk_manager,
                                               self.data_handler)

        result = BacktestResult()
        result.initial_capital = self.config.initial_capital
        result.backtest_period = (candles[0].time, candles[-1].time)

        account_balance = self.config.initial_capital
        equity_curve = [account_balance]

        # Simulate candle-by-candle
        lookback_buffer = 50  # Need history for indicators

        for i in range(lookback_buffer, len(candles)):
            current_candle = candles[i]
            history_candles = candles[max(0, i-200):i+1]

            # 1. Check if we should analyze for new signals
            # (Only on specific candles or based on conditions)
            if i % 5 == 0:  # Analyze every 5 candles to reduce overhead
                signal = self.strategy_engine.analyze(symbol, history_candles)

                if signal:
                    # Queue signal awaiting candle close
                    self.execution_engine.queue_signal(symbol, signal)

            # 2. Check if pending signal should be executed
            # This simulates candle close on next bar
            if i > lookback_buffer:
                executed_trade = self.execution_engine.check_candle_close_and_execute(
                    symbol,
                    current_candle
                )

            # 3. Monitor active positions
            self.execution_engine.monitor_and_update_positions(
                symbol,
                current_candle,
                account_balance
            )

            # 4. Update account balance based on closed trades
            new_closed_trades = [t for t in result.trades if t.status.value.startswith('closed')]
            for trade in self.risk_manager.closed_trades:
                if trade not in result.trades:
                    result.trades.append(trade)
                    account_balance += trade.profit_loss

            equity_curve.append(account_balance)

        # Calculate final stats
        result.equity_curve = equity_curve
        result.final_capital = account_balance
        result.net_profit = account_balance - result.initial_capital
        result.total_return_percent = (result.net_profit / result.initial_capital) * 100

        result.trades = self.risk_manager.closed_trades
        result.total_trades = len(result.trades)

        winning_trades = [t for t in result.trades if t.profit_loss > 0]
        losing_trades = [t for t in result.trades if t.profit_loss < 0]

        result.winning_trades = len(winning_trades)
        result.losing_trades = len(losing_trades)

        if result.total_trades > 0:
            result.win_rate = (result.winning_trades / result.total_trades) * 100
        else:
            result.win_rate = 0.0

        # Profit factor
        gross_profit = sum(t.profit_loss for t in winning_trades)
        gross_loss = abs(sum(t.profit_loss for t in losing_trades))

        if gross_loss > 0:
            result.profit_factor = gross_profit / gross_loss
        else:
            result.profit_factor = float('inf') if gross_profit > 0 else 0.0

        # Drawdown
        peak = result.initial_capital
        max_dd = 0.0
        for equity in equity_curve:
            if equity < peak:
                dd = ((peak - equity) / peak) * 100
                max_dd = max(max_dd, dd)
            else:
                peak = equity
        result.max_drawdown = max_dd

        # Largest win/loss
        if winning_trades:
            result.largest_win = max(t.profit_loss for t in winning_trades)
            result.avg_win = gross_profit / len(winning_trades)
        if losing_trades:
            result.largest_loss = min(t.profit_loss for t in losing_trades)
            result.avg_loss = gross_loss / len(losing_trades)

        # Average bars in trade
        if result.trades:
            avg_days = sum(t.days_open() for t in result.trades) / len(result.trades)
            result.avg_bars_in_trade = avg_days * 6  # 6 4H candles per day

        logger.info(f"Backtest complete: {result.total_trades} trades, "
                   f"{result.win_rate:.1f}% win rate, "
                   f"{result.total_return_percent:+.2f}% return")

        return result

    def run_multiperiod_backtest(self, symbols: List[str]) -> Dict[str, BacktestResult]:
        """Run backtest for multiple symbols."""
        results = {}
        for symbol in symbols:
            results[symbol] = self.run_backtest(symbol)
        return results

    def export_trades_to_csv(self, result: BacktestResult, filename: str):
        """Export trade list to CSV."""
        trades_data = []
        for trade in result.trades:
            trades_data.append({
                'id': trade.trade_id,
                'symbol': trade.entry.symbol,
                'direction': trade.entry.direction,
                'entry_price': trade.entry.entry_price,
                'entry_time': trade.entry.entry_time,
                'exit_price': trade.exit_price,
                'exit_time': trade.exit_time,
                'exit_reason': trade.exit_reason,
                'lot_size': trade.entry.lot_size,
                'profit_loss': trade.profit_loss,
                'profit_loss_pips': trade.profit_loss_pips,
                'profit_loss_percent': trade.profit_loss_percent,
                'rr_ratio': trade.entry.initial_rr,
                'days_open': trade.days_open(),
            })

        df = pd.DataFrame(trades_data)
        df.to_csv(filename, index=False)
        logger.info(f"Trades exported to {filename}")

    def plot_equity_curve(self, result: BacktestResult, filename: str = "equity_curve.png"):
        """Plot equity curve (requires matplotlib)."""
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(14, 6))
            ax.plot(result.equity_curve, label='Equity Curve', linewidth=2)
            ax.fill_between(range(len(result.equity_curve)), result.equity_curve,
                            alpha=0.3)
            ax.axhline(y=result.initial_capital, color='r', linestyle='--',
                       label='Initial Capital')
            ax.set_xlabel('Candle Index')
            ax.set_ylabel('Account Balance ($)')
            ax.set_title(f'Equity Curve Backtest')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(filename, dpi=150)
            logger.info(f"Equity curve saved to {filename}")
            plt.close()

        except ImportError:
            logger.warning("Matplotlib not installed, skipping plot")
