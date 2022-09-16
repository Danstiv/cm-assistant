#!/usr/bin/env python3
import asyncio
import datetime
import os
import random
import string
import time

import pyrogram
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from sqlalchemy import func, select

from enums import EventType, UserRole
from gui.admin import AdminWindow
from gui.settings import SettingsWindow
from tables import (
    Event,
    Group,
    GroupUserAssociation,
    User,
)
import texts
from tgbot import BotController
from tgbot.db import db
from tgbot.group_manager import group_manager
from tgbot.handler_decorators import on_message
from tgbot.helpers import ContextVarWrapper
from tgbot.users import current_user
from tgbot.enums import Category

group_manager.add_left_group('load_group')
group_manager.add_right_group('reset_group_context')
group_manager.add_left_group('start_in_group')

current_group = ContextVarWrapper('current_group')


class Controller(BotController):
    def __init__(self):
        super().__init__(bot_name='cm_assistant', user_table=User)

    @on_message(filters.group, category=Category.INITIALIZE, group=group_manager.LOAD_GROUP)
    async def load_group_handler(self, message):
        stmt = select(Group).where(
            Group.group_id == message.chat.id
        )
        group = (await db.execute(stmt)).scalar()
        if not group:
            return
        current_group.set_context_var_value(group)

    @on_message(filters.group, category=Category.FINALIZE, group=group_manager.RESET_GROUP_CONTEXT)
    async def reset_group_context(self, message):
        if not current_group.is_set:
            return
        current_group.reset_context_var()

    @on_message(filters.command('start') & filters.private)
    async def start_handler(self, message):
        await message.reply(texts.START_MESSAGE)

    @on_message(filters.command('bind') & filters.private)
    async def bind_handler(self, message):
        current_user.group_bind_code = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=42))
        bind_button = pyrogram.types.InlineKeyboardButton('Привязать', url=f'https://t.me/{self.app.me.username}?startgroup={current_user.group_bind_code}')
        await message.reply(
            texts.BIND_TEXT,
            reply_markup=pyrogram.types.InlineKeyboardMarkup([[bind_button]])
        )

    @on_message(filters.command('settings') & filters.private)
    async def settings_handler(self, message):
        window = SettingsWindow(self, message.chat.id)
        await window.build()
        await window.render()

    @on_message(filters.command('admin') & filters.private)
    async def admin_handler(self, message):
        window = AdminWindow(self, message.chat.id)
        await window.build()
        await window.render()

    @on_message(filters.command('start') & filters.group, group=group_manager.START_IN_GROUP)
    async def group_start_handler(self, message):
        self.log.info('Начата обработка команды /start')
        group_bind_code = message.command[1] if len(message.command) > 1 else None
        if group_bind_code:
            self.log.info('Выполняется получение пользователя из базы по переданному коду')
            stmt = select(User).where(User.group_bind_code == group_bind_code)
            user = (await db.execute(stmt)).scalar()
            self.log.info(f'Пользователь{" " if user else " не "}был получен')
        else:
            self.log.info('Код не был передан')
            user = None
        no_code_msg = 'Код для привязки не был передан.'
        code_invalid_msg = 'Код для привязки неверный или устарел.'
        if not message.from_user:
            self.log.info('Пользователь анонимен и будет считаться администратором группы')
            # User is anonymous. And only group admins can be anonymous users.
            user_is_admin = True
        else:
            member = await self.app.get_chat_member(message.chat.id, message.from_user.id)
            user_is_admin = member.status == ChatMemberStatus.OWNER or member.status == ChatMemberStatus.ADMINISTRATOR
        if not current_group.is_set:
            self.log.info('Текущая группа неизвестна')
            if group_bind_code is None:
                self.log.info('Код не был передан, будет осуществлён выход из группы')
                await self.send_message(no_code_msg, chat_id=message.chat.id, blocking=True)
                await message.chat.leave()
                return
            if user is None:
                self.log.info('Пользователь не был получен (невалидный код), осуществляется выход из группы')
                await self.send_message(code_invalid_msg, chat_id=message.chat.id, blocking=True)
                await message.chat.leave()
                return
            if not user_is_admin:
                self.log.info('Пользователь не является администратором группы, она будет покинута')
                await self.send_message('Группа может быть привязана только её администратором.', chat_id=message.chat.id, blocking=True)
                await message.chat.leave()
                return
            self.log.info('Производится создание инстанса группы и привязка пользователя к ней')
            group = Group(group_id=message.chat.id)
            association = GroupUserAssociation(group=group, user=user, role=UserRole.ADMIN)
            db.add(group)
            user.group_bind_code = None
            current_group.set_context_var_value(group)
            await self.send_message('Привязка выполнена, теперь вы можете использовать команду /admin для настройки.', user.user_id)
            self.log.info(f'Бот ассоциирован с группой. Группа: {message.chat.title}, администратор: {user.pyrogram_user.full_name}')
            return
        else:
            self.log.info('Группа уже привязана')
            if group_bind_code is None:
                self.log.info('Код для привязки не был передан')
                await self.send_message(no_code_msg, chat_id=message.chat.id, blocking=True)
                return
            if user is None:
                self.log.info('Пользователь не был найден (невалидный код)')
                await self.send_message(code_invalid_msg, chat_id=message.chat.id, blocking=True)
                return
            if not user_is_admin:
                self.log.info('Пользователь не является администратором группы')
                await self.send_message('Роль админа таким способом может получить только администратор группы.', chat_id=message.chat.id, blocking=True)
                return
            db.add(current_group)
            if current_group not in user.groups:
                self.log.info('Пользователь не связан с группой, выполняется создание объекта привязки')
                association = GroupUserAssociation(group=current_group, user=user)
                db.add(association)
                self.log.info('Объект привязки создан')
            else:
                self.log.info('Пользователь связан с группой, производится поиск объекта привязки')
                association  = None
                for a in user.group_associations:
                    if a.group == current_group:
                        association = a
                        self.log.info('Объект привязки найден')
                        break
            if association.role == UserRole.ADMIN:
                self.log.info('Пользователь уже является админом в группе')
                await self.send_message('Эта группа уже привязана, и вы являетесь админом. Используйте команду /admin для настройки.', user.user_id)
                return
            self.log.info('Задаётся роль админа для пользователя')
            association.role = UserRole.ADMIN
            await self.send_message('Вам назначена роль админа. Используйте команду /admin для настройки.', user.user_id)

    @on_message(filters.new_chat_members)
    async def join_handler(self, message):
        self.log.info(f'Начата обработка добавленных участников')
        if not current_group.is_set:
            self.log.info('Группа неизвестна, обработка не будет произведена')
            return
        events = []
        timestamp = int(time.time())
        for member in message.new_chat_members:
            event = Event(
                group=current_group,
                user_id=member.id,
                time=timestamp,
                type=EventType.JOIN
            )
            events.append(event)
        db.add_all(events)
        self.log.info(f'Добавлено {len(events)} участников')
        if current_group.remove_joins:
            self.log.info('Будет выполнена попытка удалить сервисное сообщение о добавлении участников')
            try:
                await message.delete()
                self.log.info('Сервисное сообщение удалено')
            except pyrogram.errors.Forbidden:
                self.log.info('Не удалось удалить сервисное сообщение, вероятно, бот не является администратором в группе')
                pass

    @on_message(filters.left_chat_member)
    async def leave_handler(self, message):
        self.log.info(f'Начата обработка вышедшего участника')
        if not current_group.is_set:
            self.log.info('Группа неизвестна, обработка не будет произведена')
            return
        event = Event(
            group=current_group,
            time=int(time.time()),
            type=EventType.LEAVE,
            user_id=message.left_chat_member.id
        )
        db.add(event)
        if current_group.remove_leaves:
            self.log.info('Будет выполнена попытка удалить сервисное сообщение о выходе участника')
            try:
                await message.delete()
                self.log.info('Сервисное сообщение удалено')
            except pyrogram.errors.Forbidden:
                self.log.info('Не удалось удалить сервисное сообщение, вероятно, бот не является администратором в группе')
                pass

    @on_message(filters.group & ~filters.service)
    async def group_message_handler(self, message):
        if not current_group.is_set or not current_user.is_set:
            return
        db.add(Event(
            group=current_group,
            user_id=current_user.user_id,
            time=int(time.time()),
            type=EventType.MESSAGE
        ))
        self.log.info('Зарегистрировано сообщение')


if __name__ == '__main__':
    controller = Controller()
    asyncio.run(controller.start())
