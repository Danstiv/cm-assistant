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

from tgbot import (
    custom_methods,
    db,
    exception_handler,
)
from tgbot.core import TGBotCoreMixin
from tgbot.handler_decorators import get_handlers
from tgbot.gui import TGBotGUIMixin
from tgbot.messages import TGBotMessagesMixin
from tgbot.users import TGBotUsersMixin

dotenv.load_dotenv()


class BotController(
    TGBotCoreMixin,
    db.TGBotDBMixin,
    TGBotGUIMixin,
    TGBotMessagesMixin,
    TGBotUsersMixin,
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
                raise ValueError('uvloop is not installed')
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
        await self.app.start()
        self.add_task(self.message_sender, 23)
        self.log.info('Приложение запущено')
        try:
            await self.monitor_tasks()
        finally:
            print('\r', end='')  # To remove C character from terminal
            self.log.info('Выход')
            await self.app.stop()
            await self.close_db()

    def stop_from_signal(self, *args, **kwargs):
        self.stop()

    def stop(self):
        self.canceling = True
        self.monitor_task.cancel()
        [task.cancel() for task in self.async_tasks]
