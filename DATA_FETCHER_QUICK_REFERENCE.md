# Data Fetcher - Quick Reference

Cheat sheet for common data fetching tasks.

---

## 5-Second Examples

### Fetch data
```python
from data_fetcher import ForexDataFetcher
fetcher = ForexDataFetcher()
data = fetcher.fetch_all_pairs(['EURUSD', 'GBPUSD'])
```

### Use cache (instant)
```python
data = fetcher.fetch_all_pairs(['EURUSD'], use_cache=True)
```

### Load from CSV
```python
df = fetcher.load_from_csv('EURUSD')
```

### Manual pipeline
```python
raw = fetcher.fetch_raw_data('EURUSD')           # 1H data
h4 = fetcher.convert_to_h4(raw)                 # Resample
fetcher.save_to_csv(h4, 'EURUSD')               # Save
```

---

## Supported Pairs

```python
ForexDataFetcher.TICKER_MAP  # Dict of all supported pairs

# Major:   EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, NZDUSD, USDCHF
# Cross:   EURGBP, EURJPY, GBPJPY, AUDJPY, NZDJPY
# Commodities: XAUUSD, XAGUSD
```

---

## Common Parameters

| Parameter | Default | Example |
|-----------|---------|---------|
| `history_period` | '2y' | '1mo', '3mo', '1y', '2y' |
| `min_candles` | 3000 | 1000, 2000, 5000 |
| `data_dir` | './data' | './forex_data' |
| `use_cache` | True | True (use CSV if exists) |

---

## Functions

### High-Level
```python
from bot_data_pipeline import prepare_data_for_backtest

h4_data = prepare_data_for_backtest(['EURUSD', 'GBPUSD'])
```

### Low-Level (manual)
```python
fetcher = ForexDataFetcher()

df_1h = fetcher.fetch_raw_data('EURUSD')        # Get 1H data
df_4h = fetcher.convert_to_h4(df_1h)            # Resample
is_valid = fetcher.validate_data(df_4h)         # Check quality
fetcher.save_to_csv(df_4h, 'EURUSD')            # Save
df_cached = fetcher.load_from_csv('EURUSD')     # Load
```

---

## Data Output

**CSV location:** `./data/{PAIR}_H4.csv`

**DataFrame columns:** `open`, `high`, `low`, `close`, `volume`

**Index:** Datetime (UTC)

```python
df = fetcher.fetch_all_pairs(['EURUSD'])['EURUSD']
print(df)
#           datetime      open      high       low     close  volume
# 2024-04-01 00:00:00  1.08524  1.08745  1.08412  1.08690    15234500
```

---

## Backtest Integration

```python
from bot_data_pipeline import prepare_data_for_backtest
from backtest import Backtester

# Fetch
h4_data = prepare_data_for_backtest(['EURUSD'])

# Backtest
backtester = Backtester(BotConfig())
for pair, df in h4_data.items():
    result = backtester.run_backtest(pair)
    result.print_summary()
```

---

## CLI Commands

```bash
# Fetch and backtest
python fetch_and_backtest.py --pairs EURUSD GBPUSD --period 1y

# Use cache only
python fetch_and_backtest.py --skip-fetch

# Export trades to CSV
python fetch_and_backtest.py --export
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Slow fetch | Use `use_cache=True` |
| "No data" | Check pair in `TICKER_MAP` |
| "Insufficient candles" | Increase `history_period` |
| Internet error | Verify connection / retry |
| Zero volume | Normal for forex (it's OK!) |

---

## Performance

- Fetch 1H (1 pair, 1 month): ~1 sec
- Fetch 1H (5 pairs, 2 years): ~5 sec
- Load from cache: < 100ms
- Resample to 4H: < 100ms

---

For full docs: See [DATA_FETCHER_GUIDE.md](DATA_FETCHER_GUIDE.md)

