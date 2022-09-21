from sqlalchemy import select

from tgbot.db import db
from tgbot.gui.tabs import Tab
from tgbot.gui.keyboards import GridKeyboard
from tgbot.gui.buttons import SimpleButton
from tgbot.users import current_user
from tables import GroupUserAssociation


class GroupSelectionTabMixin(Tab):

    def get_keyboard(self):
        return GridKeyboard(self, width=1)

    async def set_groups(self, groups, callback):
        for group in groups:
            group_title = (await self.window.controller.app.get_chat(group.group_id)).title
            self.keyboard.add_button(SimpleButton(
                group_title,
                arg=group.id,
                callback=callback
            ))


class GroupTabMixin(Tab):
    async def custom_switch_tab(self, *args, **kwargs):
        kwargs['group_id'] = self.row.group_id
        return await self.window.switch_tab(*args, **kwargs)

    async def get_association_object(self):
        stmt = select(GroupUserAssociation).where(
            GroupUserAssociation.group_id == self.row.group_id,
            GroupUserAssociation.user_id == current_user.id
        )
        return (await db.execute(stmt)).scalar()
