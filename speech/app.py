import base64

from fastapi import FastAPI, WebSocket, Response

from .synth import Synthizer

app = FastAPI()


@app.get("/speech")
async def speech(text: str) -> str:
    raw = await Synthizer().process(text)
    return Response(content=raw, media_type='audio/wav')


@app.websocket("/ws/speech")
async def speech(websocket: WebSocket) -> None:
    await websocket.accept()
    synth = Synthizer()
    while True:
        text = await websocket.receive_text()
        raw = await synth.process()
        await websocket.send(raw)
