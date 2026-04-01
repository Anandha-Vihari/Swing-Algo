# 🚀 Data Fetcher: 5-Minute Getting Started

Get real forex data and run backtests in **5 minutes**.

---

## Step 1: Install Dependencies (1 min)

```bash
pip install -r requirements.txt
```

This installs:
- `yfinance` - For fetching forex data
- `pandas`, `numpy` - Data processing
- `matplotlib` - Plotting
- All other bot dependencies

---

## Step 2: Verify Installation (1 min)

```bash
python test_data_fetcher.py
```

**Expected output:**
```
✓ PASS: Imports
✓ PASS: Supported Pairs
✓ PASS: Data Fetcher
✓ PASS: Data Pipeline
Result: 4/4 tests passed!
```

If you see errors, check your internet connection and retry.

---

## Step 3: Fetch Real Data (2-3 min)

```bash
python fetch_and_backtest.py
```

This will:
1. Fetch 2 years of 1H data for major forex pairs
2. Resample to 4H
3. Validate quality
4. Save to `./data/`
5. Run backtest

**Example output:**
```
EURUSD: Fetching 1h data...
EURUSD: Successfully fetched 10656 candles
EURUSD: Resampled to 5328 4H candles
EURUSD: Data validation passed (5328 candles, 2024-04-01 to 2026-04-01)
EURUSD: Saved 5328 candles to ./data/EURUSD_H4.csv

...

============================================================
DATA FETCHING SUMMARY
============================================================
✓ Successfully Processed (5):
Pair       Candles    From             To
EURUSD     5328       2024-04-01       2026-04-01
GBPUSD     5104       2024-04-02       2026-04-01
USDJPY     5456       2024-04-01       2026-04-01
...
```

---

## Step 4: Check Results (instant)

**View summary:**
```bash
cat data_summary.csv
```

**Output:**
```
Pair,Candles,Start Date,End Date,Days,Min Close,Max Close,Mean Close,Std Dev
EURUSD,5328,2024-04-01,2026-04-01,731,1.054,1.123,1.0892,0.0156
GBPUSD,5104,2024-04-02,2026-04-01,730,1.192,1.287,1.2358,0.0245
...
```

**View CSV files:**
```bash
ls -lh data/
```

**Output:**
```
data/
├── EURUSD_H4.csv  (100 KB)
├── GBPUSD_H4.csv  (95 KB)
├── USDJPY_H4.csv  (110 KB)
├── ... (one file per pair)
└── data_summary.csv
```

---

## 🎉 Done!

You now have:
- ✅ 5+ pairs with 5000+ 4H candles each
- ✅ Clean, validated data in CSV format
- ✅ Ready for backtesting or live trading

---

## Common Operations

### Fetch Specific Pairs Only

```bash
python fetch_and_backtest.py --pairs EURUSD GBPUSD USDJPY
```

### Use Cached Data (No Download)

```bash
python fetch_and_backtest.py --skip-fetch
```

### Export & Plot Results

```bash
python fetch_and_backtest.py --export --plot
```

**Creates:**
- `trades_EURUSD.csv` - Trade details
- `equity_EURUSD.png` - Equity curve chart

---

## Python API

### One-Liner Fetch

```python
from data_fetcher import ForexDataFetcher
data = ForexDataFetcher().fetch_all_pairs()
```

### With Bot

```python
from bot_data_pipeline import prepare_data_for_backtest
data = prepare_data_for_backtest(pairs=['EURUSD', 'GBPUSD'])

for pair, df in data.items():
    print(f"{pair}: {len(df)} candles")
```

### Custom Config

```python
fetcher = ForexDataFetcher(
    data_dir='./mydata',
    history_period='5y',       # 5 years
    min_candles=5000
)
data = fetcher.fetch_all_pairs(use_cache=True)
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| "ModuleNotFoundError" | Run: `pip install -r requirements.txt` |
| "No data returned" | Check internet, wait 5 min, retry |
| "Insufficient candles" | Use `history_period='5y'` or lower threshold |
| Tests fail | Check internet, run `python test_data_fetcher.py -v` |

---

## Documentation

- **Quick Ref:** `DATA_FETCHER_QUICK_REFERENCE.md`
- **Full Guide:** `DATA_FETCHER_GUIDE.md`
- **Implementation:** `DATA_FETCHER_IMPLEMENTATION.md`
- **Summary:** `DATA_FETCHER_DELIVERY_SUMMARY.md`

---

## What's Next?

### Option 1: Backtest
```bash
python main.py backtest
```

### Option 2: Paper Trade
```bash
python main.py paper-trading --iterations 10
```

### Option 3: Analyze Signal
```bash
python main.py analyze-signal EURUSD
```

---

## Files Created

| File | Purpose |
|---|---|
| `data_fetcher.py` | Core module (514 lines) |
| `bot_data_pipeline.py` | Integration (178 lines) |
| `fetch_and_backtest.py` | CLI (194 lines) |
| `test_data_fetcher.py` | Tests (182 lines) |
| `data_summary.csv` | Statistics output |
| `data/` | CSV storage (auto-created) |

---

**Ready? Run this:**
```bash
python fetch_and_backtest.py
```

**Time to first backtest: ~3 minutes ⏱️**

---

Last updated: 2026-04-01
