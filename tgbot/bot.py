import asyncio
import logging
import logging.handlers
import os
import signal
import sys

import dotenv
import pyrogram
try:
    import uvloop
except ImportError:
    uvloop = None

from . import custom_methods
from . import db
from . import exception_handler
from .handler_decorators import get_handlers
from .keyboard_handler import KeyboardHandler
from .logging_helpers import Formatter, WarningErrorHandler
from .message_handler import MessageHandler

dotenv.load_dotenv()

LOG_MAX_SIZE = 10*2**20  # 10MB
LOG_MAX_BACKUPS = 9


class BotController(
    MessageHandler,
    KeyboardHandler,
    db.DB,
):

    def __init__(self, bot_name, api_id=None, api_hash=None, use_uvloop=False):
        self.api_id = api_id or os.environ['API_ID']
        self.api_hash = api_hash or os.environ['API_HASH']
        self.async_tasks = []
        self.monitor_task = None
        self.canceling = False
        self.log = logging.getLogger(bot_name)
        self.log.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        self.log.addHandler(console_handler)
        file_handler = logging.handlers.RotatingFileHandler(
            'log.log',
            encoding='utf-8',
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_MAX_BACKUPS
        )
        file_handler.setLevel(logging.DEBUG)
        detailed_formatter = Formatter(
            '%(asctime)s - %(levelname)s - %(module)s'
            '.%(funcName)s (%(lineno)d)\n%(message)s'
        )
        file_handler.setFormatter(detailed_formatter)
        self.log.addHandler(file_handler)
        file_error_handler = logging.handlers.RotatingFileHandler(
            'error.log',
            encoding='utf-8',
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_MAX_BACKUPS,
            delay=True
        )
        file_error_handler.setLevel(logging.ERROR)
        file_error_handler.setFormatter(detailed_formatter)
        self.log.addHandler(file_error_handler)
        warning_error_handler = WarningErrorHandler(self)
        warning_error_handler.setFormatter(detailed_formatter)
        self.log.addHandler(warning_error_handler)
        self.app = None
        if sys.platform != 'win32' and use_uvloop:
            if not uvloop:
                self.log.warning('uvloop не установлен')
            else:
                uvloop.install()
        super().__init__()

    def add_task(self, callable, *args, name=None, **kwargs):
        name = name or callable.__name__
        task = asyncio.create_task(callable(*args, **kwargs), name=name)
        self.async_tasks.append(task)
        if self.monitor_task:
            self.monitor_task.cancel()
        self.log.debug(f'Добавлена асинхронная задача {name}')

    async def monitor_tasks(self):
        while True:
            if self.canceling:
                break
            if not self.async_tasks:
                self.monitor_task = asyncio.create_task(asyncio.Event().wait())
            else:
                self.monitor_task = asyncio.create_task(
                    asyncio.wait(
                        self.async_tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                )
            try:
                done_tasks, pending_tasks = await self.monitor_task
            except asyncio.exceptions.CancelledError:
                if not self.canceling:
                    continue
                break
            for task in done_tasks:
                try:
                    task.result()
                    self.log.debug(f'Асинхронная задача "{task.get_name()}" выполнена')
                except Exception:
                    self.log.exception(f'Необработанное исключение в асинхронной задаче "{task.get_name()}": ')
                finally:
                    self.async_tasks.remove(task)

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
