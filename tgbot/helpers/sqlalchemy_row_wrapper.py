from tgbot.db import db


class SQLAlchemyRowWrapper:

    def __getattr__(self, name):
        if 'row' not in self.__dict__:
            return self.__dict__[name]
        if hasattr(self.row, name):
            return getattr(self.row, name)
        raise AttributeError

    def __setattr__(self, name, value):
        if 'row' not in self.__dict__:
            self.__dict__[name] = value
            return
        setattr(self.row, name, value)

    async def save(self):
        db.add(self.row)
        await db.commit()
