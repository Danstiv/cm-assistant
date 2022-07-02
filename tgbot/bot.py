import asyncio
import os
import signal
import sys

import dotenv
import pyrogram
try:
    import uvloop
except ImportError:
    uvloop = None

from sqlalchemy import select
from tgbot import (
    custom_methods,
    db,
    exception_handler,
    pyrogram_client_state_management,
)
from tgbot.core import Core
from tgbot.db import tables
from tgbot.handler_decorators import get_handlers
from tgbot.keyboard_handler import KeyboardHandler
from tgbot.message_handler import MessageHandler
from tgbot.user_handler import UserHandler

dotenv.load_dotenv()


class BotController(
    Core,
    db.DB,
    KeyboardHandler,
    MessageHandler,
    UserHandler,
):

    def __init__(self, bot_name, use_uvloop=False, user_table=None):
        for var in ['api_id', 'api_hash', 'bot_token', 'db_url', 'dev_ids']:
            setattr(self, var, os.getenv(var.upper()))
            if not getattr(self, var):
                raise RuntimeError(f'"{var.upper()}" environment variable not specified')
        self.dev_ids = [int(i) for i in self.dev_ids.split(',')]
        self.bot_name = bot_name
        self.app = None
        if sys.platform != 'win32' and use_uvloop:
            if not uvloop:
                self.log.warning('uvloop не установлен')
            else:
                uvloop.install()
        self.User = user_table or db.tables.User
        super().__init__()

    def get_global_filter(self):
        pass

    async def initialize(self):
        self.app.controller = self
        pyrogram.types.Message.reply = custom_methods.reply
        exception_handler.wrap_methods(self)
        global_filter = self.get_global_filter()
        for handler in get_handlers():
            decorator = getattr(self.app, handler['decorator_name'])
            if global_filter and handler['decorator_name'] == 'on_message':
                if not handler['handler_args']:
                    handler['handler_args'] = [global_filter]
                else:
                    handler['handler_args'][0] = global_filter & handler['handler_args'][0]
            decorator = decorator(*handler['handler_args'], **handler['handler_kwargs'])
            method = getattr(self, handler['handler_name'])
            decorator(method)
        await self.init_db()

    async def start(self):
        try:
            asyncio.get_running_loop().add_signal_handler(signal.SIGINT, self.stop_from_signal)
        except NotImplementedError:
            signal.signal(signal.SIGINT, self.stop_from_signal)
        self.app = pyrogram.Client(
            'telegram_account',
            api_id=self.api_id,
            api_hash=self.api_hash,
            bot_token=self.bot_token,
            workdir='.',
            sleep_threshold=0,
        )
        await self.initialize()
        async with self.db.begin() as db:
            state = (await db.execute(select(tables.PyrogramClientState))).scalar()
        await pyrogram_client_state_management.set_pyrogram_client_state_and_start(self.app, state.state if state else None)
        self.add_task(self.message_sender, 23)
        self.log.info('Приложение запущено')
        try:
            await self.monitor_tasks()
        finally:
            print('\r', end='')  # To remove C character from terminal
            self.log.info('Выход')
            state = pyrogram_client_state_management.get_pyrogram_client_state(self.app)
            await self.app.stop()
            async with self.db.begin() as db:
                db_state = (await db.execute(select(tables.PyrogramClientState))).scalar()
                if not db_state:
                    db.add(tables.PyrogramClientState(state=state))
                else:
                    db_state.state = state
            await self.close_db()

    def stop_from_signal(self, *args, **kwargs):
        self.stop()

    def stop(self):
        self.canceling = True
        self.monitor_task.cancel()
        [task.cancel() for task in self.async_tasks]
