"""
Configuration management for the algorithmic trading bot.
Centralized settings for all trading parameters, symbols, and system configuration.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class TimeFrame(Enum):
    """Supported timeframes."""
    H4 = "4h"
    H1 = "1h"
    D1 = "1d"


@dataclass
class TradeConfig:
    """Trade execution and risk parameters."""
    # Risk Management
    risk_percent_per_trade: float = 1.5  # 1-2% of account
    min_risk_reward_ratio: float = 2.0  # Minimum 1:2 RR

    # Entry Parameters
    timeframe: TimeFrame = TimeFrame.H4
    candle_close_only: bool = True  # Wait for candle close

    # Position Sizing
    max_concurrent_trades: int = 3  # Max simultaneous trades
    max_risk_per_symbol: float = 2.0  # Max 2% per symbol

    # Trailing Stop
    trailing_stop_distance_r: float = 1.0  # Start trailing at +1R
    trailing_stop_pips: int = 50  # Trail by 50 pips

    # Structure Parameters
    lookback_periods: int = 50  # Periods to analyze structure
    min_swing_size_pips: int = 100  # Minimum swing size
    support_resistance_proximity: int = 50  # Proximity threshold (pips)


@dataclass
class StrategyConfig:
    """Strategy parameters."""
    # Trend Detection (EMA)
    ema_fast: int = 50
    ema_slow: int = 200

    # Momentum Confirmation
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30

    # Structure Detection
    detect_bos: bool = True  # Break of Structure
    detect_choch: bool = True  # Change of Character
    detect_support_resistance: bool = True

    # Volume (optional)
    check_volume: bool = True
    volume_ma_period: int = 20
    volume_threshold: float = 1.2  # 20% above average


@dataclass
class Symbol:
    """Symbol configuration."""
    pair: str  # e.g., "EURUSD", "GBPUSD"
    broker: str = "mt5"
    pip_value: float = 0.0001  # For forex
    pip_cost: float = 10.0  # Cost per pip (depends on lot size)
    min_lot: float = 0.01
    max_lot: float = 100.0


@dataclass
class BotConfig:
    """Main bot configuration."""
    # Trading Mode
    live_trading: bool = False
    paper_trading: bool = True
    backtesting: bool = False

    # Account Settings
    initial_capital: float = 10000.0
    leverage: float = 1.0  # No leverage for safety

    # Symbols to Trade
    symbols: List[Symbol] = field(default_factory=lambda: [
        Symbol(pair="EURUSD", pip_value=0.0001, pip_cost=10.0),
        Symbol(pair="GBPUSD", pip_value=0.0001, pip_cost=10.0),
        Symbol(pair="USDJPY", pip_value=0.01, pip_cost=9.0),
        Symbol(pair="XAUUSD", pip_value=0.01, pip_cost=100.0),
    ])

    # Configuration Objects
    trade_config: TradeConfig = field(default_factory=TradeConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)

    # Logging
    log_level: str = "INFO"
    log_file: str = "trading_bot.log"
    output_trades_to_csv: bool = True
    trades_csv_file: str = "trades.csv"

    # Data Source
    data_source: str = "mt5"  # "mt5", "csv", "api"
    data_path: str = "./data"

    # Execution delay simulation (for paper trading)
    execution_delay_ms: int = 100

    def get_symbol_config(self, pair: str) -> Optional[Symbol]:
        """Get configuration for a specific symbol."""
        for sym in self.symbols:
            if sym.pair == pair:
                return sym
        return None


# Default configuration instance
DEFAULT_CONFIG = BotConfig()
