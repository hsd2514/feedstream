import pytest
import time
import asyncio
from fastapi.testclient import TestClient
from main import app
from services.feed import store_image, add_images_tags, update_engagement, get_seen_images, mark_image_as_seen
from services.feed_generator import generate_feed, get_prefetched_batch
from services.session import create_session
from services.redis import get_redis
import uuid

client = TestClient(app)

def log_step(step_name):
    """Helper to log test steps with timestamp"""
    print(f"  [{time.strftime('%H:%M:%S')}] {step_name}")

def timed_operation(name):
    """Context manager to time operations"""
    class Timer:
        def __init__(self, name):
            self.name = name
        def __enter__(self):
            self.start = time.perf_counter()
            log_step(f"Starting: {self.name}")
            return self
        def __exit__(self, *args):
            elapsed = (time.perf_counter() - self.start) * 1000
            log_step(f"Completed: {self.name} ({elapsed:.2f}ms)")
    return Timer(name)

@pytest.fixture(scope="function")
def clean_redis():
    redis = get_redis()
    if redis:
        redis.flushdb()
    yield
    redis = get_redis()
    if redis:
        redis.flushdb()

@pytest.fixture
def test_images():
    return [
        {"image_id": "test_img1", "url": "https://example.com/img1.jpg", "tags": ["nature", "mountain"]},
        {"image_id": "test_img2", "url": "https://example.com/img2.jpg", "tags": ["city", "urban"]},
        {"image_id": "test_img3", "url": "https://example.com/img3.jpg", "tags": ["nature", "forest"]},
        {"image_id": "test_img4", "url": "https://example.com/img4.jpg", "tags": ["beach", "ocean"]},
        {"image_id": "test_img5", "url": "https://example.com/img5.jpg", "tags": ["mountain", "snow"]},
        {"image_id": "test_img6", "url": "https://example.com/img6.jpg", "tags": ["city", "night"]},
        {"image_id": "test_img7", "url": "https://example.com/img7.jpg", "tags": ["nature", "sunset"]},
        {"image_id": "test_img8", "url": "https://example.com/img8.jpg", "tags": ["urban", "modern"]},
        {"image_id": "test_img9", "url": "https://example.com/img9.jpg", "tags": ["forest", "wildlife"]},
        {"image_id": "test_img10", "url": "https://example.com/img10.jpg", "tags": ["ocean", "beach"]},
        {"image_id": "test_img11", "url": "https://example.com/img11.jpg", "tags": ["mountain", "adventure"]},
        {"image_id": "test_img12", "url": "https://example.com/img12.jpg", "tags": ["city", "architecture"]},
        {"image_id": "test_img13", "url": "https://example.com/img13.jpg", "tags": ["nature", "landscape"]},
        {"image_id": "test_img14", "url": "https://example.com/img14.jpg", "tags": ["urban", "night"]},
        {"image_id": "test_img15", "url": "https://example.com/img15.jpg", "tags": ["forest", "nature"]},
    ]

@pytest.fixture
def seeded_images(clean_redis, test_images):
    for img in test_images:
        store_image(img["image_id"], img["url"], img["tags"])
        add_images_tags(img["image_id"], img["tags"])
        update_engagement(img["image_id"])
    return test_images

def test_no_duplicates_in_single_feed(clean_redis, seeded_images):
    with timed_operation("Create session"):
        session_id = create_session(["nature", "mountain"])
    
    with timed_operation("Generate feed"):
        feed = generate_feed(session_id)
    
    log_step(f"Feed has {len(feed.get('visible', []))} visible, {len(feed.get('prefetched', []))} prefetched")
    
    assert "visible" in feed
    assert "prefetched" in feed
    
    visible_urls = [img["image_url"] for img in feed["visible"]]
    prefetched_urls = [img["image_url"] for img in feed["prefetched"]]
    
    with timed_operation("Check for duplicates"):
        assert len(visible_urls) == len(set(visible_urls)), "Duplicate images in visible feed"
        assert len(prefetched_urls) == len(set(prefetched_urls)), "Duplicate images in prefetched feed"
        
        all_urls = visible_urls + prefetched_urls
        assert len(all_urls) == len(set(all_urls)), "Duplicate images between visible and prefetched"
    
    log_step("No duplicates found")

