import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker


class TGBotDBMixin:

    async def init_db(self):
        self.db_engine = create_async_engine(
            self.db_url,
        )
        async_session = sessionmaker(self.db_engine, AsyncSession, expire_on_commit=False)
        self.db = async_session

    async def close_db(self):
        await self.db_engine.dispose()
