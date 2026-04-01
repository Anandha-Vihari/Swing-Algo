# Data Fetcher Guide - Complete Reference

Production-grade forex data pipeline for 4-hour trading system using yfinance.

## Table of Contents
1. [Quick Start](#quick-start)
2. [API Reference](#api-reference)
3. [Supported Pairs](#supported-pairs)
4. [Examples](#examples)
5. [Data Format](#data-format)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Basic Usage (30 seconds)

```python
from data_fetcher import ForexDataFetcher

fetcher = ForexDataFetcher()
data = fetcher.fetch_all_pairs(['EURUSD', 'GBPUSD'])

eurusd_df = data['EURUSD']
print(f"Fetched {len(eurusd_df)} candles")
```

### CLI

```bash
# Fetch data (automatic CSV caching)
python fetch_and_backtest.py --pairs EURUSD GBPUSD --period 1y

# Use cached data only
python fetch_and_backtest.py --skip-fetch

# Fetch and export trades
python fetch_and_backtest.py --pairs EURUSD --export
```

---

## API Reference

### ForexDataFetcher Class

#### Constructor

```python
ForexDataFetcher(
    data_dir='./data',           # Where to save CSV files
    history_period='2y',         # Fetch period (1mo, 3mo, 1y, 2y, etc.)
    min_candles=3000             # Minimum candles required
)
```

**Parameters:**
- `data_dir` (str): Directory for storing CSV files
- `history_period` (str): yfinance period string
- `min_candles` (int): Fail if fewer candles returned

**Example:**
```python
fetcher = ForexDataFetcher(
    data_dir='./forex_data',
    history_period='1y',
    min_candles=2000
)
```

---

#### fetch_raw_data(pair: str, interval: str = '1h')

Fetch raw 1-hour data from Yahoo Finance.

**Parameters:**
- `pair` (str): Currency pair (e.g., 'EURUSD')
- `interval` (str): Fetch interval (default: '1h')

**Returns:**
- `pd.DataFrame` with columns: open, high, low, close, volume
- `None` if failed

**Example:**
```python
df = fetcher.fetch_raw_data('EURUSD')
print(f"Fetched {len(df)} 1H candles")
```

---

#### convert_to_h4(df: pd.DataFrame, pair: str = '')

Resample 1H data to 4H candles with proper OHLCV aggregation.

**OHLCV Aggregation:**
- **Open**: First value
- **High**: Maximum value
- **Low**: Minimum value
- **Close**: Last value
- **Volume**: Sum

**Parameters:**
- `df` (pd.DataFrame): 1-hour DataFrame
- `pair` (str): Pair name for logging

**Returns:**
- `pd.DataFrame` with 4H candles
- `None` if failed

**Example:**
```python
h4_df = fetcher.convert_to_h4(df, 'EURUSD')
print(f"Resampled to {len(h4_df)} 4H candles")
```

---

#### validate_data(df: pd.DataFrame, pair: str = '')

Validate OHLCV data for quality and integrity.

**Validation Checks:**
- ✓ No NaN values
- ✓ OHLC relationships (high ≥ open/close, low ≤ open/close)
- ✓ Minimum candle count
- ✓ Sorted datetime index
- ✓ No duplicate timestamps

**Parameters:**
- `df` (pd.DataFrame): DataFrame to validate
- `pair` (str): Pair name for logging

**Returns:**
- `True` if passes all checks
- `False` otherwise

**Example:**
```python
if fetcher.validate_data(h4_df, 'EURUSD'):
    print("Data is valid")
else:
    print("Data validation failed")
```

---

#### save_to_csv(df: pd.DataFrame, pair: str)

Save 4H DataFrame to CSV file.

**Files saved as:**
- `./data/EURUSD_H4.csv`
- `./data/GBPUSD_H4.csv`
- etc.

**Parameters:**
- `df` (pd.DataFrame): 4-hour DataFrame
- `pair` (str): Currency pair

**Returns:**
- `True` if saved successfully
- `False` otherwise

**Example:**
```python
fetcher.save_to_csv(h4_df, 'EURUSD')
```

---

#### fetch_all_pairs(pairs: Optional[List[str]], use_cache: bool = True)

Fetch and process multiple pairs (complete pipeline).

**Pipeline:**
1. Fetch raw 1H data
2. Resample to 4H
3. Validate
4. Save to CSV
5. Return 4H DataFrames

**Parameters:**
- `pairs` (List[str]): Pairs to fetch (default: all supported)
- `use_cache` (bool): Use cached CSV if available

**Returns:**
- `Dict[str, pd.DataFrame]`: {"EURUSD": df, "GBPUSD": df, ...}

**Example:**
```python
data = fetcher.fetch_all_pairs(['EURUSD', 'GBPUSD', 'USDJPY'])

for pair, df in data.items():
    print(f"{pair}: {len(df)} candles")
```

---

#### load_from_csv(pair: str)

Load previously cached CSV data.

**Parameters:**
- `pair` (str): Currency pair

**Returns:**
- `pd.DataFrame` if file exists
- `None` otherwise

**Example:**
```python
df = fetcher.load_from_csv('EURUSD')
if df is not None:
    print(f"Loaded {len(df)} candles from cache")
```

---

### Integration Functions

#### prepare_data_for_backtest()

High-level function to fetch and prepare data for backtesting.

```python
from bot_data_pipeline import prepare_data_for_backtest

h4_data = prepare_data_for_backtest(
    pairs=['EURUSD', 'GBPUSD'],
    history_period='2y',
    min_candles=3000,
    use_cache=True
)

for pair, df in h4_data.items():
    print(f"{pair}: {len(df)} candles")
```

---

## Supported Pairs

**Defined in:** `ForexDataFetcher.TICKER_MAP`

### Major Pairs
- EURUSD ↔ EURUSD=X
- GBPUSD ↔ GBPUSD=X
- USDJPY ↔ JPY=X
- USDCAD ↔ CADUSD=X
- AUDUSD ↔ AUDUSD=X
- NZDUSD ↔ NZDUSD=X
- USDCHF ↔ CHFUSD=X

### Cross Pairs
- EURGBP ↔ EURGBP=X
- EURJPY ↔ EURJPY=X
- GBPJPY ↔ GBPJPY=X
- AUDJPY ↔ AUDJPY=X
- NZDJPY ↔ NZDJPY=X

### Commodities
- XAUUSD (Gold) ↔ GC=F
- XAGUSD (Silver) ↔ SI=F

### Add Custom Pairs

```python
fetcher = ForexDataFetcher()
fetcher.TICKER_MAP['GBPJPY'] = 'GBPJPY=X'
fetcher.fetch_raw_data('GBPJPY')
```

---

## Examples

### Example 1: Simple Fetch and Save

```python
from data_fetcher import ForexDataFetcher

fetcher = ForexDataFetcher()
data = fetcher.fetch_all_pairs(['EURUSD'])

eurusd = data['EURUSD']
print(eurusd.head())
```

### Example 2: Fetch with Custom History

```python
fetcher = ForexDataFetcher(
    history_period='1y',      # 1 year of data
    min_candles=1000          # Require at least 1000 candles
)

data = fetcher.fetch_all_pairs(['EURUSD', 'GBPUSD'])
```

### Example 3: Use Cache

```python
fetcher = ForexDataFetcher()

# First run: fetches from yfinance
data = fetcher.fetch_all_pairs(['EURUSD'], use_cache=True)

# Second run: loads from CSV instantly
data = fetcher.fetch_all_pairs(['EURUSD'], use_cache=True)
```

### Example 4: Backtest with Real Data

```python
from bot_data_pipeline import prepare_data_for_backtest
from backtest import Backtester
from config import BotConfig

# Fetch data
h4_data = prepare_data_for_backtest(['EURUSD', 'GBPUSD'])

# Run backtest
config = BotConfig(initial_capital=50000)
backtester = Backtester(config)

for pair, df in h4_data.items():
    result = backtester.run_backtest(pair)
    result.print_summary()
```

### Example 5: Data Validation

```python
from bot_data_pipeline import validate_backtest_data, prepare_data_for_backtest

h4_data = prepare_data_for_backtest(['EURUSD', 'GBPUSD'])

if validate_backtest_data(h4_data):
    print("✓ All data valid")
else:
    print("✗ Data validation failed")
```

---

## Data Format

### CSV File Structure

**File:** `./data/EURUSD_H4.csv`

```
datetime,open,high,low,close,volume
2024-04-01 00:00:00,1.08524,1.08745,1.08412,1.08690,15234500
2024-04-01 04:00:00,1.08691,1.09012,1.08650,1.08920,14892300
2024-04-01 08:00:00,1.08920,1.09150,1.08850,1.09050,15100200
```

**Columns:**
- `datetime`: UTC timestamp (YYYY-MM-DD HH:MM:SS)
- `open`: Opening price
- `high`: Highest price in period
- `low`: Lowest price in period
- `close`: Closing price
- `volume`: Trading volume (may be 0 for forex)

### DataFrame Structure (Python)

```python
df = fetcher.fetch_all_pairs(['EURUSD'])['EURUSD']

# Index: DatetimeIndex (UTC)
# Columns: ['open', 'high', 'low', 'close', 'volume']
# Dtype: float64 for OHLCV

print(df.head(2))
#              Datetime                  open      high       low     close  volume
# 2024-04-01 00:00:00Z  1.08524  1.08745  1.08412  1.08690  15234500
# 2024-04-01 04:00:00Z  1.08691  1.09012  1.08650  1.08920  14892300
```

---

## Logging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
fetcher = ForexDataFetcher()
data = fetcher.fetch_all_pairs(['EURUSD'])
```

### Log Output

```
2026-04-01 08:37:08,037 [INFO] data_fetcher: Fetching 1 pairs: EURUSD
2026-04-01 08:37:08,038 [INFO] data_fetcher: EURUSD: Fetching 1h data...
2026-04-01 08:37:08,689 [INFO] data_fetcher: EURUSD: Successfully fetched 531 candles
2026-04-01 08:37:08,731 [INFO] data_fetcher: EURUSD: Data validation passed
2026-04-01 08:37:08,733 [INFO] data_fetcher: EURUSD: Saved 136 candles
```

---

## Troubleshooting

### Problem: "No data returned from yfinance"

**Cause:** Network issue or invalid pair

**Solution:**
```python
# Check if pair is supported
print(ForexDataFetcher.TICKER_MAP.keys())

# Verify internet connection
import yfinance as yf
df = yf.download('EURUSD=X', period='1d')
```

### Problem: "Insufficient candles"

**Cause:** Requested history period is too short

**Solution:**
```python
# Increase history period
fetcher = ForexDataFetcher(
    history_period='2y',      # 2 years instead of 1 month
    min_candles=3000
)
```

### Problem: "Missing required columns"

**Cause:** yfinance returned unexpected columns

**Solution:**
```python
# Check what columns were returned
df = yf.download('EURUSD=X', period='1d', interval='1h')
print(df.columns)
```

### Problem: Slow fetch speed

**Solution:**
```python
# Use cache (cached data loads instantly)
data = fetcher.fetch_all_pairs(['EURUSD'], use_cache=True)

# Or load from CSV directly
data = fetcher.load_from_csv('EURUSD')
```

### Problem: Zero volume in data

**Cause:** Normal for forex data from yfinance

**Note:** Forex volume data from yfinance is limited. This is expected. The trading bot doesn't rely on volume for forex.

---

## Performance

| Operation | Time |
|-----------|------|
| Fetch 1H data (1 pair, 1 month) | ~1 second |
| Fetch 1H data (5 pairs, 2 years) | ~5 seconds |
| Resample to 4H | < 100ms |
| Validate data | < 50ms |
| Save to CSV | < 100ms |
| Load from CSV | < 50ms |

**Tips for speed:**
- Use `use_cache=True` on subsequent runs (instant)
- Fetch shorter history periods for testing (e.g., '1mo' instead of '2y')
- Parallelize fetches using threading (optional enhancement)

---

## See Also

- [Trading Bot README](README.md)
- [Quick Reference Guide](DATA_FETCHER_QUICK_REFERENCE.md)
- [Architecture Document](ARCHITECTURE.md)

