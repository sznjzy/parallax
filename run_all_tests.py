import subprocess

def run_cmd(cmd, header):
    print(f"\n--- {header} ---")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
    except Exception as e:
        print(f"Error: {e}")

run_cmd("python scratch_test_9_live.py", "TEST 9")
run_cmd("python scratch_test_19.py", "TEST 19")
run_cmd("python scratch_test_combined.py", "TEST COMBINED (20, 22, 24, 25)")
run_cmd("python -m backend.api.pipeline", "TEST 21")
