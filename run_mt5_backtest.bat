@echo off
REM MT5 Fetch and Backtest - Windows Batch Script
REM Run this on your local PC (NOT in codespace)

echo.
echo ============================================================================
echo  MT5 FETCH AND BACKTEST - Windows
echo ============================================================================
echo.

REM Install MT5 if needed
echo Installing MetaTrader5 module...
pip install MetaTrader5 -q

REM Run the backtest
echo.
echo Starting backtest...
echo.

python "%~dp0mt5_fetch_and_backtest.py"

pause
