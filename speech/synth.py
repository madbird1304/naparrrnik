import os
import asyncio
import subprocess
import tempfile

from contextlib import contextmanager

from .config import SS_COMMAND, SS_CACHE_DIR, SS_BINARY, SS_CACHE_KEEP
import pathlib
import os
from string import Template

COMMAND = SS_COMMAND.split()
MISSING = object()

@contextmanager
def tempf(**kwargs):
    params = {'delete': not SS_CACHE_KEEP, 'dir': os.path.abspath(SS_CACHE_DIR)}
    params |= kwargs
    with tempfile.NamedTemporaryFile(**params) as f:
        yield f

# @contextmanager
# def letenv(**kwargs: str):
#     old = os.environ.copy()
#     os.environ.update(kwargs)
#     try:
#         yield
#     finally:
#         os.environ.clear()
#         os.environ.update(old)


async def wait_process(process, interval: float = 0.1) -> int:
    res = None
    while res is None:
        await asyncio.sleep(interval)
        res = process.poll()
    return res



class Synthizer:
    def __init__(self) -> None:
        pass

    # async def run(self, fi, fo, text):
    #     await asyncio.to_thread(fi.write, text)
    #     await asyncio.to_thread(fi.flush)
    #     print(COMMAND)
    #     proc = subprocess.Popen(COMMAND, env=env)
    #     await asyncio.to_thread(proc.wait)
    #     await asyncio.to_thread(fo.seek, 0)
    #     return await asyncio.to_thread(fo.read)

    def run(self, fi, fo, text):
        with fi as fi, fo as fo:
            env = {
                **os.environ,
                'INP': os.path.abspath(fi.name),
                'OUT': os.path.abspath(fo.name),
                'CMD': os.path.abspath(SS_BINARY),
                # 'DISPLAY': os.environ.get('DISPLAY'),
            }
            command = [Template(s).safe_substitute(env) for s in COMMAND]
            fi.write(text)
            fi.flush()
            print(command, env)
            proc =  subprocess.Popen(command, env=env)
            proc.wait()
            res = fo.read()
        return res


    async def process(self, text: str):
        fi = tempf(mode='wt', suffix='.txt', encoding='cp1251')
        fo = tempf(mode='rb', suffix='.wav')
        return await asyncio.to_thread(self.run, fi, fo, text)
