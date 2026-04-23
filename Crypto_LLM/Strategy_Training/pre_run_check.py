"""
PRE-RUN CHECK (The Gatekeeper)
Checks infrastructure, data integrity, and Git status.
Run this before starting the Auto Loop.
"""

import os
import subprocess
import sys

def check_environment(timeframe="1h"):
    # Dynamically build the path based on timeframe (e.g., "1h" -> "1H_Candle_Data")
    folder_name = f"{timeframe.upper()}_Candle_Data"
    data_dir = f"./Candle_Data/{folder_name}/"
    
    print(f"🔍 [Pre-Run] Checking {timeframe} environment in {data_dir}...")

    # Files must exist for the specific timeframe
    required_files = [f"btc_{timeframe}_3m.csv", f"btc_{timeframe}_1y.csv", f"btc_{timeframe}_3y.csv"]
    
    if not os.path.exists(data_dir):
        print(f"❌ FAIL: Directory {data_dir} does not exist.")
        return False

    for f in required_files:
        if not os.path.exists(os.path.join(data_dir, f)):
            print(f"❌ FAIL: Missing {f} in {data_dir}")
            return False

    # 3. Git Check (Essential for the 'Auto-Revert' logic)
    try:
        subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FAIL: Git not initialized. Auto Loop cannot revert failed code without Git.")
        return False

    # 4. Critical File Check
    essential_scripts = ["strategy.py", "evaluator.py", "auto_loop.py"]
    for script in essential_scripts:
        if not os.path.exists(script):
            print(f"❌ FAIL: {script} is missing from the root folder.")
            return False

    print("✅ [PASS] Environment is stable. Green light for Auto Loop.")
    return True

if __name__ == "__main__":
    # You can pass the timeframe as a command line arg: python pre_run_check.py 15m
    tf = sys.argv[1] if len(sys.argv) > 1 else "1h"
    if not check_environment(tf):
        sys.exit(1)
    print("✅ Ready.")