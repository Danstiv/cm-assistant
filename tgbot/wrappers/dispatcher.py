"""Performs approximately the same as the standard pyrogram dispatcher,
but handles exceptions and manages database sessions a little differently.
"""
import inspect

import pyrogram

from tgbot.db import db


class Dispatcher(pyrogram.dispatcher.Dispatcher):

    async def handler_worker(self, lock):
        log = self.client.controller.log
        while True:
            packet = await self.updates_queue.get()

            if packet is None:
                break

            try:
                update, users, chats = packet
                parser = self.update_parsers.get(type(update), None)

                parsed_update, handler_type = (
                    await parser(update, users, chats)
                    if parser is not None
                    else (None, type(None))
                )

                session_in_context = False

                async with lock:
                    for group in self.groups.values():
                        for handler in group:
                            args = None

                            if isinstance(handler, handler_type):
                                try:
                                    if await handler.check(self.client, parsed_update):
                                        args = (parsed_update,)
                                except Exception as e:
                                    log.error(e, exc_info=True)
                                    raise pyrogram.StopPropagation

                            elif isinstance(handler, pyrogram.handlers.RawUpdateHandler):
                                args = (update, users, chats)

                            if args is None:
                                continue

                            try:
                                if not session_in_context and isinstance(args[0], (pyrogram.types.Message, pyrogram.types.CallbackQuery)):
                                    db.set_context_var_value(self.client.controller.session())
                                    session_in_context = True
                                    log.debug('Создана сессия бд')
                                if inspect.iscoroutinefunction(handler.callback):
                                    await handler.callback(*args)
                                else:
                                    await self.loop.run_in_executor(
                                        self.client.executor,
                                        handler.callback,
                                        *args
                                    )
                            except pyrogram.StopPropagation:
                                raise
                            except pyrogram.ContinuePropagation:
                                continue
                            except Exception as e:
                                log.exception(f'В обработчике {handler.callback.__name__} произошло необработанное исключение:')
                                if session_in_context:
                                    await db.rollback()
                                    await db.close()
                                    db.reset_context_var()
                                    session_in_context = False
                                    log.debug('Выполнен rollback и сессия бд закрыта')
                                raise pyrogram.StopPropagation
                            break
            except pyrogram.StopPropagation:
                pass
            except Exception as e:
                log.error(e, exc_info=True)
            finally:
                if session_in_context:
                    await db.commit()
                    await db.close()
                    db.reset_context_var()
                    session_in_context = False
                    log.debug('Выполнен commit и сессия бд закрыта')
