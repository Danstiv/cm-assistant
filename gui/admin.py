from sqlalchemy import select

from tgbot.db import db
from tgbot.gui import (
    BaseTab,
    CheckBoxButton,
    current_callback_query,
    SimpleButton,
    Window
)
from tgbot.users import current_user
from tables import (
    Group,
    GroupUserAssociation,
    GroupTab,
    User,
    UserRole,
)


class GroupSelectionTab(BaseTab):
    text = 'Выберите группу.'

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
        for group in groups:
            self.keyboard.add_button(SimpleButton(
                f'group {group.id}',
                arg=group.id,
                callback=self.on_group_btn
            ))

    async def on_group_btn(self, arg):
        await self.window.switch_tab(GroupAdminSettingsTab, group_id=arg, save_current_tab=False)


class GroupAdminSettingsTab(BaseTab):
    table = GroupTab
    text = 'Настройки группы {group_name}'

    async def get_text_data(self):
        return {'group_name': self.row.group_id}

    async def get_association_object(self):
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == self.row.group_id,
            GroupUserAssociation.user_id == current_user.id
        )
        return (await db.execute(stmt)).scalar()

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        association = await self.get_association_object()
        self.keyboard.add_button(CheckBoxButton(
            'Удалять сервисные сообщения о новых участниках',
            is_checked=association.group.remove_joins,
            callback=self.on_remove_joins_cb
        ))
        self.keyboard.add_button(CheckBoxButton(
            'Удалять сервисные сообщения о вышедших участниках',
            is_checked=association.group.remove_leaves,
            callback=self.on_remove_leaves_cb
        ))
        if association.role == UserRole.ADMIN:
            self.keyboard.add_button(SimpleButton(
                'Управление администраторами и модераторами',
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
        await current_callback_query.answer('Извините, этот функционал пока не реализован', show_alert=True)

    async def on_back_btn(self, arg):
        await self.window.switch_tab(GroupSelectionTab)


class AdminWindow(Window):
    tabs = [
        GroupSelectionTab,
        GroupAdminSettingsTab,
    ]
