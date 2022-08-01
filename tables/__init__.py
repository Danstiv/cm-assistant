import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship

from tgbot.db.tables import Base, User
from tgbot.keyboard.mixins import ButtonMixin

class UserRole(enum.Enum):
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class EventType(enum.Enum):
    JOIN = 'join'
    LEAVE = 'leave'
    MESSAGE = 'message'


class User(User):
    group_bind_code = Column(String)
    groups = association_proxy('group_associations', 'group')
    group_associations = relationship('GroupUserAssociation', back_populates='user', lazy='selectin')


class Group(Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, nullable=False)
    remove_joins = Column(Boolean, default=False)
    remove_leaves = Column(Boolean, default=False)
    users = association_proxy('user_associations', 'user')
    user_associations = relationship('GroupUserAssociation', back_populates='group', lazy='selectin')


class GroupUserAssociation(Base):
    __tablename__ = 'group_user_association'
    group_id = Column(ForeignKey('group.id'), primary_key=True)
    user_id = Column(ForeignKey('user.id'), primary_key=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    subscribed_to_mailings = Column(Boolean, nullable=False, default=False)
    group = relationship(Group, back_populates='user_associations', lazy='selectin')
    user = relationship(User, back_populates='group_associations', lazy='selectin')


class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    type = Column(Enum(EventType), nullable=False)

class GroupUserButton(ButtonMixin, Base):
    __tablename__ = 'group_user_button'
    group_id = Column(Integer, nullable=False)
    member_id = Column(Integer, nullable=False)
