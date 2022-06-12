import asyncio
import logging
import logging.handlers
import os
import signal
import sys

import dotenv
import pyrogram
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.utils import get_peer_type
try:
    import uvloop
except ImportError:
    uvloop = None

from . import custom_methods
from . import db
from . import exception_handler
from . import split_text
from .keyboard_handler import KeyboardHandler
from .limiter import Limiter
from .logging_helpers import Formatter, WarningErrorHandler
from .handler_decorators import get_handlers
from .prioritized_item import PrioritizedItem

dotenv.load_dotenv()

LOG_MAX_SIZE = 10*2**20  # 10MB
LOG_MAX_BACKUPS = 9


class BotController(
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
        self.message_queue = asyncio.PriorityQueue()
        self.message_id = 1
        self.global_message_limiter = Limiter(self, 30, 1, name='broadcast_messages')
        self.message_limiters = {}
        self.message_event_chains = {}
        if sys.platform != 'win32' and use_uvloop:
            if not uvloop:
                self.log.warning('uvloop не установлен')
            else:
                uvloop.install()

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

    def get_default_chat_id(self):
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
        self.add_task(self.message_sender, 42)
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

    def get_message_texts(self, text, title='', **kwargs):
        return split_text.split_text_by_units(header=title, body=text, max_part_length=4096, **kwargs)

    def send_message_sync(self, text, *args, priority=2, blocking=False, **kwargs):
        args = list(args)
        texts = self.get_message_texts(text, title=kwargs.get('title', ''))
        self.log.debug(f'Постановка {len(texts)} частей сообщения в очередь с приоритетом {priority} ({"блокирующая" if blocking else "неблокирующая"} отправка, текущий id {self.message_id})')
        if not blocking:
            for text in texts:
                message_data = {
                    'args': [text]+args,
                    'kwargs': kwargs,
                }
                self.message_queue.put_nowait(PrioritizedItem(priority, self.message_id, message_data))
                self.message_id += 1
            self.log.debug(f'Неблокирующие сообщения поставлены в очередь (текущий id {self.message_id})')
            return
        semaphore = asyncio.Semaphore(len(texts))
        event = asyncio.Event()
        for text in texts:
            message_data = {
                'args': [text]+args,
                'kwargs': kwargs,
                'semaphore': semaphore,
                'event': event,
            }
            self.message_queue.put_nowait(PrioritizedItem(priority, self.message_id, message_data))
            self.message_id += 1
        self.log.debug(f'Блокирующие сообщения поставлены в очередь (текущий id {self.message_id})')
        return event

    async def send_message(self, *args, **kwargs):
        event = self.send_message_sync(*args, **kwargs)
        if event:
            await event.wait()
            return event.message

    def send_warning_error_message_sync(self, *args, **kwargs):
        self.send_message_sync(
            *args,
            priority=1,
            ignore_errors=True,
            parse_mode=ParseMode.DISABLED,
            **kwargs,
        )

    async def message_sender(self, max_concurrent_sendings):
        message_tasks = []
        get_message_task = None
        while True:
            if not get_message_task and len(message_tasks) < max_concurrent_sendings:
                get_message_task = asyncio.create_task(self.message_queue.get())
                message_tasks.append(get_message_task)
            try:
                done_tasks, pending_tasks = await asyncio.wait(message_tasks, return_when=asyncio.FIRST_COMPLETED)
            except asyncio.CancelledError:
                [t.cancel() for t in message_tasks]
                raise
            for task in done_tasks:
                message_tasks.remove(task)
                if task == get_message_task:
                    get_message_task = None
                    item = task.result()
                    message_id = item.id
                    priority = item.priority
                    message_data = item.item
                    while True:
                        try:
                            self.log.debug(f'Создаётся задача для отправки сообщения с приоритетом {priority}, id {message_id}')
                            message_task = asyncio.create_task(self.send_message_blocking(*message_data['args'], priority=priority, **message_data['kwargs']))
                        except Exception:
                            ignore_errors = message_data.get('kwargs', {}).get('ignore_errors', False)
                            (self.log.info if ignore_errors else self.log.error)('Необработанное исключение при создании задачи для отправки сообщения:', exc_info=True)
                        else:
                            message_task.message_data = message_data
                            message_tasks.append(message_task)
                        if len(message_tasks) >= max_concurrent_sendings or self.message_queue.empty():
                            break
                        item = self.message_queue.get_nowait()
                        message_id = item.id
                        priority = item.priority
                        message_data = item.item
                    continue
                result = None
                try:
                    event = task.message_data.get('event')
                    semaphore = task.message_data.get('semaphore')
                    result = task.result()
                except Exception:
                    ignore_errors = message_data['kwargs'].get('ignore_errors', False)
                    (self.log.info if ignore_errors else self.log.error)('Необработанное исключение при отправке сообщения:', exc_info=True)
                finally:
                    if semaphore:
                        await semaphore.acquire()
                        if semaphore.locked():
                            event.message = result
                            event.set()

    async def send_message_blocking(self, text, /, chat_id=None, ignore_errors=False, priority=None, **kwargs):
        chat_id = chat_id or self.get_default_chat_id()
        if chat_id not in self.message_limiters:
            if get_peer_type(chat_id) == 'user':
                limiter = Limiter(self, 3, 1, name=f'user_{chat_id}', static=False)
            else:
                limiter = Limiter(self, 20, 60, name=f'chat_{chat_id}', static=False)
            self.message_limiters[chat_id] = limiter
        else:
            limiter = self.message_limiters[chat_id]
        event_chain = {}
        if priority is not None:
            key = (chat_id, priority)
            if key not in self.message_event_chains:
                event_chain = {'previous_invoke_event': None, 'current_invoke_event': asyncio.Event()}
            else:
                event_chain = self.message_event_chains[key]
            new_chain = {'previous_invoke_event': event_chain['current_invoke_event'], 'current_invoke_event': asyncio.Event()}
            self.message_event_chains[key] = new_chain
        self.log.debug(f'Отправка сообщения в чат {chat_id}')
        try:
            return await self.app.send_message(chat_id, text, ignore_errors=ignore_errors, limiters=[self.global_message_limiter, limiter], **kwargs|event_chain)
        except Exception:  # Probably exceptions shouldn't freeze sending messages
            event_chain['current_invoke_event'].set()
            raise
