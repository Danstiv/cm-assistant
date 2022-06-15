import enum

from sqlalchemy import Column, Enum, Integer, String

from tgbot.db.tables import Base, User


class UserRole(enum.Enum):
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class EventType(enum.Enum):
    JOIN = 'join'


class User(User):
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    message_count = Column(Integer, default=0)


class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    type = Column(Enum(EventType), nullable=False)
