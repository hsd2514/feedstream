from redis import Redis 
import os
from config import REDIS_HOST, REDIS_PORT, REDIS_DB


def get_redis():
    try:
        return Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return None



