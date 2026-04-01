"""
Main trading bot orchestrator.
Coordinates data fetching, analysis, execution, and monitoring across multiple symbols.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time

from config import BotConfig, TimeFrame
from data_handler import DataHandler
from strategy import StrategyEngine
from risk_manager import RiskManager
from execution import ExecutionEngine
from backtest import Backtester, BacktestResult

logger = logging.getLogger(__name__)


class TradingBot:
    """
    Main trading bot for live/paper trading.
    Manages lifecycle, scanning, execution, and monitoring.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.data_handler = DataHandler(config)
        self.strategy_engine = StrategyEngine(config)
        self.risk_manager = RiskManager(config)
        self.execution_engine = ExecutionEngine(config, self.risk_manager,
                                               self.data_handler)

        self.last_scan_time: Dict[str, datetime] = {}
        self.bot_start_time = datetime.now()
        self.is_running = False

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging system."""
        log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format=log_format,
            handlers=[
                logging.FileHandler(self.config.log_file),
                logging.StreamHandler()
            ]
        )

    def start(self):
        """Start the trading bot."""
        logger.info("=" * 60)
        logger.info("TRADING BOT STARTED")
        logger.info("=" * 60)
        logger.info(f"Mode: {'LIVE' if self.config.live_trading else 'PAPER'} TRADING")
        logger.info(f"Initial Capital: ${self.config.initial_capital:,.2f}")
        logger.info(f"Symbols: {[s.pair for s in self.config.symbols]}")
        logger.info(f"Timeframe: {self.config.trade_config.timeframe.value}")
        logger.info(f"Risk per trade: {self.config.trade_config.risk_percent_per_trade}%")
        logger.info("=" * 60 + "\n")

        self.is_running = True

    def stop(self):
        """Stop the trading bot gracefully."""
        logger.info("\nStopping trading bot...")
        self._print_session_summary()
        self.is_running = False
        logger.info("Bot stopped successfully")

    def scan_all_symbols(self) -> Dict[str, bool]:
        """
        Scan all configured symbols for trading signals.

        Returns:
            Dict mapping symbol -> signal_found (bool)
        """
        scan_results = {}

        for symbol_config in self.config.symbols:
            symbol = symbol_config.pair

            # Check if enough time has passed since last scan (avoid reanalyzing)
            last_scan = self.last_scan_time.get(symbol)
            if last_scan and (datetime.now() - last_scan) < timedelta(minutes=5):
                logger.debug(f"{symbol}: Skipping scan (last scan recent)")
                scan_results[symbol] = False
                continue

            try:
                signal = self._analyze_symbol(symbol)
                scan_results[symbol] = signal is not None

                if signal:
                    logger.info(
                        f"{symbol}: NEW SIGNAL - {signal.direction.name} @ "
                        f"{signal.entry_price:.5f} (RR: {signal.risk_reward:.2f})"
                    )
                    # Queue signal for execution
                    self.execution_engine.queue_signal(symbol, signal)

                self.last_scan_time[symbol] = datetime.now()

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                scan_results[symbol] = False

        return scan_results

    def _analyze_symbol(self, symbol: str) -> Optional:
        """Analyze a single symbol for trading signals."""
        # Get latest candles
        candles = self.data_handler.get_ohlcv_objects(
            symbol,
            self.config.trade_config.timeframe,
            periods=500
        )

        if not candles or len(candles) < 50:
            logger.warning(f"{symbol}: Insufficient data")
            return None

        # Run strategy analysis
        signal = self.strategy_engine.analyze(symbol, candles)
        return signal

    def update_positions(self):
        """
        Check on all open positions.
        Update trailing stops, check for SL/TP, execute pending signals.
        """
        for symbol_config in self.config.symbols:
            symbol = symbol_config.pair

            try:
                # Get latest candle
                candles = self.data_handler.get_ohlcv_objects(
                    symbol,
                    self.config.trade_config.timeframe,
                    periods=10  # Just need latest candle
                )

                if not candles:
                    continue

                current_candle = candles[-1]

                # Check if pending signal should execute
                self.execution_engine.check_candle_close_and_execute(
                    symbol,
                    current_candle
                )

                # Monitor active trades
                self.execution_engine.monitor_and_update_positions(
                    symbol,
                    current_candle,
                    account_balance=self.config.initial_capital
                )

            except Exception as e:
                logger.error(f"Error updating positions for {symbol}: {e}")

    def run_live_loop(self, scan_interval_minutes: int = 30):
        """
        Main live trading loop.
        Periodically scans for signals and updates positions.
        """
        self.start()

        try:
            while self.is_running:
                logger.debug(f"Bot loop iteration at {datetime.now()}")

                # Scan for new signals
                self.scan_all_symbols()

                # Update positions (check stops/takes, trailing stops)
                self.update_positions()

                # Print status
                self._print_status()

                # Wait before next scan
                logger.debug(f"Waiting {scan_interval_minutes} minutes until next scan...")
                time.sleep(scan_interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def _print_status(self):
        """Print current bot status."""
        pending = len(self.execution_engine.pending_signals)
        open_trades = len(self.risk_manager.active_trades)
        closed_trades = len(self.risk_manager.closed_trades)

        stats = self.risk_manager.get_account_stats(self.config.initial_capital)

        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BOT STATUS")
        print(f"  Pending Signals: {pending}")
        print(f"  Open Trades: {open_trades}")
        print(f"  Closed Trades: {closed_trades}")
        if closed_trades > 0:
            print(f"  Win Rate: {stats['win_rate']:.1f}%")
            print(f"  Net P/L: ${stats['net_profit']:,.2f}")

    def _print_session_summary(self):
        """Print trading session summary."""
        uptime = datetime.now() - self.bot_start_time
        stats = self.risk_manager.get_account_stats(self.config.initial_capital)

        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Session Duration: {uptime}")
        print(f"Total Trades: {stats['total_trades']}")
        if stats['total_trades'] > 0:
            print(f"Win Rate: {stats['win_rate']:.1f}%")
            print(f"Profit Factor: {stats['profit_factor']:.2f}")
            print(f"Net P/L: ${stats['net_profit']:,.2f}")
            print(f"Max Drawdown: {stats['max_drawdown']:.2f}%")
        print("=" * 60 + "\n")


class BotMonitor:
    """Monitoring utilities for bot performance."""

    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager

    def get_performance_report(self, account_balance: float) -> str:
        """Generate performance report."""
        stats = self.risk_manager.get_account_stats(account_balance)

        report = f"""
PERFORMANCE REPORT
{'='*50}
Total Trades:         {stats['total_trades']}
Winning Trades:       {stats['winning_trades']}
Losing Trades:        {stats['losing_trades']}
Win Rate:             {stats['win_rate']:.2f}%

Gross Profit:         ${stats['gross_profit']:,.2f}
Gross Loss:           ${stats['gross_loss']:,.2f}
Net Profit:           ${stats['net_profit']:,.2f}

Profit Factor:        {stats['profit_factor']:.2f}
Max Drawdown:         {stats['max_drawdown']:.2f}%

Largest Win:          ${stats['largest_win']:,.2f}
Largest Loss:         ${stats['largest_loss']:,.2f}
{'='*50}
        """
        return report


def create_default_bot() -> TradingBot:
    """Factory function to create a bot with default configuration."""
    from config import DEFAULT_CONFIG
    return TradingBot(DEFAULT_CONFIG)
