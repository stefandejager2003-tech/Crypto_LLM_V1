import pandas as pd
import numpy as np
import os
import sys

# Constants
FEE = 0.002
# Multipliers for Sharpe Ratio (Intervals per year)
TIMEFRAME_MULTIPLIERS = {
    "1m": 525600,
    "5m": 105120,
    "15m": 35040,
    "1h": 8760, 
    "4h": 2190, 
    "1d": 365
}

def fetch_data(symbol, timeframe, period):
    # 1. Clean inputs
    clean_tf = timeframe.lower()
    symbol_base = symbol.split('/')[0].lower()
    tf_folder = f"{clean_tf.upper()}_Candle_Data"
    
    # 2. Path resolution
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(
        script_dir, 
        "Candle_Data", 
        tf_folder, 
        f"{symbol_base}_{clean_tf}_{period}.csv"
    )
    
    if not os.path.exists(filename):
        print(f"❌ Error: Data not found at {filename}")
        return pd.DataFrame()
        
    # Loaded with index_col=0 to catch 'timestamp' as index
    df = pd.read_csv(filename, index_col=0, parse_dates=True)
    return df

def evaluate_strategy(symbol, timeframe, period):
    try:
        import importlib
        import strategy
        importlib.reload(strategy)
        from strategy import get_signals

        # 1. Get Data
        df = fetch_data(symbol, timeframe, period)
        if df.empty: return -1.0

        # 2. Run Strategy
        df = get_signals(df)
        if 'signal' not in df.columns: return -1.0
        
        # Ensure signal is clean (-1, 0, 1)
        df['signal'] = np.sign(df['signal'].fillna(0))
        
        # 3. Returns & Fees 
        # Using the PRE-CALCULATED 'log_return' from your new format
        df['strat_ret'] = df['signal'].shift(1) * df['log_return']
        
        # Transaction Costs
        trades_series = df['signal'].diff().abs().fillna(0)
        df['strat_ret'] -= (trades_series * FEE)
        df = df.dropna()

        # 4. Metrics
        df['equity'] = np.exp(df['strat_ret'].cumsum())
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
        
        max_dd = df['drawdown'].min()
        total_return = df['equity'].iloc[-1] - 1
        returns = df['strat_ret']
        
        # Dynamic Sharpe Calculation based on input timeframe
        intervals_per_year = TIMEFRAME_MULTIPLIERS.get(timeframe, 8760)
        ann_factor = np.sqrt(intervals_per_year)
        std = returns.std()
        sharpe = (returns.mean() / std) * ann_factor if std > 1e-8 else -1.0
        
        trade_count = int(trades_series.sum()) # Number of signal changes
        win_rate = (returns > 0).mean() if trade_count > 0 else 0
        
        # Expectancy and RR
        avg_win = returns[returns > 0].mean() if (returns > 0).any() else 0
        avg_loss = abs(returns[returns < 0].mean()) if (returns < 0).any() else 1e-8
        rr_ratio = avg_win / avg_loss
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        # 5. Penalties (-1.0 each)
        adjustment = 0.0
        if total_return <= 0: adjustment -= 1.0
        if max_dd < -0.15: adjustment -= 1.0
        if win_rate < 0.40: adjustment -= 1.0
        if rr_ratio < 2.0: adjustment -= 1.0
        if trade_count < 50: adjustment -= 1.0 # Adjusted for various timeframes
        if expectancy < FEE: adjustment -= 1.0

        raw_score = (sharpe * 0.3) + (total_return * 0.2) + (expectancy * 100 * 0.3)
        final_score = raw_score + adjustment

        print(f"""
            --- REPORT [{timeframe} | {period}] ---
            Sharpe Ratio  : {sharpe:.2f}
            Total Return  : {total_return:.2%}
            Max Drawdown  : {max_dd:.2%}
            Win Rate      : {win_rate:.2%}
            Risk:Reward   : {rr_ratio:.2f}
            Expectancy    : {expectancy:.4f}
            Total Trades  : {trade_count}
            ---------------------------------
            RAW SCORE     : {raw_score:.4f}
            ADJUSTMENT    : {adjustment:+.2f}
            FINAL SCORE   : {final_score:.4f}
            """)
            
        return final_score

    except Exception as e:
        print(f"[!] Critical Judge Error: {e}")
        return -10.0

if __name__ == "__main__":
    # Handle command line args for the Auto Loop
    # Usage: python evaluator.py btc 15m 1y
    s = sys.argv[1] if len(sys.argv) > 1 else "btc"
    t = sys.argv[2] if len(sys.argv) > 2 else "1h"
    p = sys.argv[3] if len(sys.argv) > 3 else "3y"

    score = evaluate_strategy(s, t, p)
    print(f"FINAL_RESULT:{score}")