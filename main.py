#!/usr/bin/env python3
"""
Main entry point for the algorithmic trading bot.
Provides CLI interface for running backtest, paper trading, or live trading.
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta

from config import BotConfig, DEFAULT_CONFIG
from backtest import Backtester
from bot import TradingBot
from data_generator import create_trading_setup_data


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format
    )


def cmd_backtest(args):
    """Run backtest command."""
    print("=" * 60)
    print("BACKTESTING MODULE")
    print("=" * 60)

    backtester = Backtester(DEFAULT_CONFIG)

    symbols = args.symbols or [s.pair for s in DEFAULT_CONFIG.symbols]

    for symbol in symbols:
        print(f"\nBacktesting {symbol}...")
        try:
            result = backtester.run_backtest(symbol)
            result.print_summary()

            if args.export:
                backtester.export_trades_to_csv(result, f"trades_{symbol}.csv")

            if args.plot:
                backtester.plot_equity_curve(result, f"equity_{symbol}.png")

        except Exception as e:
            print(f"Error backtesting {symbol}: {e}")
            logging.exception(e)


def cmd_paper_trading(args):
    """Run paper trading mode."""
    print("=" * 60)
    print("PAPER TRADING MODE (Simulation)")
    print("=" * 60)

    config = DEFAULT_CONFIG
    config.paper_trading = True
    config.live_trading = False

    bot = TradingBot(config)

    try:
        iterations = args.iterations or 999999
        scan_interval = args.interval or 30

        bot.start()

        for i in range(iterations):
            logging.info(f"Iteration {i+1}/{iterations if iterations < 999999 else 'inf'}")

            # Scan for signals
            bot.scan_all_symbols()

            # Update positions
            bot.update_positions()

            # Print status
            bot._print_status()

            if iterations > 1 and i < iterations - 1:
                import time
                logging.info(f"Waiting {scan_interval} seconds until next iteration...")
                time.sleep(scan_interval)

    except KeyboardInterrupt:
        logging.info("Paper trading interrupted by user")
    finally:
        bot.stop()


def cmd_live_trading(args):
    """Run live trading mode (REAL MONEY WARNING)."""
    print("\n" + "!" * 60)
    print("WARNING: LIVE TRADING MODE - REAL MONEY AT RISK")
    print("!" * 60 + "\n")

    if not args.force:
        confirm = input("Type 'YES' to enable LIVE TRADING with real money: ")
        if confirm != "YES":
            print("Live trading cancelled.")
            return

    print("=" * 60)
    print("LIVE TRADING MODE")
    print("=" * 60)

    config = DEFAULT_CONFIG
    config.live_trading = True
    config.paper_trading = False

    logging.warning("LIVE TRADING ENABLED - REAL MONEY AT RISK")

    bot = TradingBot(config)

    try:
        scan_interval = args.interval or 30
        bot.run_live_loop(scan_interval_minutes=scan_interval)

    except KeyboardInterrupt:
        logging.info("Live trading interrupted by user")
    finally:
        bot.stop()


def cmd_analyze_signal(args):
    """Analyze a single symbol for signals."""
    from data_handler import DataHandler
    from strategy import StrategyEngine
    from config import TimeFrame

    symbol = args.symbol
    print(f"Analyzing {symbol} for trading signals...")

    config = DEFAULT_CONFIG
    data_handler = DataHandler(config)
    strategy = StrategyEngine(config)

    try:
        candles = data_handler.get_ohlcv_objects(symbol, TimeFrame.H4, periods=500)

        if not candles:
            print(f"No data available for {symbol}")
            return

        signal = strategy.analyze(symbol, candles)

        print("\n" + "=" * 60)
        if signal:
            print(f"SIGNAL FOUND for {symbol}")
            print(f"Direction:      {signal.direction.name}")
            print(f"Entry Price:    {signal.entry_price:.5f}")
            print(f"Stop Loss:      {signal.stop_loss:.5f}")
            print(f"Take Profit:    {signal.take_profit:.5f}")
            print(f"Risk/Reward:    {signal.risk_reward:.2f}")
            print(f"Confirmation:   {signal.confirmation_type}")
            print(f"Timestamp:      {signal.timestamp}")
        else:
            print(f"NO SIGNAL FOUND for {symbol}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        logging.exception(e)


def cmd_setup_data(args):
    """Generate sample data for backtesting."""
    print("Generating synthetic OHLCV data for backtesting...")
    try:
        create_trading_setup_data()
        print("✓ Sample data created in ./data/ directory")
        print("  You can now run: python main.py backtest")
    except Exception as e:
        print(f"Error generating data: {e}")
        logging.exception(e)


def cmd_show_config(args):
    """Show current configuration."""
    config = DEFAULT_CONFIG

    print("\n" + "=" * 60)
    print("BOT CONFIGURATION")
    print("=" * 60)

    print(f"\nTrading Mode:")
    print(f"  Live Trading:     {config.live_trading}")
    print(f"  Paper Trading:    {config.paper_trading}")
    print(f"  Initial Capital:  ${config.initial_capital:,.2f}")

    print(f"\nStrategy:")
    print(f"  Timeframe:        {config.trade_config.timeframe.value}")
    print(f"  EMA Fast:         {config.strategy_config.ema_fast}")
    print(f"  EMA Slow:         {config.strategy_config.ema_slow}")
    print(f"  RSI Period:       {config.strategy_config.rsi_period}")

    print(f"\nRisk Management:")
    print(f"  Risk per Trade:   {config.trade_config.risk_percent_per_trade}%")
    print(f"  Min RR Ratio:     1:{config.trade_config.min_risk_reward_ratio:.1f}")
    print(f"  Max Concurrent:   {config.trade_config.max_concurrent_trades} trades")
    print(f"  Trailing Stop @1R: {config.trade_config.trailing_stop_distance_r}R")
    print(f"  Trail Distance:   {config.trade_config.trailing_stop_pips} pips")

    print(f"\nSymbols Trading:")
    for sym in config.symbols:
        print(f"  - {sym.pair}")

    print("\n" + "=" * 60 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Production-Grade 4H Structure-Based Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py backtest                    # Run backtest
  python main.py paper-trading --iterations 5  # Paper trade (5 cycles)
  python main.py analyze-signal EURUSD       # Analyze single symbol
  python main.py setup-data                  # Generate sample data
  python main.py config                      # Show configuration
        """
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run backtest")
    backtest_parser.add_argument("--symbols", nargs="+", help="Symbols to backtest")
    backtest_parser.add_argument("--export", action="store_true", help="Export trades to CSV")
    backtest_parser.add_argument("--plot", action="store_true", help="Plot equity curve")
    backtest_parser.set_defaults(func=cmd_backtest)

    # Paper trading command
    paper_parser = subparsers.add_parser("paper-trading", help="Run paper trading simulation")
    paper_parser.add_argument("--iterations", type=int, help="Number of scan iterations")
    paper_parser.add_argument("--interval", type=int, help="Seconds between scans")
    paper_parser.set_defaults(func=cmd_paper_trading)

    # Live trading command
    live_parser = subparsers.add_parser("live-trading", help="Run LIVE TRADING (REAL MONEY)")
    live_parser.add_argument("--interval", type=int, help="Minutes between scans")
    live_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    live_parser.set_defaults(func=cmd_live_trading)

    # Analyze signal command
    analyze_parser = subparsers.add_parser("analyze-signal", help="Analyze symbol for signals")
    analyze_parser.add_argument("symbol", help="Symbol to analyze (e.g., EURUSD)")
    analyze_parser.set_defaults(func=cmd_analyze_signal)

    # Setup data command
    setup_parser = subparsers.add_parser("setup-data", help="Generate sample data")
    setup_parser.set_defaults(func=cmd_setup_data)

    # Config command
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_show_config)

    args = parser.parse_args()
    setup_logging(args.log_level)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
