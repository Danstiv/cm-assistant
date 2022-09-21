import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from tgbot.enums import Category
from tgbot.group_manager import group_manager
from tgbot.handler_decorators import on_callback_query, on_message
from tgbot.helpers import ContextVarWrapper

db = ContextVarWrapper('db')


class TGBotDBMixin:

    async def init_db(self):
        self.db_engine = create_async_engine(
            self.db_url,
        )
        async_session = sessionmaker(self.db_engine, AsyncSession, expire_on_commit=False)
        self.session = async_session

    async def close_db(self):
        await self.db_engine.dispose()

    @on_message(category=Category.INITIALIZE, group=group_manager.CREATE_SESSION)
    @on_callback_query(category=Category.INITIALIZE, group=group_manager.CREATE_SESSION)
    async def create_session(self, update):
        db.set_context_var_value(self.session())

    @on_message(category=Category.RESTORE, group=group_manager.ROLLBACK_SESSION)
    @on_callback_query(category=Category.RESTORE, group=group_manager.ROLLBACK_SESSION)
    async def rollback_session(self, update):
        await db.rollback()

    @on_message(category=Category.FINISH, group=group_manager.COMMIT_SESSION)
    @on_callback_query(category=Category.FINISH, group=group_manager.COMMIT_SESSION)
    async def commit_session(self, update):
        await db.commit()

    @on_message(category=Category.FINALIZE, group=group_manager.RESET_SESSION_CONTEXT)
    @on_callback_query(category=Category.FINALIZE, group=group_manager.RESET_SESSION_CONTEXT)
    async def reset_session_context(self, update):
        db.reset_context_var()
