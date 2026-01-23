# PulseFeed API Documentation

**Realtime Personalized Image Feed with Dynamic Ranking**

---

## Overview

PulseFeed is a backend API that generates personalized image feeds based on user preferences. The system learns from user interactions (likes/dislikes) and adapts the feed in real-time.

**Base URL:** `http://localhost:8000`

---

## Quick Start

### 1. Seed the Database

```bash
python seed.py
```

This populates Redis with 100 images across 15 tags.

### 2. Start the Server

```bash
uvicorn main:app --reload
```

Or:

```bash
python main.py
```

---

## API Endpoints

### Health Checks

#### `GET /health`

Check if the API is running.

**Response:**
```json
{
  "message": "OK"
}
```

---

#### `GET /health/redis`

Check if Redis connection is working.

**Response:**
```json
{
  "message": "Redis connection successful"
}
```

**Error (503):**
```json
{
  "detail": "Redis connection failed"
}
```

---

### Session Management

#### `POST /sessions/create`

Create a new user session with preferred tags.

**Request Body:**
```json
{
  "preferred_tags": ["nature", "mountain", "sunset"]
}
```

**Response:**
```json
{
  "session_id": "abc123-def456-ghi789",
  "message": "Session created successfully"
}
```

**What it does:**
- Generates a unique session ID
- Sets initial tag preferences (each tag gets +3 score)
- Session expires after 1 hour of inactivity

**Available Tags (15 total):**
- `nature`, `mountain`, `forest`, `sunset`, `beach`, `ocean`, `snow`
- `city`, `urban`, `architecture`, `night`, `modern`, `landscape`
- `wildlife`, `adventure`

---

### Feed Generation

#### `GET /feed?session_id={session_id}`

Get personalized feed (10 visible + 10 prefetched images).

**Query Parameters:**
- `session_id` (required): The session ID from `/sessions/create`

**Response:**
```json
{
  "visible": [
    {
      "image_url": "https://images.unsplash.com/photo-...",
      "image_tags": ["nature", "mountain", "landscape"]
    },
    {
      "image_url": "https://images.unsplash.com/photo-...",
      "image_tags": ["nature", "forest"]
    },
    ...
  ],
  "prefetched": [
    {
      "image_url": "https://images.unsplash.com/photo-...",
      "image_tags": ["beach", "ocean"]
    },
    ...
  ]
}
```

**Special Response (when 50 images shown):**
```json
{
  "message": "All 50 images are shown"
}
```

**What it does:**
- Returns 10 visible images (marked as seen) + 10 prefetched images (not marked as seen)
- Filters out already-seen images
- Scores images: `global_score + tag_boost`
- Marks only visible images as seen
- Maximum 50 images per session
- Prefetched images are updated in real-time via SSE when user likes/dislikes

**Feed Flow:**
- Request 1: Visible 1-10, Prefetched 11-20
- Request 2: Visible 11-20, Prefetched 21-30
- Request 3: Visible 21-30, Prefetched 31-40
- Request 4: Visible 31-40, Prefetched 41-50
- Request 5: Visible 41-50, Prefetched: []
- Request 6+: Returns "All 50 images are shown"

---

#### `GET /feed/stream?session_id={session_id}`

Open Server-Sent Events (SSE) stream for real-time prefetch updates.

**Query Parameters:**
- `session_id` (required): The session ID from `/sessions/create`

**Response Type:** `text/event-stream`

**Event Format:**
```
data: {"type": "prefetch_update", "prefetched": [...]}

data: {"type": "ping"}
```

**What it does:**
- Keeps connection open for real-time updates
- Sends updated prefetched batch when user likes/dislikes an image
- Sends ping every 30 seconds to keep connection alive
- Automatically cleans up on disconnect

