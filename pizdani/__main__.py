import io
import os
import json
import hashlib
import logging
import asyncio
import aiohttp
from aiohttp import FormData
from functools import partial
from contextlib import AsyncExitStack
import tempfile
from speech.synth import Synthizer
from .config import TG_BOT_TOKEN, TG_URL_BASE, TG_URL_TEMPLATE, INLINE_STORAGE_CHAT, INLINE_USERS
from contextlib import asynccontextmanager
from collections import OrderedDict
from typing import IO
from .models import enums, models

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

KEYWORDS = ['пиздани']

BOT_URL = 'https://t.me/naparrrnik_bot'
VOICE_CACHE_SIZE = 1000

# Synthesis is CPU heavy, run it strictly one at a time.
synth_lock = asyncio.Lock()
# query text -> voice file_id, lets inline answer with a real voice message.
voice_cache = OrderedDict()

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
        print(method, url.rsplit('/', 1)[-1], params)
        if method == 'get':
            request = self.session.get(url, params=params)
        elif method == 'post':
            data = {
                k: v if hasattr(v, 'read') else str(v)
                for k, v in params.items() if v is not None
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
            try:
                updates = await self.client.call(
                    'getUpdates', offset=offset, timeout=15, limit=self.queue.maxsize,
                )
            except (aiohttp.ClientError, asyncio.TimeoutError, ClientError) as exc:
                log.warning('getUpdates failed: %r', exc)
                await asyncio.sleep(5)
                continue
            for payload in updates:
                offset = max(offset, payload['update_id'] + 1)
                try:
                    update = models.Update.parse_obj(payload)
                except ValueError:
                    log.exception('skipping bad update: %s', payload)
                    continue
                await self.queue.put(update)


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
        **kwargs,
    )


async def delete_message(client: Client, chat_id: str, message_id: int):
    return await client.call(
        'deleteMessage', http_method='post', chat_id=chat_id, message_id=message_id,
    )


@asynccontextmanager
async def text_to_voice(text: str):
    with tempfile.NamedTemporaryFile(mode='rb', suffix='.ogg', delete=False) as ogg:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.wav') as wav:
            async with synth_lock:
                data = await Synthizer().process(text)
            await asyncio.to_thread(wav.write, data)
            await asyncio.to_thread(wav.flush)
            await asyncio.to_thread(
                # os.system, f'oggenc -q 3 -o {ogg.name} {wav.name}'
                os.system, f'ffmpeg -y -loglevel error -i {wav.name} -c:a libopus -b:a 32k -application voip {ogg.name}'
            )
        with open(ogg.name, mode='rb') as f:
            yield f


async def upload_to_storage(client: Client, ogg: IO, text: str) -> tuple:
    """Return (voice file_id, audio file_id), leaving nothing in the storage chat."""
    voice = await send_voice(client, ogg, INLINE_STORAGE_CHAT, disable_notification='true')
    await delete_message(client, INLINE_STORAGE_CHAT, voice['message_id'])
    with tempfile.NamedTemporaryFile(suffix='.mp3') as mp3:
        await asyncio.to_thread(
            os.system, f'ffmpeg -y -loglevel error -i {ogg.name} -b:a 64k {mp3.name}'
        )
        mp3.seek(0)
        audio = await client.call(
            'sendAudio', http_method='post',
            chat_id=INLINE_STORAGE_CHAT,
            audio=mp3,
            title=text[:64],
            performer='Напарррник',
            disable_notification='true',
        )
    await delete_message(client, INLINE_STORAGE_CHAT, audio['message_id'])
    return voice['voice']['file_id'], audio['audio']['file_id']


def inline_allowed(user: models.User) -> bool:
    return bool(INLINE_STORAGE_CHAT) and (not INLINE_USERS or user.id in INLINE_USERS)


async def handle_inline_query(client: Client, query: models.InlineQuery):
    text = query.query.strip()
    results = []
    if text and inline_allowed(query.from_):
        result_id = hashlib.md5(text.encode()).hexdigest()
        if text in voice_cache:
            results = [{
                'type': 'voice',
                'id': result_id,
                'voice_file_id': voice_cache[text],
                'title': text[:64],
            }]
        else:
            # An inline keyboard is what makes telegram report inline_message_id.
            results = [{
                'type': 'article',
                'id': result_id,
                'title': 'Озвучить',
                'description': text[:128],
                'input_message_content': {'message_text': f'⏳ {text}'},
                'reply_markup': {
                    'inline_keyboard': [[{'text': 'Генерирую...', 'url': BOT_URL}]],
                },
            }]
    await client.call(
        'answerInlineQuery', http_method='post',
        inline_query_id=query.id,
        results=json.dumps(results),
        cache_time=0,
        is_personal='true',
    )


async def handle_chosen_inline_result(client: Client, chosen: models.ChosenInlineResult):
    message_id = chosen.inline_message_id
    if message_id is None or not inline_allowed(chosen.from_):
        return
    text = chosen.query.strip()
    try:
        async with text_to_voice(text) as ogg:
            voice_id, audio_id = await upload_to_storage(client, ogg, text)
    except Exception:
        log.exception('inline synthesis failed: %r', text)
        await client.call(
            'editMessageText', http_method='post',
            inline_message_id=message_id,
            text=f'Не смог озвучить: {text}',
        )
        raise
    voice_cache[text] = voice_id
    while len(voice_cache) > VOICE_CACHE_SIZE:
        voice_cache.popitem(last=False)
    await client.call(
        'editMessageMedia', http_method='post',
        inline_message_id=message_id,
        media=json.dumps({'type': 'audio', 'media': audio_id}),
    )


async def handle_update(client: Client, update: models.Update):
    log.debug('update: %s', update.json(indent=2))

    if update.inline_query is not None:
        return await handle_inline_query(client, update.inline_query)
    if update.chosen_inline_result is not None:
        return await handle_chosen_inline_result(client, update.chosen_inline_result)

    msg = update.message or update.edited_message
    if msg is None:
        return



    text = msg.text

    chat_id = msg.chat.id

    cnt = await get_chat_members_count(client, chat_id=chat_id)
    if cnt > 2:
        for entity in msg.entities or []:
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

if __name__ == '__main__':
    asyncio.run(main(), debug=True)
