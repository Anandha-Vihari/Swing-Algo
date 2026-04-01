"""
Production-grade forex data fetching and processing module for 4-hour trading system.
Fetches multi-pair data via yfinance, resamples to 4H, validates, and stores as CSV.

Author: Quantitative Trading System
Date: 2026-04-01
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import warnings

# Suppress yfinance warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('data_fetcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ForexDataFetcher:
    """
    Production-grade forex data fetching and processing pipeline.
    Fetches 1H data, resamples to 4H, validates, and stores as CSV.
    """

    # Yahoo Finance ticker mappings for forex pairs
    TICKER_MAP = {
        # Major pairs (base currency = from, quote = USD by default)
        'EURUSD': 'EURUSD=X',
        'GBPUSD': 'GBPUSD=X',
        'USDJPY': 'JPY=X',
        'USDCAD': 'CADUSD=X',
        'AUDUSD': 'AUDUSD=X',
        'NZDUSD': 'NZDUSD=X',
        'USDCHF': 'CHFUSD=X',

        # Cross pairs
        'EURGBP': 'EURGBP=X',
        'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X',
        'AUDJPY': 'AUDJPY=X',
        'NZDJPY': 'NZDJPY=X',

        # Commodities (for XAUUSD, XAGUSD)
        'XAUUSD': 'GC=F',  # Gold Futures
        'XAGUSD': 'SI=F',  # Silver Futures
    }

    def __init__(self,
                 data_dir: str = './data',
                 history_period: str = '2y',
                 min_candles: int = 500):
        """
        Initialize data fetcher.

        Args:
            data_dir: Directory to store CSV files
            history_period: yfinance period parameter ('1y', '2y', '5y', etc.)
            min_candles: Minimum candles required per pair (default: 500 = ~2 months at 4H)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.history_period = history_period
        self.min_candles = min_candles
        self.raw_data: Dict[str, pd.DataFrame] = {}
        self.h4_data: Dict[str, pd.DataFrame] = {}
        self.fetch_errors: List[str] = []

        logger.info(f"Initialized ForexDataFetcher with data_dir={self.data_dir}")

    def fetch_raw_data(self, pair: str, interval: str = '1h') -> Optional[pd.DataFrame]:
        """
        Fetch raw 1H OHLCV data from yfinance for a forex pair.

        Args:
            pair: Currency pair (e.g., 'EURUSD')
            interval: Fetch interval (default '1h' for 1-hour candles)

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        if pair not in self.TICKER_MAP:
            logger.error(f"{pair}: Not in supported pairs list")
            self.fetch_errors.append(f"{pair}: Unsupported pair")
            return None

        ticker = self.TICKER_MAP[pair]
        logger.info(f"{pair}: Fetching {interval} data (ticker: {ticker}, period: {self.history_period})...")

        try:
            # Fetch data from Yahoo Finance with error suppression
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = yf.download(ticker,
                                period=self.history_period,
                                interval=interval,
                                progress=False,
                                prepost=False)

            if df is None or df.empty:
                logger.error(f"{pair}: No data returned from yfinance")
                self.fetch_errors.append(f"{pair}: Empty response from yfinance")
                return None

            # Check if result is a Series (single ticker) or DataFrame (multiple)
            if isinstance(df, pd.Series):
                logger.error(f"{pair}: Received Series instead of DataFrame")
                self.fetch_errors.append(f"{pair}: Invalid data format from yfinance")
                return None

            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                try:
                    df.index = pd.to_datetime(df.index)
                except Exception as e:
                    logger.error(f"{pair}: Failed to parse datetime index: {e}")
                    return None

            # Remove timezone info (if present) to avoid issues
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Handle MultiIndex columns (yfinance returns (Type, Ticker) tuples)
            if isinstance(df.columns, pd.MultiIndex):
                # Get the first level (OHLCV type)
                df.columns = df.columns.get_level_values(0)

            # Rename columns: yfinance returns 'Close', 'Open', 'High', 'Low', 'Volume'
            col_map = {}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if col_lower == 'close':
                    col_map[col] = 'close'
                elif col_lower == 'open':
                    col_map[col] = 'open'
                elif col_lower == 'high':
                    col_map[col] = 'high'
                elif col_lower == 'low':
                    col_map[col] = 'low'
                elif col_lower == 'volume':
                    col_map[col] = 'volume'

            df.rename(columns=col_map, inplace=True)

            # Ensure required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                # Try alternative column names
                if 'adj close' in df.columns and 'close' not in df.columns:
                    df['close'] = df['adj close']
                    logger.debug(f"{pair}: Using 'adj close' as 'close'")
                    missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                logger.error(f"{pair}: Missing columns {missing_cols}")
                self.fetch_errors.append(f"{pair}: Missing columns {missing_cols}")
                return None

            # Keep only OHLCV (reorder for consistency)
            df = df[required_cols].copy()

            # Remove duplicates
            df = df[~df.index.duplicated(keep='first')]

            # Sort by datetime
            df = df.sort_index()

            logger.info(f"{pair}: Successfully fetched {len(df)} candles "
                       f"({df.index[0].date()} to {df.index[-1].date()})")
            return df

        except Exception as e:
            logger.error(f"{pair}: Error fetching data: {e}")
            self.fetch_errors.append(f"{pair}: {str(e)}")
            return None

    def convert_to_h4(self, df: pd.DataFrame, pair: str = "") -> Optional[pd.DataFrame]:
        """
        Resample 1H data to 4H candles.

        OHLC aggregation:
        - Open: first value
        - High: maximum
        - Low: minimum
        - Close: last value
        - Volume: sum

        Args:
            df: 1-hour DataFrame
            pair: Pair name (for logging)

        Returns:
            4-hour resampled DataFrame or None if invalid
        """
        if df is None or df.empty:
            logger.error(f"{pair}: Cannot resample empty DataFrame")
            return None

        try:
            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Resample to 4h with proper OHLCV aggregation (use lowercase 'h')
            h4_df = df.resample('4h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })

            # Remove rows with NaN (incomplete candles)
            h4_df = h4_df.dropna()

            # For forex data, volume might be 0 or NaN - this is normal from yfinance
            # Don't filter by volume for forex pairs
            # h4_df = h4_df[h4_df['volume'] > 0]

            logger.debug(f"{pair}: Resampled to {len(h4_df)} 4H candles")
            return h4_df

        except Exception as e:
            logger.error(f"{pair}: Error converting to 4H: {e}")
            self.fetch_errors.append(f"{pair}: Conversion to 4H failed: {str(e)}")
            return None

    def validate_data(self, df: pd.DataFrame, pair: str = "") -> bool:
        """
        Validate 4H OHLCV data for quality and integrity.

        Checks:
        - No NaN values
        - OHLC relationships (high >= open/close, low <= open/close)
        - Minimum candle count
        - Sorted datetime index
        - No duplicate timestamps

        Args:
            df: DataFrame to validate
            pair: Pair name (for logging)

        Returns:
            True if valid, False otherwise
        """
        if df is None or df.empty:
            logger.error(f"{pair}: DataFrame is empty")
            return False

        # Check for NaN values
        if df.isnull().any().any():
            nan_rows = df.isnull().sum()
            logger.error(f"{pair}: Found NaN values: {dict(nan_rows[nan_rows > 0])}")
            return False

        # Check OHLC relationships
        invalid_ohlc = df[~((df['high'] >= df['open']) &
                            (df['high'] >= df['close']) &
                            (df['low'] <= df['open']) &
                            (df['low'] <= df['close']))]
        if not invalid_ohlc.empty:
            logger.error(f"{pair}: Found {len(invalid_ohlc)} invalid OHLC candles")
            logger.debug(f"First invalid candle: {invalid_ohlc.iloc[0]}")
            return False

        # Check minimum candle count
        if len(df) < self.min_candles:
            logger.error(f"{pair}: Insufficient candles: {len(df)} < {self.min_candles}")
            self.fetch_errors.append(f"{pair}: Insufficient data ({len(df)} candles)")
            return False

        # Check sorted datetime
        if not df.index.is_monotonic_increasing:
            logger.error(f"{pair}: DateTime index not sorted")
            return False

        # Check for duplicate timestamps
        if df.index.duplicated().any():
            logger.error(f"{pair}: Found {df.index.duplicated().sum()} duplicate timestamps")
            return False

        logger.info(f"{pair}: Data validation passed ({len(df)} candles, "
                   f"{df.index[0].date()} to {df.index[-1].date()})")
        return True

    def save_to_csv(self, df: pd.DataFrame, pair: str) -> bool:
        """
        Save 4H DataFrame to CSV file.

        File format:
        - Location: data/{PAIR}_H4.csv
        - Index: Datetime
        - Columns: open, high, low, close, volume

        Args:
            df: 4-hour DataFrame
            pair: Currency pair (e.g., 'EURUSD')

        Returns:
            True if saved successfully, False otherwise
        """
        if df is None or df.empty:
            logger.error(f"{pair}: Cannot save empty DataFrame")
            return False

        try:
            filename = self.data_dir / f"{pair}_H4.csv"
            df.to_csv(filename, index=True, index_label='datetime')
            logger.info(f"{pair}: Saved {len(df)} candles to {filename}")
            return True

        except Exception as e:
            logger.error(f"{pair}: Error saving to CSV: {e}")
            self.fetch_errors.append(f"{pair}: Failed to save CSV: {str(e)}")
            return False

    def load_from_csv(self, pair: str) -> Optional[pd.DataFrame]:
        """
        Load 4H data from CSV file (if exists).

        Args:
            pair: Currency pair (e.g., 'EURUSD')

        Returns:
            DataFrame if file exists, None otherwise
        """
        filename = self.data_dir / f"{pair}_H4.csv"

        if not filename.exists():
            return None

        try:
            df = pd.read_csv(filename, index_col='datetime', parse_dates=True)
            logger.info(f"{pair}: Loaded {len(df)} candles from {filename}")
            return df
        except Exception as e:
            logger.error(f"{pair}: Error loading from CSV: {e}")
            return None

    def process_pair(self, pair: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Complete pipeline for a single pair: fetch → convert → validate → save.

        Args:
            pair: Currency pair (e.g., 'EURUSD')
            use_cache: If True, try to load from CSV first

        Returns:
            4H DataFrame if successful, None otherwise
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {pair}")
        logger.info(f"{'='*60}")

        # Try to load from cache (CSV)
        if use_cache:
            cached_df = self.load_from_csv(pair)
            if cached_df is not None and len(cached_df) >= self.min_candles:
                logger.info(f"{pair}: Using cached CSV data")
                self.h4_data[pair] = cached_df
                return cached_df

        # Fetch raw 1H data
        raw_df = self.fetch_raw_data(pair)
        if raw_df is None:
            return None

        self.raw_data[pair] = raw_df

        # Convert to 4H
        h4_df = self.convert_to_h4(raw_df, pair)
        if h4_df is None:
            return None

        # Validate
        if not self.validate_data(h4_df, pair):
            return None

        # Save to CSV
        self.save_to_csv(h4_df, pair)

        self.h4_data[pair] = h4_df
        return h4_df

    def fetch_all_pairs(self, pairs: Optional[List[str]] = None,
                       use_cache: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fetch and process multiple pairs in parallel-safe manner.

        Args:
            pairs: List of pairs to fetch (default: all supported)
            use_cache: If True, use cached CSV data when available

        Returns:
            Dictionary of 4H DataFrames: {"EURUSD": df, "GBPUSD": df, ...}
        """
        if pairs is None:
            pairs = list(self.TICKER_MAP.keys())

        logger.info(f"\nFetching {len(pairs)} pairs: {', '.join(pairs)}")
        logger.info(f"History: {self.history_period}, Min candles: {self.min_candles}")

        successful_pairs = []
        failed_pairs = []

        for pair in pairs:
            df = self.process_pair(pair, use_cache=use_cache)
            if df is not None:
                successful_pairs.append(pair)
            else:
                failed_pairs.append(pair)

        # Print summary
        self._print_summary(successful_pairs, failed_pairs)

        return self.h4_data

    def _print_summary(self, successful: List[str], failed: List[str]):
        """Print data fetching summary table."""
        logger.info(f"\n{'='*80}")
        logger.info("DATA FETCHING SUMMARY")
        logger.info(f"{'='*80}")

        if successful:
            logger.info(f"\n✓ Successfully Processed ({len(successful)}):")
            logger.info(f"{'Pair':<10} {'Candles':<10} {'From':<15} {'To':<15}")
            logger.info("-" * 50)

            for pair in successful:
                df = self.h4_data[pair]
                logger.info(f"{pair:<10} {len(df):<10} {df.index[0].date()!s:<15} {df.index[-1].date()!s:<15}")

        if failed:
            logger.info(f"\n✗ Failed ({len(failed)}):")
            for pair in failed:
                logger.info(f"  - {pair}")

        if self.fetch_errors:
            logger.info(f"\nErrors encountered:")
            for error in self.fetch_errors:
                logger.info(f"  - {error}")

        logger.info(f"\nTotal: {len(successful)} successful, {len(failed)} failed")
        logger.info(f"{'='*80}\n")

    def get_dataframe(self, pair: str) -> Optional[pd.DataFrame]:
        """
        Get processed 4H DataFrame for a specific pair.

        Args:
            pair: Currency pair (e.g., 'EURUSD')

        Returns:
            DataFrame or None if not available
        """
        return self.h4_data.get(pair)

    def get_all_dataframes(self) -> Dict[str, pd.DataFrame]:
        """Get all processed 4H DataFrames."""
        return self.h4_data.copy()

    def export_summary_to_csv(self, filename: str = "data_summary.csv"):
        """
        Export summary statistics for all pairs to CSV.

        Includes: Pair, Candles, Start Date, End Date, Min, Max, Mean Close
        """
        try:
            summaries = []

            for pair, df in self.h4_data.items():
                summary = {
                    'Pair': pair,
                    'Candles': len(df),
                    'Start Date': df.index[0],
                    'End Date': df.index[-1],
                    'Days': (df.index[-1] - df.index[0]).days,
                    'Min Close': df['close'].min(),
                    'Max Close': df['close'].max(),
                    'Mean Close': df['close'].mean(),
                    'Std Dev': df['close'].std(),
                }
                summaries.append(summary)

            summary_df = pd.DataFrame(summaries)
            filepath = self.data_dir / filename
            summary_df.to_csv(filepath, index=False)
            logger.info(f"Summary exported to {filepath}")
            return summary_df

        except Exception as e:
            logger.error(f"Error exporting summary: {e}")
            return None