**Frontend Usage:**
```javascript
const eventSource = new EventSource(
  `http://localhost:8000/feed/stream?session_id=${sessionId}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'prefetch_update') {
    // Update prefetched images in UI
    updatePrefetchedImages(data.prefetched);
  }
};
```

---

### User Interactions

#### `POST /like?session_id={session_id}&image_id={image_id}`

Like an image.

**Query Parameters:**
- `session_id` (required): User's session ID
- `image_id` (required): ID of the image to like (e.g., "img1")

**Response:**
```json
{
  "message": "Liked"
}
```

**Error (404):**
```json
{
  "detail": "Image not found"
}
```

**What it does:**
- Increments image's global like counter
- Updates global ranking score
- Increases user's preference for image's tags (+1.0 for each tag)
- Broadcasts updated prefetched batch via SSE (if SSE connection is open)
- Next feed request will show more images with those tags

---

#### `POST /dislike?session_id={session_id}&image_id={image_id}`

Dislike an image.

**Query Parameters:**
- `session_id` (required): User's session ID
- `image_id` (required): ID of the image to dislike (e.g., "img5")

**Response:**
```json
{
  "message": "Disliked"
}
```

**Error (404):**
```json
{
  "detail": "Image not found"
}
```

**What it does:**
- Increments image's global dislike counter
- Updates global ranking score
- Decreases user's preference for image's tags:
  - If user already likes the tag (score > 0): small penalty (-0.5)
  - If user already dislikes the tag (score < 0): bigger penalty (-1.0)
  - If user has no preference (score = 0): no change
- Broadcasts updated prefetched batch via SSE (if SSE connection is open)
- Next feed request will show fewer images with those tags

---

## How Personalization Works

### Initial State (Cold Start)

1. User creates session with preferred tags: `["nature", "mountain", "sunset"]`
2. Each tag gets initial score: `+3.0`
3. First feed request: Shows mix of popular content + nature/mountain/sunset images

### After User Likes Image

1. User likes image with tags: `["nature", "forest"]`
2. Tag scores update:
   - `nature`: +3.0 → +4.0
   - `forest`: 0 → +1.0
3. Next feed request: More nature/forest images appear (boosted by +4.0 and +1.0)

### After User Dislikes Image

1. User dislikes image with tags: `["city", "urban"]`
2. Tag scores update (if user had preferences):
   - If `city` was +2.0: → +1.5 (small penalty)
   - If `city` was 0: no change (user neutral)
3. Next feed request: Fewer city/urban images appear (penalized or filtered out)

### Scoring Formula

For each image:
```
final_score = global_score + tag_boost

Where:
- global_score = (total_likes * 2) - (total_dislikes * 1)
- tag_boost = sum of user's tag_scores for image's tags
```

**Example:**
- Image has tags: `["nature", "mountain"]`
- User's tag_scores: `{"nature": +4.0, "mountain": +3.0}`
- tag_boost = 4.0 + 3.0 = 7.0
- If global_score = 50, then final_score = 57

---

## Complete User Flow

### Step 1: Create Session

```javascript
// Frontend
const response = await fetch('http://localhost:8000/sessions/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    preferred_tags: ['nature', 'mountain', 'sunset']
  })
});

const { session_id } = await response.json();
// Store session_id in localStorage or state
```

### Step 2: Get Feed

```javascript
// Frontend
const response = await fetch(`http://localhost:8000/feed?session_id=${session_id}`);
const feed = await response.json();

// Display visible images (first 10)
feed.visible.forEach(image => {
  console.log(image.image_url, image.image_tags);
});

// Prefetch next 10 images (for smooth scrolling)
feed.prefetched.forEach(image => {
  // Preload images in background
  const img = new Image();
  img.src = image.image_url;
});
```

### Step 3: Open SSE Stream (Real-time Updates)

```javascript
// Frontend - open SSE connection for real-time prefetch updates
const eventSource = new EventSource(
  `http://localhost:8000/feed/stream?session_id=${session_id}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'prefetch_update') {
    // Update prefetched images when user likes/dislikes
    updatePrefetchedImages(data.prefetched);
  }
};

// Clean up on page unload
window.addEventListener('beforeunload', () => {
  eventSource.close();
});
```

### Step 4: User Likes Image

```javascript
// Frontend
await fetch(`http://localhost:8000/like?session_id=${session_id}&image_id=img5`, {
  method: 'POST'
});

// SSE will automatically send updated prefetched batch
// Next feed request will be more personalized
```

### Step 5: Get Next Batch

```javascript
// Frontend - request next 10 images
const response = await fetch(`http://localhost:8000/feed?session_id=${session_id}`);
const feed = await response.json();

// feed.visible contains images 11-20, personalized based on previous likes
// feed.prefetched contains images 21-30 (updated via SSE if preferences changed)
```

---

## Data Models

### Image Object

```json
{
  "image_url": "https://images.unsplash.com/photo-...",
  "image_tags": ["nature", "mountain", "landscape"]
}
```

**Note:** Image ID is not returned in feed, but you can extract it from the URL or track it client-side.

---

## Error Handling

### Common Status Codes

- **200**: Success
- **404**: Image not found
- **503**: Redis connection failed

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

---

## Session Lifecycle

1. **Create**: User selects 3 preferred tags → session created
2. **Active**: User browses feed, likes/dislikes images
3. **Expires**: Session expires after 1 hour of inactivity
4. **New Session**: User creates new session to continue

**Note:** Once a session expires, all preferences are lost. User must create a new session.

---

## Available Tags (15 total)

**Nature (7):**
- `nature`, `mountain`, `forest`, `sunset`, `beach`, `ocean`, `snow`

**City (6):**
- `city`, `urban`, `architecture`, `night`, `modern`, `landscape`

**Other (2):**
- `wildlife`, `adventure`

---

## Rate Limits

Currently: **No rate limits** (demo scope)

---

## Environment Variables

Create a `.env` file:

```
REDIS_HOST=your_redis_host
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password
```

---

## Testing the API

### Using curl

```bash
# Create session
curl -X POST http://localhost:8000/sessions/create \
  -H "Content-Type: application/json" \
  -d '{"preferred_tags": ["nature", "mountain", "sunset"]}'

