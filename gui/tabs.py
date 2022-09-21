from sqlalchemy import select

from tgbot.db import db
from tgbot.gui.tabs import Tab
from tgbot.users import current_user
from gui.mixins import GroupTabMixin
import tables
from tables import GroupUserAssociation


class GroupTab(GroupTabMixin):
    table = tables.GroupTab
