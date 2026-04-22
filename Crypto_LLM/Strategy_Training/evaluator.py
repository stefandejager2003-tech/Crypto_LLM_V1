import pandas as pd
import numpy as np
import os
import sys

# Constants for your specific setup
FEE = 0.0006 
TIMEFRAME = "1h"
TIMEFRAME_MULTIPLIERS = {"1h": 8760, "4h": 2190, "1d": 365}

def fetch_data(period):
    # Load your specific CSV here
    df = pd.read_csv(f"../data/btc_1h_{period}.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df

def evaluate_strategy(target_period):
    try:
        import importlib
        import strategy
        importlib.reload(strategy)
        from strategy import get_signals

        # 1. Get Data
        df = fetch_data(target_period)
        if df.empty: return -1.0

        # 2. Run Strategy
        df = get_signals(df)
        if 'signal' not in df.columns: return -1.0
        df['signal'] = np.sign(df['signal'].fillna(0))
        
        # 3. Returns & Fees
        df['market_log_ret'] = np.log(df['close'] / df['close'].shift(1))
        df['strat_ret'] = df['signal'].shift(1) * df['market_log_ret']
        trades_series = df['signal'].diff().abs().fillna(0)
        df['strat_ret'] -= (trades_series * FEE)
        df = df.dropna()

        # 4. Metrics Calculation
        df['equity'] = np.exp(df['strat_ret'].cumsum())
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
        
        max_dd = df['drawdown'].min()
        total_return = df['equity'].iloc[-1] - 1
        returns = df['strat_ret']
        
        # Sharpe Calculation
        ann_factor = np.sqrt(TIMEFRAME_MULTIPLIERS.get(TIMEFRAME, 8760))
        std = returns.std()
        sharpe = (returns.mean() / std) * ann_factor if std > 1e-8 else -1.0
        
        # Trade Analysis
        trade_count = int(trades_series.sum() / 2)
        win_rate = (returns > 0).mean() if trade_count > 0 else 0
        
        # RR Calculation (Avg Win / Avg Loss)
        avg_win = returns[returns > 0].mean() if (returns > 0).any() else 0
        avg_loss = abs(returns[returns < 0].mean()) if (returns < 0).any() else 1e-8
        rr_ratio = avg_win / avg_loss

        # Expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        # Consistency
        yearly_rets = df.groupby(df.index.year)['strat_ret'].sum()
        losing_years = int((yearly_rets < 0).sum())

        # 5. Score Logic
        raw_score = (sharpe * 0.3) + (total_return * 0.2) + (expectancy * 100 * 0.3) + ((1 + max_dd) * 0.2)

        # 6. UPDATED PENALTIES (-1.0 each per your requirements)
        adjustment = 0.0
        
        if total_return <= 0:
            adjustment -= 1.0  # Penalty: Return <= 0%
            
        if max_dd < -0.15:
            adjustment -= 1.0  # Penalty: Drawdown >= 15%
            
        if win_rate < 0.40:
            adjustment -= 1.0  # Penalty: Win Rate <= 40%
            
        if rr_ratio < 2.0:
            adjustment -= 1.0  # Penalty: RR Ratio < 1:2
            
        if losing_years > 0:
            adjustment -= 1.0  # Penalty: Any losing years
            
        if trade_count < 70:
            adjustment -= 1.0  # Penalty: Total Trades <= 70
        if expectancy < FEE:
            adjustment -= 1.0  # Penalty: overtrading in fees

        # REWARDS (Optional: kept for high performance cases)
        # if max_dd > -0.15 and trade_count >= MIN_TRADES:
        #     adjustment += 0.5  
        # if win_rate > 0.60:
        #     adjustment += 0.5  
        # if total_return > 0.50:
        #     adjustment += 1.0  
        # if expectancy > (FEE * 3):
        #     adjustment += 1.0  High quality "Alpha"

        final_score = raw_score + adjustment

        print(f"""
            --- PERFORMANCE REPORT [{target_period}] ---
            Sharpe Ratio  : {sharpe:.2f}
            Total Return  : {total_return:.2%}
            Max Drawdown  : {max_dd:.2%}
            Win Rate      : {win_rate:.2%}
            Risk:Reward   : {rr_ratio:.2f}
            Expectancy    : {expectancy:.4f}
            Losing Years  : {losing_years}
            Total Trades  : {trade_count}
            ---------------------------------
            RAW SCORE     : {raw_score:.4f}
            ADJUSTMENT    : {adjustment:+.2f}
            FINAL SCORE   : {final_score:.4f}
            """)
            
        return final_score

    except Exception as e:
        print(f"[!] Critical Judge Error: {e}")
        import traceback
        traceback.print_exc()
        return -10.0

if __name__ == "__main__":
    # This runs when the Auto Loop calls: python evaluator.py
    # You can change "3y" to whatever period you want to test
    score = evaluate_strategy("3y")
    
    # This is the line the Auto Loop is listening for!
    print(f"FINAL_RESULT:{score}")