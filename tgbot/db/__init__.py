from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine


async def init_db(controller):
    engine = create_async_engine(
        "sqlite+aiosqlite:///db.sqlite3",
    )
    controller.db_engine = engine
    async_session = AsyncSession(engine, expire_on_commit=False)
    controller.db = async_session
