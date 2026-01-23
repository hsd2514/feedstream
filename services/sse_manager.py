from typing import Dict, Set
import asyncio

active_connections: Dict[str, Set[asyncio.Queue]] = {}

def register_connection(session_id: str, queue: asyncio.Queue):
    if session_id not in active_connections:
        active_connections[session_id] = set()
    
    if len(active_connections[session_id]) >= 3:
        old_queue = next(iter(active_connections[session_id]))
        active_connections[session_id].discard(old_queue)
    
    active_connections[session_id].add(queue)

def unregister_connection(session_id: str, queue: asyncio.Queue):
    if session_id in active_connections:
        active_connections[session_id].discard(queue)
        if not active_connections[session_id]:
            del active_connections[session_id]

def has_active_connections(session_id: str) -> bool:
    return session_id in active_connections and len(active_connections[session_id]) > 0

async def broadcast_to_session(session_id: str, message: dict):
    if session_id not in active_connections:
        return
    
    import json
    message_str = f"data: {json.dumps(message)}\n\n"
    
    disconnected = set()
    for queue in list(active_connections[session_id]):
        try:
            queue.put_nowait(message_str)
        except asyncio.QueueFull:
            disconnected.add(queue)
        except Exception:
            disconnected.add(queue)
    
    for queue in disconnected:
        unregister_connection(session_id, queue)
