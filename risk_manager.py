"""
Risk management module.
Handles position sizing, stop loss/take profit adjustments,
trailing stops, and drawdown monitoring.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum
import logging
from datetime import datetime

from config import BotConfig, TradeConfig, Symbol

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position lifecycle states."""
    PENDING = "pending"       # Waiting for entry
    OPEN = "open"             # Active position
    CLOSED_WIN = "closed_win"
    CLOSED_LOSS = "closed_loss"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"
    CLOSED_MANUAL = "closed_manual"


@dataclass
class TradeEntry:
    """Trade entry point details."""
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    entry_time: datetime
    lot_size: float
    stop_loss: float
    take_profit: float
    risk_amount: float  # In base currency
    initial_rr: float  # Initial risk-reward ratio


@dataclass
class Trade:
    """Complete trade with lifecycle tracking."""
    trade_id: int
    entry: TradeEntry
    status: PositionStatus = PositionStatus.PENDING
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    current_stop_loss: Optional[float] = None  # Updated SL (trailing stop)
    current_take_profit: Optional[float] = None
    profit_loss: Optional[float] = None  # In base currency
    profit_loss_pips: Optional[float] = None
    profit_loss_percent: Optional[float] = None
    peak_profit: float = 0.0  # For drawdown tracking
    closing_notes: str = ""

    def days_open(self) -> float:
        """Return number of days position has been open."""
        if self.exit_time:
            return (self.exit_time - self.entry.entry_time).total_seconds() / 86400
        else:
            return (datetime.now() - self.entry.entry_time).total_seconds() / 86400

    def roi_percent(self) -> float:
        """Return return on investment percentage."""
        if self.profit_loss is None:
            return 0.0
        return (self.profit_loss / self.entry.risk_amount) * 100 if self.entry.risk_amount > 0 else 0.0


