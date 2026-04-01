#!/bin/bash
# Installation verification script for data fetcher module

echo "════════════════════════════════════════════════════════════════"
echo "DATA FETCHER MODULE - INSTALLATION VERIFICATION"
echo "════════════════════════════════════════════════════════════════"

# Check Python files exist
echo -e "\n1. Checking Python modules..."
files=(
    "data_fetcher.py"
    "bot_data_pipeline.py"
    "fetch_and_backtest.py"
    "test_data_fetcher.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file")
        echo "✓ $file ($lines lines)"
    else
        echo "✗ $file - NOT FOUND"
    fi
done

# Check documentation
echo -e "\n2. Checking documentation..."
docs=(
    "DATA_FETCHER_GUIDE.md"
    "DATA_FETCHER_QUICK_REFERENCE.md"
    "DATA_FETCHER_DELIVERY_SUMMARY.md"
)

for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        echo "✓ $doc"
    else
        echo "✗ $doc - NOT FOUND"
    fi
done

# Check Python syntax
echo -e "\n3. Checking Python syntax..."
python3 -m py_compile data_fetcher.py 2>/dev/null && echo "✓ data_fetcher.py - Valid" || echo "✗ data_fetcher.py - Invalid"
python3 -m py_compile bot_data_pipeline.py 2>/dev/null && echo "✓ bot_data_pipeline.py - Valid" || echo "✗ bot_data_pipeline.py - Invalid"
python3 -m py_compile fetch_and_backtest.py 2>/dev/null && echo "✓ fetch_and_backtest.py - Valid" || echo "✗ fetch_and_backtest.py - Invalid"
python3 -m py_compile test_data_fetcher.py 2>/dev/null && echo "✓ test_data_fetcher.py - Valid" || echo "✗ test_data_fetcher.py - Invalid"

# Check requirements
echo -e "\n4. Checking dependencies..."
if grep -q "yfinance" requirements.txt; then
    echo "✓ yfinance in requirements.txt"
else
    echo "✗ yfinance NOT in requirements.txt"
fi

# Check data directory
echo -e "\n5. Checking data directory..."
if [ -d "data" ]; then
    count=$(ls data/*.csv 2>/dev/null | wc -l)
    echo "✓ data/ directory exists ($count CSV files)"
else
    echo "⚠ data/ directory not created yet (will be created on first run)"
fi

echo -e "\n════════════════════════════════════════════════════════════════"
echo "VERIFICATION COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo -e "\nNext steps:"
echo "  1. pip install -r requirements.txt"
echo "  2. python test_data_fetcher.py"
echo "  3. python fetch_and_backtest.py"
echo ""
