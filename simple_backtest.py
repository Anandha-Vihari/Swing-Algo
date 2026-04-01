#!/usr/bin/env python3
"""
Simplified backtest script that uses cached CSV data directly.
Bypasses MT5 dependency and tests the optimized strategy.
"""

import logging
from datetime import datetime
from typing import List, Dict, Tuple
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


def csv_to_ohlcv(df: pd.DataFrame) -> List[OHLCV]:
    """Convert DataFrame row to OHLCV objects."""
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
    """Run backtest on a single pair."""
    logger.info(f"\n{'='*60}")
    logger.info(f"BACKTESTING {pair}")
    logger.info(f"{'='*60}")

    # Convert to OHLCV objects
    candles = csv_to_ohlcv(df)
    logger.info(f"Loaded {len(candles)} candles for {pair}")

    strategy = StrategyEngine(config)

    signals = []
    lookback_buffer = 50

    # Scan through candles
    for i in range(lookback_buffer, len(candles)):
        history = candles[max(0, i-200):i+1]

        signal = strategy.analyze(pair, history)
        if signal:
            signals.append(signal)

    logger.info(f"Generated {len(signals)} signals")

    # Print signals
    if signals:
        print(f"\n{pair} Signals:")
        for i, sig in enumerate(signals[:10], 1):  # Show first 10
            direction = "LONG" if sig.direction == TrendDirection.BULLISH else "SHORT"
            print(f"  {i}. {direction} @ {sig.entry_price} | SL: {sig.stop_loss} | TP: {sig.take_profit} | RR: {sig.risk_reward:.2f} | {sig.confirmation}")

        if len(signals) > 10:
            print(f"  ... and {len(signals)-10} more signals")

    result = {
        'pair': pair,
        'total_candles': len(candles),
        'signals': len(signals),
        'first_signal_date': signals[0].timestamp if signals else None,
        'last_signal_date': signals[-1].timestamp if signals else None,
    }

    return result


def main():
    print("\n" + "="*80)
    print("SIMPLIFIED BACKTEST - CSV DATA ONLY")
    print("="*80)

    # Load cached data
    logger.info("Loading cached CSV data...")
    pairs = ['EURUSD', 'GBPUSD', 'USDJPY']
    h4_data = get_cached_data(pairs)

    if not h4_data:
        logger.error("No cached data found")
        return 1

    # Validate
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

    total_signals = 0
    for pair, result in results.items():
        print(f"{pair}: {result['signals']} signals from {result['total_candles']} candles")
        total_signals += result['signals']

    print(f"\nTotal Signals: {total_signals}")
    print("="*80 + "\n")

    return 0 if total_signals > 0 else 1


if __name__ == "__main__":
    exit(main())
