from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Button(Base):
    __tablename__ = 'button'
    id = Column(Integer, primary_key=True)
    creation_date = Column(Integer)
    callback_data = Column(String)
    callback_name = Column(String)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
