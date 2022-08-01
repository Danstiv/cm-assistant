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

from tables import (
    Event,
    EventType,
    Group,
    GroupUserAssociation,
    User,
    UserRole,
)
import texts
from tgbot import BotController
from tgbot.db import db
from tgbot.group_manager import group_manager
from tgbot.handler_decorators import on_message
from tgbot.helpers import ContextVarWrapper
from tgbot.keyboard import (
    SimpleButton,
    SimpleCheckBoxButton,
    create_simple_check_box_keyboard,
    create_simple_keyboard,
    current_callback_query,
)
from tgbot.users import current_user

group_manager.add_left_group('load_group')
group_manager.add_right_group('save_group')
group_manager.add_left_group('start_in_group')

current_group = ContextVarWrapper('current_group')


class Controller(BotController):
    def __init__(self):
        super().__init__(bot_name='cm_assistant', user_table=User)

    @on_message(filters.group, group=group_manager.LOAD_GROUP)
    async def load_group_handler(self, message):
        stmt = select(Group).where(
            Group.group_id == message.chat.id
        )
        group = (await db.execute(stmt)).scalar()
        if not group:
            return
        current_group.set_context_var_value(group)

    @on_message(filters.group, group=group_manager.SAVE_GROUP)
    async def save_group_handler(self, message):
        if not current_group.is_set:
            return
        db.add(current_group)
        await db.commit()

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

    async def get_settings_message_data(self):
        if not current_user.groups:
            return 'Вы не состоите ни в одной из групп, к которым я привязан.', None
        keyboard = [[]]
        for group in current_user.groups:
            keyboard[0].append(
                {'name': f'group {group.id}', 'kwargs': {'arg': group.id}}
            )
        keyboard = await create_simple_keyboard(self, keyboard, callback=self.group_settings_handler)
        return 'Выберите группу.', keyboard

    @on_message(filters.command('settings') & filters.private)
    async def settings_handler(self, message):
        text, keyboard = await self.get_settings_message_data()
        await message.reply(text, reply_markup=keyboard)

    async def group_settings_handler(self, keyboard, button, row_index, column_index):
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == button.arg,
            GroupUserAssociation.user_id == current_user.id
        )
        association = (await db.execute(stmt)).scalar()
        keyboard = await create_simple_check_box_keyboard(
            self,
            [[
                {'name': 'Подписаться на рассылки', 'kwargs': {'is_checked': association.subscribed_to_mailings, 'arg': 'subscribed_to_mailings'}}
            ], [
                {'name': 'Применить', 'button_class': SimpleButton, 'kwargs': {'callback_name': self.group_settings_apply_handler.__name__, 'arg': association.group_id}},
                {'name': 'Назад', 'button_class': SimpleButton, 'kwargs': {'callback_name': self.group_settings_back_handler.__name__}},
            ]]
        )
        await current_callback_query.message.edit_text(f'Настройки группы {association.group_id}.', reply_markup=keyboard)

    async def group_settings_apply_handler(self, keyboard, button, column_index, row_index):
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == button.arg,
            GroupUserAssociation.user_id == current_user.id
        )
        association = (await db.execute(stmt)).scalar()
        for row in keyboard:
            for button in row:
                if not isinstance(button, SimpleCheckBoxButton):
                    continue
                setattr(association, button.arg, button.is_checked)
        await db.commit()
        text, keyboard = await self.get_settings_message_data()
        await current_callback_query.message.edit_text('Настройки применены.\n' + text, reply_markup=keyboard)

    async def group_settings_back_handler(self, *args, **kwargs):
        text, keyboard = await self.get_settings_message_data()
        await current_callback_query.message.edit_text(text, reply_markup=keyboard)

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
            await db.commit()
            current_group.set_context_var_value(group)
            await self.send_message('Привязка выполнена, теперь вы можете использовать команду /admin для настройки.', user.user_id)
            self.log.info(f'Бот ассоциирован с группой. Группа: {message.chat.id}, администратор: {user.user_id}')
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
            await db.commit()
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
                user_id=member.id,
                time=timestamp,
                type=EventType.JOIN
            )
            events.append(event)
        db.add_all(events)
        await db.commit()
        self.log.info(f'Добавлено {len(events)} участников')
        if current_group.remove_joins:
            self.log.info('Будет выполнена попытка удалить сервисное сообщение о добавлении участников')
            try:
                await message.delete()
                self.log.info('Сервисное сообщение удалено')
            except pyrogram.errors.Forbidden:
                self.log.info('Не удалось удалить сервисное сообщение, вероятно, бот не является администратором в группе')
                pass

    @on_message(filters.private&filters.command('admin'))
    async def admin_handler(self, message):
        await message.reply('This feature is deprecated and will be removed.')
        return
        if current_user.role != UserRole.ADMIN:
            return
        if len(message.command) < 2:
            await message.reply('Задайте username')
            return
        try:
            user_list = await self.app.get_users([message.command[1]])
            user = user_list[0] if user_list else None
        except pyrogram.errors.BadRequest:
            user = None
        if not user:
            await message.reply('Пользователь не найден')
            return
        user = await self.get_or_create_user(user.id)
        if user.role == UserRole.ADMIN:
            await message.reply('Этот пользователь уже является админом')
            return
        user.role = UserRole.ADMIN
        async with self.db.begin() as db:
            db.add(user)
        await message.reply('Готово.')
        self.log.info(f'Пользователь {current_user.user_id} сделал админом пользователя {user.user_id}')

    @on_message(filters.private&filters.command('stats'))
    async def stats_handler(self, message):
        await message.reply('This feature is deprecated and will be removed.')
        return
        if current_user.role != UserRole.ADMIN:
            return
        date = datetime.datetime.now()-datetime.timedelta(days=7)
        start_timestamp = int(date.timestamp())
        joins_stmt = select(func.count()).select_from(Event).where(
            Event.type==EventType.JOIN,
            Event.time >= start_timestamp
        )
        messages_stmt = select(func.count()).select_from(Event).where(
            Event.type==EventType.MESSAGE,
            Event.time >= start_timestamp
        )
        async with self.db.begin() as db:
            joins = (await db.execute(joins_stmt)).scalar()
            messages = (await db.execute(messages_stmt)).scalar()
        await message.reply(
            f'Статистика с {date:%Y-%m-%d %H:%M:%S}\n'
            f'Новых пользователей: {joins}\n'
            f'Написано сообщений: {messages}'
        )

    @on_message(filters.group & ~filters.service)
    async def group_message_handler(self, message):
        if not current_group.is_set or not current_user.is_set:
            return
        db.add(Event(
            user_id=current_user.user_id,
            time=int(time.time()),
            type=EventType.MESSAGE
        ))
        await db.commit()
        self.log.info('Зарегистрировано сообщение')


if __name__ == '__main__':
    controller = Controller()
    asyncio.run(controller.start())
