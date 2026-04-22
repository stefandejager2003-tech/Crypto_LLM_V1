import pandas as pd
import numpy as np
import os
import sys
import importlib.util
from tabulate import tabulate

class ProBacktester:
    def __init__(self, strategy_path="strategy.py", initial_capital=200, fee=0.002):
        self.strategy_path = strategy_path
        self.initial_capital = initial_capital
        self.fee = fee 
        self.results = {}

    def _load_strategy(self):
        """Dynamically loads and validates the strategy module."""
        if not os.path.exists(self.strategy_path):
            print(f"❌ Error: {self.strategy_path} not found.")
            sys.exit(1)

        try:
            spec = importlib.util.spec_from_file_location("strategy", self.strategy_path)
            strat_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(strat_mod)
            
            # VALIDATION: Check for the required function
            if not hasattr(strat_mod, 'get_signals'):
                raise AttributeError("strategy.py must contain a 'get_signals(df)' function.")
                
            return strat_mod
        except Exception as e:
            print(f"❌ CRITICAL LOAD ERROR: {e}")
            sys.exit(1)

    def run_test(self, data_path, label):
        if not os.path.exists(data_path):
            print(f"⚠️ Skipping {label}: File not found at {data_path}")
            return

        df = pd.read_csv(data_path)
        
        # Load and execute strategy
        strat = self._load_strategy()
        df = strat.get_signals(df)

        # VALIDATION: Ensure the user's script actually produced signals
        if 'signal' not in df.columns:
            # Automatic Fix: If user has 'long_signal' and 'short_signal', merge them
            if 'long_signal' in df.columns and 'short_signal' in df.columns:
                df['signal'] = 0
                df.loc[df['long_signal'] == True, 'signal'] = 1
                df.loc[df['short_signal'] == True, 'signal'] = -1
            else:
                print(f"❌ Error in {label}: strategy.py failed to create a 'signal' column.")
                return

        # 1. Calculate Returns
        df['market_return'] = df['close'].pct_change()
        df['strat_return'] = df['signal'].shift(1) * df['market_return']
        
        # 2. Apply Fees (on signal changes)
        df['trade_executed'] = df['signal'].diff().fillna(0).abs()
        df['strat_return_net'] = df['strat_return'] - (df['trade_executed'] * self.fee)
        
        # 3. Equity Curve
        df['equity_curve'] = (1 + df['strat_return_net'].fillna(0)).cumprod()
        df['portfolio_value'] = df['equity_curve'] * self.initial_capital
        
        self.results[label] = self._calculate_metrics(df)
        print(f"✅ Success: {label} processing complete.")

    def _calculate_metrics(self, df):
        # Time-based metrics
        total_return = (df['equity_curve'].iloc[-1] - 1) * 100
        net_profit = df['portfolio_value'].iloc[-1] - self.initial_capital
        
        trades = df[df['trade_executed'] != 0]['strat_return_net']
        if len(trades) == 0:
            return {k: "N/A" for k in ["Total Return (%)", "Win Rate (%)", "Sharpe", "Max DD"]}

        win_rate = (len(trades[trades > 0]) / len(trades)) * 100
        
        # Profit Factor
        gross_profit = trades[trades > 0].sum()
        gross_loss = abs(trades[trades < 0].sum())
        pf = gross_profit / gross_loss if gross_loss != 0 else np.inf
        
        # Drawdown
        rolling_max = df['equity_curve'].cummax()
        drawdown = (df['equity_curve'] - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100
        
        # Risk Adjusted (Annualized for 1H)
        returns = df['strat_return_net'].dropna()
        sharpe = (returns.mean() / returns.std()) * np.sqrt(8760) if returns.std() != 0 else 0
        
        # Smoothness (R-Squared)
        x = np.arange(len(df))
        y = df['equity_curve'].values
        slope, intercept = np.polyfit(x, y, 1)
        r_squared = 1 - (np.sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y)))

        return {
            "Total Return (%)": f"{total_return:.2f}%",
            "Net Profit ($)": f"${net_profit:.2f}",
            "Win Rate (%)": f"{win_rate:.2f}%",
            "Profit Factor": f"{pf:.2f}",
            "Max Drawdown": f"{max_dd:.2f}%",
            "Sharpe Ratio": f"{sharpe:.2f}",
            "Equity Smoothness": f"{r_squared:.4f}",
            "Trade Count": len(trades)
        }

    def print_report(self):
        if not self.results:
            print("No results to display.")
            return
            
        report_data = []
        for label, metrics in self.results.items():
            row = [label] + list(metrics.values())
            report_data.append(row)
        
        headers = ["Horizon"] + list(next(iter(self.results.values())).keys())
        print("\n" + "="*110)
        print("📊 INSTITUTIONAL STRATEGY PERFORMANCE REPORT")
        print("="*110)
        print(tabulate(report_data, headers=headers, tablefmt="grid"))

if __name__ == "__main__":
    tester = ProBacktester(strategy_path=r"C:\Users\Stefa\OneDrive\Desktop\Crypto_LLM_V4\Crypto_LLM\strategy.py")
    
    # YOUR SPECIFIC PATHS
    base_path = r"C:\Users\Stefa\OneDrive\Desktop\Crypto_LLM_V4\Crypto_LLM\Candle_Data\1H_Candle_Data"
    
    tester.run_test(os.path.join(base_path, "btc_1h_3m.csv"), "3-MONTH")
    tester.run_test(os.path.join(base_path, "btc_1h_1y.csv"), "1-YEAR")
    tester.run_test(os.path.join(base_path, "btc_1h_3y.csv"), "3-YEAR")
    
    tester.print_report()