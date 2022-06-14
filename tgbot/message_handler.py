import asyncio
from collections import OrderedDict

from pyrogram.enums.parse_mode import ParseMode
from pyrogram.utils import get_peer_type

from tgbot import split_text
from tgbot.limiter import Limiter
from tgbot.prioritized_item import PrioritizedItem


class MessageHandler:

    def __init__(self):
        self.message_queue = asyncio.PriorityQueue()
        self.message_id = 1
        self.global_message_limiter = Limiter(
            self,
            30,
            1,
            name='broadcast_messages'
        )
        self.message_limiters = {}
        self.message_event_chains = {}
        self.messages_info = OrderedDict()
        for priority in range(1, 4):
            self.messages_info[priority] = {'pending': 0, 'processing': 0}
        super().__init__()

    def get_default_chat_id(self):
        pass

    def get_message_texts(self, text, title='', **kwargs):
        return split_text.split_text_by_units(header=title, body=text, max_part_length=4096, **kwargs)

    def send_message_sync(self, text, /, chat_id=None, *args, priority=2, blocking=False, **kwargs):
        chat_id = chat_id or self.get_default_chat_id()
        if chat_id not in self.message_limiters:
            if get_peer_type(chat_id) == 'user':
                limiter = Limiter(self, 3, 1, name=f'user_{chat_id}', static=False)
            else:
                limiter = Limiter(self, 20, 60, name=f'chat_{chat_id}', static=False)
            self.message_limiters[chat_id] = limiter
        else:
            limiter = self.message_limiters[chat_id]
        kwargs['limiters'] = [self.global_message_limiter, limiter]
        event_chain_key = (chat_id, priority)
        if event_chain_key not in self.message_event_chains:
            event_chain = {}
        else:
            event_chain = self.message_event_chains[event_chain_key]
        info = self.messages_info[priority]
        texts = self.get_message_texts(text, title=kwargs.get('title', ''))
        self.log.debug(f'Постановка {len(texts)} частей сообщения в очередь с приоритетом {priority} ({"блокирующая" if blocking else "неблокирующая"} отправка, текущий id {self.message_id})')
        for i, text in enumerate(texts):
            event_chain['current_invoke_event'] = asyncio.Event()
            new_event_chain = {'previous_invoke_event': event_chain['current_invoke_event']}
            self.message_event_chains[event_chain_key] = new_event_chain
            send_message_coroutine = self.app.send_message(
                chat_id,
                text,
                *args,
                **kwargs|event_chain
            )
            finish_event = None
            if blocking and i == len(texts)-1:
                finish_event = asyncio.Event()
            message_data = {
                'coroutine': send_message_coroutine,
                'priority': priority,
                'message_id': self.message_id,
                'chat_id': chat_id,
                'ignore_errors': kwargs.get('ignore_errors', False),
                'finish_event': finish_event,
                'current_invoke_event': event_chain['current_invoke_event'],
            }
            event_chain = new_event_chain
            self.message_queue.put_nowait(PrioritizedItem(priority, self.message_id, message_data))
            info['pending'] += 1
            self.message_id += 1
        self.log.debug(f'Сообщения поставлены в очередь (текущий id {self.message_id})')
        if blocking:
            return finish_event

    async def send_message(self, *args, **kwargs):
        event = self.send_message_sync(*args, **kwargs)
        if event:
            await event.wait()
            return event.message

    def send_warning_error_message_sync(self, *args, **kwargs):
        for dev_id in self.dev_ids:
            self.send_message_sync(
                *args,
                chat_id=dev_id,
                priority=1,
                ignore_errors=True,
                parse_mode=ParseMode.DISABLED,
                **kwargs,
            )

    async def message_sender(self, max_concurrent_sendings_per_priority):
        def could_get_next_item():
            next_item_priority = None
            next_item_priority_queue_size = None
            first_full_queue_priority = None
            for priority, info in self.messages_info.items():
                if next_item_priority is None and info['pending'] > 0:
                    next_item_priority = priority
                    next_item_priority_queue_size = info['processing']
                if first_full_queue_priority is None and info['processing'] == max_concurrent_sendings_per_priority:
                    first_full_queue_priority = priority
                if next_item_priority is not None and first_full_queue_priority is not None:
                    break
            if first_full_queue_priority is None:
                return True
            if next_item_priority is None:
                return False
            if next_item_priority_queue_size >= max_concurrent_sendings_per_priority:
                return False
            return True
        message_tasks = []
        get_message_task = None
        while True:
            if not get_message_task and could_get_next_item():
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
                    while True:
                        priority = item.priority
                        message_id = item.id
                        message_data = item.item
                        self.log.debug(f'Создаётся задача для отправки сообщения в чат {message_data["chat_id"]} с приоритетом {priority}, id {message_id}')
                        message_task = asyncio.create_task(message_data['coroutine'])
                        message_task.message_data = message_data
                        message_tasks.append(message_task)
                        info = self.messages_info[priority]
                        info['pending'] -= 1
                        info['processing'] += 1
                        if self.message_queue.empty() or not could_get_next_item():
                            break
                        item = self.message_queue.get_nowait()
                    continue
                result = None
                try:
                    message_data = task.message_data
                    result = task.result()
                except Exception:
                    message_data['current_invoke_event'].set()
                    (self.log.info if message_data['ignore_errors'] else self.log.error)(
                        f'Необработанное исключение при отправке сообщения {message_data["message_id"]}:',
                        exc_info=True
                    )
                finally:
                    self.messages_info[message_data['priority']]['processing'] -= 1
                    if message_data['finish_event']:
                        message_data['finish_event'].message = result
                        message_data['finish_event'].set()
