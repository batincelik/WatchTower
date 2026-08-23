from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from watchtower.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def session() -> AsyncIterator[AsyncSession]:
    async with Session() as db:
        yield db
