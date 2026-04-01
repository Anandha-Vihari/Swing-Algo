"""
Example usage and run scripts for the trading bot.
"""

import logging
from datetime import datetime, timedelta
from config import BotConfig, TradeConfig, StrategyConfig, Symbol, TimeFrame
from bot import TradingBot, create_default_bot
from backtest import Backtester

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def example_custom_config():
    """Create a custom bot configuration."""
    config = BotConfig(
        live_trading=False,
        paper_trading=True,
        initial_capital=50000.0,
        leverage=1.0,
        symbols=[
            Symbol(pair="EURUSD", pip_value=0.0001, pip_cost=10.0),
            Symbol(pair="GBPUSD", pip_value=0.0001, pip_cost=10.0),
            Symbol(pair="USDJPY", pip_value=0.01, pip_cost=9.0),
        ],
        trade_config=TradeConfig(
            risk_percent_per_trade=1.5,
            min_risk_reward_ratio=2.0,
            timeframe=TimeFrame.H4,
            candle_close_only=True,
            max_concurrent_trades=3,
            trailing_stop_distance_r=1.0,
        ),
        strategy_config=StrategyConfig(
            ema_fast=50,
            ema_slow=200,
            rsi_period=14,
            detect_bos=True,
            detect_choch=True,
            detect_support_resistance=True,
            check_volume=True,
        ),
        data_source="csv",  # Use CSV data for backtesting
    )
    return config


def example_run_backtest():
    """
    Example: Run backtest on historical data.

    Expected directory structure:
    ./data/
        EURUSD_4h.csv
        GBPUSD_4h.csv
        USDJPY_4h.csv

    CSV format: time (ISO), open, high, low, close, volume
    """
    logger.info("Starting backtest example...")

    config = example_custom_config()
    backtester = Backtester(config)

    # Backtest a single symbol
    logger.info("Running backtest for EURUSD...")
    result = backtester.run_backtest("EURUSD")
    result.print_summary()

    # Export trades to CSV
    if config.output_trades_to_csv:
        backtester.export_trades_to_csv(result, config.trades_csv_file)

    # Optionally plot equity curve
    try:
        backtester.plot_equity_curve(result)
    except:
        pass

    return result


def example_run_paper_trading():
    """
    Example: Run bot in paper trading mode.
    Paper trading simulates execution without real money.
    """
    logger.info("Starting paper trading example...")

    config = example_custom_config()
    bot = TradingBot(config)

    # For demo: run for limited iterations instead of infinite loop
    bot.start()

    try:
        for i in range(5):  # Run 5 scan cycles
            logger.info(f"Scan cycle {i+1}/5...")
            bot.scan_all_symbols()
            bot.update_positions()
            bot._print_status()

            # In real bot, this would be time.sleep(30*60)
            # For demo, we do a short sleep
            import time
            time.sleep(2)

    finally:
        bot.stop()


def example_run_live_trading():
    """
    Example: Run bot in LIVE TRADING mode.
    WARNING: This will place real trades with real money!
    Use only after thorough backtesting and paper trading validation.
    """
    logger.warning("=" * 60)
    logger.warning("LIVE TRADING MODE - REAL MONEY AT RISK")
    logger.warning("=" * 60)

    # User must explicitly enable this
    confirm = input("Type 'YES' to confirm live trading: ")
    if confirm != "YES":
        logger.info("Live trading cancelled")
        return

    config = BotConfig(
        live_trading=True,
        paper_trading=False,
        initial_capital=10000.0,
        # ... other settings
    )

    bot = TradingBot(config)
    # Run main live trading loop (scans every 30 minutes)
    bot.run_live_loop(scan_interval_minutes=30)


def example_analyze_single_signal():
    """
    Example: Analyze a single symbol to see signal generation.
    Useful for debugging strategy logic.
    """
    from data_handler import DataHandler
    from strategy import StrategyEngine

    config = example_custom_config()
    data_handler = DataHandler(config)
    strategy = StrategyEngine(config)

    # Fetch data
    candles = data_handler.get_ohlcv_objects("EURUSD", TimeFrame.H4, periods=500)

    # Analyze
    signal = strategy.analyze("EURUSD", candles)

    if signal:
        print(f"\nSignal Found!")
        print(f"Direction: {signal.direction.name}")
        print(f"Entry: {signal.entry_price:.5f}")
        print(f"SL: {signal.stop_loss:.5f}")
        print(f"TP: {signal.take_profit:.5f}")
        print(f"RR: {signal.risk_reward:.2f}")
        print(f"Confirmation: {signal.confirmation_type}")
    else:
        print("No signal found")


def example_show_account_stats():
    """Example: Get account statistics from closed trades."""
    from risk_manager import RiskManager

    config = example_custom_config()
    risk_manager = RiskManager(config)

    # Simulate some trades
    # (In real app, these would come from actual trading)

    stats = risk_manager.get_account_stats(config.initial_capital)

    print("\nAccount Statistics:")
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"Max Drawdown: {stats['max_drawdown']:.2f}%")
    print(f"Net Profit: ${stats['net_profit']:,.2f}")


if __name__ == "__main__":
    # Uncomment the example you want to run:

    # 1. Backtest historical data
    example_run_backtest()

    # 2. Paper trading (simulation)
    # example_run_paper_trading()

    # 3. Live trading (WARNING: REAL MONEY)
    # example_run_live_trading()

    # 4. Analyze single signal
    # example_analyze_single_signal()

    # 5. Show account stats
    # example_show_account_stats()
