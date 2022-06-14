from contextvars import ContextVar, Token

from sqlalchemy import select

from tables import User


user_storage = ContextVar('tg_user')

class UserHandler:

    async def get_or_create_user(self, user_id):
        stmt = select(User).where(
            User.user_id == user_id
        )
        user = (await self.db.execute(stmt)).scalar()
        if not user:
            user = User(user_id=user_id)
            self.db.add(user)
            await self.db.commit()
            self.log.info(f'Создан пользователь {user_id}')
        user_storage.set(user)


class EmptyUserContextException(Exception):
    pass


class UserContext:

    def get(self, *args, **kwargs):
        try:
            return user_storage.get(*args, **kwargs)
        except LookupError:
            raise EmptyUserContextException

    def __getattr__(self, name):
        return getattr(self.get(), name)

    def __setattr__(self, name, value):
        return setattr(self.get(), name, value)


user_context = UserContext()
