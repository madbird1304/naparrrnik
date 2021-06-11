import io
import os
import logging
import asyncio
import aiohttp
from aiohttp import FormData
from functools import partial
from contextlib import AsyncExitStack
import tempfile
from ..speech.synth import Synthizer
from .config import TG_BOT_TOKEN, TG_URL_BASE, TG_URL_TEMPLATE
from contextlib import asynccontextmanager
from typing import IO
from .models import enums, models

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

KEYWORDS = ['пиздани']

class ClientError(Exception):
    def __init__(self, response):
        self.response = response


class Client:
    def __init__(self, token: str = TG_BOT_TOKEN, template_url: str = TG_URL_TEMPLATE):
        self.template_url = template_url
        self.token = token
        self.stack = None
        self.session = None

    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *exc_info):
        if self.session is not None:
            session = self.session
            self.session = None
            await session.close()

    def url_for_method(self, method: str) -> str:
        return self.template_url.format(base=TG_URL_BASE, token=self.token, method=method)

    async def request(self, method, url: str, **params: object) -> object:
        print(method, url, params)
        # print(url, params)
        if method == 'get':
            request = self.session.get(url, params=params)
        elif method == 'post':
            data = {
                k: v if hasattr(v, 'read') else str(v)
                for k, v in params.items()
            }
            request = self.session.post(url, data=data)
        async with request as resp:

            return await resp.json()

    async def call(self, method, http_method='get', **params):
        resp = await self.request(method=http_method, url=self.url_for_method(method), **params)
        if resp['ok']:
            return resp['result']
        raise ClientError(resp)



class Poller(asyncio.AbstractServer):
    def __init__(self, client: Client, maxsize: int = 100):
        self.client = client
        self.task = None
        self.queue = asyncio.Queue(maxsize=maxsize)

    async def start_serving(self):
        if self.task is None:
            self.task = asyncio.create_task(self.serve_forever())

    async def serve_forever(self):
        offset = 0
        while True:
            updates = await self.client.call(
                'getUpdates', offset=offset, timeout=15, limit=self.queue.maxsize,
            )
            for update in updates:
                models.Update.parse_obj(update)
                await self.queue.put(update)
                offset = max(offset, update['update_id']+1)


    def __aiter__(self):
        return UpdateQueue(self)

    def close(self):
        if self.task is not None:
            task, self.task = self.task, None
            task.cancel()
            # self.closed.set()

    async def wait_closed(self):
        if self.task is not None:
            await self.task

    def is_serving(self):
        return self.task is not None


class UpdateQueue:
    def __init__(self, poller):
        self.poller = poller

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.poller.is_serving():
            raise StopAsyncIteration
        return await self.poller.queue.get()


async def get_chat_members_count(client: Client, chat_id: str) -> int:
    return await client.call('getChatMembersCount', chat_id=chat_id)


async def send_voice(
    client: Client,
    voice: IO,
    chat_id: str,
    reply_to=None,
    **kwargs,
):
    return await client.call(
        'sendVoice', http_method='post',
        chat_id=chat_id,
        voice=voice,
        reply_to_message_id=reply_to,
    )


@asynccontextmanager
async def text_to_voice(text: str):
    with tempfile.NamedTemporaryFile(mode='rb', suffix='.ogg', delete=False) as ogg:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.wav') as wav:
            data = await Synthizer().process(text)
            await asyncio.to_thread(wav.write, data)
            await asyncio.to_thread(wav.flush)
            await asyncio.to_thread(
                # os.system, f'oggenc -q 3 -o {ogg.name} {wav.name}'
                os.system, f'opusenc --speech {wav.name} {ogg.name}'
            )
        with open(ogg.name, mode='rb') as f:
            yield f


async def handle_update(client: Client, update: models.Update):
    log.debug('update: %s', update.json(indent=2))

    msg = update.message or update.edited_message
    if msg is None:
        return



    text = msg.text

    chat_id = msg.chat.id

    cnt = await get_chat_members_count(client, chat_id=chat_id)
    if cnt > 2:
        for entity in msg.entities:
            if entity.type == enums.EntityType.BOT_COMMAND:
                c = msg.text[entity.offset:entity.length]
                if c.lower().startswith('/pizdani'):
                    text = text[entity.offset + entity.length:]
                    break
        else:
            return


    print(msg)
    message_id = msg.message_id
    name = msg.from_.first_name
    print(name, text)
    if not text:
        return
    async with text_to_voice(text) as voice:
        res = await send_voice(client, voice, chat_id, reply_to=message_id)
        print(f'Sent: {res}')


async def ratelimit(sem, func, *args, **kwargs):
    async with sem:
        return await func(*args, **kwargs)


async def main():
    sem = asyncio.Semaphore(100)
    async with Client() as client:
        async with Poller(client) as poller:
            await poller.start_serving()

            async for upd in poller:
                async with sem:
                    asyncio.create_task(ratelimit(sem, handle_update, client, upd))

asyncio.run(main(), debug=True)
