from services.feed import get_image, get_seen_images, is_image_seen, mark_image_as_seen, update_tag_scores, get_tag_scores,get_all_images,get_top_global_images,get_images_by_tag,get_global_score,increment_likes,update_engagement,increment_dislikes,ensure_session,get_images_batch,get_global_scores_batch
from services.redis import get_redis
from services.sse_manager import broadcast_to_session, has_active_connections
from fastapi import HTTPException
import asyncio



def get_candidate(session_id:str):
    all_images = get_all_images()

    tag_scores = get_tag_scores(session_id)


    tag_based_images = []
    if tag_scores:
        top_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)[:3]    
        for tag, score in top_tags:
            images_by_tag = get_images_by_tag(tag)
            tag_based_images.extend(images_by_tag)

    candidate = list(set(all_images + tag_based_images))
    return candidate

def get_prefetched_batch(session_id: str, count: int = 10):
    seen_images = get_seen_images(session_id)
    if len(seen_images) >= 50:
        return []
    
    candidate = get_candidate(session_id)
    available = [img for img in candidate if img not in seen_images]
    
    if not available:
        return []
    
    global_scores = get_global_scores_batch(available)
    images_dict = get_images_batch(available)
    
    tag_scores = get_tag_scores(session_id)
    scored = []
    
    for image_id in available:
        if image_id not in images_dict:
            continue
        image = images_dict[image_id]
        global_score = global_scores.get(image_id, 0)
        image_tags = image["image_tags"]
        tag_boost = sum(tag_scores.get(tag, 0) for tag in image_tags)
        final_score = global_score + tag_boost
        scored.append((image_id, final_score))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    top_images = [image_id for image_id, _ in scored[:count]]
    
    prefetched = [images_dict[img_id] for img_id in top_images if img_id in images_dict]
    
    return prefetched

def generate_feed(session_id:str):

    seen_images = get_seen_images(session_id)
    if len(seen_images)>=50:
        return {"message": "All 50 images are shown"}

    candidate = get_candidate(session_id)

    available = [img for img in candidate if img not in seen_images]
    
    if not available:
        return {"message": "All 50 images are shown"}

    global_scores = get_global_scores_batch(available)
    images_dict = get_images_batch(available)

    tag_scores = get_tag_scores(session_id)
    scored = []

    for image_id in available:
        if image_id not in images_dict:
            continue
        image = images_dict[image_id]
        global_score = global_scores.get(image_id, 0)
        image_tags = image["image_tags"]
        tag_boost = sum(tag_scores.get(tag, 0) for tag in image_tags)
        final_score = global_score + tag_boost
        scored.append((image_id, final_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_20 = [image_id for image_id, _ in scored[:20]]

    visible_ids = top_20[:10]
    prefetched_ids = top_20[10:20]

    for image_id in visible_ids + prefetched_ids:
        mark_image_as_seen(session_id, image_id)

    visible_images = [images_dict[img_id] for img_id in visible_ids if img_id in images_dict]
    prefetched_images = [images_dict[img_id] for img_id in prefetched_ids if img_id in images_dict]
    
    return {
        "visible": visible_images,
        "prefetched": prefetched_images
    }



async def like_handler(session_id:str, image_id:str):
    ensure_session(session_id)
    image = get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    increment_likes(image_id)
    update_engagement(image_id)
    for tag in image["image_tags"]:
        update_tag_scores(session_id, tag, 1.0)
    
    # Run prefetch update in background - don't block the response
    if has_active_connections(session_id):
        asyncio.create_task(_broadcast_prefetch_update(session_id))
    
    return {"message": "Liked", "liked_tags": image["image_tags"]}

async def dislike_handler(session_id:str, image_id:str):
    ensure_session(session_id)
    image = get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    increment_dislikes(image_id)
    update_engagement(image_id)
    
    tag_scores = get_tag_scores(session_id)
    image_tags = image["image_tags"]
    
    for tag in image_tags:
        current_score = tag_scores.get(tag, 0)
        if current_score > 0:
            update_tag_scores(session_id, tag, -0.5)
        elif current_score < 0:
            update_tag_scores(session_id, tag, -1.0)
        else:
            pass
    
    # Run prefetch update in background - don't block the response
    if has_active_connections(session_id):
        asyncio.create_task(_broadcast_prefetch_update(session_id))
    
    return {"message": "Disliked", "disliked_tags": image_tags}


async def _broadcast_prefetch_update(session_id: str):
    """Background task to calculate and broadcast prefetch updates"""
    try:
        prefetched = get_prefetched_batch(session_id, 10)
        await broadcast_to_session(session_id, {
            "type": "prefetch_update",
            "prefetched": prefetched
        })
    except Exception as e:
        print(f"Error broadcasting prefetch update: {e}")
    