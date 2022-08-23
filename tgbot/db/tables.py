from sqlalchemy import Boolean, Column, Integer, LargeBinary, String
from sqlalchemy.orm import declarative_base, relationship

from tgbot.constants import DEFAULT_USER_ID
from tgbot.gui.mixins import ButtonMixin, CheckBoxButtonMixin, TabMixin, TableWithWindowMixin

Base = declarative_base()


class Window(Base):
    __tablename__ = 'window'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False, default=DEFAULT_USER_ID)
    message_id = Column(Integer, nullable=True)
    current_tab_index = Column(Integer)


class Tab(TabMixin, Base):
    __tablename__ = 'tab'


class PyrogramButton(TableWithWindowMixin, Base):
    __tablename__ = 'pyrogram_button'
    id = Column(Integer, primary_key=True)
    text = Column(String)
    callback_data = Column(LargeBinary(64))
    url = Column(String)
    web_app_url = Column(String)
    login_url = Column(String)
    user_id = Column(Integer)
    switch_inline_query = Column(String)
    switch_inline_query_current_chat = Column(String)
    # callback_game: "Placeholder, currently holds no information."
    right_button = Column(Boolean, default=False)
    tab_index = Column(Integer)


class SimpleButton(ButtonMixin, Base):
    __tablename__ = 'simple_button'
    arg = Column(String)


class CheckBoxButton(CheckBoxButtonMixin, Base):
    __tablename__ = 'check_box_button'
    arg = Column(String)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
