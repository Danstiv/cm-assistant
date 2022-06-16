import enum

from sqlalchemy import Column, Enum, Integer, String

from tgbot.db.tables import Base, User


class UserRole(enum.Enum):
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class EventType(enum.Enum):
    JOIN = 'join'
    MESSAGE = 'message'


class User(User):
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)


class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    type = Column(Enum(EventType), nullable=False)


class Group(Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, nullable=False)
