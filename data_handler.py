"""
Data handling module for fetching, processing, and storing OHLCV data.
Supports multiple data sources: MT5, CSV, historical API feeds.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from config import BotConfig, Symbol, TimeFrame

logger = logging.getLogger(__name__)


class OHLCV:
    """OHLCV data point."""

    def __init__(self, open_: float, high: float, low: float, close: float,
                 volume: float, time: datetime):
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.time = time
        self.hl2 = (high + low) / 2.0
        self.hlc3 = (high + low + close) / 3.0
        self.ohlc4 = (open_ + high + low + close) / 4.0


class DataHandler:
    """
    Handles OHLCV data fetching, alignment, and preprocessing.
    Ensures 4H candle alignment and handles missing data.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.cache: Dict[str, pd.DataFrame] = {}
        self.last_update: Dict[str, datetime] = {}

    def fetch_data(self, pair: str, timeframe: TimeFrame,
                   periods: int = 500) -> pd.DataFrame:
        """
        Fetch OHLCV data for a symbol.

        Args:
            pair: Currency pair (e.g., "EURUSD")
            timeframe: TimeFrame enum value
            periods: Number of candles to fetch

        Returns:
            DataFrame with columns: [open, high, low, close, volume]
        """
        # Check cache
        cache_key = f"{pair}_{timeframe.value}"
        if cache_key in self.cache:
            cached_df = self.cache[cache_key]
            age = datetime.now() - self.last_update.get(cache_key, datetime.now())
            # Refresh cache if older than 30 minutes
            if age.total_seconds() < 1800:
                return cached_df

        logger.info(f"Fetching {pair} data ({timeframe.value}, {periods} candles)")

        if self.config.data_source == "csv":
            df = self._fetch_from_csv(pair, timeframe)
        elif self.config.data_source == "mt5":
            df = self._fetch_from_mt5(pair, timeframe, periods)
        else:
            raise ValueError(f"Unknown data source: {self.config.data_source}")

        # Align to proper timeframe
        df = self._align_timeframe(df, timeframe)

        # Cache it
        self.cache[cache_key] = df
        self.last_update[cache_key] = datetime.now()

        logger.info(f"Fetched {len(df)} candles for {pair}")
        return df

    def _fetch_from_mt5(self, pair: str, timeframe: TimeFrame,
                        periods: int) -> pd.DataFrame:
        """Fetch data from MetaTrader 5."""
        try:
            import MetaTrader5 as mt5

            if not mt5.initialize():
                logger.error("MT5 initialization failed")
                raise ConnectionError("Cannot connect to MT5")

            # Map timeframe enum to MT5 timeframe
            tf_map = {
                TimeFrame.H4: mt5.TIMEFRAME_H4,
                TimeFrame.H1: mt5.TIMEFRAME_H1,
                TimeFrame.D1: mt5.TIMEFRAME_D1,
            }

            rates = mt5.copy_rates_from_pos(pair, tf_map[timeframe], 0, periods)
            mt5.shutdown()

            if rates is None or len(rates) == 0:
                raise ValueError(f"No data returned for {pair}")

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
            df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            df.set_index('time', inplace=True)

            return df

        except ImportError:
            logger.error("MetaTrader5 module not installed")
            raise

    def _fetch_from_csv(self, pair: str, timeframe: TimeFrame) -> pd.DataFrame:
        """Fetch data from CSV file."""
        file_path = f"{self.config.data_path}/{pair}_{timeframe.value}.csv"

        df = pd.read_csv(file_path)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        return df[required_cols]

    def _align_timeframe(self, df: pd.DataFrame,
                         timeframe: TimeFrame) -> pd.DataFrame:
        """
        Align data to correct timeframe (handle missing candles).
        For 4H: starts at 00:00, 04:00, 08:00, etc. UTC
        """
        df = df.copy()

        # Resample to ensure consistent timeframe
        tf_str = timeframe.value.upper()
        df = df.resample(tf_str).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })

        # Validate alignment for 4H
        if timeframe == TimeFrame.H4:
            invalid_hours = df.index[~df.index.hour.isin([0, 4, 8, 12, 16, 20])]
            if len(invalid_hours) > 0:
                logger.warning(f"Found {len(invalid_hours)} misaligned 4H candles")

        # Fill missing data using forward fill (conservative approach)
        df = df.fillna(method='ffill')

        # Remove rows with NaN values
        df = df.dropna()

        return df

    def get_ohlcv_objects(self, pair: str, timeframe: TimeFrame,
                          periods: int = 500) -> List[OHLCV]:
        """Get OHLCV objects for analysis."""
        df = self.fetch_data(pair, timeframe, periods)

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

    def validate_data_integrity(self, df: pd.DataFrame) -> bool:
        """Validate data for issues."""
        # Check for NaN values
        if df.isnull().any().any():
            logger.error("Data contains NaN values")
            return False

        # Check for invalid OHLC relationships
        invalid_ohlc = df[~((df['high'] >= df['open']) &
                            (df['high'] >= df['close']) &
                            (df['low'] <= df['open']) &
                            (df['low'] <= df['close']))]

        if len(invalid_ohlc) > 0:
            logger.error(f"Found {len(invalid_ohlc)} invalid OHLC candles")
            return False

        # Check for zero volume (can indicate data issues)
        zero_volume = df[df['volume'] == 0]
        if len(zero_volume) > len(df) * 0.1:
            logger.warning(f"Found {len(zero_volume)} zero-volume candles")

        return True

    def resample_to_higher_timeframe(self, df: pd.DataFrame,
                                     target_timeframe: str) -> pd.DataFrame:
        """Resample data to higher timeframe (e.g., 1H → 4H)."""
        df = df.copy()

        resampled = df.resample(target_timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })

        return resampled.dropna()
