# Hard hack to fetch updates that arrived while the client was offline
# It even seems to work, but it's not certain.
# Will be removed after the issue is resolved https://github.com/pyrogram/pyrogram/issues/263

import pickle

from pyrogram import raw
from pyrogram.session import Session
from pyrogram.methods.utilities.start import log
from pyrogram.session.internals.msg_id import MsgId


def get_pyrogram_client_state(client):
    state = {}
    state['session.session_id'] = client.session.session_id
    state['session.msg_factory.seq_no.content_related_messages_sent'] = client.session.msg_factory.seq_no.content_related_messages_sent
    state['msg_id.reference_clock'] = MsgId.reference_clock
    state['msg_id.last_time'] = MsgId.last_time
    state['msg_id.msg_id_offset'] = MsgId.msg_id_offset
    state['msg_id.server_time'] = MsgId.server_time
    state['session.salt'] = client.session.salt
    state['session.pending_acks'] = client.session.pending_acks
    return pickle.dumps(state)


async def set_pyrogram_client_state_and_start(client, state=None):
    if client.is_connected:
        raise ConnectionError("Client is already connected")
    await client.load_session()
    client.session = Session(
        client, await client.storage.dc_id(),
        await client.storage.auth_key(), await client.storage.test_mode()
    )
    if state is not None:
        state = pickle.loads(state)
        client.session.session_id = state['session.session_id']
        client.session.msg_factory.seq_no.content_related_messages_sent = state['session.msg_factory.seq_no.content_related_messages_sent'] + 42
        MsgId.reference_clock = state['msg_id.reference_clock']
        MsgId.last_time = state['msg_id.last_time']
        MsgId.msg_id_offset = state['msg_id.msg_id_offset']
        MsgId.server_time = state['msg_id.server_time']
        client.session.salt = state['session.salt']
        client.session.pending_acks = state['session.pending_acks']
    await client.session.start()
    client.is_connected = True
    is_authorized = bool(await client.storage.user_id())
    try:
        if not is_authorized:
            await client.authorize()
        if not await client.storage.is_bot() and self.takeout:
            client.takeout_id = (await client.invoke(raw.functions.account.InitTakeoutSession())).id
            log.warning(f"Takeout session {client.takeout_id} initiated")
        await client.invoke(raw.functions.updates.GetState())
    except (Exception, KeyboardInterrupt):
        await client.disconnect()
        raise
    else:
        await client.initialize()
        return client
