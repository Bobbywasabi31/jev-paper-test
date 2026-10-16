# jev-paper-test

Forward paper-trading evaluation of Jev-family decision models. Two suites, both
**paper only** — no orders are ever submitted, no account API is touched.

## Suites

- **spy-qqq/** — Next-session direction calls on SPY and QQQ. Two cohorts run
  side by side: a baseline feature set and an enriched one (RSI/MACD/ATR,
  multi-horizon returns, plus VIX/10Y/dollar/TLT/HYG/GLD/USO/XLK/XLF and ES/NQ
  futures). Predictions are frozen before the session, settled against actual
  open/close prices, and scored with accuracy and Brier score. See
  `spy-qqq/README-spy-qqq.md` for the full design.
- **btc/** — Exact-contract forecasts on Kalshi BTC markets (15-minute, hourly,
  and daily 5pm-ET legs) plus a Bitcoin ETF direction leg (IBIT proxy, BITU/SBIT
  paper positions). Kalshi settlement uses only finalized YES/NO results from
  Kalshi's public API. See `btc/README.md`.

## Backends

The model runs locally: MiniCPM5-2B-Jev served on `127.0.0.1:8013`
(`serve.py --host 127.0.0.1 --port 8013`). The launchers check the server and
start it if needed.

## Quick start (Windows)

```bat
cd spy-qqq
Start_Jev.bat      :: settle -> predict -> report, both cohorts

cd ..\btc
Start_Jev_BTC.bat  :: Kalshi legs + ETF legs (both cohorts)
```

Python 3.10+, `pip install -r spy-qqq/requirements.txt`. The 15-minute Kalshi leg
is meant to run on a ~15 minute cadence:

```powershell
schtasks /create /tn "Jev15min" /tr "C:\Jev\Start_Jev_BTC.bat" /sc minute /mo 15
```

(a run lock prevents overlapping executions).

## Layout

```
jev-paper-test/
  spy-qqq/          SPY/QQQ next-session paper test (baseline vs enriched A/B)
  btc/              Kalshi BTC exact-contract + ETF paper test
```

## Notes

- Logs (`predictions*.csv`, `*.log`, `latest_report.txt`, `technical_log.txt`)
  are local working state and are gitignored — they are not part of the repo.
- Nothing here trades real money. Every P&L figure is hypothetical paper P&L
  before fees.
