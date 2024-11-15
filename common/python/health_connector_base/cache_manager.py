import os

import redis


class RedisCacheManager:
    def __init__(self):
        self.client = redis.StrictRedis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )

    def set_value(self, key, value):
        self.client.set(key, value)

    def get_value(self, key):
        return self.client.get(key)
