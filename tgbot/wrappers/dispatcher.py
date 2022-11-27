import asyncio
from collections import OrderedDict
import inspect

import pyrogram
from pyrogram.raw.types import UpdateNewMessage, UpdateNewChannelMessage, UpdateBotCallbackQuery
from pyrogram.utils import get_peer_id

from tgbot.enums import Category


class Dispatcher(pyrogram.dispatcher.Dispatcher):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories = {c: OrderedDict() for c in Category}
        self.chat_locks = {}

    async def add_handler(self, handler, category=Category.MAIN, group=0):
        if category not in self.categories:
            raise ValueError(f'Category {category} does not exist')
        for lock in self.locks_list:
            await lock.acquire()
        try:
            if group not in self.categories[category]:
                self.categories[category][group] = []
            self.categories[category][group].append(handler)
            self.categories[category] = OrderedDict(
                sorted(self.categories[category].items())
            )
        finally:
            for lock in self.locks_list:
                lock.release()

    async def remove_handler(self, handler, category=Category.MAIN, group=0):
        if category not in self.categories:
            raise ValueError(f'Category {category} does not exist')
        category = self.categories[category]
        for lock in self.locks_list:
            await lock.acquire()
        try:
            if group not in category:
                raise ValueError(f'Group {group} does not exist')
            category[group].remove(handler)
            if not category[group]:
                category.pop(group)
        finally:
            for lock in self.locks_list:
                lock.release()

    @staticmethod
    def get_handler_name(handler):
        try:
            if hasattr(handler.callback, '__name__'):
                return handler.callback.__name__
            return repr(handler.callback)
        except Exception:
            return 'Unknown handler'

    async def handle_category(self, category, packet, parsed_update, handler_type):
        log = self.client.controller.log
        log.debug(f'Выполняется обработка категории {category.name}')
        for group in self.categories[category].values():
            for handler in group:
                args = None
                kwargs = None
                if isinstance(handler, handler_type):
                    parsed_update.args_for_handler = []
                    parsed_update.kwargs_for_handler = {}
                    try:
                        if await handler.check(self.client, parsed_update):
                            args = (parsed_update, *parsed_update.args_for_handler)
                            kwargs = {**parsed_update.kwargs_for_handler}
                    except Exception:
                        log.exception(f'Необработанное исключение при проверке обработчика {self.get_handler_name(handler)}:')
                        return False
                elif isinstance(handler, pyrogram.handlers.RawUpdateHandler):
                    args = packet
                    kwargs = {}
                if args is None:
                    continue
                try:
                    log.debug(f'Вызывается обработчик {self.get_handler_name(handler)}')
                    await handler.callback(*args, **kwargs)
                except pyrogram.StopPropagation:
                    return True
                except pyrogram.ContinuePropagation:
                    continue
                except Exception:
                    log.exception(f'В обработчике {self.get_handler_name(handler)} произошло необработанное исключение:')
                    return False
                break
        return True

    async def handler_worker(self, lock):
        while True:
            packet = await self.updates_queue.get()
            if packet is None:
                break
            update, users, chats = packet
            chat_lock = None
            if self.client.controller.worker_per_chat:
                peer = None
                if isinstance(update, (UpdateNewMessage, UpdateNewChannelMessage)):
                    peer = update.message.peer_id
                if isinstance(update, UpdateBotCallbackQuery):
                    peer = update.peer
                if peer is not None:
                    peer_id = get_peer_id(peer)
                    if peer_id not in self.chat_locks:
                        self.chat_locks[peer_id] = asyncio.Lock()
                    chat_lock = self.chat_locks[peer_id]
            if chat_lock is not None:
                await chat_lock.acquire()
            try:
                parser = self.update_parsers.get(type(update), None)
                parsed_update, handler_type = (
                    await parser(update, users, chats)
                    if parser is not None
                    else (None, type(None))
                )
                kwargs = {
                    'packet': packet,
                    'parsed_update': parsed_update,
                    'handler_type': handler_type,
                }
                async with lock:
                    if not await self.handle_category(Category.INITIALIZE, **kwargs):
                        await self.handle_category(Category.FINALIZE, **kwargs)
                        continue
                    if await self.handle_category(Category.MAIN, **kwargs):
                        await self.handle_category(Category.FINISH, **kwargs)
                    else:
                        await self.handle_category(Category.RESTORE, **kwargs)
                    await self.handle_category(Category.FINALIZE, **kwargs)
            except Exception:
                self.client.controller.log.exception('Необработанное исключение при обработке обновления:')
            finally:
                if chat_lock is not None:
                    chat_lock.release()
