import pytest
import time
from services.feed import store_image, add_images_tags, update_engagement, get_seen_images
from services.feed_generator import generate_feed
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
        log_step("Redis flushed")
    yield
    log_step("Cleanup: flushing Redis DB...")
    redis = get_redis()
    if redis:
        redis.flushdb()
    log_step("Cleanup complete")

@pytest.fixture
def test_images(clean_redis):
    log_step("Creating 20 test images...")
    images = []
    start = time.time()
    
    for i in range(20):
        img_id = f"dup_test_img{i}"
        tags = ["nature"] if i % 2 == 0 else ["city"]
        store_image(img_id, f"https://example.com/{img_id}.jpg", tags)
        add_images_tags(img_id, tags)
        update_engagement(img_id)
        images.append(img_id)
        
        if (i + 1) % 5 == 0:
            log_step(f"Created {i + 1}/20 images...")
    
    elapsed = time.time() - start
    log_step(f"Created 20 images in {elapsed:.2f}s")
    return images

def test_no_duplicates_in_visible_feed(clean_redis, test_images):
    session_id = create_session(["nature"])
    
    all_visible_urls = set()
    
    for i in range(5):
        feed = generate_feed(session_id)
        
        if "message" in feed:
            break
        
        visible_urls = [img["image_url"] for img in feed["visible"]]
        
        for url in visible_urls:
            assert url not in all_visible_urls, f"Duplicate URL {url} found in feed {i+1}"
            all_visible_urls.add(url)

def test_no_duplicates_in_prefetched_feed(clean_redis, test_images):
    session_id = create_session(["nature"])
    
    all_prefetched_urls = set()
    
    for i in range(5):
        feed = generate_feed(session_id)
        
        if "message" in feed:
            break
        
        prefetched_urls = [img["image_url"] for img in feed["prefetched"]]
        
        for url in prefetched_urls:
            assert url not in all_prefetched_urls, f"Duplicate URL {url} found in prefetched {i+1}"
            all_prefetched_urls.add(url)

def test_no_overlap_between_visible_and_prefetched(clean_redis, test_images):
    session_id = create_session(["nature"])
    
    for i in range(5):
        feed = generate_feed(session_id)
        
        if "message" in feed:
            break
        
        visible_urls = {img["image_url"] for img in feed["visible"]}
        prefetched_urls = {img["image_url"] for img in feed["prefetched"]}
        
        overlap = visible_urls & prefetched_urls
        assert len(overlap) == 0, f"Overlap between visible and prefetched in feed {i+1}: {overlap}"

def test_no_duplicates_across_feed_requests(clean_redis, test_images):
    log_step("Creating session...")
    session_id = create_session(["nature"])
    
    all_seen_urls = set()
    
    for i in range(10):
        log_step(f"Generating feed {i+1}...")
        feed = generate_feed(session_id)
        
        if "message" in feed:
            log_step(f"Feed {i+1}: {feed['message']}")
            break
        
        visible_urls = [img["image_url"] for img in feed["visible"]]
        prefetched_urls = [img["image_url"] for img in feed["prefetched"]]
        
        log_step(f"Feed {i+1}: {len(visible_urls)} visible, {len(prefetched_urls)} prefetched")
        
        combined = visible_urls + prefetched_urls
        
        for url in combined:
            assert url not in all_seen_urls, f"Duplicate URL {url} seen across feeds (first seen in feed {i+1})"
            all_seen_urls.add(url)
    
    log_step(f"Total unique images: {len(all_seen_urls)}")

def test_seen_images_tracking(clean_redis, test_images):
    session_id = create_session(["nature"])
    
    all_seen_ids = set()
    
    for i in range(5):
        feed = generate_feed(session_id)
        
        if "message" in feed:
            break
        
        seen_images = get_seen_images(session_id)
        
        for img in feed["visible"]:
            image_id = None
            for test_id in test_images:
                if f"/{test_id}.jpg" in img["image_url"]:
                    image_id = test_id
                    break
            
            if image_id:
                assert image_id in seen_images, f"Image {image_id} should be in seen_images"
                assert image_id not in all_seen_ids or i == 0, f"Image {image_id} already seen"
                all_seen_ids.add(image_id)

def test_image_appears_only_once_per_session(clean_redis, test_images):
    log_step("Creating session...")
    session_id = create_session(["nature"])
    
    image_url_counts = {}
    
    for i in range(10):
        log_step(f"Generating feed {i+1}...")
        feed = generate_feed(session_id)
        
        if "message" in feed:
            log_step(f"Feed {i+1}: {feed['message']}")
            break
        
        log_step(f"Feed {i+1}: {len(feed['visible'])} visible, {len(feed['prefetched'])} prefetched")
        
        for img in feed["visible"] + feed["prefetched"]:
            url = img["image_url"]
            image_url_counts[url] = image_url_counts.get(url, 0) + 1
    
    duplicates = {url: count for url, count in image_url_counts.items() if count > 1}
    
    log_step(f"Total unique images: {len(image_url_counts)}")
    if duplicates:
        log_step(f"DUPLICATES FOUND: {duplicates}")
    
    assert len(duplicates) == 0, f"Found duplicates: {duplicates}"

def test_multiple_sessions_no_cross_contamination(clean_redis, test_images):
    session1 = create_session(["nature"])
    session2 = create_session(["city"])
    
    feed1 = generate_feed(session1)
    feed2 = generate_feed(session2)
    
    seen1 = get_seen_images(session1)
    seen2 = get_seen_images(session2)
    
    overlap = seen1 & seen2
    
    assert len(overlap) == 0, f"Sessions should not share seen images, but found: {overlap}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
