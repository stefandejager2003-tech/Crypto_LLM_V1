import os
import subprocess
import re
import time
import sys
import traceback
from litellm import completion
from rag_memory import StrategyMemoryBank

# --- CONFIGURATION ---
# AIDER_CMD = os.path.join(os.path.dirname(sys.executable), "aider.exe")
AIDER_CMD = "aider"
STRATEGY_FILE = "strategy.py"
# We now point to evaluator.py and pass arguments (Symbol, Timeframe, Period)
EVAL_CMD = [sys.executable, "evaluator.py", "btc", "1h", "3y"]
RESULTS_FILE = "results.tsv"

def get_history_and_best():
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w") as f:
            f.write("commit\tfinal_result\tstatus\tdescription\n")
        return -999.0, []
    
    best_score = -999.0
    history = []
    with open(RESULTS_FILE, "r") as f:
        lines = f.readlines()[1:]
        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                try:
                    score = float(parts[1])
                    status = parts[2]
                    if status == "keep" and score > best_score:
                        best_score = score
                    history.append(f"Score: {score} | Status: {status}")
                except ValueError: pass
    return best_score, history[-5:]

def get_current_commit():
    return subprocess.getoutput("git rev-parse --short HEAD").strip()

def log_result(commit, score, status, desc):
    with open(RESULTS_FILE, "a") as f:
        f.write(f"{commit}\t{score}\t{status}\t{desc}\n")
        f.flush()
        os.fsync(f.fileno())

def generate_hypothesis(best_score):
    print("🤔 Lead Quant is analyzing market features...")
    try:
        response = completion(
            model="openai/deepseek-v3.2",
            api_base="http://localhost:4000", 
            api_key="sk-dummy-key", 
            temperature=0.7, 
            messages=[
                {"role": "system", "content": "You are an elite quantitative researcher. Use V2 features: cvd_trend, atr_14, close_zscore_50, volume_zscore_24."},
                {"role": "user", "content": f"Current best score: {best_score}. Format response as THINKING: [logic] HYPOTHESIS: [instruction]"}
            ]
        )
        content = response.choices[0].message.content
        content_clean = re.sub(r'<think>.*?(</think>|$)', '', content, flags=re.DOTALL).strip()
        
        thinking = re.search(r'THINKING\s*[:\-]?\s*(.*?)(?=HYPOTHESIS|$)', content_clean, re.I | re.S).group(1).strip()
        hypothesis = re.search(r'HYPOTHESIS\s*[:\-]?\s*(.*)', content_clean, re.I | re.S).group(1).strip()
        return thinking, hypothesis
    except Exception as e:
        print(f"⚠️ Hypothesis failed: {e}")
        return "Error", ""

def run_experiment(memory_bank):
    best_score, _ = get_history_and_best()
    print(f"\n🚀 TARGET TO BEAT: {best_score}")
    commit_before = get_current_commit()

    # 1. GENERATE HYPOTHESIS
    thinking, hypothesis = generate_hypothesis(best_score)
    if not hypothesis: return

    # 2. RAG MEMORY CHECK (The Bouncer)
    raw_memories = memory_bank.query_similar_trials(hypothesis, n_results=5)
    if sum(1 for m in raw_memories if m['status'] in ['discard', 'crash']) >= 2:
        print("🛑 REJECTED: Idea is too similar to past failures.")
        return

    # 3. AIDER CODING
    prompt = f"Mission: {hypothesis}\nLogic: {thinking}\nUpdate {STRATEGY_FILE} using SEARCH/REPLACE."
    print(f"🤖 Aider is coding...")
    subprocess.run([AIDER_CMD, "--message", prompt, "--no-auto-commits", "--yes", STRATEGY_FILE], capture_output=True)

    git_status = subprocess.getoutput(f"git status --porcelain {STRATEGY_FILE}").strip()
    if not git_status:
        print("⚠️ No changes made."); return

    subprocess.run(["git", "add", STRATEGY_FILE], capture_output=True)
    subprocess.run(["git", "commit", "-m", f"Experiment: {hypothesis[:50]}"], capture_output=True)
    commit_after = get_current_commit()

    # 4. EXTERNAL EVALUATION (The Judge)
    # UPDATE THIS BLOCK (around line 102):
    print(f"📈 Running Evaluator...")
    # We MUST capture output to use re.search on result.stdout
    result = subprocess.run(EVAL_CMD, capture_output=True, text=True) 

    # Capture the "FINAL_RESULT:X" from evaluator.py
    raw_output = result.stdout if result.stdout else ""
    match = re.search(r"FINAL_RESULT:([-\d.]+)", raw_output)

    if match:
        score = float(match.group(1))
    else:
        # If the evaluator crashed (like the Missing Column error), result.stdout 
        # will contain the error message, but not the FINAL_RESULT string.
        print(f"⚠️ Evaluator crashed. Check console. Output: {raw_output[:100]}...")
        score = -10.0
    score = float(match.group(1)) if match else -10.0
    status = "keep" if score > best_score else "discard"

    # 5. SAVE & REVERT
    print(f"📊 Result: {score}")
    log_result(commit_after, score, status, hypothesis[:50])
    memory_bank.log_trial(commit_after, hypothesis, score, status)

    if status == "discard" or score <= 0.0:
        print(f"❌ Reverting to {commit_before}...")
        subprocess.run(["git", "restore", "--source", commit_before, "--staged", "--worktree", STRATEGY_FILE], capture_output=True)
        subprocess.run(["git", "commit", "-m", "Auto-revert"], capture_output=True)
    else:
        print("✅ NEW HIGH SCORE!")

if __name__ == "__main__":
    db = StrategyMemoryBank()
    while True:
        try: run_experiment(db)
        except KeyboardInterrupt: break
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            traceback.print_exc()
            time.sleep(10)