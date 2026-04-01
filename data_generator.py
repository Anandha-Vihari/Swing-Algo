"""
Sample data generation for testing and backtesting without live data source.
Generates realistic synthetic OHLCV data for testing the strategy.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def generate_synthetic_ohlcv(symbol: str, days: int = 365, freq: str = '4H',
                            initial_price: float = 1.1,
                            volatility: float = 0.01,
                            trend: float = 0.0001) -> pd.DataFrame:
    """
    Generate realistic synthetic OHLCV data using random walk with trend.

    Args:
        symbol: Symbol name (for reference)
        days: Number of days to generate
        freq: Frequency (4H, 1H, etc.)
        initial_price: Starting price
        volatility: Daily volatility (std dev)
        trend: Daily drift (slight uptrend if positive)

    Returns:
        DataFrame with OHLCV data
    """
    # Calculate number of candles
    if freq == '4H':
        candles_per_day = 6
    elif freq == '1H':
        candles_per_day = 24
    elif freq == '1D':
        candles_per_day = 1
    else:
        raise ValueError(f"Unsupported frequency: {freq}")

    num_candles = days * candles_per_day

    # Generate times
    start_time = datetime.now() - timedelta(days=days)
    times = pd.date_range(start=start_time, periods=num_candles, freq=freq)

    # Generate price path using geometric Brownian motion
    returns = np.random.normal(trend, volatility / np.sqrt(candles_per_day), num_candles)
    prices = initial_price * np.exp(np.cumsum(returns))

    # Generate OHLCV
    data = []
    for i, time in enumerate(times):
        # Create realistic OHLC within the candle
        close = prices[i]
        open_ = prices[i-1] if i > 0 else prices[i]

        # Generate high and low
        candle_range = abs(close - open_) + np.abs(np.random.normal(0, volatility * 0.5))
        high = max(close, open_) + candle_range * np.random.uniform(0.2, 0.8)
        low = min(close, open_) - candle_range * np.random.uniform(0.2, 0.8)

        # Generate volume (realistic)
        volume = np.random.lognormal(10, 1) * 1e6

        data.append({
            'time': time,
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data)
    df.set_index('time', inplace=True)

    logger.info(f"Generated {len(df)} candles for {symbol}")
    return df


def create_trading_setup_data():
    """
    Create sample data files for backtesting.
    Generates CSV files in ./data directory.
    """
    import os

    os.makedirs('./data', exist_ok=True)

    # Generate data for multiple symbols
    symbols = [
        ('EURUSD', 1.0850, 0.008),
        ('GBPUSD', 1.2700, 0.009),
        ('USDJPY', 110.50, 0.012),
    ]

    for symbol, price, volatility in symbols:
        df = generate_synthetic_ohlcv(
            symbol=symbol,
            days=365,
            freq='4H',
            initial_price=price,
            volatility=volatility,
            trend=0.00005  # Slight uptrend
        )

        filename = f'./data/{symbol}_4h.csv'
        df.to_csv(filename)
        logger.info(f"Saved {symbol} data to {filename}")


def inject_signal_pattern(df: pd.DataFrame, signal_type: str = 'breakout',
                         pattern_count: int = 5):
    """
    Inject trading signal patterns into synthetic data.
    Useful for testing strategy detection.

    Args:
        df: DataFrame to modify
        signal_type: 'breakout', 'reversal', 'pullback'
        pattern_count: Number of patterns to inject
    """
    df = df.copy()
    indices = np.random.choice(len(df) - 100, pattern_count, replace=False)

    for idx in indices:
        if signal_type == 'breakout':
            # Create strong uptrend
            df.loc[df.index[idx:idx+20], 'close'] *= np.linspace(1.0, 1.02, 20)
            df.loc[df.index[idx:idx+20], 'high'] *= np.linspace(1.0, 1.025, 20)

        elif signal_type == 'reversal':
            # Create reversal pattern (HH/HL before LL/LH)
            df.loc[df.index[idx:idx+10], 'high'] *= np.linspace(1.0, 1.015, 10)
            df.loc[df.index[idx+10:idx+20], 'low'] *= np.linspace(1.0, 0.985, 10)

    return df


if __name__ == "__main__":
    logger.basicConfig(level=logging.INFO)
    create_trading_setup_data()
    print("Sample data created in ./data/ directory")