def main():
    """
    Main execution script: fetch, process, validate, and save forex data.
    """
    logger.info("\n" + "=" * 80)
    logger.info("FOREX DATA FETCHER - PRODUCTION PIPELINE")
    logger.info("=" * 80)

    # Initialize fetcher
    fetcher = ForexDataFetcher(
        data_dir='./data',
        history_period='2y',  # 2 years of history
        min_candles=3000      # Minimum 3000 candles (≈ 1-2 months at 4H)
    )

    # Define pairs to fetch (customize as needed)
    pairs_to_fetch = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD',
        'AUDUSD', 'NZDUSD', 'USDCHF',
        'EURGBP', 'EURJPY', 'GBPJPY',
    ]

    # Fetch all pairs (use cache if available)
    result = fetcher.fetch_all_pairs(pairs=pairs_to_fetch, use_cache=True)

    # Export summary
    fetcher.export_summary_to_csv('data_summary.csv')

    # Return processed data
    logger.info(f"\nReturned {len(result)} processed dataframes ready for trading bot")
    return result


if __name__ == "__main__":
    # Run the main pipeline
    h4_data = main()

    # Example: Access a specific pair
    if 'EURUSD' in h4_data:
        eurusd_df = h4_data['EURUSD']
        print(f"\nEURUSD sample (last 5 candles):")
        print(eurusd_df.tail())
