@echo off
setlocal
title Jev BTC - Kalshi and ETF Paper Tests
set "PYTHONUTF8=1"
"C:\Jev\.venv\Scripts\python.exe" "C:\Jev\MarketTest\Jev_BTC_Paper_Test\run_btc.py"
set "JEV_RESULT=%ERRORLEVEL%"
if not defined JEV_NO_PAUSE pause
exit /b %JEV_RESULT%
