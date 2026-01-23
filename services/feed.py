from fastapi import HTTPException
from services.redis import get_redis
import json


def store_image(image_id: str, image_url: str,image_tags: list[str]):    
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"image:{image_id}"
    redis.hset(key, mapping={
        "image_url": image_url,
        "image_tags": json.dumps(image_tags)
    })
    return {"message": "Image stored successfully"}

def get_image(image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"image:{image_id}"
    image = redis.hgetall(key)
    if image is None or len(image) == 0:
        return None
    return {
        "image_id": image_id,
        "image_url": image["image_url"],
        "image_tags": json.loads(image["image_tags"])
    }


def increment_likes(image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key  = f"image:{image_id}:likes"
    likes =redis.incr(key)
    return {
        "likes": likes
    }

def increment_dislikes(image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key  = f"image:{image_id}:dislikes"
    dislikes = redis.incr(key)
    return {
        "dislikes": dislikes
    }


def get_engagement(image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    likes = redis.get(f"image:{image_id}:likes")
    dislikes = redis.get(f"image:{image_id}:dislikes")
    return {
        "likes": int(likes or 0),
        "dislikes": int(dislikes or 0)
    }

def update_engagement(image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    engagement = get_engagement(image_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Image not found")
    like , dislike = engagement["likes"], engagement["dislikes"]
    score = (like*2)-(dislike*1)
    key = f"feed:global"
    redis.zadd(key, {image_id: score})
    return score


def add_images_tags(image_id: str, tags: list[str]):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    for tag in tags:
        key = f"tag:{tag}"
        redis.sadd(key, image_id)
    return {"message": "Tags added successfully"}

def get_images_by_tag(tag: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"tag:{tag}"
    images = redis.smembers(key)
    return list(images)

def mark_image_as_seen(session_id: str, image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    ensure_session(session_id)
    
    key = f"session:{session_id}:seen_images"
    added = redis.sadd(key, image_id)
    
    return added == 1


def ensure_session(session_id: str, ttl_seconds: int = 3600):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    key_seen = f"session:{session_id}:seen_images"
    key_tag_scores = f"session:{session_id}:tag_scores"
    
    if not redis.exists(key_seen):
        redis.sadd(key_seen, "__init__")
        redis.srem(key_seen, "__init__")
        redis.expire(key_seen, ttl_seconds)
    
    if not redis.exists(key_tag_scores):
        redis.hset(key_tag_scores, "__init__", "0")
        redis.hdel(key_tag_scores, "__init__")
        redis.expire(key_tag_scores, ttl_seconds)
    
    return True
    

def get_seen_images(session_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"session:{session_id}:seen_images"
    images = redis.smembers(key)
    return set(images)

def is_image_seen(session_id: str, image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"session:{session_id}:seen_images"
    return redis.sismember(key, image_id) == 1

def update_tag_scores(session_id: str, tag, delta: float):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"session:{session_id}:tag_scores"
    return redis.hincrbyfloat(key, tag, delta)

def get_tag_scores(session_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"session:{session_id}:tag_scores"
    raw_scores = redis.hgetall(key)
    return {k: float(v) for k, v in raw_scores.items()}

def get_top_global_images(count: int = 10):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"feed:global"
    return redis.zrevrange(key, 0, count - 1, withscores=True)

def get_global_score(image_id: str):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"feed:global"
    return redis.zscore(key, image_id)

def get_all_images():
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    key = f"feed:global"
    images = redis.zrange(key, 0, -1, withscores=True)
    return [img for img, _ in images]

def get_images_batch(image_ids: list[str]):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    pipe = redis.pipeline()
    for image_id in image_ids:
        pipe.hgetall(f"image:{image_id}")
    results = pipe.execute()
    
    images = {}
    for image_id, result in zip(image_ids, results):
        if result and len(result) > 0:
            images[image_id] = {
                "image_id": image_id,
                "image_url": result["image_url"],
                "image_tags": json.loads(result["image_tags"])
            }
    return images

def get_global_scores_batch(image_ids: list[str]):
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    key = f"feed:global"
    pipe = redis.pipeline()
    for image_id in image_ids:
        pipe.zscore(key, image_id)
    results = pipe.execute()
    
    scores = {}
    for image_id, score in zip(image_ids, results):
        scores[image_id] = float(score) if score is not None else 0.0
    return scores