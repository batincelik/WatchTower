import asyncio
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select

from watchtower.config import get_settings
from watchtower.db import Session
from watchtower.models import Check, CheckStatus, Monitor
from watchtower.queue import enqueue_check


async def schedule_due(redis: Redis, batch_size: int = 100) -> int:
    now = datetime.now(UTC)
    queued: list[Check] = []
    async with Session.begin() as db:
        due = (
            await db.scalars(
                select(Monitor)
                .where(Monitor.enabled.is_(True), Monitor.next_check_at <= now)
                .order_by(Monitor.next_check_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for monitor in due:
            active = await db.scalar(
                select(Check.id).where(
                    Check.monitor_id == monitor.id,
                    Check.status.in_([CheckStatus.QUEUED, CheckStatus.RUNNING]),
                )
            )
            # Advance atomically even when an active job exists, bounding queue growth.
            monitor.next_check_at = now + timedelta(seconds=monitor.interval_seconds)
            if active is None:
                check = Check(monitor_id=monitor.id, status=CheckStatus.QUEUED, scheduled_at=now)
                db.add(check)
                queued.append(check)
        await db.flush()
    for check in queued:
        await enqueue_check(redis, check.id)
    return len(queued)


async def main() -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    try:
        while True:
            await schedule_due(redis)
            await asyncio.sleep(5)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
