from sqlalchemy import select

from tgbot.group_manager import group_manager
from tgbot.handler_decorators import on_callback_query, on_message
from tgbot.helpers import ContextVarWrapper

current_user = ContextVarWrapper('current_user')


class TGBotUsersMixin:

    @on_callback_query(group=group_manager.LOAD_USER)
    @on_message(group=group_manager.LOAD_USER)
    async def load_user_handler(self, update):
        if not update.from_user:
            update.continue_propagation()
        user = await self.get_or_create_user(update.from_user.id)
        user.pyrogram_user = update.from_user
        current_user.set_context_var_value(user)
        update.continue_propagation()

    @on_callback_query(group=group_manager.SAVE_USER)
    @on_message(group=group_manager.SAVE_USER)
    async def save_user_handler(self, update):
        if not update.from_user:
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
