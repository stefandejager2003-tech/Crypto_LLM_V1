import os
import subprocess
import sys
import pandas as pd

def check_environment(timeframe="1h"):
    # 1. Resolve Paths (Moving up from Strategy_Training to project root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    
    folder_name = f"{timeframe.upper()}_Candle_Data"
    data_dir = os.path.join(project_root, "Candle_Data", folder_name)
    
    print(f"🔍 [Pre-Run] Project Root: {project_root}")
    print(f"🔍 [Pre-Run] Checking {timeframe} data in: {data_dir}")

    # 2. Required Files and Columns
    required_files = [f"btc_{timeframe}_3m.csv", f"btc_{timeframe}_1y.csv", f"btc_{timeframe}_3y.csv"]
    required_columns = ['close', 'log_return', 'cvd_trend', 'close_zscore_50']
    
    if not os.path.exists(data_dir):
        print(f"❌ FAIL: Directory {data_dir} does not exist.")
        return False

    for f in required_files:
        file_path = os.path.join(data_dir, f)
        if not os.path.exists(file_path):
            print(f"❌ FAIL: Missing file: {f}")
            return False
        
        # Data Integrity Check: Verify Columns
        try:
            df_sample = pd.read_csv(file_path, nrows=5)
            missing_cols = [c for c in required_columns if c not in df_sample.columns]
            if missing_cols:
                print(f"❌ FAIL: {f} is missing V2 columns: {missing_cols}")
                print(f"👉 Run fetch_data.py to rebuild your indicators.")
                return False
        except Exception as e:
            print(f"❌ FAIL: Could not read {f}. Error: {e}")
            return False

    # 3. Git Check (Essential for the 'Auto-Revert' logic)
    try:
        subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], 
                               cwd=project_root, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FAIL: Git not initialized in project root.")
        return False

    # 4. Critical File Check (Looking in Strategy_Training folder)
    essential_scripts = ["strategy.py", "evaluator.py", "auto_loop.py"]
    for script in essential_scripts:
        if not os.path.exists(os.path.join(script_dir, script)):
            print(f"❌ FAIL: {script} is missing from {script_dir}")
            return False

    print("✅ [PASS] Data integrity and V2 features verified. Green light.")
    return True

if __name__ == "__main__":
    # Usage: python pre_run_check.py 15m
    tf = sys.argv[1] if len(sys.argv) > 1 else "1h"
    if not check_environment(tf):
        sys.exit(1)