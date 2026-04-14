import redis
import os
import json

client = redis.Redis(host='localhost', port=6379, db=0)

def get_cache(key):
    data = client.get(key)
    if data:
        return json.loads(data)
    return None

def set_cache(key:str, value, ttl: int = 3600):
    client.setex(key, ttl, json.dumps(value))

def delete_cache(key: str):
    client.delete(key)

def flush_cache():
    client.flushdb()