class PositionSizer:
    """Calculates position size based on risk parameters."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.trade_config = config.trade_config

    def calculate_lot_size(self, account_balance: float, symbol_config: Symbol,
                           entry_price: float, stop_loss_price: float,
                           risk_percent: Optional[float] = None) -> float:
        """
        Calculate lot size based on risk management rules.
        Risk = (Entry - SL) * lot_size * pip_cost

        Args:
            account_balance: Current account equity
            symbol_config: Symbol configuration with pip values
            entry_price: Proposed entry price
            stop_loss_price: Proposed stop loss price
            risk_percent: Override risk percentage (default from config)

        Returns:
            Lot size in the symbol's unit
        """
        if risk_percent is None:
            risk_percent = self.trade_config.risk_percent_per_trade

        # Risk in base currency
        risk_amount = account_balance * (risk_percent / 100.0)

        # Distance in pips
        price_distance = abs(entry_price - stop_loss_price) / symbol_config.pip_value
        if price_distance == 0:
            return 0.0

        # Lot size = risk_amount / (price_distance_pips * pip_cost_per_lot)
        lot_size = risk_amount / (price_distance * symbol_config.pip_cost)

        # Bound by min/max lot sizes
        lot_size = max(lot_size, symbol_config.min_lot)
        lot_size = min(lot_size, symbol_config.max_lot)

        logger.info(
            f"Position sizing for {symbol_config.pair}: "
            f"Lot={lot_size:.2f}, Risk={risk_amount:.2f}, Distance={price_distance:.0f}pips"
        )

        return lot_size


class RiskManager:
    """
    Manages all risk aspects of trading.
    Handles stops, take profits, trailing stops, and position monitoring.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.trade_config = config.trade_config
        self.position_sizer = PositionSizer(config)
        self.active_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.trade_id_counter = 0

    def create_trade(self, symbol: str, direction: str, entry_price: float,
                     stop_loss: float, take_profit: float, lot_size: float,
                     account_balance: float) -> Trade:
        """Create a new trade object."""
        self.trade_id_counter += 1

        risk_amount = abs(entry_price - stop_loss) * lot_size * 10  # Simplified: assumes pip cost

        entry = TradeEntry(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=datetime.now(),
            lot_size=lot_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            initial_rr=abs(take_profit - entry_price) / abs(stop_loss - entry_price)
        )

        trade = Trade(
            trade_id=self.trade_id_counter,
            entry=entry,
            current_stop_loss=stop_loss,
            current_take_profit=take_profit
        )

        logger.info(
            f"Created trade #{trade.trade_id}: {symbol} {direction} "
            f"@ {entry_price:.5f} (SL: {stop_loss:.5f}, TP: {take_profit:.5f})"
        )

        return trade

    def open_trade(self, trade: Trade) -> None:
        """Register opened trade in active list."""
        trade.status = PositionStatus.OPEN
        self.active_trades.append(trade)
        logger.info(f"Trade #{trade.trade_id} OPENED")

    def check_take_profit(self, trade: Trade, current_price: float) -> bool:
        """Check if take profit is hit."""
        if trade.entry.direction == "long":
            if current_price >= trade.current_take_profit:
                self.close_trade(trade, current_price, "take_profit")
                return True
        else:
            if current_price <= trade.current_take_profit:
                self.close_trade(trade, current_price, "take_profit")
                return True
        return False

    def check_stop_loss(self, trade: Trade, current_price: float) -> bool:
        """Check if stop loss is hit."""
        if trade.entry.direction == "long":
            if current_price <= trade.current_stop_loss:
                self.close_trade(trade, current_price, "stop_loss")
                return True
        else:
            if current_price >= trade.current_stop_loss:
                self.close_trade(trade, current_price, "stop_loss")
                return True
        return False

    def update_trailing_stop(self, trade: Trade, current_price: float,
                             pip_value: float = 0.0001) -> None:
        """
        Update trailing stop according to rules:
        - At +1R: move SL to breakeven (entry price)
        - At +2R: trail by fixed pips
        """
        entry_price = trade.entry.entry_price
        current_profit = current_price - entry_price if trade.entry.direction == "long" else entry_price - current_price

        risk_amount = abs(trade.entry.stop_loss - entry_price)
        current_r = current_profit / risk_amount if risk_amount > 0 else 0

        trailing_distance = self.trade_config.trailing_stop_distance_r * risk_amount

        # 1R rule: Move SL to breakeven
        if current_r >= 1.0 and trade.current_stop_loss != entry_price:
            old_sl = trade.current_stop_loss
            trade.current_stop_loss = entry_price
            logger.info(
                f"Trade #{trade.trade_id}: Trailing stop to breakeven (was {old_sl:.5f})"
            )

        # 2R rule: Trail by fixed distance
        if current_r >= 2.0:
            if trade.entry.direction == "long":
                new_sl = current_price - (self.trade_config.trailing_stop_pips * pip_value)
                if new_sl > trade.current_stop_loss:
                    trade.current_stop_loss = new_sl
                    logger.info(
                        f"Trade #{trade.trade_id}: Trailing stop updated to {new_sl:.5f} "
                        f"(current P&L: +{current_r:.1f}R)"
                    )
            else:
                new_sl = current_price + (self.trade_config.trailing_stop_pips * pip_value)
                if new_sl < trade.current_stop_loss:
                    trade.current_stop_loss = new_sl
                    logger.info(
                        f"Trade #{trade.trade_id}: Trailing stop updated to {new_sl:.5f} "
                        f"(current P&L: +{current_r:.1f}R)"
                    )

        # Track peak profit
        if current_profit > trade.peak_profit:
            trade.peak_profit = current_profit

    def close_trade(self, trade: Trade, exit_price: float,
                    reason: str = "manual") -> None:
        """Close a trade and calculate P&L."""
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.exit_reason = reason

        # Calculate P&L
        if trade.entry.direction == "long":
            trade.profit_loss_pips = (exit_price - trade.entry.entry_price) / 0.0001
            trade.profit_loss = (exit_price - trade.entry.entry_price) * trade.entry.lot_size * 10
        else:
            trade.profit_loss_pips = (trade.entry.entry_price - exit_price) / 0.0001
            trade.profit_loss = (trade.entry.entry_price - exit_price) * trade.entry.lot_size * 10

        trade.profit_loss_percent = (trade.profit_loss / trade.entry.risk_amount * 100) if trade.entry.risk_amount > 0 else 0

        # Determine status
        if trade.exit_reason == "take_profit":
            trade.status = PositionStatus.CLOSED_TP
        elif trade.exit_reason == "stop_loss":
            trade.status = PositionStatus.CLOSED_SL
        elif trade.profit_loss > 0:
            trade.status = PositionStatus.CLOSED_WIN
        elif trade.profit_loss < 0:
            trade.status = PositionStatus.CLOSED_LOSS
        else:
            trade.status = PositionStatus.CLOSED_MANUAL

        # Remove from active and add to closed
        if trade in self.active_trades:
            self.active_trades.remove(trade)
        self.closed_trades.append(trade)

        logger.info(
            f"Trade #{trade.trade_id} CLOSED ({trade.exit_reason}): "
            f"Exit @ {exit_price:.5f} | P&L: {trade.profit_loss:.2f} "
            f"({trade.profit_loss_pips:.0f}pips, {trade.profit_loss_percent:+.1f}%)"
        )

    def get_total_pending_risk(self) -> float:
        """Calculate total risk in all active trades."""
        return sum(trade.entry.risk_amount for trade in self.active_trades)

    def get_account_stats(self, account_balance: float) -> Dict:
        """Get comprehensive account statistics."""
        if not self.closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_profit": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
            }

        total_trades = len(self.closed_trades)
        winning_trades = len([t for t in self.closed_trades if t.profit_loss > 0])
        losing_trades = len([t for t in self.closed_trades if t.profit_loss < 0])

        gross_profit = sum(t.profit_loss for t in self.closed_trades if t.profit_loss > 0)
        gross_loss = sum(t.profit_loss for t in self.closed_trades if t.profit_loss < 0)

        net_profit = gross_profit + gross_loss
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
        largest_win = max((t.profit_loss for t in self.closed_trades if t.profit_loss > 0), default=0)
        largest_loss = min((t.profit_loss for t in self.closed_trades if t.profit_loss < 0), default=0)

        # Calculate max drawdown
        equity_curve = [account_balance]
        for trade in self.closed_trades:
            equity_curve.append(equity_curve[-1] + trade.profit_loss)

        peak_equity = account_balance
        max_drawdown = 0.0
        for equity in equity_curve:
            if equity < peak_equity:
                dd = (peak_equity - equity) / peak_equity * 100
                max_drawdown = max(max_drawdown, dd)
            else:
                peak_equity = equity

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_profit": net_profit,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
        }

    def get_concurrent_trades(self, symbol: Optional[str] = None) -> int:
        """Get number of concurrent open trades."""
        if symbol:
            return len([t for t in self.active_trades if t.entry.symbol == symbol])
        return len(self.active_trades)

    def can_open_trade(self, symbol: str) -> bool:
        """Check if new trade is allowed (respects limits)."""
        # Check max concurrent trades limit
        if self.get_concurrent_trades() >= self.trade_config.max_concurrent_trades:
            logger.warning(f"Max concurrent trades limit ({self.trade_config.max_concurrent_trades}) reached")
            return False

        # Check max concurrent trades per symbol
        if self.get_concurrent_trades(symbol) > 0:
            logger.warning(f"Already have open trade for {symbol}")
            return False

        return True
