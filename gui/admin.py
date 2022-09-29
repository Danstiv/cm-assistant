import datetime
import re

import pyrogram
from sqlalchemy import select

from tgbot.db import db
from tgbot.gui import InputField, Window
from tgbot.gui.buttons import CheckBoxButton, SimpleButton
from tgbot.gui.keyboards import GridKeyboard
from tgbot.gui.tabs.mixins import DateTimeSelectionTabMixin
from tgbot.users import current_user
from enums import EventType, GroupStatsDateTimeRangeSelectionScreen, UserRole
from gui.mixins import GroupSelectionTabMixin, GroupTabMixin
from gui.tabs import GroupTab
import tables
from tables import (
    Event,
    Group,
    GroupUserAssociation,
    User,
)
import texts


class GroupSelectionTab(GroupSelectionTabMixin):

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        groups = []
        for association in current_user.group_associations:
            if not association.role in [UserRole.MODERATOR, UserRole.ADMIN]:
                continue
            groups.append(association.group)
        if not groups:
            self.text.set_body('Вы не являетесь админом или модератором ни в одной из групп, к которым я привязан.')
            return
        self.text.set_body('Выберите группу.')
        await self.set_groups(groups, callback=self.on_group_btn)

    async def on_group_btn(self, arg):
        await self.window.switch_tab(GroupAdminSettingsTab, group_id=arg)


class GroupAdminSettingsTab(GroupTab):
    rerender_text = False

    async def get_text_data(self):
        return {'group_name': (await self.window.controller.app.get_chat((await self.get_association_object()).group.group_id)).title}

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        association = await self.get_association_object()
        self.text.set_body('Настройки группы {group_name}')
        self.keyboard.add_row()
        self.keyboard.add_button(CheckBoxButton(
            'Удалять джойны',
            is_checked=association.group.remove_joins,
            callback=self.on_remove_joins_cb
        ))
        self.keyboard.add_button(CheckBoxButton(
            'Удалять ливы',
            is_checked=association.group.remove_leaves,
            callback=self.on_remove_leaves_cb
        ))
        self.keyboard.add_row(SimpleButton(
            'Статистика',
            callback=self.on_stats_btn
        ))
        if association.role == UserRole.ADMIN:
            self.keyboard.add_button(SimpleButton(
                'Админы и модераторы',
                callback=self.on_staff_btn
            ))
        self.keyboard.add_row(SimpleButton('Назад', callback=self.on_back_btn))

    async def on_remove_joins_cb(self, state, arg):
        group = (await self.get_association_object()).group
        # Handle settings changes from several unsynchronized messages
        if group.remove_joins == state:
            return
        group.remove_joins = state
        db.add(group)

    async def on_remove_leaves_cb(self, state, arg):
        group = (await self.get_association_object()).group
        if group.remove_leaves == state:
            return
        group.remove_leaves = state
        db.add(group)

    async def on_stats_btn(self, arg):
        await self.custom_switch_tab(GroupStatsDateTimeRangeSelectionTab)

    async def on_staff_btn(self, arg):
        await self.custom_switch_tab(GroupStaffTab)

    async def on_back_btn(self, arg):
        await self.window.switch_tab(GroupSelectionTab)


