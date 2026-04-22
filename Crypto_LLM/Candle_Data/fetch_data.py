import os
import time
import pandas as pd
import ccxt
from tqdm import tqdm

# ---------------- CONFIGURATION (EDIT ONLY THIS) ----------------
SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '15m'    # '1m', '5m', '15m', '1h', '4h', '1d'
PERIOD = '3y'        # '30d', '3m', '6m', '1y', '2y', '3y'
# ---------------------------------------------------------------


def fetch_data():
    def parse_period(period_str):
        unit = period_str[-1]
        value = int(period_str[:-1])
        if unit == 'y':
            return value * 365
        elif unit == 'm':
            return value * 30
        elif unit == 'd':
            return value
        else:
            raise ValueError(f"Invalid period: {period_str}")

    tf_to_hours = {
        '1m': 1/60,
        '5m': 5/60,
        '15m': 15/60,
        '1h': 1,
        '4h': 4,
        '1d': 24
    }

    # -------- PATH SETUP (YOUR FORMAT) --------
    script_dir = os.path.dirname(os.path.abspath(__file__))

    clean_tf = TIMEFRAME.lower().replace('/', '').replace(':', '')
    symbol_clean = SYMBOL.split('/')[0].lower()

    # Convert timeframe to folder name (e.g. 15M_Candle_Data)
    tf_folder_name = f"{clean_tf.upper()}_Candle_Data"

    base_dir = os.path.join(script_dir, "Candle_Data")
    data_dir = os.path.join(base_dir, tf_folder_name)

    os.makedirs(data_dir, exist_ok=True)

    filename = os.path.join(data_dir, f"{symbol_clean}_{clean_tf}_{PERIOD}.csv")
    # -----------------------------------------

    exchange = ccxt.bybit({'enableRateLimit': True})

    if os.path.exists(filename):
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index)
        print(f"[*] Found local data: {len(df)} candles")
    else:
        df = pd.DataFrame()

    days_to_fetch = parse_period(PERIOD)
    now_ms = exchange.milliseconds()
    hours_per_candle = tf_to_hours.get(TIMEFRAME, 1)

    if not df.empty:
        last_ts = int(df.index[-1].timestamp() * 1000)
        since = last_ts + 1
        ms_diff = now_ms - last_ts
        total_needed = max(1, int(ms_diff / (1000 * 60 * 60 * hours_per_candle)))
        print(f"[*] Resuming {PERIOD} ({TIMEFRAME})...")
    else:
        since = now_ms - (days_to_fetch * 24 * 60 * 60 * 1000)
        candles_per_day = int(24 / hours_per_candle)
        total_needed = days_to_fetch * candles_per_day
        print(f"[*] Fresh fetch: {PERIOD} ({TIMEFRAME})...")

    all_ohlcv = []
    batch_size = 200
    pbar = tqdm(total=total_needed, desc=f"{TIMEFRAME} | {PERIOD}")

    max_retries = 5
    retry_count = 0

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(
                SYMBOL,
                timeframe=TIMEFRAME,
                since=since,
                limit=batch_size
            )

            if not ohlcv:
                retry_count += 1
                if retry_count > max_retries:
                    break
                time.sleep(2)
                continue

            retry_count = 0
            all_ohlcv.extend(ohlcv)

            last_ts = ohlcv[-1][0]
            since = last_ts + 1

            pbar.update(len(ohlcv))

            if last_ts >= (exchange.milliseconds() - 3600000):
                print("\n[*] Up to date.")
                break

            time.sleep(exchange.rateLimit / 1000)

        except Exception as e:
            print(f"[!] API Error: {e}")
            time.sleep(5)

    pbar.close()

    if all_ohlcv:
        new_df = pd.DataFrame(
            all_ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
        new_df.set_index('timestamp', inplace=True)

        df = pd.concat([df, new_df])
        df = df[~df.index.duplicated(keep='last')]
        df.sort_index(inplace=True)

        candles_per_day = int(24 / hours_per_candle)
        max_rows = parse_period(PERIOD) * candles_per_day

        if len(df) > max_rows:
            df = df.tail(max_rows)

        df.to_csv(filename)
        print(f"[*] Saved: {filename} ({len(df)} rows)")

    return df


if __name__ == "__main__":
    df = fetch_data()
    print(f"[✓] Done. Total rows: {len(df)}")