from contextvars import ContextVar

from sqlalchemy import select

from tgbot.handler_decorators import on_message

user_storage = ContextVar('tg_user')

class UserHandler:

    @on_message()
    async def initial_handler(self, message):
        user = await self.get_or_create_user(message.from_user.id)
        user_storage.set(user)
        message.continue_propagation()

    async def get_or_create_user(self, user_id):
        stmt = select(self.User).where(
            self.User.user_id == user_id
        )
        user = (await self.db.execute(stmt)).scalar()
        if not user:
            user = self.User(user_id=user_id)
            self.db.add(user)
            await self.db.commit()
            self.log.info(f'Создан пользователь {user_id}')
        return user


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


user_context = user = UserContext()