class GroupStatsDateTimeRangeSelectionTab(DateTimeSelectionTabMixin, GroupTabMixin):
    table = tables.GroupStatsDateTimeRangeSelectionTab

    async def build(self, *args, **kwargs):
        dt = datetime.datetime.now().replace(second=0, microsecond=0)
        kwargs['start_date_time'] = dt
        kwargs['end_date_time'] = dt
        await super().build(*args, **kwargs)
        self.keyboard.add_row(
            SimpleButton('Назад', callback=self.on_back_btn),
            SimpleButton('Далее', callback=self.on_next_btn),
        )
        await self.set_start_date_time_selection_data()

    async def set_date_time(self, dt):
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.START_DATE_TIME:
            self.row.start_date_time = dt
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.END_DATE_TIME:
            self.row.end_date_time = dt

    async def get_date_time(self):
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.START_DATE_TIME:
            return self.row.start_date_time
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.END_DATE_TIME:
            return self.row.end_date_time

    async def set_start_date_time_selection_data(self):
        self.text.set_body('Выберите дату, с которой хотите просмотреть статистику.\n{date_time}.')
        self.row.screen = GroupStatsDateTimeRangeSelectionScreen.START_DATE_TIME

    async def set_end_date_time_selection_data(self):
        self.text.set_body('Выберите дату, по которую хотите просмотреть статистику.\n{date_time}.')
        self.row.screen = GroupStatsDateTimeRangeSelectionScreen.END_DATE_TIME

    async def on_back_btn(self, arg):
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.START_DATE_TIME:
            await self.custom_switch_tab(GroupAdminSettingsTab)
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.END_DATE_TIME:
            await self.set_start_date_time_selection_data()

    async def on_next_btn(self, arg):
        if self.row.screen == GroupStatsDateTimeRangeSelectionScreen.START_DATE_TIME:
            await self.set_end_date_time_selection_data()
        elif self.row.screen == GroupStatsDateTimeRangeSelectionScreen.END_DATE_TIME:
            await self.custom_switch_tab(
                GroupStatsTab,
                start_date_time=self.row.start_date_time,
                end_date_time=self.row.end_date_time,
                save_current_tab=True
            )


class GroupStatsTab(GroupTabMixin):
    table = tables.GroupStatsTab

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        self.text.set_body(texts.STATS_TEXT)
        self.keyboard.add_row(SimpleButton(
            'Обновить',
            callback=self.on_update_btn
        ))
        self.keyboard.add_row(SimpleButton(
            'Назад',
            callback=self.on_back_btn
        ))

    async def on_update_btn(self, arg):
        update_time = datetime.datetime.now().strftime('%H:%M:%S')
        self.text.set_header(f'Обновлено в {update_time}.')

    async def on_back_btn(self, arg):
        await self.custom_switch_tab(GroupStatsDateTimeRangeSelectionTab)

    async def get_text_data(self):
        group = (await self.get_association_object()).group
        start_timestamp = self.row.start_date_time.timestamp()
        end_timestamp = self.row.end_date_time.timestamp()
        stmt = select(Event).where(
            Event.time >= start_timestamp,
            Event.time <= end_timestamp,
            Event.group_id == group.id,
        )
        events = (await db.execute(stmt)).scalars()
        joins = 0
        leaves = 0
        messages = 0
        for event in events:
            if event.type == EventType.JOIN:
                joins += 1
            elif event.type == EventType.LEAVE:
                leaves += 1
            else:
                messages += 1
        return {
            'start_date_time': self.row.start_date_time,
            'end_date_time': self.row.end_date_time,
            'joins': joins,
            'leaves': leaves,
            'messages': messages,
            'group_name': (await self.window.controller.app.get_chat((await self.get_association_object()).group.group_id)).title,
        }


class GroupStaffTab(GroupTab):

    def get_keyboard(self):
        return GridKeyboard(self, width=2)

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == self.row.group_id,
            GroupUserAssociation.role.in_([UserRole.MODERATOR, UserRole.ADMIN])
        )
        associations = (await db.execute(stmt)).scalars()
        data = []
        for association in associations:
            role = None
            if association.role == UserRole.MODERATOR:
                role = 'модератор'
            else:
                role = 'админ'
            data.append({'role': role, 'id': association.user_id, 'user_id': association.user.user_id})
        users = await self.window.controller.app.get_users([i['user_id'] for i in data])
        usernames = [u.full_name for u in users]
        for i, username in zip(data, usernames):
            self.keyboard.add_button(SimpleButton(
                f'Сместить {username} ({i["role"]})',
                callback=self.on_staff_to_user_btn,
                arg=i['id']
            ))
        self.keyboard.add_row()
        self.keyboard.add_button(SimpleButton('Добавить админа', callback=self.on_add_staff_btn, arg='admin'))
        self.keyboard.add_button(SimpleButton('Добавить модератора', callback=self.on_add_staff_btn, arg='moderator'))
        self.keyboard.add_row(SimpleButton('Назад', callback=self.on_back_btn))
        self.text.set_body('Выберите действие.')

    async def on_staff_to_user_btn(self, arg):
        await self.custom_switch_tab(GroupStaffToUserConfirmTab, user_id=arg)

    async def on_add_staff_btn(self, arg):
        staff_type = UserRole.ADMIN if arg == 'admin' else UserRole.MODERATOR
        await self.custom_switch_tab(GroupAddStaffTab, staff_type=staff_type)

    async def on_back_btn(self, arg):
        await self.custom_switch_tab(GroupAdminSettingsTab)


