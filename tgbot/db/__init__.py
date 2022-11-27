import asyncio
from functools import wraps
import os

import sqlalchemy
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
        await db.close()
        db.restrict_access_to_context_var_value()
        db.reset_context_var()


class DBManager:

    def __init__(self, controller, wait_for_transaction=False, commit_after_cancel=False, path_to_session='session'):
        self.controller = controller
        self.wait_for_transaction = wait_for_transaction
        self.commit_after_cancel = commit_after_cancel
        self.path_to_session = path_to_session

    async def _wait_for_transaction(self):
        self._wait_for_transaction_result = None
        self._wait_for_transaction_event = asyncio.Event()
        sqlalchemy.event.listen(db.sync_session, 'after_commit', self._after_commit)
        sqlalchemy.event.listen(db.sync_session, 'after_soft_rollback', self._after_rollback)
        await self._wait_for_transaction_event.wait()
        if not self._wait_for_transaction_result:
            # Somewhere in another task something went wrong, we should not continue
            raise RuntimeError('Previous transaction was rollbacked')

    def _after_rollback(self, session, previous_transaction):
        self._wait_for_transaction_result = False
        self._wait_for_transaction_event.set()

    def _after_commit(self, session):
        self._wait_for_transaction_result = True
        self._wait_for_transaction_event.set()

    async def __aenter__(self):
        if self.wait_for_transaction:
            await self._wait_for_transaction()
        self.previous_db_value = None
        if db.is_set:
            # We want this context manager to have minimal impact on the state of the application and return the state of the db back upon completion.
            # Therefore, we ignore restrictions.
            self.previous_db_value = db.get_context_var_value(ignore_restrictions=True)
        path = self.path_to_session.split('.')
        session = self.controller
        for element in path:
            session = getattr(session, element)
        db.set_context_var_value(session())

    async def __aexit__(self, exc_type, exc, tb):
        # First we get the session and restrict access to it,
        # So that only we can work with it.
        # And for sure, no one would have time to accidentally write something while a commit or close is being performed.
        session = db.get_context_var_value()
        db.restrict_access_to_context_var_value()
        if self.previous_db_value is not None:
            db.set_context_var_value(self.previous_db_value)
        else:
            db.reset_context_var()
        commit = False
        if exc is None or (isinstance(exc, asyncio.exceptions.CancelledError) and self.commit_after_cancel == True):
            commit = True
        await (session.commit() if commit else session.rollback())
        await session.close()
        return True if isinstance(exc, asyncio.exceptions.CancelledError) else False


def with_db(*db_manager_args, **db_manager_kwargs):
    def decorator(method):
        @wraps(method)
        async def wrapper(self, *args, **kwargs):
            async with DBManager(self, *db_manager_args, **db_manager_kwargs):
                return await method(self, *args, **kwargs)
        return wrapper
    return decorator
