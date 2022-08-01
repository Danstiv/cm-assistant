from sqlalchemy import Column, Enum, Integer, String

from tables import UserRole
from tgbot.db.tables import Base
from tgbot.states import StateMixin


class AddStaffMemberForm(StateMixin, Base):
    staff_type = Column(Enum(UserRole))
    message_id = Column(Integer)
    group_id = Column(Integer)
    username = Column(String)
