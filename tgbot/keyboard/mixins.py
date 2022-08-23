from sqlalchemy import Boolean, Column, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import declarative_mixin

from tgbot.constants import DEFAULT_USER_ID


@declarative_mixin
class BaseButtonMixin:
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, default=DEFAULT_USER_ID)
    creation_date = Column(DateTime, nullable=False)
    callback_data = Column(LargeBinary(20), unique=True, nullable=False)
    answer = Column(Boolean, default=True)


class ButtonMixin(BaseButtonMixin):
    callback_name = Column(String)


class CheckBoxButtonMixin(BaseButtonMixin):
    unchecked_prefix = Column(String, nullable=False, default='')
    checked_prefix = Column(String, nullable=False, default='✔ ')
    is_checked = Column(Boolean, nullable=False, default=False)
