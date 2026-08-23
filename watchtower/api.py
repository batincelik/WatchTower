import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from watchtower.config import get_settings
from watchtower.db import session
from watchtower.models import Check, CheckStatus, Monitor, MonitorType, Project
from watchtower.queue import enqueue_check
from watchtower.schemas import CheckRead, MonitorCreate, MonitorRead
from watchtower.security import SSRFBlockedError, validate_url

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = Redis.from_url(settings.redis_url)
    yield
    await app.state.redis.aclose()


app = FastAPI(title="Watchtower API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    identifier = request.headers.get("x-request-id", f"req_{uuid.uuid4().hex}")[:128]
    request.state.request_id = identifier
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = identifier
    return response


@app.exception_handler(SSRFBlockedError)
async def ssrf_error(request: Request, exc: SSRFBlockedError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": exc.code, "message": str(exc), "request_id": request.state.request_id}},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(session)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    await request.app.state.redis.ping()
    return {"status": "ready"}


@app.get("/api/v1/monitors", response_model=list[MonitorRead])
async def list_monitors(db: AsyncSession = Depends(session)) -> list[Monitor]:
    return list((await db.scalars(select(Monitor).order_by(Monitor.created_at.desc()))).all())


@app.post("/api/v1/monitors", response_model=MonitorRead, status_code=status.HTTP_201_CREATED)
async def create_monitor(payload: MonitorCreate, db: AsyncSession = Depends(session)) -> Monitor:
    if payload.browser_enabled or payload.monitor_type == MonitorType.VISUAL:
        raise HTTPException(
            status_code=422,
            detail="Browser monitoring is not available yet; no HTTP fallback will be substituted.",
        )
    await validate_url(str(payload.url), allow_private=settings.ssrf_allow_private_networks)
    project = (await db.scalars(select(Project).limit(1))).first()
    if project is None:
        project = Project(name="Default")
        db.add(project)
        await db.flush()
    monitor = Monitor(
        project_id=project.id,
        name=payload.name,
        url=str(payload.url),
        monitor_type=payload.monitor_type,
        interval_seconds=payload.interval_seconds,
        browser_enabled=payload.browser_enabled,
        selector=payload.selector,
        ignore_selectors=payload.ignore_selectors,
        ignore_regexes=payload.ignore_regexes,
        timeout_seconds=payload.timeout_seconds,
        change_threshold=payload.change_threshold,
        next_check_at=datetime.now(UTC),
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return monitor


async def get_monitor(monitor_id: uuid.UUID, db: AsyncSession) -> Monitor:
    monitor = await db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(404, "Monitor not found")
    return monitor


@app.get("/api/v1/monitors/{monitor_id}", response_model=MonitorRead)
async def monitor_detail(monitor_id: uuid.UUID, db: AsyncSession = Depends(session)) -> Monitor:
    return await get_monitor(monitor_id, db)


@app.post("/api/v1/monitors/{monitor_id}/check", response_model=CheckRead, status_code=202)
async def check_now(monitor_id: uuid.UUID, request: Request, db: AsyncSession = Depends(session)) -> Check:
    await get_monitor(monitor_id, db)
    active = await db.scalar(
        select(Check).where(Check.monitor_id == monitor_id, Check.status.in_([CheckStatus.QUEUED, CheckStatus.RUNNING]))
    )
    if active is not None:
        return active
    check = Check(monitor_id=monitor_id, status=CheckStatus.QUEUED, scheduled_at=datetime.now(UTC))
    db.add(check)
    await db.commit()
    await enqueue_check(request.app.state.redis, check.id)
    await db.refresh(check)
    return check


@app.post("/api/v1/monitors/{monitor_id}/pause", response_model=MonitorRead)
async def pause(monitor_id: uuid.UUID, db: AsyncSession = Depends(session)) -> Monitor:
    monitor = await get_monitor(monitor_id, db)
    monitor.enabled = False
    monitor.next_check_at = None
    await db.commit()
    return monitor


@app.post("/api/v1/monitors/{monitor_id}/resume", response_model=MonitorRead)
async def resume(monitor_id: uuid.UUID, db: AsyncSession = Depends(session)) -> Monitor:
    monitor = await get_monitor(monitor_id, db)
    monitor.enabled = True
    monitor.next_check_at = datetime.now(UTC)
    await db.commit()
    return monitor


@app.get("/api/v1/monitors/{monitor_id}/checks", response_model=list[CheckRead])
async def checks(monitor_id: uuid.UUID, db: AsyncSession = Depends(session)) -> list[Check]:
    await get_monitor(monitor_id, db)
    query = select(Check).where(Check.monitor_id == monitor_id).order_by(Check.created_at.desc()).limit(100)
    return list((await db.scalars(query)).all())
