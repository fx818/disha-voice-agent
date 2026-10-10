"""Demo server: serves the web page, persona specs, WebRTC signalling and live events.

Run:  .venv/bin/python -m agent.server   → open http://localhost:7860
"""

import asyncio
import json
import uuid

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from agent.bot import run_call
from agent.events import bus
from agent.persona_state import PERSONA_DIR, ROOT

app = FastAPI()
webrtc = SmallWebRTCRequestHandler()


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/personas")
async def personas():
    idx = PERSONA_DIR / "index.json"
    if idx.exists():
        return json.loads(idx.read_text())
    return [{"seller_id": p.stem, "label": p.stem} for p in sorted(PERSONA_DIR.glob("*.json"))]


@app.get("/api/persona/{seller_id}")
async def persona(seller_id: str):
    path = PERSONA_DIR / f"{seller_id}.json"
    if not path.is_file() or path.parent != PERSONA_DIR:
        raise HTTPException(404)
    return json.loads(path.read_text())


@app.post("/api/offer")
async def offer(req: SmallWebRTCRequest, background: BackgroundTasks):
    data = req.request_data or {}
    seller_id, session_id = str(data.get("seller_id", "")), str(data.get("session_id") or uuid.uuid4())
    if not (PERSONA_DIR / f"{seller_id}.json").is_file():
        raise HTTPException(400, "unknown seller_id")

    async def on_connection(connection):
        background.add_task(run_call, connection, seller_id, session_id)

    return await webrtc.handle_web_request(request=req, webrtc_connection_callback=on_connection)


@app.patch("/api/offer")
async def ice(req: SmallWebRTCPatchRequest):
    await webrtc.handle_patch_request(req)
    return {"status": "success"}


@app.get("/api/events/{session_id}")
async def events(session_id: str, request: Request):
    async def stream():
        q = bus.subscribe(session_id)
        try:
            while not await request.is_disconnected():
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(session_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7860)
