from fastapi import HTTPException
from services.session import create_session
from fastapi import APIRouter
from pydantic import BaseModel

class SessionCreateRequest(BaseModel):
    preferred_tags: list[str]


router = APIRouter()

@router.post("/sessions/create")
async def create_session_route(request: SessionCreateRequest):
    preferred_tags = request.preferred_tags
    session_id = create_session(preferred_tags)
    return {"session_id": session_id,"message": "Session created successfully"}