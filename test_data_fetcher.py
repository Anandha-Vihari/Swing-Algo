#!/usr/bin/env python3
"""
Test suite for data fetcher module.
Validates all functionality of ForexDataFetcher and related pipelines.
"""

import logging
import sys
import os
from pathlib import Path
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Tests counter
tests_passed = 0
tests_failed = 0


def test(name: str, condition: bool, message: str = ""):
    """Helper to track test results."""
    global tests_passed, tests_failed

    if condition:
        logger.info(f"✓ PASS: {name}")
        tests_passed += 1
    else:
        logger.error(f"✗ FAIL: {name} - {message}")
        tests_failed += 1


def test_imports():
    """Test that all modules import correctly."""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: IMPORTS")
    logger.info("="*70)

    try:
        import pandas as pd
        import yfinance as yf
        import numpy as np
        logger.info("✓ Core dependencies available")
        test("Core dependencies", True)
    except ImportError as e:
        test("Core dependencies", False, str(e))
        return

    try:
        from data_fetcher import ForexDataFetcher
        logger.info("✓ ForexDataFetcher imports")
        test("ForexDataFetcher", True)
    except ImportError as e:
        test("ForexDataFetcher", False, str(e))
        return

    try:
        from bot_data_pipeline import prepare_data_for_backtest
        logger.info("✓ bot_data_pipeline imports")
        test("bot_data_pipeline", True)
    except ImportError as e:
        test("bot_data_pipeline", False, str(e))


def test_ticker_map():
    """Test that ticker mappings are defined."""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: TICKER MAPPINGS")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    ticker_map = ForexDataFetcher.TICKER_MAP
    test("Ticker map exists", len(ticker_map) > 0, f"Found {len(ticker_map)} pairs")

    required_pairs = ['EURUSD', 'GBPUSD', 'USDJPY']
    for pair in required_pairs:
        test(f"  {pair} mapped", pair in ticker_map)

    logger.info(f"✓ Total supported pairs: {len(ticker_map)}")


def test_data_fetcher_initialization():
    """Test ForexDataFetcher initialization."""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: INITIALIZATION")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    try:
        fetcher = ForexDataFetcher(
            data_dir='test_data',
            history_period='1mo',
            min_candles=50
        )
        test("Initialization", True)
        test("  data_dir created", Path('test_data').exists())
        test("  data_dir is Path", isinstance(fetcher.data_dir, Path))
    except Exception as e:
        test("Initialization", False, str(e))


def test_fetch_data():
    """Test actual data fetching."""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: DATA FETCHING")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    fetcher = ForexDataFetcher(
        data_dir='test_data',
        history_period='1mo',
        min_candles=50
    )

    try:
        df = fetcher.fetch_raw_data('EURUSD')
        test("Fetch raw data", df is not None and not df.empty)

        if df is not None:
            test("  Has datetime index", isinstance(df.index, pd.DatetimeIndex))
            test("  Required columns", all(col in df.columns.tolist() for col in ['open', 'high', 'low', 'close', 'volume']))
            logger.info(f"  Fetched {len(df)} candles")

    except Exception as e:
        test("Fetch raw data", False, str(e))


def test_resample_to_4h():
    """Test resampling to 4H."""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: RESAMPLING TO 4H")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    fetcher = ForexDataFetcher(data_dir='test_data', history_period='1mo', min_candles=50)

    try:
        raw_df = fetcher.fetch_raw_data('EURUSD')
        if raw_df is not None:
            h4_df = fetcher.convert_to_h4(raw_df, 'EURUSD')
            test("Resample to 4H", h4_df is not None and not h4_df.empty)

            if h4_df is not None:
                logger.info(f"  Input: {len(raw_df)} 1H candles → Output: {len(h4_df)} 4H candles")
                test("  Ratio correct", len(h4_df) <= len(raw_df) // 3)  # Roughly 1/4 ratio
                test("  Has OHLCV", all(col in h4_df.columns for col in ['open', 'high', 'low', 'close', 'volume']))

    except Exception as e:
        test("Resample to 4H", False, str(e))


def test_data_validation():
    """Test data validation logic."""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: DATA VALIDATION")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    fetcher = ForexDataFetcher(data_dir='test_data', history_period='1mo', min_candles=50)

    try:
        raw_df = fetcher.fetch_raw_data('EURUSD')
        if raw_df is not None:
            h4_df = fetcher.convert_to_h4(raw_df, 'EURUSD')
            if h4_df is not None:
                is_valid = fetcher.validate_data(h4_df, 'EURUSD')
                test("Data validation", is_valid)

    except Exception as e:
        test("Data validation", False, str(e))


def test_csv_save_load():
    """Test saving and loading CSV."""
    logger.info("\n" + "="*70)
    logger.info("TEST 7: CSV SAVE/LOAD")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    fetcher = ForexDataFetcher(data_dir='test_data', history_period='1mo', min_candles=50)

    try:
        raw_df = fetcher.fetch_raw_data('EURUSD')
        if raw_df is not None:
            h4_df = fetcher.convert_to_h4(raw_df, 'EURUSD')
            if h4_df is not None:
                # Save
                saved = fetcher.save_to_csv(h4_df, 'TEST_PAIR')
                test("Save to CSV", saved)

                # Load
                loaded_df = fetcher.load_from_csv('TEST_PAIR')
                test("Load from CSV", loaded_df is not None)

                # Verify
                if loaded_df is not None:
                    test("  Data integrity", len(loaded_df) == len(h4_df))

    except Exception as e:
        test("CSV save/load", False, str(e))


def test_multi_pair():
    """Test multi-pair fetching."""
    logger.info("\n" + "="*70)
    logger.info("TEST 8: MULTI-PAIR FETCHING")
    logger.info("="*70)

    from data_fetcher import ForexDataFetcher

    fetcher = ForexDataFetcher(
        data_dir='test_data',
        history_period='1mo',
        min_candles=50
    )

    try:
        result = fetcher.fetch_all_pairs(['EURUSD', 'GBPUSD'], use_cache=True)
        test("Multi-pair fetch", len(result) == 2)

        for pair in ['EURUSD', 'GBPUSD']:
            df = result.get(pair)
            test(f"  {pair} in result", df is not None)
            if df is not None:
                test(f"  {pair} is DataFrame", isinstance(df, pd.DataFrame))

    except Exception as e:
        test("Multi-pair fetch", False, str(e))


def test_pipeline_integration():
    """Test pipeline integration functions."""
    logger.info("\n" + "="*70)
    logger.info("TEST 9: PIPELINE INTEGRATION")
    logger.info("="*70)

    try:
        from bot_data_pipeline import prepare_data_for_backtest

        h4_data = prepare_data_for_backtest(
            pairs=['EURUSD'],
            history_period='1mo',
            min_candles=50,
            use_cache=True
        )

        test("prepare_data_for_backtest", h4_data is not None and len(h4_data) > 0)

    except Exception as e:
        test("Pipeline integration", False, str(e))


def cleanup():
    """Clean up test files."""
    import shutil
    if Path('test_data').exists():
        shutil.rmtree('test_data')
        logger.info("Cleaned up test_data directory")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("DATA FETCHER TEST SUITE")
    print("="*70)

    test_imports()
    test_ticker_map()
    test_data_fetcher_initialization()
    test_fetch_data()
    test_resample_to_4h()
    test_data_validation()
    test_csv_save_load()
    test_multi_pair()
    test_pipeline_integration()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✓ Passed: {tests_passed}")
    print(f"✗ Failed: {tests_failed}")
    print(f"Total: {tests_passed + tests_failed}")
    print("="*70 + "\n")

    cleanup()

    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
