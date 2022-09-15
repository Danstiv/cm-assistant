from sqlalchemy import Boolean, Column, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import backref, declarative_mixin, declared_attr, relationship

from tgbot.constants import DEFAULT_USER_ID

DEFAULT_CASCADE = 'save-update, merge, expunge, delete'


@declarative_mixin
class TableWithWindowMixin:
    @declared_attr
    def window_id(cls):
        return Column(Integer, ForeignKey('window.id', name='fk_window_id'))

    @declared_attr
    def window(cls):
        return relationship(
        'Window',
        backref=backref(cls.__tablename__+'_set', cascade=DEFAULT_CASCADE+', delete-orphan')
    )


class TabMixin(TableWithWindowMixin):
    id = Column(Integer, primary_key=True)
    index_in_window = Column(Integer)
    text = Column(String)
    current_input_field_index = Column(Integer)


class TextMixin(TableWithWindowMixin):
    id = Column(Integer, primary_key=True)
    tab_id = Column(Integer)
    header = Column(String)
    body = Column(String)
    input_field_text = Column(String)


class BaseButtonMixin(TableWithWindowMixin):
    id = Column(Integer, primary_key=True)
    callback_data = Column(LargeBinary(64), unique=True, nullable=False)


class ButtonMixin(BaseButtonMixin):
    callback_name = Column(String)


class CheckBoxButtonMixin(ButtonMixin):
    text = Column(String)
    is_checked = Column(Boolean, nullable=False, default=False)
    is_unchecked_prefix = Column(String, nullable=False, default='')
    is_checked_prefix = Column(String, nullable=False, default='☑ ')
