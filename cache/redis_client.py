"""
Redis caching layer with TTL management.
"""
import json
import logging
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator
from redis.asyncio import Redis, from_url
from config.settings import REDIS_URL

logger = logging.getLogger(__name__)

# Cache TTL Constants
# Static data — doesn't change day-to-day (train routes, schedules, station stops)
TRAINS_BETWEEN_TTL      = 86400        # 24h  — exact date key, guards same-session re-queries
TRAINS_BETWEEN_PERM_TTL = 2592000      # 30 days — date-independent, filtered by day-of-week at read time
TRAIN_SCHEDULE_PERM_TTL = 2592000      # 30 days — date-independent permanent schedule cache

# Dynamic data — changes frequently
AVAILABILITY_TTL        = 300          # 5 minutes

class CacheClient:
    def __init__(self):
        self.redis: Optional[Redis] = None

    async def connect(self):
        self.redis = from_url(REDIS_URL, decode_responses=True)
        # Test connection
        await self.redis.ping()
        logger.info("Connected to Redis successfully.")

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[dict]:
        if not self.redis:
            return None
        try:
            val = await self.redis.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Redis get error for {key}: {e}")
        return None

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        if not self.redis:
            return
        try:
            val_str = json.dumps(value)
            await self.redis.set(key, val_str, ex=ttl_seconds)
        except Exception as e:
            logger.error(f"Redis set error for {key}: {e}")

    async def delete(self, key: str) -> None:
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error for {key}: {e}")

    async def exists(self, key: str) -> bool:
        if not self.redis:
            return False
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists error for {key}: {e}")
        return False

    async def get_ttl(self, key: str) -> int:
        """Return remaining TTL in seconds. -2 = doesn't exist, -1 = no TTL."""
        if not self.redis:
            return -2
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl error for {key}: {e}")
        return -2

    async def acquire_irctc_token(self, max_wait_seconds: float = 8.0) -> bool:
        """
        Global token-bucket rate limiter for IRCTC calls, shared across all
        workers and machines via Redis.

        Allows IRCTC_RATE_LIMIT calls per second globally. If the bucket is
        empty, waits up to max_wait_seconds for a token to become available.
        Returns True if a token was acquired, False if timed out (caller should
        degrade gracefully instead of hitting IRCTC).

        Token bucket algorithm (atomic Lua script):
          - Bucket refills at `rate` tokens/second up to `capacity`.
          - Each call consumes one token.
          - State stored as (token_count, last_refill_timestamp) in Redis.
        """
        if not self.redis:
            return True  # No Redis — don't block (degraded mode)

        # Tune these two values to stay under IRCTC's radar
        rate = 10        # tokens added per second (= max sustained IRCTC call rate globally)
        capacity = 20    # burst capacity (handles short spikes above the sustained rate)

        lua_script = """
        local key       = KEYS[1]
        local rate      = tonumber(ARGV[1])
        local capacity  = tonumber(ARGV[2])
        local now       = tonumber(ARGV[3])

        local data      = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens    = tonumber(data[1]) or capacity
        local last      = tonumber(data[2]) or now

        local elapsed   = math.max(0, now - last)
        tokens          = math.min(capacity, tokens + elapsed * rate)

        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 60)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 60)
            return 0
        end
        """

        deadline = asyncio.get_event_loop().time() + max_wait_seconds
        while True:
            try:
                result = await self.redis.eval(
                    lua_script, 1, "irctc:rate_limit",
                    rate, capacity, time.time()
                )
                if result == 1:
                    return True
            except Exception as e:
                logger.warning(f"Rate limiter error: {e}")
                return True  # Fail open — don't block on Redis errors

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("[RateLimit] IRCTC token wait timed out — degrading gracefully")
                return False
            # Wait proportional to how full the bucket will be, capped at 0.5s
            await asyncio.sleep(min(0.5, 1.0 / rate))

    @asynccontextmanager
    async def lock(self, key: str, timeout: int = 30, blocking_timeout: int = 15) -> AsyncIterator[bool]:
        """
        Distributed lock to prevent cache stampede across multiple workers/instances.
        Yields True if the lock was acquired, False if Redis is unavailable (non-blocking fallback).

        Usage:
            async with cache_client.lock("my-key") as acquired:
                if acquired:
                    # do the expensive work
        """
        if not self.redis:
            yield False
            return
        redis_lock = self.redis.lock(f"lock:{key}", timeout=timeout, blocking_timeout=blocking_timeout)
        acquired = False
        try:
            acquired = await redis_lock.acquire()
            yield acquired
        except Exception as e:
            logger.warning(f"Redis lock error for {key}: {e}")
            yield False
        finally:
            if acquired:
                try:
                    await redis_lock.release()
                except Exception:
                    pass  # Lock may have already expired


# Global instance
cache_client = CacheClient()
