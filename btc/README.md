# btc/ — Kalshi BTC + Bitcoin ETF paper test

**Paper evaluation only.** Reads public Kalshi market data; never submits orders,
never touches account APIs.

## How it runs

`Start_Jev_BTC.bat` → `run_btc.py`:

1. Checks the local MiniCPM5-2B-Jev server on `127.0.0.1:8013` (starts it via
   `C:\Jev\serve.py` if needed). A `.run.lock` prevents overlapping runs.
2. Runs `kalshi_btc.py` — settles finalized Kalshi forecasts, freezes new ones.
3. Runs the ETF leg (`etf/jev_market_test.py`) for both `baseline` and
   `enriched` cohorts: settle → predict → report.
4. Writes a human-readable summary to `latest_report.txt` (technical detail in
   `technical_log.txt`).

## Kalshi legs (`kalshi_btc.py`)

- **15-minute** (`KXBTC15M-*`), **hourly**, and **daily-5pm-ET** (`KXBTCD-*`)
  BTC contracts, selected from Kalshi's public API.
- Per lane it takes the earliest-closing eligible contract nearest the current
  spot price, asks the model for P(YES) on the exact contract under its exact
  rules, and freezes the forecast (both cohorts) before expiry.
- Settlement uses only Kalshi's finalized YES/NO result. Accuracy and Brier
  score per lane/cohort.
- Known limitation: selection only considers the earliest-closing contract per
  lane, so a frozen-but-still-open contract blocks newer contracts in the same
  lane until it closes. (Fix in progress: consider all eligible contracts,
  filter out already-frozen ones, then take the earliest.)

## ETF leg (`etf/`)

Direction forecast on BTC proxied via IBIT; paper positions in BITU (2x long)
or SBIT (2x short) settled against actual ETF open/close prices.

## Setup notes

- Python 3.10+, `yfinance`, `requests` (`pip install yfinance requests`).
- Helper modules expected alongside `kalshi_btc.py`: `btc_data.py`
  (`load_history`), `feature_helpers.py` (`features_from_history`),
  `enriched_features.py` (`enrich`), `simple_report.py` (`build_summary`).
  If any are missing here, copy them from the live install at
  `C:\Jev\MarketTest\Jev_BTC_Paper_Test\`.
- Yahoo BTC minute data is a proxy for features; settlement never depends on
  it — only on Kalshi's official results.
