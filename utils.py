"""
Utility functions and helpers for the trading bot.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def align_to_4h_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align dataframe to proper 4H candles.
    Ensures candles start at 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC.
    """
    df = df.copy()

    # Resample to 4H
    df = df.resample('4H').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })

    # Validate alignment
    invalid_hours = df.index[~df.index.hour.isin([0, 4, 8, 12, 16, 20])]
    if len(invalid_hours) > 0:
        logger.warning(f"Found {len(invalid_hours)} misaligned candles after resampling")

    return df.dropna()


def calculate_pips(entry: float, exit: float, pip_size: float = 0.0001) -> float:
    """Calculate pip distance between two prices."""
    return (exit - entry) / pip_size


def calculate_lot_from_risk(account_size: float, risk_percent: float,
                           entry: float, stop_loss: float,
                           pip_cost: float = 10.0, pip_size: float = 0.0001) -> float:
    """
    Calculate lot size from risk parameters.

    Args:
        account_size: Account balance
        risk_percent: Percent of account to risk
        entry: Entry price
        stop_loss: Stop loss price
        pip_cost: Cost per pip per lot
        pip_size: Pip size (0.0001 for major pairs)

    Returns:
        Lot size
    """
    risk_amount = account_size * (risk_percent / 100)
    price_distance_pips = abs(entry - stop_loss) / pip_size
    lot_size = risk_amount / (price_distance_pips * pip_cost)
    return lot_size


def drawdown_from_equity_curve(equity_curve: List[float]) -> Tuple[float, int, int]:
    """
    Calculate maximum drawdown from equity curve.

    Args:
        equity_curve: List of account values over time

    Returns:
        (max_drawdown_percent, peak_index, trough_index)
    """
    if not equity_curve:
        return 0.0, 0, 0

    peak = equity_curve[0]
    peak_idx = 0
    max_dd = 0.0
    trough_idx = 0

    for i, value in enumerate(equity_curve):
        if value > peak:
            peak = value
            peak_idx = i

        dd = (peak - value) / peak * 100
        if dd > max_dd:
            max_dd = dd
            trough_idx = i

    return max_dd, peak_idx, trough_idx


def recovery_factor(net_profit: float, max_drawdown: float,
                   initial_capital: float) -> float:
    """
    Calculate recovery factor (profit / max drawdown).
    Higher values indicate better risk-adjusted returns.
    """
    if max_drawdown == 0 or initial_capital == 0:
        return 0.0

    dd_amount = (max_drawdown / 100) * initial_capital
    if dd_amount == 0:
        return float('inf') if net_profit > 0 else 0.0

    return net_profit / dd_amount


def profit_factor(trades: List) -> float:
    """
    Calculate profit factor (gross_profit / abs(gross_loss)).
    > 1.5 is considered good.
    """
    gross_profit = sum(t.profit_loss for t in trades if t.profit_loss > 0)
    gross_loss = abs(sum(t.profit_loss for t in trades if t.profit_loss < 0))

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0,
                periods_per_year: int = 252) -> float:
    """
    Calculate Sharpe ratio for a series of returns.

    Args:
        returns: List of periodic returns (e.g., daily)
        risk_free_rate: Annual risk-free rate (default 0%)
        periods_per_year: Number of periods in a year (252 for daily)

    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0

    returns_array = np.array(returns)
    excess_returns = returns_array - (risk_free_rate / periods_per_year)

    if excess_returns.std() == 0:
        return 0.0

    return np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std()


def generate_trade_report(trades: List, filename: str = "trade_report.txt"):
    """Generate detailed trade report."""
    with open(filename, 'w') as f:
        f.write("TRADE REPORT\n")
        f.write("=" * 80 + "\n\n")

        for i, trade in enumerate(trades, 1):
            f.write(f"Trade #{trade.trade_id}\n")
            f.write(f"  Symbol: {trade.entry.symbol}\n")
            f.write(f"  Direction: {trade.entry.direction.upper()}\n")
            f.write(f"  Entry: {trade.entry.entry_price:.5f} @ {trade.entry.entry_time}\n")
            f.write(f"  Exit: {trade.exit_price:.5f} @ {trade.exit_time} ({trade.exit_reason})\n")
            f.write(f"  Lot Size: {trade.entry.lot_size:.2f}\n")
            f.write(f"  P&L: ${trade.profit_loss:.2f} ({trade.profit_loss_percent:+.2f}%)\n")
            f.write(f"  Pips: {trade.profit_loss_pips:.0f}\n")
            f.write(f"  RR Ratio: {trade.entry.initial_rr:.2f}\n")
            f.write(f"  Duration: {trade.days_open():.2f} days\n")
            f.write("\n")

    logger.info(f"Trade report saved to {filename}")


def export_to_csv(trades: List, filename: str = "trades.csv"):
    """Export trades to CSV format."""
    data = []
    for trade in trades:
        data.append({
            'trade_id': trade.trade_id,
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
            'peak_profit': trade.peak_profit,
        })

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    logger.info(f"Trades exported to {filename}")


def import_csv_ohlcv(filename: str) -> pd.DataFrame:
    """
    Import OHLCV data from CSV.
    Expected columns: time, open, high, low, close, volume
    """
    df = pd.read_csv(filename)

    required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)

    return df[required_cols]


def validate_csv_ohlcv(df: pd.DataFrame) -> bool:
    """Validate OHLCV CSV data."""
    # Check for NaN
    if df.isnull().any().any():
        logger.error("Data contains NaN values")
        return False

    # Check OHLC relationships
    invalid = df[~((df['high'] >= df['open']) &
                   (df['high'] >= df['close']) &
                   (df['low'] <= df['open']) &
                   (df['low'] <= df['close']))]

    if len(invalid) > 0:
        logger.error(f"Found {len(invalid)} invalid OHLC candles")
        return False

    # Check for gaps
    gaps = df.index.to_series().diff() > timedelta(hours=4.5)
    if gaps.sum() > len(df) * 0.05:  # More than 5% gaps
        logger.warning(f"Found {gaps.sum()} potential data gaps")

    return True


def normalize_returns(returns: List[float]) -> List[float]:
    """Normalize returns to 0 mean, 1 std dev."""
    returns_array = np.array(returns)
    return ((returns_array - returns_array.mean()) / returns_array.std()).tolist()
