from fastapi import APIRouter
from services.feed_generator import generate_feed, like_handler, dislike_handler


router = APIRouter()

@router.get("/feed")
async def get_feed(session_id: str):
    return generate_feed(session_id)

@router.post("/like")
async def like_image(session_id: str, image_id: str):
    return like_handler(session_id, image_id)

@router.post("/dislike")
async def dislike_image(session_id: str, image_id: str):
    return dislike_handler(session_id, image_id)