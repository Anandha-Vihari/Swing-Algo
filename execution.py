"""
Trade execution module.
Handles order placement, candle close detection, and position updates.
Supports both live trading and paper trading modes.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from data_handler import OHLCV, DataHandler
from risk_manager import RiskManager, Trade
from config import BotConfig

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Manages trade execution.
    Enforces candle-close-only entry rule and handles both live and paper trading.
    """

    def __init__(self, config: BotConfig, risk_manager: RiskManager,
                 data_handler: DataHandler):
        self.config = config
        self.risk_manager = risk_manager
        self.data_handler = data_handler
        self.pending_signals: Dict[str, Dict] = {}  # Signals awaiting candle close
        self.last_candle_time: Dict[str, datetime] = {}  # Track previous candle closes

    def queue_signal(self, symbol: str, signal_context) -> None:
        """
        Queue a signal awaiting candle close.
        Signal will be executed on next candle open.
        """
        self.pending_signals[symbol] = {
            'signal': signal_context,
            'created_at': datetime.now(),
            'executed': False
        }
        logger.info(f"{symbol}: Signal queued, awaiting candle close confirmation")

    def check_candle_close_and_execute(self, symbol: str,
                                       current_candle: OHLCV) -> Optional[Trade]:
        """
        Check if pending signal should be executed on candle close.
        Returns Trade if executed, None otherwise.
        """
        if symbol not in self.pending_signals:
            return None

        pending = self.pending_signals[symbol]
        signal = pending['signal']

        # Check if signal is stale (older than 4 hours + some buffer)
        age = datetime.now() - pending['created_at']
        if age > timedelta(hours=5):
            logger.warning(f"{symbol}: Signal expired (age: {age})")
            del self.pending_signals[symbol]
            return None

        # Get previous candle to detect close
        previous_time = self.last_candle_time.get(symbol)

        # If we have a new candle (different timestamp), execute on its open
        if previous_time and previous_time != current_candle.time:
            return self._execute_signal(symbol, signal, current_candle)

        # Update last candle time
        self.last_candle_time[symbol] = current_candle.time

        return None

    def _execute_signal(self, symbol: str, signal_context,
                        entry_candle: OHLCV) -> Optional[Trade]:
        """Execute a pending signal."""
        # Pre-execution checks
        if not self.risk_manager.can_open_trade(symbol):
            logger.warning(f"{symbol}: Cannot open trade (risk limits)")
            del self.pending_signals[symbol]
            return None

        # Get symbol configuration
        symbol_config = self.config.get_symbol_config(symbol)
        if not symbol_config:
            logger.error(f"Symbol config not found: {symbol}")
            return None

        # Use entry candle opening price for execution
        execution_price = entry_candle.open
        logger.info(
            f"{symbol}: Executing signal at candle open: {execution_price:.5f}"
        )

        # Calculate position size
        lot_size = self.risk_manager.position_sizer.calculate_lot_size(
            account_balance=self.config.initial_capital,
            symbol_config=symbol_config,
            entry_price=execution_price,
            stop_loss_price=signal_context.stop_loss
        )

        if lot_size <= 0:
            logger.error(f"{symbol}: Invalid lot size: {lot_size}")
            del self.pending_signals[symbol]
            return None

        # Create trade object
        direction = "long" if signal_context.direction.value > 0 else "short"
        trade = self.risk_manager.create_trade(
            symbol=symbol,
            direction=direction,
            entry_price=execution_price,
            stop_loss=signal_context.stop_loss,
            take_profit=signal_context.take_profit,
            lot_size=lot_size,
            account_balance=self.config.initial_capital
        )

        # Place order based on trading mode
        if self.config.live_trading:
            success = self._place_live_order(trade)
        else:  # Paper trading
            success = self._place_paper_order(trade)

        if success:
            self.risk_manager.open_trade(trade)
            del self.pending_signals[symbol]
            logger.info(f"Trade #{trade.trade_id} successfully opened")
            return trade
        else:
            logger.error(f"Failed to execute trade for {symbol}")
            del self.pending_signals[symbol]
            return None

    def _place_live_order(self, trade: Trade) -> bool:
        """
        Place actual live order on broker.
        This would integrate with MT5, REST API, etc.
        """
        try:
            # TODO: Implement actual broker integration
            # For now, log the order
            logger.info(
                f"[LIVE ORDER] {trade.entry.symbol} {trade.entry.direction.upper()} "
                f"Lot: {trade.entry.lot_size:.2f} @ {trade.entry.entry_price:.5f}"
            )
            return True
        except Exception as e:
            logger.error(f"Error placing live order: {e}")
            return False

    def _place_paper_order(self, trade: Trade) -> bool:
        """Simulate paper trading order."""
        logger.info(
            f"[PAPER TRADING] {trade.entry.symbol} {trade.entry.direction.upper()} "
            f"Lot: {trade.entry.lot_size:.2f} @ {trade.entry.entry_price:.5f}"
        )
        return True

    def monitor_and_update_positions(self, symbol: str,
                                     current_candle: OHLCV,
                                     account_balance: float):
        """
        Monitor active trades and update stops/TPs.
        Check for SL/TP hits and update trailing stops.
        """
        trades_to_check = [t for t in self.risk_manager.active_trades
                           if t.entry.symbol == symbol]

        for trade in trades_to_check:
            current_price = current_candle.close

            # Update trailing stop
            self.risk_manager.update_trailing_stop(
                trade,
                current_price,
                pip_value=self.config.get_symbol_config(symbol).pip_value
            )

            # Check for SL hit
            if self.risk_manager.check_stop_loss(trade, current_price):
                logger.info(f"Trade #{trade.trade_id}: Stop loss hit at {current_price:.5f}")
                continue

            # Check for TP hit
            if self.risk_manager.check_take_profit(trade, current_price):
                logger.info(f"Trade #{trade.trade_id}: Take profit hit at {current_price:.5f}")
                continue

            # Log current status
            logger.debug(
                f"Trade #{trade.trade_id}: {trade.entry.symbol} "
                f"Entry: {trade.entry.entry_price:.5f}, "
                f"Current: {current_price:.5f}, "
                f"SL: {trade.current_stop_loss:.5f}, "
                f"TP: {trade.current_take_profit:.5f}"
            )

    def get_pending_signals_summary(self) -> Dict:
        """Get summary of pending signals awaiting candle close."""
        summary = {}
        for symbol, pending in self.pending_signals.items():
            summary[symbol] = {
                'direction': pending['signal'].direction.name,
                'entry_price': pending['signal'].entry_price,
                'created_at': pending['signal'].timestamp,
                'confirmation': pending['signal'].confirmation_type,
            }
        return summary

    def cancel_pending_signal(self, symbol: str) -> bool:
        """Cancel a pending signal."""
        if symbol in self.pending_signals:
            del self.pending_signals[symbol]
            logger.info(f"{symbol}: Pending signal cancelled")
            return True
        return False
