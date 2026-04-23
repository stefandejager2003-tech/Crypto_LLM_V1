import pandas as pd
import numpy as np

def get_signals(df):
    """
    Generate trading signals based on CVD trend, z‑scores, and volume,
    with ATR‑based stop loss and 10‑bar time exit.
    """
    # Ensure required columns exist (they should be pre‑computed)
    required = ['cvd_trend', 'close_zscore_50', 'volume_zscore_24', 'atr_14']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Initialize columns for output
    df = df.copy()
    df['signal'] = 0
    df['stop_price'] = np.nan
    df['exit_bar'] = np.nan
    df['position_size'] = np.nan
    
    # State variables
    position = 0               # 0: flat, 1: long, -1: short
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    exit_idx = 0
    
    # Iterate over DataFrame
    for i in range(len(df)):
        row = df.iloc[i]
        close = row['close']
        high = row['high']
        low = row['low']
        atr = row['atr_14']
        close_zscore = row['close_zscore_50']
        
        # If we are currently in a position
        if position != 0:
            # Check stop loss
            stop_triggered = False
            if position == 1 and low <= stop_price:
                stop_triggered = True
            elif position == -1 and high >= stop_price:
                stop_triggered = True
            
            # Check time exit
            time_exit = i >= exit_idx
            
            # Check z-score exit condition (HYPOTHESIS: Exit long when close_zscore_50 > -0.5, exit short when close_zscore_50 < 0.5)
            zscore_exit = False
            if position == 1 and close_zscore > -0.5:
                zscore_exit = True
            elif position == -1 and close_zscore < 0.5:
                zscore_exit = True
            
            # Exit if any condition met
            if stop_triggered or time_exit or zscore_exit:
                position = 0
                # signal for this bar is 0 (already flat)
                # (we could set a signal to indicate exit, but backtester uses signal column for desired position)
                # We'll keep signal 0 for this bar (no new entry)
                # Clear auxiliary columns for this bar (they remain NaN)
                pass
            else:
                # Maintain position
                df.loc[i, 'signal'] = position
                df.loc[i, 'stop_price'] = stop_price
                df.loc[i, 'exit_bar'] = exit_idx
                # Position size inversely proportional to ATR (normalized by 1/ATR)
                df.loc[i, 'position_size'] = 1.0 / atr if atr > 0 else 1.0
                continue
        
        # If flat, check entry conditions
        if position == 0:
            # Long condition (HYPOTHESIS: Buy when close_zscore_50 < -1.5, cvd_trend > 0, volume_zscore_24 > 1)
            if (row['cvd_trend'] > 0 and 
                row['close_zscore_50'] < -1.5 and 
                row['volume_zscore_24'] > 1.0):
                position = 1
                entry_price = close
                entry_idx = i
                stop_price = close - 2.0 * atr
                exit_idx = i + 10
                df.loc[i, 'signal'] = 1
                df.loc[i, 'stop_price'] = stop_price
                df.loc[i, 'exit_bar'] = exit_idx
                df.loc[i, 'position_size'] = 1.0 / atr if atr > 0 else 1.0
            # Short condition (symmetric opposite for mean reversion)
            elif (row['cvd_trend'] < 0 and 
                  row['close_zscore_50'] > 1.5 and 
                  row['volume_zscore_24'] > 1.0):
                position = -1
                entry_price = close
                entry_idx = i
                stop_price = close + 2.0 * atr
                exit_idx = i + 10
                df.loc[i, 'signal'] = -1
                df.loc[i, 'stop_price'] = stop_price
                df.loc[i, 'exit_bar'] = exit_idx
                df.loc[i, 'position_size'] = 1.0 / atr if atr > 0 else 1.0
            # else remain flat (signal stays 0)
    
    return df
