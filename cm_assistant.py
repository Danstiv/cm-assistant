import asyncio
import datetime
import os
import time

import pyrogram
from pyrogram import filters
from sqlalchemy import func, select

from tables import (
    Event,
    EventType,
    Group,
    User,
    UserRole,
)
from tgbot import BotController
from tgbot.handler_decorators import on_message
from tgbot.user_handler import user


class Controller(BotController):
    def __init__(self):
        super().__init__(bot_name='cm_assistant', user_table=User)
        self.group_id = None

    async def initialize(self):
        await super().initialize()
        self.group_id = (await self.db.execute(select(Group.group_id))).scalar()

    @on_message(filters.new_chat_members)
    async def join_handler(self, message):
        events = []
        timestamp = int(time.time())
        for member in message.new_chat_members:
            event = Event(
                user_id=member.id,
                time=timestamp,
                type=EventType.JOIN
            )
            events.append(event)
            if self.group_id is None and member.is_self:
                self.group_id = message.chat.id
                self.db.add(Group(group_id=self.group_id))
                user.role = UserRole.ADMIN
                self.log.info(f'Бот ассоциирован с группой. Группа: {self.group_id}, администратор: {user.user_id}')
        self.db.add_all(events)
        await self.db.commit()
        self.log.info(f'Добавлено {len(events)} участников')
        try:
            await message.delete()
        except pyrogram.errors.Forbidden:
            pass

    @on_message(filters.private&filters.command('admin'))
    async def admin_handler(self, message):
        if user.role != UserRole.ADMIN:
            return
        if len(message.command) < 2:
            await message.reply('Задайте username')
            return
        try:
            admin = await self.app.get_users(message.command[1])
        except pyrogram.errors.BadRequest:
            await message.reply('Пользователь не найден')
            return
        admin = await self.get_or_create_user(admin.id)
        if admin.role == UserRole.ADMIN:
            await message.reply('Этот пользователь уже является админом')
            return
        admin.role = UserRole.ADMIN
        await self.db.commit()
        await message.reply('Готово.')
        self.log.info(f'Пользователь {user.user_id} сделал админом пользователя {admin.user_id}')

    @on_message(filters.private&filters.command('stats'))
    async def stats_handler(self, message):
        if user.role != UserRole.ADMIN:
            return
        date = datetime.datetime.now()-datetime.timedelta(days=7)
        start_timestamp = int(date.timestamp())
        stmt = select(func.count()).select_from(Event).where(
            Event.type==EventType.JOIN,
            Event.time >= start_timestamp
        )
        joins = (await self.db.execute(stmt)).scalar()
        stmt = select(func.count()).select_from(Event).where(
            Event.type==EventType.MESSAGE,
            Event.time >= start_timestamp
        )
        messages = (await self.db.execute(stmt)).scalar()
        await message.reply(
            f'Статистика с {date:%Y-%m-%d %H:%M:%S}\n'
            f'Новых пользователей: {joins}\n'
            f'Написано сообщений: {messages}'
        )

    @on_message(filters.group & ~filters.service)
    async def group_message_handler(self, message):
        if message.chat.id != self.group_id:
            return
        self.db.add(Event(
            user_id=user.user_id,
            time=int(time.time()),
            type=EventType.MESSAGE
        ))
        await self.db.commit()


if __name__ == '__main__':
    controller = Controller()
    asyncio.run(controller.start())
