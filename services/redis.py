from redis import Redis 
import os
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


def get_redis():
    try:
        redis_kwargs = {
            'host': REDIS_HOST,
            'port': REDIS_PORT,
            'db': REDIS_DB,
            'decode_responses': True,
            'encoding': 'utf-8'
        }
        if REDIS_PASSWORD:
            redis_kwargs['password'] = REDIS_PASSWORD
        
        if 'upstash' in REDIS_HOST.lower():
            redis_kwargs['ssl'] = True
        
        return Redis(**redis_kwargs)
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return None



