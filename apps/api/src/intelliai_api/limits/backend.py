"""Redis-backed protection state: token buckets and concurrency leases.

Two operations, each a single Lua script, because **atomicity is the
entire point**. A read-then-write from Python is a race that fails
precisely under the concurrent load the limiter exists to control — it
would pass every quiet test and leak exactly when it mattered.

Time comes from ``redis.call('TIME')``, not from the caller. Redis is
then the single clock for every gateway instance; with client-supplied
timestamps a fast-clocked instance would refill its buckets early and
quietly grant more than the plan allows.

Nothing here is durable. Buckets and leases may be lost at any moment
without a revenue consequence — which is exactly why they are allowed to
live in Redis at all (ADR-0022).
"""

from typing import Any, cast

# Token bucket. KEYS[1] = bucket. ARGV = capacity, refill/s, cost, ttl_ms.
# Returns {allowed, remaining, retry_after_seconds, reset_seconds}.
_CONSUME_LUA = """
local now = redis.call('TIME')
local now_ms = (tonumber(now[1]) * 1000) + math.floor(tonumber(now[2]) / 1000)

local capacity = tonumber(ARGV[1])
local refill   = tonumber(ARGV[2])
local cost     = tonumber(ARGV[3])
local ttl_ms   = tonumber(ARGV[4])

local state  = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts     = tonumber(state[2])
if tokens == nil or ts == nil then
    tokens = capacity
    ts = now_ms
end

local elapsed = math.max(0, now_ms - ts) / 1000.0
tokens = math.min(capacity, tokens + (elapsed * refill))

local allowed = 0
local retry_after = 0
if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
else
    retry_after = math.ceil((cost - tokens) / refill)
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now_ms)
redis.call('PEXPIRE', KEYS[1], ttl_ms)

local reset = math.ceil((capacity - tokens) / refill)
return {allowed, math.floor(tokens), retry_after, reset}
"""

# Concurrency lease. A sorted set scored by expiry, so a lease held by a
# process that died is evicted by the next caller instead of leaking a
# slot forever: self-healing, with no reconciliation job.
# KEYS[1] = lease set. ARGV = limit, lease_id, ttl_ms.
_ACQUIRE_LEASE = """
local now = redis.call('TIME')
local now_ms = (tonumber(now[1]) * 1000) + math.floor(tonumber(now[2]) / 1000)

local limit  = tonumber(ARGV[1])
local lease  = ARGV[2]
local ttl_ms = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
local held = redis.call('ZCARD', KEYS[1])
if held >= limit then
    return {0, held}
end
redis.call('ZADD', KEYS[1], now_ms + ttl_ms, lease)
redis.call('PEXPIRE', KEYS[1], ttl_ms * 2)
return {1, held + 1}
"""


class RedisLimiterBackend:
    """Thin, atomic operations over a Redis client.

    The client is injected rather than constructed here so the caller
    owns connection policy — in particular the short socket timeout that
    makes failing open also fail *fast* (a limiter that hangs for thirty
    seconds has taken the platform down more effectively than one that
    refuses).
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        self._bucket = client.register_script(_CONSUME_LUA)
        self._acquire = client.register_script(_ACQUIRE_LEASE)

    async def consume(
        self, key: str, *, capacity: int, refill_per_second: float, cost: int = 1
    ) -> tuple[bool, int, int, int]:
        """Take one token. Returns (allowed, remaining, retry_after, reset)."""
        ttl_ms = int((capacity / max(refill_per_second, 0.001)) * 1000) + 60_000
        result = cast(
            list[int],
            await self._bucket(keys=[key], args=[capacity, refill_per_second, cost, ttl_ms]),
        )
        allowed, remaining, retry_after, reset = result
        return bool(allowed), int(remaining), int(retry_after), int(reset)

    async def acquire_slot(
        self, key: str, *, limit: int, lease_id: str, ttl_ms: int
    ) -> tuple[bool, int]:
        """Claim one in-flight slot. Returns (acquired, held_after)."""
        result = cast(list[int], await self._acquire(keys=[key], args=[limit, lease_id, ttl_ms]))
        return bool(result[0]), int(result[1])

    async def release_slot(self, key: str, *, lease_id: str) -> None:
        await self._client.zrem(key, lease_id)

    async def close(self) -> None:
        await self._client.aclose()
