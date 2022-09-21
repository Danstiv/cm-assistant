import pyrogram
from sqlalchemy import select

from tgbot.db import db
from tgbot.gui import Window
from tgbot.gui.buttons import CheckBoxButton, SimpleButton
from tgbot.gui.keyboards import GridKeyboard
from tgbot.users import current_user
from gui.mixins import GroupSelectionTabMixin
from gui.tabs import GroupTab
import tables
from tables import (
    Group,
    GroupUserAssociation,
    User,
)


class GroupSelectionTab(GroupSelectionTabMixin):

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        if not current_user.groups:
            self.text.set_body('Вы не состоите ни в одной из групп, к которым я привязан.')
            return
        self.text.set_body('Выберите группу.')
        await self.set_groups(current_user.groups, callback=self.on_group_btn)

    async def on_group_btn(self, arg):
        await self.window.switch_tab(GroupSettingsTab, group_id=arg)


class GroupSettingsTab(GroupTab):
    rerender_text = False

    async def get_text_data(self):
        return {'group_name': (await self.window.controller.app.get_chat((await self.get_association_object()).group.group_id)).title}

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        association = await self.get_association_object()
        self.text.set_body('Настройки группы {group_name}')
        self.keyboard.add_row(CheckBoxButton(
            'Подписаться на рассылки',
            is_checked=association.subscribed_to_mailings,
            callback=self.on_subscribed_to_mailings_cb
        ))
        self.keyboard.add_row(SimpleButton('Назад', callback=self.on_back_btn))

    async def on_subscribed_to_mailings_cb(self, state, arg):
        association = (await self.get_association_object())
        if association.subscribed_to_mailings == state:
            return
        association.subscribed_to_mailings = state
        db.add(association)

    async def on_back_btn(self, arg):
        await self.window.switch_tab(GroupSelectionTab)


class SettingsWindow(Window):
    tabs = [
        GroupSelectionTab,
        GroupSettingsTab,
    ]