# Get feed
curl "http://localhost:8000/feed?session_id=YOUR_SESSION_ID"

# Open SSE stream (use in browser or with EventSource)
# curl doesn't support SSE well - use browser EventSource API instead
# GET http://localhost:8000/feed/stream?session_id=YOUR_SESSION_ID

# Like image
curl -X POST "http://localhost:8000/like?session_id=YOUR_SESSION_ID&image_id=img1"

# Dislike image
curl -X POST "http://localhost:8000/dislike?session_id=YOUR_SESSION_ID&image_id=img5"
```

---

## Frontend Integration Example

```javascript
class PulseFeedClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.sessionId = null;
    this.eventSource = null;
  }

  async createSession(preferredTags) {
    const response = await fetch(`${this.baseUrl}/sessions/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preferred_tags: preferredTags })
    });
    const data = await response.json();
    this.sessionId = data.session_id;
    return data.session_id;
  }

  async getFeed() {
    if (!this.sessionId) throw new Error('No session created');
    const response = await fetch(`${this.baseUrl}/feed?session_id=${this.sessionId}`);
    return await response.json();
  }

  openSSEStream(onPrefetchUpdate) {
    if (!this.sessionId) throw new Error('No session created');
    if (this.eventSource) this.eventSource.close();
    
    this.eventSource = new EventSource(
      `${this.baseUrl}/feed/stream?session_id=${this.sessionId}`
    );
    
    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'prefetch_update') {
        onPrefetchUpdate(data.prefetched);
      }
    };
    
    return this.eventSource;
  }

  closeSSEStream() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  async likeImage(imageId) {
    if (!this.sessionId) throw new Error('No session created');
    const response = await fetch(
      `${this.baseUrl}/like?session_id=${this.sessionId}&image_id=${imageId}`,
      { method: 'POST' }
    );
    return await response.json();
  }

  async dislikeImage(imageId) {
    if (!this.sessionId) throw new Error('No session created');
    const response = await fetch(
      `${this.baseUrl}/dislike?session_id=${this.sessionId}&image_id=${imageId}`,
      { method: 'POST' }
    );
    return await response.json();
  }
}

// Usage
const client = new PulseFeedClient();
await client.createSession(['nature', 'mountain', 'sunset']);

// Open SSE stream for real-time updates
client.openSSEStream((prefetched) => {
  console.log('Prefetch updated:', prefetched);
  // Update UI with new prefetched images
});

// Get initial feed
const feed = await client.getFeed();
console.log('Visible:', feed.visible);
console.log('Prefetched:', feed.prefetched);

// User interaction triggers SSE update
await client.likeImage('img1');
// SSE will automatically send updated prefetched batch

// Clean up
client.closeSSEStream();
```

---

## Project Structure

```
feedstream/
├── main.py                 # FastAPI app entry point
├── config.py               # Configuration (Redis settings)
├── seed.py                 # Database seeding script
├── seed_data.py            # Seed data (100 images)
├── routes/
│   ├── feed.py            # Feed endpoints (including SSE)
│   └── session.py         # Session endpoints
├── services/
│   ├── redis.py           # Redis connection
│   ├── feed.py            # Data layer (CRUD operations)
│   ├── feed_generator.py  # Feed generation logic
│   ├── session.py         # Session management
│   └── sse_manager.py      # SSE connection management
└── README.md              # This file
```

---

## Notes for Frontend Developers

1. **Session Management**: Store `session_id` in localStorage or app state
2. **Feed Response**: Feed now returns `{visible: [...], prefetched: [...]}` instead of a simple array
3. **Feed Pagination**: Call `/feed` multiple times to get next batches (10 visible + 10 prefetched each)
4. **Real-time Updates**: Open SSE stream (`/feed/stream`) to receive updated prefetched batch when user likes/dislikes
5. **Image Tracking**: Track which images you've displayed to avoid duplicates
6. **Error Handling**: Always check for `{"message": "All 50 images are shown"}` response
7. **Personalization**: Feed adapts after each like/dislike - prefetched images update in real-time via SSE
8. **SSE Best Practices**: 
   - Open SSE connection after creating session
   - Close connection on page unload
   - Handle reconnection if connection drops

---

## One-Line Summary

> **PulseFeed** is a realtime personalized image feed that dynamically re-ranks content based on engagement, using Redis for global ranking, session-based personalization, and Server-Sent Events (SSE) for live prefetch updates.
