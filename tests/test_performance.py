import pytest
import time
import statistics
from services.feed import store_image, add_images_tags, update_engagement, get_images_batch, get_global_scores_batch
from services.feed_generator import generate_feed, get_prefetched_batch
from services.session import create_session
from services.redis import get_redis

def log_step(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")

@pytest.fixture(scope="function")
def clean_redis():
    log_step("Connecting to Redis...")
    redis = get_redis()
    if redis:
        log_step("Flushing Redis DB...")
        redis.flushdb()
    yield
    redis = get_redis()
    if redis:
        redis.flushdb()

@pytest.fixture
def large_image_set(clean_redis):
    log_step("Creating 30 test images for performance tests...")
    images = []
    start = time.time()
    
    for i in range(30):
        img_id = f"perf_img{i}"
        tags = ["nature"] if i % 2 == 0 else ["city"]
        store_image(img_id, f"https://example.com/{img_id}.jpg", tags)
        add_images_tags(img_id, tags)
        update_engagement(img_id)
        images.append(img_id)
        
        if (i + 1) % 10 == 0:
            log_step(f"Created {i + 1}/30 images...")
    
    elapsed = time.time() - start
    log_step(f"Created 30 images in {elapsed:.2f}s")
    return images

def test_feed_generation_speed(clean_redis, large_image_set):
    log_step("Running 3 feed generation tests (fresh session each time)...")
    times = []
    for i in range(3):
        # Create fresh session each time to avoid "All 50 images shown"
        session_id = create_session(["nature", "mountain"])
        start = time.perf_counter()
        feed = generate_feed(session_id)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        log_step(f"  Iteration {i+1}: {elapsed*1000:.2f}ms")
        assert "visible" in feed or "message" in feed
    
    avg_time = statistics.mean(times)
    max_time = max(times)
    
    print(f"\nFeed Generation Performance:")
    print(f"  Average: {avg_time*1000:.2f}ms")
    print(f"  Max: {max_time*1000:.2f}ms")
    
    # Very relaxed thresholds for remote Redis (Upstash ~30-50ms latency per call)
    assert avg_time < 6.0, f"Average feed generation should be < 6s, got {avg_time*1000:.2f}ms"
    assert max_time < 8.0, f"Max feed generation should be < 8s, got {max_time*1000:.2f}ms"

def test_batch_operations_speed(clean_redis, large_image_set):
    from services.feed import get_all_images
    
    log_step("Getting all images...")
    all_images = get_all_images()
    log_step(f"Found {len(all_images)} images")
    
    log_step("Running batch fetch tests...")
    times = []
    for i in range(3):
        start = time.perf_counter()
        images_dict = get_images_batch(all_images)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        log_step(f"  Iteration {i+1}: {elapsed*1000:.2f}ms")
    
    avg_time = statistics.mean(times)
    
    print(f"\nBatch Image Fetch Performance:")
    print(f"  Average: {avg_time*1000:.2f}ms for {len(all_images)} images")
    
    # Relaxed for remote Redis
    assert avg_time < 0.5, f"Batch fetch should be < 500ms, got {avg_time*1000:.2f}ms"

def test_score_batch_speed(clean_redis, large_image_set):
    from services.feed import get_all_images
    
    log_step("Getting all images...")
    all_images = get_all_images()
    
    log_step("Running batch score tests...")
    times = []
    for i in range(3):
        start = time.perf_counter()
        scores_dict = get_global_scores_batch(all_images)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        log_step(f"  Iteration {i+1}: {elapsed*1000:.2f}ms")
    
    avg_time = statistics.mean(times)
    
    print(f"\nBatch Score Fetch Performance:")
    print(f"  Average: {avg_time*1000:.2f}ms for {len(all_images)} scores")
    
    # Relaxed for remote Redis
    assert avg_time < 0.5, f"Batch score fetch should be < 500ms, got {avg_time*1000:.2f}ms"

def test_prefetch_generation_speed(clean_redis, large_image_set):
    log_step("Creating session...")
    session_id = create_session(["nature"])
    
    log_step("Running prefetch tests...")
    times = []
    for i in range(3):
        start = time.perf_counter()
        prefetched = get_prefetched_batch(session_id, 10)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        log_step(f"  Iteration {i+1}: {elapsed*1000:.2f}ms")
    
    avg_time = statistics.mean(times)
    
    print(f"\nPrefetch Generation Performance:")
    print(f"  Average: {avg_time*1000:.2f}ms")
    
    # Very relaxed for remote Redis (Upstash)
    assert avg_time < 3.0, f"Prefetch should be < 3s, got {avg_time*1000:.2f}ms"

def test_concurrent_feed_requests(clean_redis, large_image_set):
    import concurrent.futures
    
    log_step("Creating 3 sessions...")
    session_ids = [create_session(["nature"]) for _ in range(3)]
    
    def get_feed(sid):
        return generate_feed(sid)
    
    log_step("Running concurrent feed requests...")
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(get_feed, sid) for sid in session_ids]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.perf_counter() - start
    
    print(f"\nConcurrent Feed Requests (3 sessions):")
    print(f"  Total time: {elapsed*1000:.2f}ms")
    print(f"  Average per request: {(elapsed/3)*1000:.2f}ms")
    
    # Very relaxed for remote Redis (Upstash)
    assert elapsed < 10.0, f"3 concurrent requests should complete in < 10s, got {elapsed*1000:.2f}ms"
    assert all("visible" in r or "message" in r for r in results)

def test_redis_connection_speed(clean_redis):
    log_step("Testing Redis ping latency...")
    redis = get_redis()
    
    times = []
    for i in range(10):
        start = time.perf_counter()
        redis.ping()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        if (i + 1) % 5 == 0:
            log_step(f"  Ping {i+1}/10: {elapsed*1000:.2f}ms")
    
    avg_time = statistics.mean(times)
    max_time = max(times)
    
    print(f"\nRedis Connection Performance:")
    print(f"  Average ping: {avg_time*1000:.2f}ms")
    print(f"  Max ping: {max_time*1000:.2f}ms")
    
    # Relaxed for remote Redis (Upstash typically has 20-100ms latency)
    assert avg_time < 0.2, f"Redis ping should be < 200ms, got {avg_time*1000:.2f}ms"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
