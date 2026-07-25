import json

import redis

from config import CACHE_TTL_SECONDS, REDIS_DB, REDIS_HOST, REDIS_PORT

client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def get_cache(key):
    try:
        data = client.get(key)
        if data:
            return json.loads(data)
    except (redis.RedisError, json.JSONDecodeError):
        return None
    return None


def set_cache(key: str, value, ttl: int = CACHE_TTL_SECONDS):
    try:
        client.setex(key, ttl, json.dumps(value))
    except redis.RedisError:
        return

def delete_cache(key: str):
    try:
        client.delete(key)
    except redis.RedisError:
        return

def flush_cache():
    try:
        client.flushdb()
    except redis.RedisError:
        return
