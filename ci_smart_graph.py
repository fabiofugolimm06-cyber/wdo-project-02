import subprocess

FILE_IMPACT_MAP = {
    "pipeline": [
        "tests/test_pipeline_regression.py",
        "tests/test_ci_stress_reliability.py",
    ],
    "contract": [
        "tests/test_contract_enforcement.py",
        "tests/test_contract_registry.py",
    ],
    "backtest": [
        "tests/test_backtest_pipeline.py",
    ],
    "ci": [
        "tests/test_ci_gates.py",
        "tests/test_ci_stress_reliability.py",
    ],
    "model": [
        "tests/test_pipeline_regression.py",
        "tests/test_ci_stress_reliability.py",
    ],
}

def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True
    )
    return [f for f in result.stdout.splitlines() if f.strip()]

def resolve_tests(files):
    tests = set()

    for file in files:
        for key, related_tests in FILE_IMPACT_MAP.items():
            if key in file:
                tests.update(related_tests)

    return list(tests)

def run_tests(tests):
    if not tests:
        tests = [
            "tests/test_pipeline_regression.py",
            "tests/test_ci_stress_reliability.py",
            "tests/test_contract_enforcement.py",
        ]

    cmd = ["pytest", "-q", "-x"] + tests

    print("\nCI SMART GRAPH RUN")
    print(" ".join(cmd))

    return subprocess.run(cmd).returncode

def main():
    files = get_changed_files()
    tests = resolve_tests(files)
    exit(subprocess.run(["pytest", "-q", "-x"] + tests).returncode)

if __name__ == "__main__":
    main()