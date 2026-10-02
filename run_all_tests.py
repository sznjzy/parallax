"""
Parallax Unified Test Suite Runner
Discovers and runs all unit tests, integration tests, and quality benchmarks.
"""
import sys
import unittest

def main():
    print("=" * 70)
    print("PARALLAX UNIFIED TEST SUITE")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="backend/tests", pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print(f"Total Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 70)
    
    if not result.wasSuccessful():
        sys.exit(1)
    print("ALL TESTS PASSED SUCCESSFULLY.")
    sys.exit(0)

if __name__ == "__main__":
    main()
