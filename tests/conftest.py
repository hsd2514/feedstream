import pytest
import time
from services.redis import get_redis

@pytest.fixture(autouse=True)
def log_test_timing(request):
    """Log timing for each test"""
    test_name = request.node.name
    print(f"\n{'='*60}")
    print(f"STARTING: {test_name}")
    print(f"{'='*60}")
    
    start_time = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start_time
    
    print(f"\n{'='*60}")
    print(f"FINISHED: {test_name}")
    print(f"Duration: {elapsed*1000:.2f}ms")
    print(f"{'='*60}\n")

@pytest.fixture(scope="session", autouse=True)
def check_redis_latency():
    """Check Redis latency at start of test session"""
    print("\n" + "="*60)
    print("CHECKING REDIS CONNECTION...")
    print("="*60)
    
    redis = get_redis()
    if not redis:
        print("WARNING: Redis not available!")
        return
    
    # Measure latency
    times = []
    for _ in range(5):
        start = time.perf_counter()
        redis.ping()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    avg_latency = sum(times) / len(times) * 1000
    print(f"Redis latency: {avg_latency:.2f}ms average")
    
    if avg_latency > 50:
        print("WARNING: High Redis latency detected!")
        print("Tests may be slow. Consider using local Redis for faster tests.")
    else:
        print("Redis connection OK")
    
    print("="*60 + "\n")
