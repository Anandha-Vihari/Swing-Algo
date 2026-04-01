#!/usr/bin/env python3
"""
Complete pipeline: Fetch data → Validate → Backtest → Report

This script demonstrates the end-to-end workflow:
1. Fetch 4H forex data via yfinance
2. Validate data quality
3. Run backtest on all pairs
4. Generate performance reports
"""

import logging
import argparse
import sys

from bot_data_pipeline import prepare_data_for_backtest, validate_backtest_data, get_cached_data
from backtest import Backtester
from config import BotConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch forex data and run backtest'
    )
    parser.add_argument('--pairs', nargs='+',
                       default=['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD'],
                       help='Pairs to fetch')
    parser.add_argument('--skip-fetch', action='store_true',
                       help='Use cached data only')
    parser.add_argument('--period', default='6mo',
                       help='History period (default: 6mo)')
    parser.add_argument('--export', action='store_true',
                       help='Export trade lists to CSV')

    args = parser.parse_args()

    print("\n" + "="*80)
    print("FOREX DATA PIPELINE + BACKTEST")
    print("="*80)

    # Step 1: Fetch data
    if args.skip_fetch:
        logger.info("Skipping fetch, loading from cache...")
        h4_data = get_cached_data(args.pairs)
        if not h4_data:
            logger.error("No cached data found")
            sys.exit(1)
    else:
        logger.info(f"Fetching {len(args.pairs)} pairs...")
        h4_data = prepare_data_for_backtest(
            pairs=args.pairs,
            history_period=args.period,
            use_cache=True
        )

    if not h4_data:
        logger.error("Failed to fetch data")
        sys.exit(1)

    print(f"\nFetched {len(h4_data)} pairs")

    # Step 2: Validate
    logger.info("Validating data...")
    if not validate_backtest_data(h4_data):
        logger.error("Data validation failed")
        sys.exit(1)

    # Step 3: Backtest
    logger.info("Running backtests...")
    print("\n" + "="*80)

    config = BotConfig(initial_capital=10000)
    backtester = Backtester(config)

    results = {}
    for pair, df in h4_data.items():
        logger.info(f"\nBacktesting {pair}...")
        result = backtester.run_backtest(pair)
        result.print_summary()
        results[pair] = result

        if args.export:
            backtester.export_trades_to_csv(result, f'trades_{pair}.csv')

    # Summary
    print("\n" + "="*80)
    print("BACKTEST SUMMARY")
    print("="*80)

    total_profit = 0
    total_trades = 0

    for pair, result in results.items():
        if result.total_trades > 0:
            total_profit += result.net_profit
            total_trades += result.total_trades
            print(f"{pair}: {result.total_trades} trades, "
                  f"{result.win_rate:.1f}% WR, {result.net_profit:+.2f}")

    print(f"\nTotal: {total_trades} trades, {total_profit:+.2f} net profit")
    print("="*80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
