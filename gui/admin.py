import pyrogram
from sqlalchemy import select

from tgbot.db import db
from tgbot.gui import (
    BaseTab,
    CheckBoxButton,
    current_callback_query,
    InputField,
    SimpleButton,
    Window
)
from tgbot.users import current_user
import tables
from tables import (
    Group,
    GroupUserAssociation,
    User,
    UserRole,
)


class GroupTab(BaseTab):
    table = tables.GroupTab

    async def custom_switch_tab(self, *args, **kwargs):
        kwargs['group_id'] = self.row.group_id
        return await self.window.switch_tab(*args, **kwargs)

    async def get_association_object(self):
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == self.row.group_id,
            GroupUserAssociation.user_id == current_user.id
        )
        return (await db.execute(stmt)).scalar()


class GroupSelectionTab(BaseTab):

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        groups = []
        for association in current_user.group_associations:
            if not association.role in [UserRole.MODERATOR, UserRole.ADMIN]:
                continue
            groups.append(association.group)
        if not groups:
            self.set_text('Вы не являетесь админом или модератором ни в одной из групп, к которым я привязан.')
            return
        self.set_text('Выберите группу.')
        for group in groups:
            self.keyboard.add_button(SimpleButton(
                f'group {group.id}',
                arg=group.id,
                callback=self.on_group_btn
            ))

    async def on_group_btn(self, arg):
        await self.window.switch_tab(GroupAdminSettingsTab, group_id=arg)


class GroupAdminSettingsTab(GroupTab):

    async def get_text_data(self):
        return {'group_name': self.row.group_id}

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        association = await self.get_association_object()
        self.set_text('Настройки группы {group_name}')
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
        if association.role == UserRole.ADMIN:
            self.keyboard.add_button(SimpleButton(
                'Админы и модераторы',
                callback=self.on_staff_btn
            ))
        self.keyboard.add_button(SimpleButton('Назад', callback=self.on_back_btn))

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

    async def on_staff_btn(self, arg):
        await self.custom_switch_tab(GroupStaffTab)

    async def on_back_btn(self, arg):
        await self.window.switch_tab(GroupSelectionTab)


class GroupStaffTab(GroupTab):

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == self.row.group_id,
            GroupUserAssociation.role.in_([UserRole.MODERATOR, UserRole.ADMIN])
        )
        associations = (await db.execute(stmt)).scalars()
        for association in associations:
            role = None
            if association.role == UserRole.MODERATOR:
                role = 'модератор'
            else:
                role = 'админ'
            self.keyboard.add_button(SimpleButton(
                f'Сместить пользователя {association.user.id} ({role})',
                callback=self.on_staff_to_user_btn,
                arg=association.user_id
            ))
        self.keyboard.add_button(SimpleButton('Добавить админа', callback=self.on_add_staff_btn, arg='admin'))
        self.keyboard.add_button(SimpleButton('Добавить модератора', callback=self.on_add_staff_btn, arg='moderator'))
        self.keyboard.add_button(SimpleButton('Назад', callback=self.on_back_btn))
        self.set_text('Выберите действие.')

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
        self.set_text(f'Понизить пользователя {user_id}?')
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
            db.add(association)
            result = 'Пользователь понижен.\n'
        tab = await self.custom_switch_tab(GroupStaffTab)
        tab.set_text(result + tab.get_text())


class GroupAddStaffTab(GroupTab):
    table = tables.GroupAddStaffTab
    input_fields = [InputField(
        'username',
        text='Отправьте мне ник пользователя, которого хотите сделать {staff_type}.'
    )]

    async def get_text_data(self):
        return {'staff_type': 'администратором' if self.row.staff_type == UserRole.ADMIN else 'модератором'}

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        self.keyboard.add_button(SimpleButton('Назад', callback=self.on_back_btn))

    async def on_back_btn(self, arg):
        await self.custom_switch_tab(GroupStaffTab)

    async def process_username(self, username):
        try:
            user_list = await self.window.controller.app.get_users([username])
            user = user_list[0] if user_list else None
        except pyrogram.errors.BadRequest:
            user = None
        self.window.schedule_swap()
        if not user:
            self.set_text('Пользователь не найден.\n' + self.input_fields[0].text)
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
        tab.set_text(f'{result}\n{tab.get_text()}')


class AdminWindow(Window):
    tabs = [
        GroupSelectionTab,
        GroupAdminSettingsTab,
        GroupStaffTab,
        GroupStaffToUserConfirmTab,
        GroupAddStaffTab,
    ]