class GroupStaffToUserConfirmTab(GroupTab):

    async def build(self, *args, user_id, **kwargs):
        # This tab is needed for a relatively simple action,
        # therefore, using GroupTab will be enough, and the user_id will be just passed to the button.
        await super().build(*args, **kwargs)
        user = (await db.execute(
            select(User).where(User.id == user_id))
        ).scalar()
        self.text.set_body(f'Понизить пользователя {(await self.window.controller.app.get_users(user.user_id)).full_name}?')
        self.keyboard.add_button(SimpleButton('Да', callback=self.on_btn, arg=user_id))
        self.keyboard.add_button(SimpleButton('Нет', callback=self.on_btn))

    async def on_btn(self, arg):
        result = ''
        if arg is not None:  # demote
            stmt = select(GroupUserAssociation).where(
                GroupUserAssociation.group_id == self.row.group_id,
                GroupUserAssociation.user_id == arg
            )
            association = (await db.execute(stmt)).scalar()
            association.role = UserRole.USER
            result = 'Пользователь понижен.'
        else:
            result = 'Действие отменено.'
        tab = await self.custom_switch_tab(GroupStaffTab)
        tab.text.set_header(result)


class GroupAddStaffTab(GroupTabMixin):
    table = tables.GroupAddStaffTab
    input_fields = [InputField(
        'username',
        text='Отправьте ник или ссылку на профиль пользователя, которому хотите выдать роль "{role}".'
    )]
    username_regexes = [
        re.compile(r'^https?\://t\.me/([a-zA-Z0-9_]+?)/?$'),
        re.compile(r'^https?\://([a-zA-Z0-9_]+?)\.t\.me/?$'),
    ]

    async def get_text_data(self):
        return {'role': 'админ' if self.row.staff_type == UserRole.ADMIN else 'модератор'}

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        self.keyboard.add_button(SimpleButton('Назад', callback=self.on_back_btn))

    async def on_back_btn(self, arg):
        tab = await self.custom_switch_tab(GroupStaffTab)
        tab.text.set_header('Действие отменено.')

    async def process_username(self, username):
        for regex in self.username_regexes:
            if match := regex.match(username):
                username = match[1]
                break
        try:
            user_list = await self.window.controller.app.get_users([username])
            user = user_list[0] if user_list else None
        except pyrogram.errors.BadRequest:
            user = None
        self.window.schedule_swap()
        if not user:
            self.text.set_header('Пользователь не найден.')
            return
        user = await self.window.controller.get_or_create_user(user.id)
        association = None
        for a in user.group_associations:
            if a.group_id == self.row.group_id:
                association = a
                break
        if not association:
            stmt = select(Group).where(Group.id == self.row.group_id)
            group = (await db.execute(stmt)).scalar()
            association = GroupUserAssociation(group=group, user=user)
            db.add(association)
        result = None
        if self.row.staff_type == UserRole.ADMIN and association.role == UserRole.ADMIN:
            result = 'Этот пользователь уже является админом.'
        elif self.row.staff_type == UserRole.MODERATOR and association.role == UserRole.MODERATOR:
            result = 'Этот пользователь уже является модератором.'
        else:
            association.role = self.row.staff_type
            result = 'Готово.'
        tab = await self.custom_switch_tab(GroupStaffTab)
        tab.text.set_header(result)


class AdminWindow(Window):
    tabs = [
        GroupSelectionTab,
        GroupAdminSettingsTab,
        GroupStatsDateTimeRangeSelectionTab,
        GroupStatsTab,
        GroupStaffTab,
        GroupStaffToUserConfirmTab,
        GroupAddStaffTab,
    ]
