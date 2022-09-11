from sqlalchemy import select

from tgbot.db import db
from tgbot.gui import BaseTab
from tgbot.users import current_user
import tables
from tables import GroupUserAssociation


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
