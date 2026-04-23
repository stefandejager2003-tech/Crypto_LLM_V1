import pandas as pd
import numpy as np

def get_signals(df):
    df = df.copy()

    # 1. SELF-HEALING: Calculate missing indicators on the fly
    if 'ema_50' not in df.columns:
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    if 'ema_200' not in df.columns:
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    if 'atr_14' not in df.columns:
        df['atr_14'] = (df['high'] - df['low']).rolling(14).mean()
    if 'rsi_14' not in df.columns:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))

    # Fill NaNs from warm-up to prevent loop crashes
    df = df.fillna(0)

    n = len(df)
    signals = np.zeros(n)
    stops = np.full(n, np.nan)
    tps = np.full(n, np.nan)

    current_pos = 0
    stop_price = 0
    tp_price = 0

    # Extract values to numpy for speed
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    ema50 = df['ema_50'].values
    ema200 = df['ema_200'].values
    rsi = df['rsi_14'].values
    atr = df['atr_14'].values

    # 2. DYNAMIC WARM-UP: Start loop after the longest indicator is ready (200 EMA)
    for i in range(200, n):
        if current_pos != 0:
            exit_trade = False
            # Check Exit Conditions
            if current_pos == 1:
                if low[i] <= stop_price or high[i] >= tp_price:
                    exit_trade = True
            elif current_pos == -1:
                if high[i] >= stop_price or low[i] <= tp_price:
                    exit_trade = True

            if exit_trade:
                current_pos = 0
                stop_price = 0
                tp_price = 0
            else:
                signals[i] = current_pos
                stops[i] = stop_price
                tps[i] = tp_price
        else:
            # TREND FILTER
            uptrend = ema50[i] > ema200[i]
            downtrend = ema50[i] < ema200[i]

            # LONG: Trend up + RSI Pullback + Bullish Candle
            if uptrend and close[i] > ema50[i] and rsi[i] < 40 and close[i] > close[i-1]:
                current_pos = 1
                stop_price = close[i] - (1.5 * atr[i])
                tp_price = close[i] + (3.0 * atr[i])

            # SHORT: Trend down + RSI Overbought + Bearish Candle
            elif downtrend and close[i] < ema50[i] and rsi[i] > 60 and close[i] < close[i-1]:
                current_pos = -1
                stop_price = close[i] + (1.5 * atr[i])
                tp_price = close[i] - (3.0 * atr[i])

            signals[i] = current_pos
            stops[i] = stop_price
            tps[i] = tp_price

    df['signal'] = signals
    df['stop_price'] = stops
    df['tp_price'] = tps
    return df