def test_no_duplicates_across_multiple_feeds(clean_redis, seeded_images):
    with timed_operation("Create session"):
        session_id = create_session(["nature", "mountain"])
    
    all_seen_urls = set()
    
    for i in range(5):
        with timed_operation(f"Generate feed {i+1}"):
            feed = generate_feed(session_id)
        
        if "message" in feed:
            log_step(f"Feed {i+1}: {feed['message']}")
            break
        
        visible_urls = [img["image_url"] for img in feed["visible"]]
        prefetched_urls = [img["image_url"] for img in feed["prefetched"]]
        
        log_step(f"Feed {i+1}: {len(visible_urls)} visible, {len(prefetched_urls)} prefetched")
        
        for url in visible_urls + prefetched_urls:
            assert url not in all_seen_urls, f"Duplicate image {url} seen in feed {i+1}"
            all_seen_urls.add(url)
    
    log_step(f"Total unique images seen: {len(all_seen_urls)}")

def test_feed_performance(clean_redis, seeded_images):
    with timed_operation("Create session"):
        session_id = create_session(["nature", "mountain"])
    
    log_step("Measuring feed generation performance...")
    start_time = time.time()
    feed = generate_feed(session_id)
    elapsed = time.time() - start_time
    
    log_step(f"Feed generation took {elapsed*1000:.2f}ms")
    log_step(f"Visible: {len(feed.get('visible', []))}, Prefetched: {len(feed.get('prefetched', []))}")
    
    # Very relaxed for remote Redis (Upstash)
    assert elapsed < 5.0, f"Feed generation took {elapsed:.3f}s, should be < 5.0s"
    assert "visible" in feed or "message" in feed

def test_prefetched_batch_performance(clean_redis, seeded_images):
    with timed_operation("Create session"):
        session_id = create_session(["nature", "mountain"])
    
    with timed_operation("Get prefetched batch"):
        start_time = time.time()
        prefetched = get_prefetched_batch(session_id, 10)
        elapsed = time.time() - start_time
    
    log_step(f"Prefetch took {elapsed*1000:.2f}ms, got {len(prefetched)} images")
    
    # Relaxed for remote Redis
    assert elapsed < 1.0, f"Prefetch generation took {elapsed:.3f}s, should be < 1.0s"

def test_feed_returns_correct_count(clean_redis, seeded_images):
    session_id = create_session(["nature", "mountain"])
    
    feed = generate_feed(session_id)
    
    assert len(feed["visible"]) <= 10, "Visible feed should have max 10 images"
    assert len(feed["prefetched"]) <= 10, "Prefetched feed should have max 10 images"

def test_feed_marks_images_as_seen(clean_redis, seeded_images):
    session_id = create_session(["nature", "mountain"])
    
    feed = generate_feed(session_id)
    
    seen_images = get_seen_images(session_id)
    visible_urls = [img["image_url"] for img in feed["visible"]]
    
    for img in feed["visible"]:
        image_id = None
        for test_img in seeded_images:
            if test_img["url"] == img["image_url"]:
                image_id = test_img["image_id"]
                break
        if image_id:
            assert image_id in seen_images, f"Image {image_id} should be marked as seen"

def test_feed_respects_50_image_limit(clean_redis, seeded_images):
    session_id = create_session(["nature", "mountain"])
    
    all_seen = set()
    
    for i in range(10):
        feed = generate_feed(session_id)
        
        if "message" in feed:
            assert feed["message"] == "All 50 images are shown"
            break
        
        visible_urls = [img["image_url"] for img in feed["visible"]]
        all_seen.update(visible_urls)
        
        if len(all_seen) >= 50:
            next_feed = generate_feed(session_id)
            assert "message" in next_feed, "Should return message after 50 images"

