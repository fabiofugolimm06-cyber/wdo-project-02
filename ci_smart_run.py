import subprocess
import sys

def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip().splitlines()

def map_tests(files):
    tests = set()

    for f in files:
        if "pipeline" in f:
            tests.update([
                "tests/test_pipeline_regression.py",
                "tests/test_ci_stress_reliability.py",
                "tests/test_contract_enforcement.py"
            ])

        if "contract" in f:
            tests.add("tests/test_contract_enforcement.py")

        if "ci" in f:
            tests.add("tests/test_ci_gates.py")

        if "backtest" in f:
            tests.add("tests/test_backtest_pipeline.py")

    return list(tests)

def main():
    files = get_changed_files()

    tests = map_tests(files)

    if not tests:
        print("No relevant changes → running CORE only")
        tests = [
            "tests/test_pipeline_regression.py",
            "tests/test_ci_stress_reliability.py",
            "tests/test_contract_enforcement.py"
        ]

    cmd = ["pytest", "-q", "-x"] + tests

    print("Running:", " ".join(cmd))

    subprocess.run(cmd)

if __name__ == "__main__":
    main()