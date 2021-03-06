from contextvars import ContextVar
import re

from sqlalchemy import Column, Integer, String, UniqueConstraint, or_, select
from sqlalchemy.orm import declarative_mixin, declared_attr
from tgbot.helpers import ContextVarWrapper

state_storage = ContextVar('current_state')
current_state = ContextVarWrapper(state_storage)

WORD_START_REGEX = re.compile('(.)([A-Z][a-z]+)')
WORD_END_REGEX = re.compile('([a-z0-9])([A-Z])')

def class_to_table_name(class_name):
    class_name = WORD_START_REGEX.sub(r'\1_\2', class_name)
    class_name = WORD_END_REGEX.sub(r'\1_\2', class_name)
    return class_name.lower()

DEFAULT_USER_ID = 0

@declarative_mixin
class StateMixin:
    @declared_attr
    def __tablename__(cls):
        return class_to_table_name(cls.__name__)+'_state'

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False, default=DEFAULT_USER_ID)
    current_state = Column(String)
    __table_args__ = (
        UniqueConstraint('chat_id', 'user_id', name='unique_state'),
    )


class StatesGroupMeta(type):

    def __getattr__(self, name):
        if name in self.table.__table__.c:
            return (self, name)
        raise AttributeError(f'Column {name} not found')


class StatesGroup(metaclass=StatesGroupMeta):
    STATE_MIXIN_COLUMNS = len(list(filter(
        lambda k: not k.startswith('_'),
        StateMixin.__dict__
    )))

    def __init__(self, controller, row):
        self.controller = controller
        self.row = row

    @classmethod
    async def create(cls, controller, chat, user=None):
        current_state = cls.table.__table__.c[cls.STATE_MIXIN_COLUMNS].name
        user_id = DEFAULT_USER_ID if user is None else user.id
        row = cls.table(
            chat_id=chat.id,
            user_id=user_id,
            current_state=current_state
        )
        stmt = select(cls.table).where(
            cls.table.chat_id == chat.id,
            cls.table.user_id == user_id,
        )
        async with controller.db.begin() as db:
            current_row = (await db.execute(stmt)).scalar()
            if current_row is not None:
                await db.delete(current_row)
                await db.flush()
            db.add(row)
        obj = cls(controller, row)
        return obj

    @classmethod
    async def get_state(cls, controller, state, chat, user=None):
        stmt = select(cls.table).where(
            cls.table.chat_id == chat.id,
            or_(cls.table.user_id == (DEFAULT_USER_ID if user is None else user.id), cls.table.user_id == DEFAULT_USER_ID),
            cls.table.current_state == state
        )
        async with controller.db.begin() as db:
            state = (await db.execute(stmt)).scalar()
        if state is None:
            return
        return cls(controller, state)

    async def set(self, value):
        async with self.controller.db.begin() as db:
            setattr(self.row, self.row.current_state, value)
            columns = self.table.__table__.c
            for i, column in enumerate(columns):
                if column.name == self.row.current_state:
                    self.row.current_state = columns[i+1].name if i < len(columns) -1 else None
                    break

    def __getattr__(self, name):
        if hasattr(self.row, name):
            return getattr(self.row, name)
        raise AttributeError


def generate_state_group(table, name=None):
    name = name or table.__name__
    return type(name, (StatesGroup,), {'table': table})
