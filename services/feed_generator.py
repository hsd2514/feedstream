from services.feed import get_image, get_seen_images, is_image_seen, mark_image_as_seen, update_tag_scores, get_tag_scores,get_all_images,get_top_global_images,get_images_by_tag,get_global_score,increment_likes,update_engagement,increment_dislikes,ensure_session
from services.redis import get_redis
from fastapi import HTTPException



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

def generate_feed(session_id:str):

    seen_images = get_seen_images(session_id)
    if len(seen_images)>=50:
        return {"message": "All 50 images are shown"}

    candidate = get_candidate(session_id)

    available = [img for img in candidate if img not in seen_images]
    

    tag_scores = get_tag_scores(session_id)
    scored = []

    for image_id in available:
        global_score = get_global_score(image_id) or 0
        image = get_image(image_id)
        if not image:
            continue
        image_tags = image["image_tags"]
        tag_boost = sum(tag_scores.get(tag, 0) for tag in image_tags)
        final_score = global_score + tag_boost
        scored.append((image_id, final_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_10 = [image_id for image_id, _ in scored[:10]]


    for image_id in top_10:
        mark_image_as_seen(session_id, image_id)

    feed_images = []

    for image_id in top_10:
        image = get_image(image_id)
        if not image:
            continue
        feed_images.append(image)
    return feed_images



def like_handler(session_id:str, image_id:str):
    ensure_session(session_id)
    image = get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    increment_likes(image_id)
    update_engagement(image_id)
    for tag in image["image_tags"]:
        update_tag_scores(session_id, tag, 1.0)
    return {"message": "Liked"}

def dislike_handler(session_id:str, image_id:str):
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
    
    return {"message": "Disliked"}
    