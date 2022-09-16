from enum import Enum


class UserRole(Enum):
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class EventType(Enum):
    JOIN = 'join'
    LEAVE = 'leave'
    MESSAGE = 'message'


class GroupStatsDateTimeRangeSelectionScreen(Enum):
    START_DATE_TIME = 'start_date_time'
    END_DATE_TIME = 'end_date_time'
