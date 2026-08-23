import asyncio
import hashlib
import socket
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select

from watchtower.config import get_settings
from watchtower.db import Session
from watchtower.fetcher import FetchFailure, fetch_url
from watchtower.models import ChangeEvent, Check, CheckStatus, Monitor, MonitorType, Snapshot
from watchtower.pipeline import Candidate, make_candidate, text_difference
from watchtower.queue import reserve_check
from watchtower.security import SSRFBlockedError

settings = get_settings()


def _error_code(exc: Exception) -> str:
    if isinstance(exc, SSRFBlockedError):
        return "SSRF_BLOCKED"
    if isinstance(exc, FetchFailure):
        return exc.code
    message = str(exc)
    known = {"INVALID_SELECTOR", "SELECTOR_NOT_FOUND", "PRICE_PARSE_FAILED", "DNS_FAILURE"}
    return message if message in known else "CHECK_FAILED"


async def process_check(check_id: uuid.UUID, worker_id: str) -> None:
    async with Session.begin() as db:
        check = await db.scalar(select(Check).where(Check.id == check_id).with_for_update())
        if check is None or check.status != CheckStatus.QUEUED:
            return
        check.status = CheckStatus.RUNNING
        check.worker_id = worker_id
        check.started_at = datetime.now(UTC)
        check.lease_expires_at = datetime.now(UTC) + timedelta(seconds=60)
        monitor = await db.get(Monitor, check.monitor_id)
        if monitor is None:
            check.status = CheckStatus.FAILED
            check.error_code = "MONITOR_NOT_FOUND"
            return
        target_url = monitor.url
        monitor_type = monitor.monitor_type
        selector = monitor.selector
        ignore_selectors = list(monitor.ignore_selectors)
        ignore_regexes = list(monitor.ignore_regexes)
    try:
        result = await fetch_url(target_url, settings)
        if result.status_code in {403, 429}:
            raise FetchFailure("ACCESS_BLOCKED", f"Remote server returned {result.status_code}")
        if result.status_code >= 400 and monitor_type != MonitorType.STATUS:
            raise FetchFailure("HTTP_ERROR", f"Remote server returned {result.status_code}")
        if monitor_type == MonitorType.STATUS:
            value = str(result.status_code)
            candidate = Candidate(content_hash=hashlib.sha256(value.encode()).hexdigest(), text=value)
        else:
            candidate = make_candidate(
                monitor_type,
                result.body,
                selector=selector,
                ignore_selectors=ignore_selectors,
                ignore_regexes=ignore_regexes,
            )
        await persist_success(check_id, result.status_code, result.duration_ms, len(result.body), candidate)
    except Exception as exc:
        await persist_failure(check_id, _error_code(exc), str(exc))


async def persist_failure(check_id: uuid.UUID, code: str, message: str) -> None:
    async with Session.begin() as db:
        check = await db.get(Check, check_id, with_for_update=True)
        if check is None or check.status == CheckStatus.COMPLETED:
            return
        check.status = CheckStatus.FAILED
        check.finished_at = datetime.now(UTC)
        check.lease_expires_at = None
        check.error_code = code
        check.error_message = message[:1000]
        # No snapshot is written and Monitor.baseline_snapshot_id is untouched.


async def persist_success(
    check_id: uuid.UUID, http_status: int, duration_ms: int, content_size: int, candidate: Candidate
) -> None:
    async with Session.begin() as db:
        check = await db.scalar(select(Check).where(Check.id == check_id).with_for_update())
        if check is None or check.status == CheckStatus.COMPLETED:
            return
        monitor = await db.scalar(select(Monitor).where(Monitor.id == check.monitor_id).with_for_update())
        if monitor is None:
            return
        baseline = await db.get(Snapshot, monitor.baseline_snapshot_id) if monitor.baseline_snapshot_id else None
        snapshot = Snapshot(
            monitor_id=monitor.id,
            check_id=check.id,
            content_hash=candidate.content_hash,
            text_content=candidate.text,
            html_content=candidate.html,
            numeric_value=candidate.numeric_value,
            availability_state=candidate.availability_state,
        )
        db.add(snapshot)
        await db.flush()
        changed = baseline is not None and baseline.content_hash != snapshot.content_hash
        score = Decimal("0")
        if changed and baseline is not None:
            score, diff = text_difference(baseline.text_content or "", snapshot.text_content or "")
            if score >= monitor.change_threshold:
                change_type = monitor.monitor_type.value
                if monitor.monitor_type == MonitorType.PRICE:
                    if baseline.numeric_value is None:
                        change_type = "PRICE_APPEARED"
                    elif snapshot.numeric_value is None:
                        change_type = "PRICE_DISAPPEARED"
                    elif snapshot.numeric_value > baseline.numeric_value:
                        change_type = "PRICE_INCREASE"
                    else:
                        change_type = "PRICE_DECREASE"
                db.add(
                    ChangeEvent(
                        monitor_id=monitor.id,
                        previous_snapshot_id=baseline.id,
                        current_snapshot_id=snapshot.id,
                        change_type=change_type,
                        change_score=score,
                        summary=f"{change_type.replace('_', ' ').title()} detected",
                        diff=diff,
                    )
                )
            else:
                changed = False
        monitor.baseline_snapshot_id = snapshot.id
        monitor.last_checked_at = datetime.now(UTC)
        check.status = CheckStatus.COMPLETED
        check.finished_at = datetime.now(UTC)
        check.lease_expires_at = None
        check.http_status = http_status
        check.duration_ms = duration_ms
        check.content_size = content_size
        check.changed = changed
        check.change_score = score


async def main() -> None:
    worker_id = f"{socket.gethostname()}:{uuid.uuid4().hex[:10]}"
    redis = Redis.from_url(settings.redis_url)
    semaphore = asyncio.Semaphore(settings.worker_concurrency)
    tasks: set[asyncio.Task[None]] = set()
    try:
        while True:
            check_id = await reserve_check(redis)
            if check_id is None:
                continue
            await semaphore.acquire()
            task = asyncio.create_task(process_check(check_id, worker_id))
            task.add_done_callback(lambda done: semaphore.release())
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
