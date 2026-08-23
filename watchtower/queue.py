import uuid
from typing import Any, cast

from redis.asyncio import Redis

QUEUE_KEY = "watchtower:jobs:monitor_check"


async def enqueue_check(redis: Redis, check_id: uuid.UUID) -> None:
    await cast(Any, redis.lpush(QUEUE_KEY, str(check_id)))


async def reserve_check(redis: Redis, timeout: int = 5) -> uuid.UUID | None:
    result = await cast(Any, redis.brpop([QUEUE_KEY], timeout=timeout))
    if result is None:
        return None
    return uuid.UUID(result[1].decode())