def test_like_updates_preferences(clean_redis, seeded_images):
    with timed_operation("Create session"):
        session_id = create_session(["nature"])
    
    from services.feed_generator import like_handler
    from services.feed import get_tag_scores
    
    with timed_operation("Get initial scores"):
        initial_scores = get_tag_scores(session_id)
    log_step(f"Initial scores: {initial_scores}")
    
    with timed_operation("Like image test_img1"):
        asyncio.run(like_handler(session_id, "test_img1"))
    
    with timed_operation("Get updated scores"):
        updated_scores = get_tag_scores(session_id)
    log_step(f"Updated scores: {updated_scores}")
    
    assert updated_scores.get("nature", 0) > initial_scores.get("nature", 0)
    assert updated_scores.get("mountain", 0) > 0
    log_step("Preferences updated correctly")

def test_dislike_updates_preferences(clean_redis, seeded_images):
    session_id = create_session(["nature"])
    
    from services.feed_generator import dislike_handler
    from services.feed import get_tag_scores
    
    asyncio.run(dislike_handler(session_id, "test_img2"))
    
    scores = get_tag_scores(session_id)
    
    assert scores.get("city", 0) <= 0
    assert scores.get("urban", 0) <= 0

def test_feed_personalization_after_like(clean_redis, seeded_images):
    from services.feed_generator import like_handler
    from services.feed import get_tag_scores
    
    with timed_operation("Create session"):
        session_id = create_session(["nature"])
    
    with timed_operation("Get initial tag scores"):
        initial_scores = get_tag_scores(session_id)
    log_step(f"Initial nature score: {initial_scores.get('nature', 0)}")
    
    with timed_operation("Like test_img1 (nature, mountain)"):
        asyncio.run(like_handler(session_id, "test_img1"))
    
    with timed_operation("Get updated tag scores"):
        updated_scores = get_tag_scores(session_id)
    log_step(f"Updated nature score: {updated_scores.get('nature', 0)}")
    log_step(f"Updated mountain score: {updated_scores.get('mountain', 0)}")
    
    # Verify that liking increased the nature score
    assert updated_scores.get("nature", 0) > initial_scores.get("nature", 0), \
        "Nature score should increase after liking nature image"
    assert updated_scores.get("mountain", 0) > 0, \
        "Mountain score should be positive after liking mountain image"

def test_session_creation(clean_redis):
    session_id = create_session(["nature", "mountain", "sunset"])
    
    assert session_id is not None
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    
    from services.feed import get_tag_scores
    scores = get_tag_scores(session_id)
    
    assert scores.get("nature", 0) > 0
    assert scores.get("mountain", 0) > 0
    assert scores.get("sunset", 0) > 0

