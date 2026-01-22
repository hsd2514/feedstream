from fastapi import HTTPException
from services.redis import get_redis
import uuid
import json
from services.feed import update_tag_scores, ensure_session

def create_session(preferred_tags: list[str]):
    session_id = str(uuid.uuid4())

    ensure_session(session_id)
    tag_scores = {tag: 0 for tag in preferred_tags}

    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis connection failed")
    
    for tag in preferred_tags:
        update_tag_scores(session_id, tag, 3)

    return session_id