from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from services.feed_generator import generate_feed, like_handler, dislike_handler
from services.sse_manager import register_connection, unregister_connection
import asyncio
import json

router = APIRouter()

@router.get("/feed")
async def get_feed(session_id: str):
    return generate_feed(session_id)

@router.get("/feed/stream")
async def stream_feed_updates(session_id: str):
    queue = asyncio.Queue(maxsize=10)
    register_connection(session_id, queue)
    
    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"ping\"}\n\n"
                    continue
        except GeneratorExit:
            pass
        except Exception as e:
            print(f"SSE error for session {session_id}: {e}")
        finally:
            unregister_connection(session_id, queue)
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/like")
async def like_image(session_id: str, image_id: str):
    return await like_handler(session_id, image_id)

@router.post("/dislike")
async def dislike_image(session_id: str, image_id: str):
    return await dislike_handler(session_id, image_id)