def test_api_session_endpoint(clean_redis, seeded_images):
    with timed_operation("POST /sessions/create"):
        response = client.post("/sessions/create", json={
            "preferred_tags": ["nature", "mountain"]
        })
    
    log_step(f"Response status: {response.status_code}")
    log_step(f"Response body: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "message" in data

def test_api_feed_endpoint(clean_redis, seeded_images):
    with timed_operation("POST /sessions/create"):
        response = client.post("/sessions/create", json={
            "preferred_tags": ["nature"]
        })
    session_id = response.json()["session_id"]
    log_step(f"Session ID: {session_id}")
    
    with timed_operation("GET /feed"):
        feed_response = client.get(f"/feed?session_id={session_id}")
    
    log_step(f"Response status: {feed_response.status_code}")
    feed = feed_response.json()
    log_step(f"Visible: {len(feed.get('visible', []))}, Prefetched: {len(feed.get('prefetched', []))}")
    
    assert feed_response.status_code == 200
    assert "visible" in feed
    assert "prefetched" in feed

def test_api_like_endpoint(clean_redis, seeded_images):
    with timed_operation("POST /sessions/create"):
        response = client.post("/sessions/create", json={
            "preferred_tags": ["nature"]
        })
    session_id = response.json()["session_id"]
    log_step(f"Session ID: {session_id}")
    
    with timed_operation("POST /like"):
        like_response = client.post(f"/like?session_id={session_id}&image_id=test_img1")
    
    log_step(f"Response status: {like_response.status_code}")
    log_step(f"Response body: {like_response.json()}")
    
    assert like_response.status_code == 200
    assert like_response.json()["message"] == "Liked"

def test_api_dislike_endpoint(clean_redis, seeded_images):
    response = client.post("/sessions/create", json={
        "preferred_tags": ["nature"]
    })
    session_id = response.json()["session_id"]
    
    dislike_response = client.post(f"/dislike?session_id={session_id}&image_id=test_img2")
    
    assert dislike_response.status_code == 200
    assert dislike_response.json()["message"] == "Disliked"

def test_like_nonexistent_image(clean_redis, seeded_images):
    session_id = create_session(["nature"])
    
    from services.feed_generator import like_handler
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(like_handler(session_id, "nonexistent_img"))
    
    assert exc_info.value.status_code == 404

def test_feed_with_no_available_images(clean_redis):
    session_id = create_session(["nature"])
    
    feed = generate_feed(session_id)
    
    assert "message" in feed or len(feed.get("visible", [])) == 0

def test_multiple_sessions_independence(clean_redis, seeded_images):
    session1 = create_session(["nature"])
    session2 = create_session(["city"])
    
    feed1 = generate_feed(session1)
    feed2 = generate_feed(session2)
    
    seen1 = get_seen_images(session1)
    seen2 = get_seen_images(session2)
    
    assert seen1 != seen2, "Sessions should have independent seen images"

def test_batch_operations_performance(clean_redis, seeded_images):
    with timed_operation("Create session"):
        session_id = create_session(["nature"])
    
    from services.feed import get_all_images, get_images_batch, get_global_scores_batch
    
    with timed_operation("Get all images"):
        all_images = get_all_images()
    log_step(f"Found {len(all_images)} images")
    
    with timed_operation("Batch image fetch"):
        start = time.time()
        images_dict = get_images_batch(all_images[:15])
        batch_time = time.time() - start
    
    with timed_operation("Batch score fetch"):
        start = time.time()
        scores_dict = get_global_scores_batch(all_images[:15])
        scores_time = time.time() - start
    
    log_step(f"Batch fetch: {batch_time*1000:.2f}ms, Score fetch: {scores_time*1000:.2f}ms")
    
    # Relaxed for remote Redis
    assert batch_time < 0.5, f"Batch image fetch took {batch_time:.3f}s"
    assert scores_time < 0.5, f"Batch score fetch took {scores_time:.3f}s"
    assert len(images_dict) > 0
    assert len(scores_dict) > 0

def test_feed_consistency(clean_redis, seeded_images):
    session_id = create_session(["nature", "mountain"])
    
    feed1 = generate_feed(session_id)
    feed2 = generate_feed(session_id)
    
    visible1_urls = {img["image_url"] for img in feed1["visible"]}
    visible2_urls = {img["image_url"] for img in feed2["visible"]}
    
    assert visible1_urls.isdisjoint(visible2_urls), "Feeds should not overlap"

def test_tag_scoring_accuracy(clean_redis, seeded_images):
    session_id = create_session(["nature"])
    
    from services.feed import get_tag_scores, update_tag_scores
    
    initial_nature = get_tag_scores(session_id).get("nature", 0)
    
    update_tag_scores(session_id, "nature", 1.0)
    
    updated = get_tag_scores(session_id)
    assert updated.get("nature", 0) == initial_nature + 1.0

def test_engagement_counters(clean_redis, seeded_images):
    from services.feed import increment_likes, increment_dislikes, get_engagement
    
    increment_likes("test_img1")
    increment_likes("test_img1")
    increment_dislikes("test_img1")
    
    engagement = get_engagement("test_img1")
    
    assert engagement["likes"] == 2
    assert engagement["dislikes"] == 1

def test_global_score_calculation(clean_redis, seeded_images):
    from services.feed import increment_likes, increment_dislikes, update_engagement, get_global_score
    
    increment_likes("test_img1")
    increment_likes("test_img1")
    increment_dislikes("test_img1")
    
    update_engagement("test_img1")
    
    score = get_global_score("test_img1")
    
    assert score == 3.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
