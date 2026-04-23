import os
import time
import pandas as pd
import numpy as np
import ccxt
from tqdm import tqdm

# ---------------- CONFIGURATION ----------------
SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '1h'    # Change this to '1m', '15m', etc.
STATIC_PERIODS = ['3m', '1y', '3y'] # These stay static
# -----------------------------------------------

def fetch_data_for_period(exchange, symbol, timeframe, period):
    """Internal function to handle the fetch for a single period."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    clean_tf = timeframe.lower().replace('/', '').replace(':', '')
    symbol_clean = symbol.split('/')[0].lower()
    
    # Path setup
    data_dir = os.path.join(script_dir, f"{clean_tf.upper()}_Candle_Data")
    os.makedirs(data_dir, exist_ok=True)
    filename = os.path.join(data_dir, f"{symbol_clean}_{clean_tf}_{period}.csv")

    # 1. Load Existing Data
    if os.path.exists(filename):
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        since = int(df.index[-1].timestamp() * 1000) + 1
    else:
        df = pd.DataFrame()
        val = int(period[:-1])
        days = val * 365 if 'y' in period else val * 30
        since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)

    # 2. Fetch Loop
    all_ohlcv = []
    pbar = tqdm(desc=f"Fetching {timeframe} | {period}", leave=False)
    
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit=1000)
            if not ohlcv: break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            pbar.update(len(ohlcv))
            if ohlcv[-1][0] >= (exchange.milliseconds() - 60000): break
            time.sleep(exchange.rateLimit / 1000)
        except Exception as e:
            time.sleep(5)
            
    pbar.close()

    # 3. Processing & Strict Tail Trimming
    if all_ohlcv:
        new_df = pd.DataFrame(all_ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        new_df['timestamp'] = pd.to_datetime(new_df['ts'], unit='ms')
        new_df.set_index('timestamp', inplace=True)
        df = pd.concat([df, new_df.drop(columns=['ts'])])
        
    if df.empty: return

    # Remove duplicates and ensure chronological order
    df = df[~df.index.duplicated(keep='last')].sort_index()

    # --- THE SLIDING WINDOW (Strict 3m, 1y, 3y) ---
    val = int(period[:-1])
    if 'y' in period:
        cutoff_date = df.index[-1] - pd.DateOffset(years=val)
    else: # 'm'
        cutoff_date = df.index[-1] - pd.DateOffset(months=val)

    # Only keep data AFTER the cutoff
    df = df[df.index >= cutoff_date]

    # --- V2 FEATURES (Update this section) ---
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    df['atr_14'] = (df['high'] - df['low']).rolling(14).mean()
    df['close_zscore_50'] = (df['close'] - df['close'].rolling(50).mean()) / df['close'].rolling(50).std()

    # ADD THIS LINE:
    df['volume_zscore_24'] = (df['volume'] - df['volume'].rolling(24).mean()) / df['volume'].rolling(24).std()

    df['cvd'] = ((df['close'] - df['open']) / (df['high'] - df['low']).replace(0, 1)) * df['volume']
    df['cvd_trend'] = df['cvd'].rolling(window=20).mean()
    
    # Save the cleaned, perfectly-sized window
    df.dropna().to_csv(filename)
    print(f"[✓] Window Updated: {filename} ({len(df)} rows | Starts: {df.index[0]})")

def run_multi_fetch():
    print(f"🚀 Starting Multi-Regime Fetch for {TIMEFRAME}...")
    exchange = ccxt.bybit({'enableRateLimit': True})
    
    for period in STATIC_PERIODS:
        fetch_data_for_period(exchange, SYMBOL, TIMEFRAME, period)
    
    print("\n✅ All regimes are up to date.")

if __name__ == "__main__":
    run_multi_fetch()