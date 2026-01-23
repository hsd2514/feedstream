import pytest
import sys
import time

if __name__ == "__main__":
    print("=" * 60)
    print("Running PulseFeed Test Suite")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    start_time = time.time()
    
    exit_code = pytest.main([
        "tests/",
        "-v",
        "-s",  # Show print statements
        "--tb=short",
        "-W", "ignore::DeprecationWarning",
        "--durations=10",  # Show 10 slowest tests
    ])
    
    total_time = time.time() - start_time
    
    print()
    print("=" * 60)
    print(f"Finished at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total duration: {total_time:.2f}s")
    if exit_code == 0:
        print("Result: All tests passed!")
    else:
        print(f"Result: Tests failed with exit code: {exit_code}")
    print("=" * 60)
    
    sys.exit(exit_code)
