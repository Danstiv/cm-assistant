from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from tgbot.keyboard.mixins import ButtonMixin, CheckBoxButtonMixin

Base = declarative_base()


class SimpleButton(ButtonMixin, Base):
    __tablename__ = 'simple_button'
    arg = Column(String)


class SimpleCheckBoxButton(CheckBoxButtonMixin, Base):
    __tablename__ = 'simple_check_box_button'
    arg = Column(String)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
