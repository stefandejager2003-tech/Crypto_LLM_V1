import pandas as pd
import numpy as np

def get_signals(df): # Renamed to match backtester's strat.apply_strategy call
    # 1. Indicators
    df['ema_200'] = df['close'].ewm(span=200).mean()
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    
    # 2. Logic Initialization
    df['signal'] = 0 

    # 3. Vectorized Signal Assignment
    # Long = 1, Short = -1
    df.loc[(df['close'] > df['ema_200']) & (df['ema_9'] > df['ema_21']), 'signal'] = 1
    df.loc[(df['close'] < df['ema_200']) & (df['ema_9'] < df['ema_21']), 'signal'] = -1

    return df