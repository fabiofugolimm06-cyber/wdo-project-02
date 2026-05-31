@'
import subprocess

def get_changed_files():
    result = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], text=True)
    return [f.strip() for f in result.splitlines() if f.strip()]

def map_tests(files):
    tests = set()

    for f in files:
        if "microstructure/model/pipeline.py" in f:
            tests.update([
                "tests/test_pipeline_regression.py",
                "tests/test_ci_stress_reliability.py",
                "tests/test_pipeline_contracts.py",
            ])

        if "contracts" in f:
            tests.update([
                "tests/test_contract_enforcement.py",
                "tests/test_pipeline_contracts.py",
                "tests/test_contract_registry.py",
            ])

        if "backtest" in f:
            tests.update([
                "tests/test_backtest_pipeline.py",
                "tests/test_backtest_v2.py",
                "tests/test_backtest_v3.py",
            ])

        if ".github" in f or "ci" in f:
            tests.update([
                "tests/test_ci_gates.py",
                "tests/test_ci_stress_reliability.py",
                "tests/test_ci_determinism_stress.py",
            ])

        if "src/" in f:
            tests.update([
                "tests/test_system_lock.py",
                "tests/test_production_runtime.py",
            ])

    return sorted(tests)

def run_tests(tests):
    if not tests:
        print("No changes detected.")
        tests = ["tests/test_pipeline_contracts.py"]

    cmd = ["pytest", "-x", "-q"] + tests
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)

if __name__ == "__main__":
    files = get_changed_files()
    tests = map_tests(files)
    exit(run_tests(tests))
'@ | Set-Content -Encoding UTF8 .\scripts\ci_smart_run.py; notepad .\scripts\ci_smart_run.py