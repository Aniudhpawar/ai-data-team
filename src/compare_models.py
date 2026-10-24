import os
import subprocess
import sys

MODELS = [
    "databricks-meta-llama-3-3-70b-instruct",
    "databricks-qwen3-next-80b-a3b-instruct",
    "databricks-llama-4-maverick",
    "databricks-gpt-oss-120b",
]
RUNS = 2
QUESTION = ("Which month had the deepest month-over-month drop in sales "
            "in each year from 2020 to 2026?")


def run(cmd, model=None):
    env = dict(os.environ)
    if model:
        env["LLM_ENDPOINT"] = model
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return p.stdout.strip(), p.stderr.strip()


print("=== GROUND TRUTH (plain SQL, no AI) ===")
out, err = run([sys.executable, "-m", "src.check_drops"])
print(out or err)

for m in MODELS:
    print(f"\n=== {m}")
    for i in range(1, RUNS + 1):
        out, err = run([sys.executable, "-m", "src.cli", QUESTION], model=m)
        if not out:
            print(f"run {i}: ERROR -> {err.splitlines()[-1] if err else 'no output'}")
            continue
        answer = out.split("\n\n")[-1]
        print(f"run {i}: {answer}\n")
