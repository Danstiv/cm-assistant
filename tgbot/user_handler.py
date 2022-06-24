from contextvars import ContextVar

from sqlalchemy import select

from tgbot.handler_decorators import on_message
from tgbot.helpers import ContextVarWrapper

user_storage = ContextVar('tg_user')
current_user = ContextVarWrapper(user_storage)


class UserHandler:

    @on_message()
    async def load_user_handler(self, message):
        if not message.from_user:
            message.continue_propagation()
        user = await self.get_or_create_user(message.from_user.id)
        user.tg = message.from_user
        user_storage.set(user)
        message.continue_propagation()

    @on_message(group=0xbaddeadbed)
    async def save_user_handler(self, message):
        if not message.from_user:
            return
        async with self.db.begin() as db:
            db.add(current_user)

    async def get_or_create_user(self, user_id):
        stmt = select(self.User).where(
            self.User.user_id == user_id
        )
        async with self.db.begin() as db:
            user = (await db.execute(stmt)).scalar()
            if not user:
                user = self.User(user_id=user_id)
                db.add(user)
        self.log.info(f'Создан пользователь {user_id}')
        return user
