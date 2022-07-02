from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base
from tgbot.keyboard_handler import ButtonMixin, button_decorator

Base = declarative_base()


@button_decorator
class SimpleButton(ButtonMixin, Base):
    __tablename__ = 'simple_button'
    arg = Column(String)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
