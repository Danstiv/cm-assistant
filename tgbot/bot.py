import asyncio
import os
import signal
import sys

import dotenv
try:
    import pymorphy2
except ImportError:
    pymorphy2 = None
import pyrogram
try:
    import uvloop
except ImportError:
    uvloop = None

from tgbot import (
    db,
    exception_handler,
)
from tgbot.core import TGBotCoreMixin
from tgbot.enums import QuoteReplyMode
from tgbot.handler_decorators import get_handlers
from tgbot.gui import TGBotGUIMixin
from tgbot.messages import TGBotMessagesMixin
from tgbot.users import TGBotUsersMixin
from tgbot.wrappers import apply_wrappers, name_inflection

dotenv.load_dotenv()


class BotController(
    TGBotCoreMixin,
    db.TGBotDBMixin,
    TGBotGUIMixin,
    TGBotMessagesMixin,
    TGBotUsersMixin,
):

    def __init__(
        self,
        bot_name,
        use_uvloop=False,
        worker_per_chat=False,
        username_inflection=False,
        user_table=None,
        quote_reply_mode=QuoteReplyMode.PYROGRAM
    ):
        for var in ['api_id', 'api_hash', 'bot_token', 'db_url', 'dev_ids']:
            setattr(self, var, os.getenv(var.upper()))
            if not getattr(self, var):
                raise RuntimeError(f'"{var.upper()}" environment variable not specified')
        self.dev_ids = [int(i) for i in self.dev_ids.split(',')]
        self.bot_name = bot_name
        self.app = None
        apply_wrappers()
        if sys.platform != 'win32' and use_uvloop:
            if not uvloop:
                raise ValueError('uvloop is not installed')
            else:
                uvloop.install()
        self.worker_per_chat = worker_per_chat
        self.User = user_table or db.tables.User
        self.quote_reply_mode = quote_reply_mode
        self.username_inflection = username_inflection
        if self.username_inflection and pymorphy2 is None:
            raise ValueError('pymorphy2 is not installed')
        super().__init__()

    def get_global_filter(self):
        pass

    async def initialize(self):
        if self.username_inflection:
            await asyncio.to_thread(name_inflection.NameWord.initialize_morph)
        self.app.controller = self
        exception_handler.wrap_methods(self)
        global_filter = self.get_global_filter()
        for handler in get_handlers():
            filters = None
            if handler['handler_args']:
                filters = handler['handler_args'][0]
            if 'filters' in handler['handler_kwargs']:
                filters = handler['handler_kwargs'].pop('filters')
            ignore_global_filter = handler['handler_kwargs'].pop('ignore_global_filter', False)
            if global_filter and handler['handler']is pyrogram.handlers.MessageHandler and not ignore_global_filter:
                if filters is None:
                    filters = [global_filter]
                else:
                    filters = global_filter & filters
            method = getattr(self, handler['handler_name'])
            await self.app.dispatcher.add_handler(
                handler['handler'](method, filters=filters),
                **handler['handler_kwargs']
            )
        await self.init_db()

    async def initialize_bot(self):
        pass

    async def terminate(self):
        pass

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
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        await self.initialize()
        await self.app.start()
        await self.initialize_bot()
        self.add_task(self.message_sender, 23)
        self.log.info('Приложение запущено')
        try:
            await self.monitor_tasks()
        finally:
            print('\r', end='')  # To remove C character from terminal
            self.log.info('Выход')
            await self.terminate()
            await self.app.stop()
            await self.close_db()
            [task.cancel() for task in self.async_tasks if task.cancellable]

    def stop_from_signal(self, *args, **kwargs):
        self.stop()

    def stop(self):
        self.canceling = True
        self.monitor_task.cancel()
