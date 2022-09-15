from sqlalchemy import select

from tgbot.db import db
from tgbot.enums import Category
from tgbot.group_manager import group_manager
from tgbot.handler_decorators import on_callback_query, on_message
from tgbot.helpers import ContextVarWrapper

current_user = ContextVarWrapper('current_user')


class TGBotUsersMixin:

    @on_callback_query(category=Category.INITIALIZE, group=group_manager.LOAD_USER)
    @on_message(category=Category.INITIALIZE, group=group_manager.LOAD_USER)
    async def load_user(self, update):
        if not update.from_user:
            return
        user = await self.get_or_create_user(update.from_user.id)
        user.pyrogram_user = update.from_user
        current_user.set_context_var_value(user)

    @on_callback_query(category=Category.FINALIZE, group=group_manager.RESET_USER_CONTEXT)
    @on_message(category=Category.FINALIZE, group=group_manager.RESET_USER_CONTEXT)
    async def reset_user_context(self, update):
        if not current_user.is_set:
            return
        current_user.reset_context_var()

    async def get_or_create_user(self, user_id):
        stmt = select(self.User).where(
            self.User.user_id == user_id
        )
        user = (await db.execute(stmt)).scalar()
        if not user:
            user = self.User(user_id=user_id, group_associations=[])
            db.add(user)
            await db.commit()
            self.log.info(f'Создан пользователь {user_id}')
        return user
