"""
Data pipeline integration for trading bot.
Bridges ForexDataFetcher with backtesting and live trading systems.
"""

import logging
from typing import Dict, List, Optional
import pandas as pd

from data_fetcher import ForexDataFetcher

logger = logging.getLogger(__name__)


def prepare_data_for_backtest(pairs: Optional[List[str]] = None,
                              history_period: str = '2y',
                              min_candles: int = 500,
                              use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Fetch and prepare forex data for backtesting.

    Args:
        pairs: List of pairs to fetch (default: major pairs)
        history_period: yfinance period ('1y', '2y', etc.)
        min_candles: Minimum candles required
        use_cache: Use cached CSV data if available

    Returns:
        Dictionary of 4H DataFrames by pair
    """
    if pairs is None:
        pairs = [
            'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD',
            'AUDUSD', 'NZDUSD', 'USDCHF'
        ]

    logger.info(f"Fetching data for {len(pairs)} pairs")

    fetcher = ForexDataFetcher(
        data_dir='./data',
        history_period=history_period,
        min_candles=min_candles
    )

    result = fetcher.fetch_all_pairs(pairs, use_cache=use_cache)
    logger.info(f"Successfully fetched {len(result)} pairs")

    return result


def get_cached_data(pairs: Optional[List[str]] = None,
                    data_dir: str = './data') -> Dict[str, pd.DataFrame]:
    """Load previously cached CSV data without fetching."""
    fetcher = ForexDataFetcher(data_dir=data_dir)
    result = {}
    if pairs:
        for pair in pairs:
            df = fetcher.load_from_csv(pair)
            if df is not None:
                result[pair] = df
    logger.info(f"Loaded {len(result)} pairs from cache")
    return result


def validate_backtest_data(h4_data: Dict[str, pd.DataFrame]) -> bool:
    """Validate all 4H data before backtesting."""
    valid = True

    for pair, df in h4_data.items():
        if len(df) < 500:
            logger.error(f"{pair}: Insufficient candles")
            valid = False
            continue

        if df.isnull().any().any():
            logger.error(f"{pair}: Contains NaN values")
            valid = False
            continue

        logger.info(f"✓ {pair}: {len(df)} candles valid")

    return valid


if __name__ == "__main__":
    h4_data = prepare_data_for_backtest(
        pairs=['EURUSD', 'GBPUSD'],
        history_period='1mo',
        min_candles=50,
        use_cache=True
    )

    if validate_backtest_data(h4_data):
        print("\n✓ Data validated successfully")
    else:
        print("\n✗ Data validation failed")
