import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker


class DB:

    async def init_db(self):
        engine = create_async_engine(
            os.environ['DB_URL'],
        )
        self.db_engine = engine
        async_session = sessionmaker(engine, AsyncSession, expire_on_commit=False)
        self.db = async_session

    async def close_db(self):
        await self.db_engine.dispose()
