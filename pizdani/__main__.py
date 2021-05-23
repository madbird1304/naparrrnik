import io
import os
import asyncio
import aiohttp
from aiohttp import FormData
from functools import partial
from contextlib import AsyncExitStack
import tempfile
from speech.synth import Synthizer
from .config import TG_BOT_TOKEN, TG_URL_BASE, TG_URL_TEMPLATE
from contextlib import asynccontextmanager
from typing import IO
# from collections.

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
        # self.producer_task = None
        # self.consumer_task = None

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
        elif method == 'post': # and any(hasattr(v, 'read') for v in params.values()):
            data = {
                k: v if hasattr(v, 'read') else str(v)
                for k, v in params.items()
            }
            print(url, data)
            request = self.session.post(url, data=data)
            # breakpoint()
        async with request as resp:

            return await resp.json()

    async def call(self, method, http_method='get', **params):
        resp = await self.request(method=http_method, url=self.url_for_method(method), **params)
        if resp['ok']:
            return resp['result']
        print(resp)
        # if resp.status_code != 200:
        raise ClientError(resp)



class Poller(asyncio.AbstractServer):
    def __init__(self, client: Client, maxsize: int = 1):
        self.client = client
        self.task = None
        self.queue = asyncio.Queue(maxsize=maxsize)

    async def start_serving(self):
        if self.task is None:
            self.task = asyncio.create_task(self.serve_forever())

    async def serve_forever(self):
        offset = 0
        # print('1')
        while True:
            # print('2')
            updates = await self.client.call(
                'getUpdates', offset=offset, timeout=15, limit=self.queue.maxsize,
            )
            # print(updates)
            # print('3')
            # breakpoint()
            for update in updates:
                # print(update)
                await self.queue.put(update)
                offset = max(offset, update['update_id']+1)
            # offset += 1
            # breakpoint()


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


# async def pizdani(text: str) -> :
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
        # path =
        with open(ogg.name, mode='rb') as f:
            yield f


# async def updload_voice(chat_id: int, voice: IO[bytes], reply_to: int):
# # with open('/tmp/tmpvytdqtpc.ogg', 'rb') as file:
#     form = aiohttp.FormData()
#     #multipart = aiohttp.MultipartWriter()

#     #form.is_multipart = True
#      #, content_type='audio/opus')
#     form.add_field('voice', voice)
#     form.add_field('chat_id', '95996727')
#     form.add_field('reply_to_message_id', '124')
#     #params = {'chat_id': 95996727, 'reply_to_message_id': 124, 'voice': file}
#     async with aiohttp.ClientSession() as session:
#         async with session.post(url, data=form) as resp:
#             data = await resp.json()
#             print(data)
async def handle_update(client: Client, update):
    msg = update['message']
    # breakpoint()
    text = msg['text']
    for e in msg['entities']:
        if e['type'] == 'bot_command':
            c = msg['text'][e['offset']:e['length']]
            if c.startswith('/pizdani'):
                text = text[e['offset'] + e['length']:]
                break
    else:
        return
    # commands = {msg['text'][e['offset']:e['length']]: msg['text'][e['offset'] + e['length']:] for e in msg['entities'] if }

    # if '/pizdani' in commands:

    # print(msg)
    message_id = msg['message_id']
    print(msg)
    chat_id = msg['chat']['id']
    name = msg['from']['first_name']
    print(name, text)

    # kwd = '/pizdani'
    # pos = text.lower().startswith(kwd)

    # if pos < 0:
    #     return

    # text = text[pos + len(kwd):]

    async with text_to_voice(text) as voice:
        print(voice.name)
        await client.call(
            'sendVoice', http_method='post',
            chat_id=chat_id,
            voice=voice, # (f'{uuid4()}.wav', voice),
            reply_to_message_id=message_id,
        )


async def ratelimit(sem, func, *args, **kwargs):
    async with sem:
        return await func(*args, **kwargs)

    # def decorator(func):
    #     sem = asyncio.Semaphore(value=max_tasks)
    #     async def wrapper(*args, **kwargs):

    #     return wrapper
    # return decorator


async def main():
    sem = asyncio.Semaphore(100)
    async with Client() as client:
        async with Poller(client) as poller:
            # await poller.serve_forever()
            await poller.start_serving()

            # print('started')

            async for upd in poller:
                async with sem:
                    asyncio.create_task(ratelimit(sem, handle_update, client, upd))

asyncio.run(main(), debug=True)