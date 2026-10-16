# Jev SPY/QQQ enriched market-data A/B paper test

**Never sends brokerage orders.** Uses `MiniCPM5-2B-Jev` at `127.0.0.1:8013`.

## Windows installation

1. Preserve existing `predictions.csv`; don't delete or edit frozen forecasts.
2. Back up `C:\Jev\MarketTest\Jev_SPY_QQQ_Paper_Test\jev_market_test.py` and `C:\Jev\Start_Jev.bat`.
3. Copy `jev_market_test.py` and `enriched_features.py` into `C:\Jev\MarketTest\Jev_SPY_QQQ_Paper_Test\`.
4. Copy `Start_Jev.bat` to `C:\Jev\`.
5. Use existing venv: `C:\Jev\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
6. Double-click `C:\Jev\Start_Jev.bat` after 4:30pm New York time on a regular market day.

## Command line

```powershell
cd C:\Jev\MarketTest\Jev_SPY_QQQ_Paper_Test
C:\Jev\.venv\Scripts\python.exe jev_market_test.py predict --backend minicpm --cohort enriched
C:\Jev\.venv\Scripts\python.exe jev_market_test.py settle --backend minicpm --cohort enriched
C:\Jev\.venv\Scripts\python.exe jev_market_test.py report --backend minicpm --cohort enriched
```

Two **separate** logs: `predictions.csv` (baseline) and `predictions_enriched.csv` (new cohort). Each cohort gets its own forecast using the same next-session open-to-close target and actual leveraged-ETF open/close settlement. No retroactive predictions or settlements. Historical entries remain frozen. 50% decision boundary: UP chooses UPRO/TQQQ; DOWN chooses SPXU/SQQQ. 0.10% illustrative round-trip cost.

Enrichment includes 1/2/5/10/20/60/200-session returns, moving averages, RSI14, MACD, ATR14, realized volatility, volume signals and 20-day range positioning, plus optional VIX, 10Y yield proxy, dollar, Treasury, credit, sector, gold, oil, and index futures daily bars. Missing optional markets are reported, not fabricated. Cross-asset data are cut off to the anchor date and stale assets (>4 calendar days) are excluded. **Daily Yahoo Finance data are not point-in-time guaranteed**: revised/backfilled records and differing vendor finalization can introduce data vintage bias in historical replays. This is a forward test only, not a historical backtest.

Note: enrichment can affect the model's confidence without improving actual directional performance. Two predictions per ETF per day are sent, one per cohort. Treat SPY and QQQ as correlated assets. Results do not establish a trading edge until a sizable prospective sample accumulates.
