from enum import Enum

from sqlalchemy import Column, Integer, String

from tgbot.db.tables import Base


class UserRole(Enum):
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class EventType(Enum):
    JOIN = 'join'


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    role = Column(String, nullable=False, default=UserRole.USER.value)
    message_count = Column(Integer, default=0)


class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
