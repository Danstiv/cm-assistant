import asyncio
import logging
import logging.handlers

from sqlalchemy.exc import SQLAlchemyError

from tgbot.logging_helpers import Formatter, WarningErrorHandler
from tgbot.helpers import EmptyContextVarException
from tgbot.users import current_user

LOG_MAX_SIZE = 10*2**20  # 10MB
LOG_MAX_BACKUPS = 9
old_log_record_factory = logging.getLogRecordFactory()
def log_record_factory(*args, **kwargs):
    record = old_log_record_factory(*args, **kwargs)
    try:
        record.username = current_user.pyrogram_user.log_name
    except (EmptyContextVarException, SQLAlchemyError):
        record.username = 'Василий'
    return record


class TGBotCoreMixin:

    def __init__(self):
        self.async_tasks = []
        self.monitor_task = None
        self.canceling = False
        logging.setLogRecordFactory(log_record_factory)
        self.log = logging.getLogger(self.bot_name)
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
            '.%(funcName)s (%(lineno)d) | %(username)s\n%(message)s'
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
        super().__init__()

    def add_task(self, callable, *args, name=None, cancellable=True, **kwargs):
        name = name or callable.__name__
        task = asyncio.create_task(callable(*args, **kwargs), name=name)
        task.cancellable = cancellable
        self.async_tasks.append(task)
        if self.monitor_task:
            self.monitor_task.cancel()
        self.log.debug(f'Добавлена асинхронная задача {name}')
        return task

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
