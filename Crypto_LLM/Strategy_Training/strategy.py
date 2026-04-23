import pandas as pd
import numpy as np

def get_signals(df):
    """
    Generate trading signals based on composite signal S:
    S = (-close_zscore_50 * cvd_trend * volume_zscore_24) / atr_14
    
    Entry long when S > 1.0, entry short when S < -1.0.
    Exit long when S < 0.5, exit short when S > -0.5.
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
    df['composite_signal'] = np.nan  # For debugging/inspection
    
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
        atr = row['atr_14']
        
        # Compute composite signal S
        # Avoid division by zero (use a small epsilon)
        atr_safe = atr if atr != 0 else 1e-8
        S = (-row['close_zscore_50'] * row['cvd_trend'] * row['volume_zscore_24']) / atr_safe
        df.loc[i, 'composite_signal'] = S
        
        # If we are currently in a position
        if position != 0:
            # Check exit conditions based on composite signal
            exit_long = (position == 1) and (S < 0.5)
            exit_short = (position == -1) and (S > -0.5)
            
            # Exit if condition met
            if exit_long or exit_short:
                position = 0
                # signal for this bar is 0 (already flat)
                # auxiliary columns remain NaN for this bar
                pass
            else:
                # Maintain position
                df.loc[i, 'signal'] = position
                df.loc[i, 'stop_price'] = stop_price
                df.loc[i, 'exit_bar'] = exit_idx
                # Position size inversely proportional to ATR (normalized by 1/ATR)
                df.loc[i, 'position_size'] = 1.0 / atr_safe
                continue
        
        # If flat, check entry conditions
        if position == 0:
            # Long condition: S > 1.0
            if S > 1.0:
                position = 1
                entry_price = close
                entry_idx = i
                # Stop loss at 2 ATR below entry (kept for risk management)
                stop_price = close - 2.0 * atr_safe
                exit_idx = i + 10  # Keep time exit as fallback (though not used in new logic)
                df.loc[i, 'signal'] = 1
                df.loc[i, 'stop_price'] = stop_price
                df.loc[i, 'exit_bar'] = exit_idx
                df.loc[i, 'position_size'] = 1.0 / atr_safe
            # Short condition: S < -1.0
            elif S < -1.0:
                position = -1
                entry_price = close
                entry_idx = i
                stop_price = close + 2.0 * atr_safe
                exit_idx = i + 10
                df.loc[i, 'signal'] = -1
                df.loc[i, 'stop_price'] = stop_price
                df.loc[i, 'exit_bar'] = exit_idx
                df.loc[i, 'position_size'] = 1.0 / atr_safe
            # else remain flat (signal stays 0)
    
    return df
