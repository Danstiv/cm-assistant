import asyncio
import os
import time

from pyrogram import filters

from tables import Event, EventType, UserRole
from tgbot import BotController
from tgbot.handler_decorators import on_message
from user_handler import UserHandler, user_context as user


class Controller(BotController, UserHandler):
    def __init__(self):
        super().__init__(bot_name='cm_assistant')
        try:
            self.group_id = int(os.environ['GROUP_ID'])
        except (KeyError, ValueError):
            raise RuntimeError('GROUP_ID not specified or invalid')

    @on_message()
    async def initial_handler(self, message):
        await self.get_or_create_user(message.from_user.id)
        message.continue_propagation()

    @on_message(filters.new_chat_members)
    async def join_handler(self, message):
        events = []
        timestamp = int(time.time())
        for member in message.new_chat_members:
            event = Event(
                user_id=member.id,
                time=timestamp,
                type=EventType.JOIN.value
            )
            events.append(event)
        self.db.add_all(events)
        await self.db.commit()
        self.log.info(f'Добавлено {len(events)} участников')
        await message.delete()

    @on_message(filters.private&filters.command('stats'))
    async def stats_handler(self, message):
        if user.role != UserRole.ADMIN.value:
            return
        await message.reply('Тут будет статистика.')


if __name__ == '__main__':
    controller = Controller()
    asyncio.run(controller.start())
