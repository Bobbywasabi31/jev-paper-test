"""Point-in-time daily market features. No intraday data or future bar access."""
import math

CROSS_ASSETS = {
    '^VIX': 'vix', '^TNX': 'us10y_yield_proxy', 'DX-Y.NYB': 'dollar_index',
    'TLT': 'long_treasury', 'HYG': 'high_yield_credit', 'GLD': 'gold',
    'USO': 'oil_etf', 'XLK': 'technology', 'XLF': 'financials',
    'ES=F': 'sp500_futures', 'NQ=F': 'nasdaq_futures',
}


def _number(value, digits=4):
    v = float(value)
    return round(v, digits) if math.isfinite(v) else None


def enrich(df, as_of, symbol, *, loader):
    """Build an enriched snapshot using data through as_of only.

    loader is dependency-injected for offline tests. Fail closed if underlying
    anchor history is incomplete; optional cross-assets fail open with notes.
    """
    import pandas as pd
    anchor = df.loc[df.index <= as_of]
    if len(anchor) < 201:
        raise ValueError('Need at least 201 historical daily sessions for enriched indicators')
    c, h, l, v = [anchor[k].astype(float) for k in ('Close', 'High', 'Low', 'Volume')]
    if (c <= 0).any() or (v < 0).any():
        raise ValueError('Invalid anchor market prices or volume')
    d = c.diff()
    gain = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain.iloc[-1] / max(loss.iloc[-1], 1e-12))
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    prevclose = c.shift(1)
    true_range = pd.concat([h-l, (h-prevclose).abs(), (l-prevclose).abs()],axis=1).max(axis=1)
    returns = c.pct_change()
    close = float(c.iloc[-1])
    base = {
        'data_cutoff_session': as_of,
        'close_usd': _number(close),
        'returns_pct': {str(n): _number(100*(close/float(c.iloc[-n-1])-1),3) for n in (1,2,5,10,20,60,200)},
        'sma_distance_pct': {str(n): _number(100*(close/float(c.iloc[-n:].mean())-1),3) for n in (10,20,50,200)},
        'rsi_14': _number(rsi,2),
        'macd_pct_of_close': _number(100*float(macd.iloc[-1])/close,3),
        'macd_histogram_pct_of_close': _number(100*float(macd.iloc[-1]-signal.iloc[-1])/close,3),
        'atr_14_pct_of_close': _number(100*true_range.iloc[-14:].mean()/close,3),
        'realized_daily_volatility_pct': {str(n): _number(100*returns.iloc[-n:].std(ddof=0),3) for n in (5,10,20,60)},
        'relative_volume_20': _number(v.iloc[-1]/max(float(v.iloc[-21:-1].mean()),1),3),
        'volume_trend_5_over_20': _number(v.iloc[-5:].mean()/max(float(v.iloc[-20:].mean()),1),3),
        'range_position_20': _number((close-l.iloc[-20:].min()) / max(float(h.iloc[-20:].max()-l.iloc[-20:].min()),1e-12),3),
        'last_candle': {'open': _number(anchor['Open'].iloc[-1]), 'high': _number(h.iloc[-1]), 'low': _number(l.iloc[-1]), 'close':_number(close)},
    }
    cross, missing = {}, {}
    for ticker, name in CROSS_ASSETS.items():
        try:
            hist = loader(ticker)
            hist = hist.loc[hist.index <= as_of]
            if len(hist) < 6:
                missing[name] = 'insufficient historical bars'; continue
            last_date = hist.index[-1]
            if (pd.Timestamp(as_of) - pd.Timestamp(last_date)).days > 4:
                missing[name] = f'stale last candle {last_date}'; continue
            prices = hist['Close'].astype(float)
            if not (prices.iloc[-1] > 0 and prices.iloc[-2] > 0 and prices.iloc[-6] > 0):
                missing[name] = 'invalid price'; continue
            cross[name] = {'ticker': ticker, 'session': last_date,
                           'close': _number(prices.iloc[-1]),
                           'one_session_return_pct': _number(100*(prices.iloc[-1]/prices.iloc[-2]-1),3),
                           'five_session_return_pct': _number(100*(prices.iloc[-1]/prices.iloc[-6]-1),3)}
        except Exception as exc:
            missing[name] = f'unavailable: {type(exc).__name__}'
    base['cross_assets'] = cross
    base['unavailable_cross_assets'] = missing
    base['data_note'] = ('Daily closing bars only; no future candles; futures settlements and '
                         'vendor updates may lag the actual market session; missing signals not imputed')
    return base
