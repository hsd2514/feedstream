from fastapi import HTTPException
from services.redis import get_redis
import json


#store images in redis
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
    like,dislike = get_engagement(image_id)
    score = (like*2)-(dislike*1)
    key = f"feed:global:{score}:{image_id}"
    score = redis.zadd(key, {image_id: score})
    return score
