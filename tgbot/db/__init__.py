import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from tgbot.group_manager import group_manager
from tgbot.helpers import ContextVarWrapper
db = ContextVarWrapper('db')

from tgbot.handler_decorators import on_callback_query, on_message


class TGBotDBMixin:

    async def init_db(self):
        self.db_engine = create_async_engine(
            self.db_url,
        )
        async_session = sessionmaker(self.db_engine, AsyncSession, expire_on_commit=False)
        self.session = async_session

    async def close_db(self):
        await self.db_engine.dispose()
