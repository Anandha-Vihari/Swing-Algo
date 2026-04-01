#!/bin/bash
# Correct installation script for the trading bot

echo "════════════════════════════════════════════════════════════════"
echo "TRADING BOT + DATA FETCHER - INSTALLATION"
echo "════════════════════════════════════════════════════════════════"

echo -e "\n1. Upgrading pip..."
python3 -m pip install --upgrade pip

echo -e "\n2. Installing dependencies from requirements.txt..."
python3 -m pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "\n✓ Installation successful!"
    echo -e "\n3. Verifying installation..."
    python3 -m py_compile data_fetcher.py && echo "✓ data_fetcher.py OK" || echo "✗ data_fetcher.py FAILED"
    python3 -m py_compile bot_data_pipeline.py && echo "✓ bot_data_pipeline.py OK" || echo "✗ bot_data_pipeline.py FAILED"
    python3 -m py_compile fetch_and_backtest.py && echo "✓ fetch_and_backtest.py OK" || echo "✗ fetch_and_backtest.py FAILED"

    echo -e "\n════════════════════════════════════════════════════════════════"
    echo "READY TO USE!"
    echo "════════════════════════════════════════════════════════════════"
    echo -e "\nNext steps:"
    echo "  1. python test_data_fetcher.py          # Run tests"
    echo "  2. python fetch_and_backtest.py         # Fetch data & backtest"
    echo "  3. python main.py config                # View bot config"
    echo ""
else
    echo -e "\n✗ Installation failed. Check your internet connection."
    exit 1
fi
