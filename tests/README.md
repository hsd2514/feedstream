# PulseFeed Test Suite

Comprehensive test suite for PulseFeed API covering functionality, performance, and duplicate detection.

## Setup

Install test dependencies:

```bash
pip install -e .
```

Or install manually:

```bash
pip install pytest pytest-asyncio httpx
```

## Running Tests

### Run All Tests

```bash
python run_tests.py
```

Or using pytest directly:

```bash
pytest tests/ -v
```

### Run Specific Test Files

```bash
# Functionality tests
pytest tests/test_feed.py -v

# Duplicate detection tests
pytest tests/test_duplicates.py -v

# Performance tests
pytest tests/test_performance.py -v -s
```

### Run Specific Test

```bash
pytest tests/test_feed.py::test_no_duplicates_in_single_feed -v
```

## Test Coverage

### 1. Functionality Tests (`test_feed.py`)

- ✅ **No Duplicates**: Ensures no duplicate images in single feed
- ✅ **Feed Count**: Verifies correct number of images (10 visible + 10 prefetched)
- ✅ **Seen Images**: Confirms images are marked as seen after being shown
- ✅ **50 Image Limit**: Tests that feed stops after 50 images
- ✅ **Like/Dislike**: Tests preference updates
- ✅ **Personalization**: Verifies feed adapts to user preferences
- ✅ **Session Management**: Tests session creation and independence
- ✅ **API Endpoints**: Tests all HTTP endpoints
- ✅ **Error Handling**: Tests error cases (nonexistent images, etc.)

### 2. Duplicate Detection Tests (`test_duplicates.py`)

- ✅ **No duplicates in visible feed**
- ✅ **No duplicates in prefetched feed**
- ✅ **No overlap between visible and prefetched**
- ✅ **No duplicates across multiple feed requests**
- ✅ **Seen images tracking**
- ✅ **Image appears only once per session**
- ✅ **Multiple sessions independence**

### 3. Performance Tests (`test_performance.py`)

- ✅ **Feed Generation Speed**: < 100ms average
- ✅ **Batch Operations**: < 50ms for 100 images
- ✅ **Prefetch Generation**: < 100ms
- ✅ **Concurrent Requests**: 5 sessions in < 500ms
- ✅ **Redis Connection**: < 10ms ping

## Performance Benchmarks

Expected performance (with Redis on localhost):

| Operation | Target | Typical |
|-----------|--------|---------|
| Feed Generation | < 100ms | 20-50ms |
| Batch Image Fetch (100) | < 50ms | 10-30ms |
| Batch Score Fetch (100) | < 50ms | 5-20ms |
| Prefetch Generation | < 100ms | 15-40ms |
| Redis Ping | < 10ms | 1-5ms |

## Test Fixtures

- `clean_redis`: Cleans Redis database before/after each test
- `test_images`: Provides 15 test images with various tags
- `seeded_images`: Seeds Redis with test images
- `large_image_set`: Provides 100 images for performance tests

## Notes

- Tests use a separate Redis database (flushed before/after each test)
- All tests are isolated and can run in any order
- Performance tests print detailed timing information
- Duplicate tests ensure data integrity

## Troubleshooting

### Tests Fail with Redis Connection Error

Make sure Redis is running:

```bash
redis-cli ping
```

### Tests Are Slow

- Check Redis connection (local vs remote)
- Ensure Redis is not under heavy load
- Check network latency if using remote Redis

### Duplicate Tests Fail

- Check that `mark_image_as_seen()` is being called
- Verify `get_seen_images()` returns correct set
- Ensure feed generation filters seen images correctly
