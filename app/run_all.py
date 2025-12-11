import subprocess
import sys

STEPS = [
    ["python", "-m", "app.speedboost"],
    ["python", "-m", "app.fetch_general"],
    # ["python", "-m", "app.fetch_general", "--cached"], # Can be used for reruns with cached symbols (optional)
    ["python", "-m", "app.fetch_financials"],
    ["python", "-m", "app.calculate_statistics"],
    ["python", "-m", "app.aggregate_industries"],
]

def run():
    for step in STEPS:
        print(f"\n=== Running: {' '.join(step)} ===\n")
        result = subprocess.run(step)
        if result.returncode != 0:
            print(f"Step failed: {' '.join(step)}")
            sys.exit(result.returncode)

    print("\nAll ETL steps completed successfully.\n")

if __name__ == "__main__":
    run()
