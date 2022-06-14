async def reply(self, *args, **kwargs):
    kwargs['reply_to_message_id'] = self.id
    return await self._client.controller.send_message(*args, **kwargs)
