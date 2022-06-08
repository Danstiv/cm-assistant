import asyncio
import contextvars
from functools import wraps

import pyrogram

invoke_data = contextvars.ContextVar('invoke_data')
WRAPPABLE_METHODS = [
    'accept_terms_of_service', 'add_chat_members', 'add_contact',
    'answer_callback_query', 'answer_inline_query', 'answer_web_app_query',
    'approve_all_chat_join_requests', 'approve_chat_join_request',
    'archive_chats', 'authorize', 'ban_chat_member', 'block_user',
    'change_cloud_password', 'check_password', 'copy_media_group',
    'copy_message', 'create_channel', 'create_chat_invite_link',
    'create_group', 'create_supergroup', 'decline_all_chat_join_requests',
    'decline_chat_join_request', 'delete_bot_commands', 'delete_channel',
    'delete_chat_admin_invite_links', 'delete_chat_invite_link',
    'delete_chat_photo', 'delete_contacts', 'delete_messages',
    'delete_profile_photos', 'delete_supergroup', 'delete_user_history',
    'download_media', 'edit_chat_invite_link', 'edit_inline_caption',
    'edit_inline_media', 'edit_inline_reply_markup', 'edit_inline_text',
    'edit_message_caption', 'edit_message_media', 'edit_message_reply_markup',
    'edit_message_text', 'enable_cloud_password', 'export_chat_invite_link',
    'export_session_string', 'fetch_peers', 'forward_messages',
    'get_bot_commands', 'get_bot_default_privileges', 'get_chat',
    'get_chat_admin_invite_links', 'get_chat_admin_invite_links_count',
    'get_chat_admins_with_invite_links', 'get_chat_event_log',
    'get_chat_history', 'get_chat_history_count', 'get_chat_invite_link',
    'get_chat_invite_link_joiners', 'get_chat_invite_link_joiners_count',
    'get_chat_join_requests', 'get_chat_member', 'get_chat_members',
    'get_chat_members_count', 'get_chat_menu_button', 'get_chat_online_count',
    'get_chat_photos', 'get_chat_photos_count', 'get_common_chats',
    'get_contacts', 'get_contacts_count', 'get_dialogs', 'get_dialogs_count',
    'get_discussion_message', 'get_discussion_replies',
    'get_discussion_replies_count', 'get_file', 'get_game_high_scores',
    'get_inline_bot_results', 'get_me', 'get_media_group', 'get_messages',
    'get_nearby_chats', 'get_password_hint', 'get_send_as_chats', 'get_users',
    'import_contacts', 'join_chat', 'leave_chat', 'log_out',
    'mark_chat_unread', 'pin_chat_message', 'promote_chat_member',
    'read_chat_history', 'recover_password', 'remove_cloud_password',
    'request_callback_answer', 'resend_code', 'resolve_peer',
    'restrict_chat_member', 'retract_vote', 'revoke_chat_invite_link',
    'save_file', 'search_global', 'search_global_count', 'search_messages',
    'search_messages_count', 'send_animation', 'send_audio',
    'send_cached_media', 'send_chat_action', 'send_code', 'send_contact',
    'send_dice', 'send_document', 'send_game', 'send_inline_bot_result',
    'send_location', 'send_media_group', 'send_message', 'send_photo',
    'send_poll', 'send_reaction', 'send_recovery_code', 'send_sticker',
    'send_venue', 'send_video', 'send_video_note', 'send_voice',
    'set_administrator_title', 'set_bot_commands',
    'set_bot_default_privileges', 'set_chat_description',
    'set_chat_menu_button', 'set_chat_permissions', 'set_chat_photo',
    'set_chat_protected_content', 'set_chat_title', 'set_chat_username',
    'set_game_score', 'set_parse_mode', 'set_profile_photo',
    'set_send_as_chat', 'set_slow_mode', 'set_username', 'sign_in',
    'sign_in_bot', 'sign_up', 'stop_poll', 'stop_transmission', 'stream_media',
    'unarchive_chats', 'unban_chat_member', 'unblock_user',
    'unpin_all_chat_messages', 'unpin_chat_message', 'update_profile',
    'vote_poll'
]


class AttemptLimitReached(Exception):
    pass


class MethodDecoratorException(Exception):
    pass


def make_invoke_decorator(controller):
    def invoke_decorator(invoke):
        @wraps(invoke)
        async def wrapper(
            *args,
            ignore_errors=False,
            max_attempts=10,
            limiters=None,
            previous_invoke_event=None,
            current_invoke_event=None,
            **kwargs
        ):
            data = invoke_data.get(None)
            if data:
                ignore_errors = data['ignore_errors']
                max_attempts = data['max_attempts']
                limiters = data['limiters']
                previous_invoke_event = data['previous_invoke_event']
                current_invoke_event = data['current_invoke_event']
            limiters = limiters or []
            log_func = controller.log.info if ignore_errors else controller.log.error
            attempt = 0
            if previous_invoke_event:
                await previous_invoke_event.wait()
            while True:
                [await limiter() for limiter in limiters]
                try:
                    attempt += 1
                    result = await invoke(*args, **kwargs)
                    if current_invoke_event:
                        current_invoke_event.set()
                    return result
                except pyrogram.errors.FloodWait as e:
                    exception = e
                    timeout = e.value
                except pyrogram.errors.InternalServerError as e:
                    exception = e
                    timeout = attempt**4
                msg = f'Ошибка при работе с telegram: {exception}'
                if attempt >= max_attempts:
                    log_func(msg)
                    if ignore_errors:
                        controller.log.info('Исчерпано количество попыток при выполнении запроса к telegram')
                        if data:
                            raise MethodDecoratorException
                        return
                    raise AttemptLimitReached
                log_func(msg+f'. Следующая попытка через {timeout} секунд')
                await asyncio.sleep(timeout)
        return wrapper
    return invoke_decorator


def make_method_decorator(controller):
    def method_decorator(method):
        @wraps(method)
        async def wrapper(*args, ignore_errors=False, max_attempts=10, limiters=None, previous_invoke_event=None, current_invoke_event=None, **kwargs):
            token = invoke_data.set({
                'ignore_errors': ignore_errors,
                'max_attempts': max_attempts,
                'limiters': limiters,
                'previous_invoke_event': previous_invoke_event,
                'current_invoke_event': current_invoke_event,
            })
            try:
                return await method(*args, **kwargs)
            except MethodDecoratorException:
                return
            finally:
                invoke_data.reset(token)
        return wrapper
    return method_decorator


def wrap_methods(controller):
        method_decorator = make_method_decorator(controller)
        for method_name in WRAPPABLE_METHODS:
            method = getattr(controller.app, method_name)
            setattr(controller.app, method_name, method_decorator(method))
        invoke_decorator = make_invoke_decorator(controller)
        controller.app.invoke = invoke_decorator(controller.app.invoke)
