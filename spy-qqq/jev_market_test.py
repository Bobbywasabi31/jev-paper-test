#!/usr/bin/env python3
"""Paper-only forward evaluation of Jev's next-session ETF direction forecasts.

Predict AFTER 4:30pm New York time for next-session open-to-close direction.
Settle only after the next session has finished.
This script NEVER sends orders to a broker.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo
from typing import Any

DATA_FILE = Path(__file__).with_name("predictions.csv")
COHORT = "baseline"
NY = ZoneInfo("America/New_York")
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"   # Pinned for comparability. Update only between evaluation cohorts.
ROUND_TRIP_COST = 0.001   # 10 basis points total, illustrative cost/slippage assumption.
LONG_THRESHOLD = 0.50
LOW_THRESHOLD = 0.50
LEVERAGED_MAP = {"SPY": {"UP": "UPRO", "DOWN": "SPXU"}, "QQQ": {"UP": "TQQQ", "DOWN": "SQQQ"}}
FIELDS = [
    "predicted_at_utc", "symbol", "as_of_date", "model", "p_up", "direction",
    "decision", "features_json", "target_date", "next_open", "next_close", "was_up",
    "intraday_return", "long_trade_net", "benchmark_always_long_net",
    "leveraged_symbol", "leveraged_open", "leveraged_close", "leveraged_net", "underlying_signal_net"
]


def require_packages():
    try:
        import yfinance  # noqa: F401
        import requests  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Install packages first: python -m pip install -r requirements.txt") from exc


def load_history(symbol: str):
    import yfinance as yf
    df = yf.Ticker(symbol).history(period="2y", interval="1d", auto_adjust=False, actions=False)
    if df is None or df.empty:
        raise RuntimeError(f"No Yahoo Finance daily candles for {symbol}")
    df = df.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
    # Index is exchange-local date; convert to plain YYYY-MM-DD to avoid TZ confusion.
    df.index = [str(x.date()) for x in df.index]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["Open", "Close"])
    if len(df) < 30:
        raise RuntimeError(f"Insufficient price history for {symbol}")
    return df


def features_from_history(df: Any) -> dict[str, Any]:
    closes = df["Close"].astype(float)
    volumes = df["Volume"].astype(float)
    daily_returns = closes.pct_change().dropna()
    last = df.iloc[-1]
    vals = {
        "as_of_date": df.index[-1],
        "last_close_usd": round(float(last["Close"]), 4),
        "last_session_open_usd": round(float(last["Open"]), 4),
        "last_session_open_to_close_pct": round(100 * (float(last["Close"]) / float(last["Open"]) - 1), 3),
        "previous_close_to_close_return_pct": round(100 * (float(closes.iloc[-1]) / float(closes.iloc[-2]) - 1), 3),
        "five_session_close_return_pct": round(100 * (float(closes.iloc[-1]) / float(closes.iloc[-6]) - 1), 3),
        "twenty_session_close_return_pct": round(100 * (float(closes.iloc[-1]) / float(closes.iloc[-21]) - 1), 3),
        "ten_session_daily_return_volatility_pct": round(100 * float(daily_returns.iloc[-10:].std(ddof=0)), 3),
        "last_volume_divided_by_prior_20_average": round(float(volumes.iloc[-1]) / float(volumes.iloc[-21:-1].mean()), 3),
        "last_session_high_low_range_pct_of_open": round(100 * (float(last["High"]) - float(last["Low"])) / float(last["Open"]), 3),
    }
    if any(not math.isfinite(v) for v in vals.values() if isinstance(v, (float, int))):
        raise RuntimeError("Bad feature caused by missing or zero market data")
    return vals


def request_jev(symbol: str, features: dict[str, Any]) -> tuple[float, str]:
    import requests
    backend = os.environ.get("JEV_BACKEND", "minicpm")
    state = {
        "asset": symbol, "market": "US ETF, regular session only",
        "as_of": f"After the {features['as_of_date']} regular-session close; no later information is available.",
        "available_information": features,
        "forecast_target": "Next regular US stock-market session OPEN to CLOSE (not close to close).",
    }
    instructions = (
        "Based ONLY on the supplied historical state, will this ETF close strictly higher "
        "than it opens during the NEXT regular US stock-market session? "
        "Do not predict the previous session."
    )
    criteria = {"true": "YES: next session close > open", "false": "NO: next session close <= open"}
    if backend == "minicpm":
        payload = {"state": json.dumps(state), "questions": {"next_session_up": {
            "type": "choice", "instructions": instructions, "criteria": criteria}}}
        response = requests.post("http://127.0.0.1:8013/v1/systemone", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        p = float(data["answers"]["next_session_up"]["probabilities"]["true"])
        model = str(data.get("model", "MiniCPM5-2B-Jev"))
    elif backend == "typesafe":
        key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not key:
            raise RuntimeError("TYPESAFE_API_KEY is not set")
        payload = {"model": MODEL, "state": state,
                   "questions": {"next_session_up": {"type": "noul", "instructions": instructions, "criteria": criteria}}}
        response = requests.post(API_URL, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        p = float(data["answers"]["next_session_up"]["noul"])
        model = str(data.get("model", MODEL))
    else:
        raise ValueError(f"Unknown backend: {backend}")
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise RuntimeError(f"Invalid Jev probability: {p}")
    return p, model


def read_rows() -> list[dict[str, str]]:
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open("r", newline="", encoding="utf-8") as f:
        # Normalize to the current schema: drop retired columns (e.g. "backend"
        # from the earlier multi-backend harness) and default new columns to "".
        # Without this, rewriting a CSV written by the older schema crashes
        # csv.DictWriter with "dict contains fields not in fieldnames".
        return [{k: (r.get(k) or "") for k in FIELDS} for r in csv.DictReader(f)]


def write_rows(rows: list[dict[str, str]]) -> None:
    temp = DATA_FILE.with_suffix(".tmp")
    with temp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(DATA_FILE)


def paper_decision(p_up: float) -> str:
    if p_up >= LONG_THRESHOLD:
        return "PAPER_LONG"
    if p_up <= LOW_THRESHOLD:
        return "PAPER_BEAR_3X"
    return "NO_TRADE"


def leveraged_choice(symbol: str, p_up: float) -> str:
    if symbol not in LEVERAGED_MAP:
        return ""
    if p_up >= LONG_THRESHOLD:
        return LEVERAGED_MAP[symbol]["UP"]
    if p_up <= 1 - LONG_THRESHOLD:
        return LEVERAGED_MAP[symbol]["DOWN"]
    return ""


def is_session_complete(session_date: str, now: datetime) -> bool:
    local = now.astimezone(NY)
    d = date.fromisoformat(session_date)
    return d < local.date() or (d == local.date() and local.time() >= time(16, 30))


def predict(symbols: list[str]) -> None:
    require_packages()
    now = datetime.now(timezone.utc)
    existing = read_rows()
    for symbol in symbols:
        try:
            df = load_history(symbol)
            as_of = df.index[-1]
            local = now.astimezone(NY)
            if as_of != local.date().isoformat() or not is_session_complete(as_of, now):
                print(f"{symbol}: SKIP — only predict after today's completed regular session (4:30pm ET onward). Latest daily bar: {as_of}.")
                continue
            if any(r["symbol"] == symbol and r["as_of_date"] == as_of for r in existing):
                print(f"{symbol}: already predicted for {as_of}; will not overwrite a frozen prediction.")
                continue
            features = features_from_history(df)
            if COHORT == "enriched":
                from enriched_features import enrich
                features["enriched_daily_market_data"] = enrich(df, as_of, symbol, loader=load_history)
            p, resolved_model = request_jev(symbol, features)
            item = dict.fromkeys(FIELDS, "")
            item.update({
                "predicted_at_utc": now.isoformat(timespec="seconds"),
                "symbol": symbol, "as_of_date": as_of,
                "model": resolved_model + "/" + COHORT, "p_up": f"{p:.6f}",
                "direction": "UP" if p >= 0.5 else "DOWN",
                "decision": paper_decision(p),
                "leveraged_symbol": leveraged_choice(symbol, p),
                "features_json": json.dumps(features, separators=(",", ":")),
            })
            existing.append(item)
            write_rows(existing)
            print(f"{symbol}: next-session P(up)={p:.1%}; direction={item['direction']}; paper action={item['decision']}")
        except Exception as exc:
            print(f"{symbol}: ERROR — {exc}")


def settle() -> None:
    require_packages()
    rows = read_rows()
    now = datetime.now(timezone.utc)
    if not rows:
        print("No predictions yet. Run: python jev_market_test.py predict")
        return
    df_by_symbol = {}
    changed = 0
    for row in rows:
        if row.get("target_date"):
            continue
        symbol = row["symbol"]
        try:
            if symbol not in df_by_symbol:
                df_by_symbol[symbol] = load_history(symbol)
            df = df_by_symbol[symbol]
            subsequent = [d for d in df.index if d > row["as_of_date"]]
            if not subsequent or not is_session_complete(subsequent[0], now):
                continue
            target = subsequent[0]
            candle = df.loc[target]
            o, c = float(candle["Open"]), float(candle["Close"])
            if o <= 0 or c <= 0:
                raise ValueError("Nonpositive price")
            raw_return = c / o - 1.0
            p = float(row["p_up"])
            # Fetch the actual leveraged ETF candle for exactly the same session.
            lev = row.get("leveraged_symbol") or ""  # Frozen historical no-trade remains no-trade.
            lev_open = lev_close = lev_net = ""
            if lev:
                if lev not in df_by_symbol:
                    df_by_symbol[lev] = load_history(lev)
                lev_df = df_by_symbol[lev]
                if target not in lev_df.index:
                    raise RuntimeError(f"Missing {lev} completed candle for {target}; keep prediction unsettled")
                lev_o = float(lev_df.loc[target]["Open"])
                lev_c = float(lev_df.loc[target]["Close"])
                if lev_o <= 0 or lev_c <= 0:
                    raise RuntimeError(f"Invalid {lev} open/close for {target}")
                lev_open = f"{lev_o:.4f}"
                lev_close = f"{lev_c:.4f}"
                lev_net = f"{lev_c / lev_o - 1 - ROUND_TRIP_COST:.9f}"
            underlying_net = (raw_return if row.get("direction") == "UP" else -raw_return) if lev else 0.0
            if lev:
                underlying_net -= ROUND_TRIP_COST
            row.update({
                "target_date": target,
                "next_open": f"{o:.4f}", "next_close": f"{c:.4f}",
                "was_up": "1" if c > o else "0",
                "intraday_return": f"{raw_return:.9f}",
                "long_trade_net": f"{raw_return - ROUND_TRIP_COST:.9f}" if p >= LONG_THRESHOLD else "0.000000000",
                "benchmark_always_long_net": f"{raw_return - ROUND_TRIP_COST:.9f}",
                "leveraged_symbol": lev,
                "leveraged_open": lev_open,
                "leveraged_close": lev_close,
                "leveraged_net": lev_net,
                "underlying_signal_net": f"{underlying_net:.9f}",
            })
            changed += 1
            print(f"{symbol}: settled prediction of {row['as_of_date']} against {target}: {'UP' if c > o else 'DOWN/FLAT'} ({raw_return:+.2%})")
        except Exception as exc:
            print(f"{symbol}: ERROR settling {row['as_of_date']} — {exc}")
    if changed:
        write_rows(rows)
    print(f"Settled {changed} prediction(s).")


def product(returns: list[float]) -> float:
    x = 1.0
    for r in returns:
        x *= 1.0 + r
    return x - 1.0


def report() -> None:
    rows = [r for r in read_rows() if r.get("target_date")]
    if not rows:
        print("No settled predictions yet. Run predict after market close; settle after next session closes.")
        return
    for symbol in sorted({r["symbol"] for r in rows}):
        group = sorted((r for r in rows if r["symbol"] == symbol), key=lambda r: r["target_date"])
        n = len(group)
        ys = [int(r["was_up"]) for r in group]
        ps = [float(r["p_up"]) for r in group]
        n_correct = sum((p >= 0.5) == bool(y) for p, y in zip(ps, ys))
        brier = sum((p-y)**2 for p, y in zip(ps,ys)) / n
        constant_brier = sum((0.5-y)**2 for y in ys) / n
        long_returns = [float(r["long_trade_net"]) for r in group]
        bench_returns = [float(r["benchmark_always_long_net"]) for r in group]
        trades = sum(p >= LONG_THRESHOLD for p in ps)
        wins = sum(float(r["long_trade_net"]) > 0 for r in group if float(r["p_up"]) >= LONG_THRESHOLD)
        # Buy-and-hold is context only; it includes overnight returns, unlike the paper intraday trades.
        buyhold = float(group[-1]["next_close"]) / float(group[0]["next_open"]) - 1.0
        print(f"\n{symbol} | {n} settled prediction(s) | {group[0]['target_date']} to {group[-1]['target_date']}")
        print(f"  Jev direction accuracy      : {n_correct/n:.1%} ({n_correct}/{n})")
        print(f"  Always-UP accuracy          : {sum(ys)/n:.1%}")
        print(f"  Brier score (lower better)  : {brier:.4f}; 50% baseline {constant_brier:.4f}")
        print(f"  Paper longs at >={LONG_THRESHOLD:.0%}        : {trades}; net-positive trades {wins}")
        leveraged_trades = [r for r in group if r.get("leveraged_symbol") and r.get("leveraged_net")]
        lev_gains = [float(r["leveraged_net"]) if r.get("leveraged_net") else 0.0 for r in group]
        signal_gains = [float(r.get("underlying_signal_net") or 0) for r in group]
        print(f"  Leveraged 3x paper trades   : {len(leveraged_trades)}; positive {sum(float(r['leveraged_net']) > 0 for r in leveraged_trades)}")
        print(f"  Leveraged/cash growth       : {product(lev_gains):+.2%} (sequential allocation, 10bp/trade)")
        print(f"  Underlying signal/cash      : {product(signal_gains):+.2%} (hypothetical shorts on DOWN)")
        print(f"  Jev paper-long/cash growth  : {product(long_returns):+.2%}")
        print(f"  Always-long intraday growth : {product(bench_returns):+.2%}")
        print(f"  Buy/hold during span*       : {buyhold:+.2%}")
        for lo, hi in [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0000001)]:
            bucket = [(p, y) for p, y in zip(ps, ys) if lo <= p < hi]
            if bucket:
                print(f"    P(up) {lo:.0%}–{min(hi,1):.0%}: n={len(bucket)}, avg predicted {sum(p for p,_ in bucket)/len(bucket):.1%}, realized UP {sum(y for _,y in bucket)/len(bucket):.1%}")
        print("  *Buy/hold includes overnight gaps, so it is not an equal-exposure comparison.")
        if n < 60:
            print("  CAUTION: fewer than 60 observations; no statistical edge established.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jev daily ETF paper-only forward-test")
    parser.add_argument("command", choices=["predict", "settle", "report"])
    parser.add_argument("--cohort", choices=["baseline", "enriched"], default="enriched")
    parser.add_argument("--backend", choices=["minicpm", "typesafe"], default="minicpm")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ"], help="US ETF tickers (default: SPY QQQ)")
    args = parser.parse_args()
    global DATA_FILE, COHORT
    COHORT = args.cohort
    DATA_FILE = Path(__file__).with_name("predictions.csv" if COHORT == "baseline" else "predictions_enriched.csv")
    os.environ["JEV_BACKEND"] = args.backend
    if args.command == "predict":
        predict([s.strip().upper() for s in args.symbols])
    elif args.command == "settle":
        settle()
    else:
        report()


if __name__ == "__main__":
    main()
