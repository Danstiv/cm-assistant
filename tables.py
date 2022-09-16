import enums

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, declarative_mixin, relationship

from tgbot.db.tables import Base, User
from tgbot.gui.mixins import ButtonMixin, TabMixin


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
    role = Column(Enum(enums.UserRole), nullable=False, default=enums.UserRole.USER)
    subscribed_to_mailings = Column(Boolean, nullable=False, default=False)
    group = relationship(Group, back_populates='user_associations', lazy='selectin')
    user = relationship(User, back_populates='group_associations', lazy='selectin')


class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('group.id'))
    group = relationship('Group', backref=backref('events', lazy='selectin'))
    user_id = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    type = Column(Enum(enums.EventType), nullable=False)


class GroupTabMixin(TabMixin):
    group_id = Column(Integer, nullable=False)


class GroupTab(GroupTabMixin, Base):
    __tablename__ = 'group_tab'


class GroupAddStaffTab(GroupTabMixin, Base):
    __tablename__ = 'group_add_staff_tab'
    staff_type = Column(Enum(enums.UserRole), nullable=False)


@declarative_mixin
class DateTimeRangeMixin:
    start_date_time = Column(DateTime, nullable=False)
    end_date_time = Column(DateTime, nullable=False)


class GroupStatsDateTimeRangeSelectionTab(GroupTabMixin, DateTimeRangeMixin, Base):
    __tablename__ = 'group_stats_date_time_range_selection_tab'
    screen = Column(Enum(enums.GroupStatsDateTimeRangeSelectionScreen))


class GroupStatsTab(GroupTabMixin, DateTimeRangeMixin, Base):
    __tablename__ = 'group_stats_tab'
