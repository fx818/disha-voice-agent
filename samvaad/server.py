"""Samvaad version of the demo: same page, persona specs and switch log, but the call runs on
Sarvam's hosted Voice Agents platform (laptop mic via PipeWire, Python SDK).

Run:  .venv/bin/python -m samvaad.server   → open http://localhost:7861
Switch-log webhook for the agent's `log_persona_switch` tool: POST /samvaad/switch (exposed via tunnel).
"""

import asyncio
import json
import os
import time
import uuid

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import SecretStr
from sarvam_conv_ai_sdk import AsyncSamvaadAgent
from sarvam_conv_ai_sdk.messages.config import InteractionConfig
from sarvam_conv_ai_sdk.messages.types import InteractionType, Role, UserIdentifierType
from sarvam_conv_ai_sdk.tool import SarvamToolLanguageName, SpeechSettings, TextToSpeechConfig

from agent.events import bus
from agent.persona_state import PERSONA_DIR, ROOT, load_persona
from agent.signals import SignalDetector
from samvaad.audio_pw import PipeWireAudioInterface
from samvaad.persona_to_samvaad import LANG_NAME, target

load_dotenv(ROOT / ".env", override=True)
LOG_DIR = ROOT / "outputs" / "switch_logs"
app = FastAPI()


class LoggingSamvaadAgent(AsyncSamvaadAgent):
    """The SDK drops platform events it has no model for (language_change, tool_call,
    variable_update). Catch them from the raw message first."""

    on_raw = None

    async def _route_message(self, message):
        t = str(message.get("type", "")) if isinstance(message, dict) else ""
        if self.on_raw and any(k in t for k in ("language_change", "tool_call", "variable_update", "state_transition")):
            await self.on_raw(t, message)
        await super()._route_message(message)


class Call:
    """One live Samvaad call and its switch log."""

    def __init__(self, seller_id: str, session_id: str, audio=None):
        self.seller_id, self.sid = seller_id, session_id
        self.audio = audio  # None → laptop mic/speaker via PipeWire
        self.spec = load_persona(seller_id)
        self.target = target()
        self.cfg = self.target["overrides"](self.spec, os.getenv("SAMVAAD_SPEAKER_OVERRIDE") or None)
        av = self.cfg["agent_variables"]
        self.started = time.time()
        self.turn = 0
        self.interaction_id: str | None = None
        self.agent_switches: list[dict] = []
        self.detector_hits: list[dict] = []
        self.transcript: list[dict] = []
        self.detector = SignalDetector(self.spec["language"]["language_code"])
        self.live = {
            "language_code": self.spec["language"]["language_code"], "speaker": self.cfg["speaker_label"],
            "pace": self.cfg["pace"], "english_mix": self.spec["language"].get("english_mix"),
            "warmth": self.spec["tone"].get("warmth"), "energy": self.spec["tone"].get("energy"),
            "max_sentences": av.get("max_sentences") or av.get("persona_style"), "focus": "pitch",
            "temperature": "fixed by agent",
        }
        self.agent: AsyncSamvaadAgent | None = None
        self.task: asyncio.Task | None = None

    def t(self):
        return round(time.time() - self.started, 1)

    # ---- callbacks -------------------------------------------------------------------------

    async def on_transcript(self, msg):
        who = "bot" if msg.role == Role.BOT else "seller"
        text = msg.content.strip()
        if not text:
            return
        self.transcript.append({"t": self.t(), "who": who, "text": text})
        bus.emit(self.sid, "transcript", {"who": who, "text": text, "t": self.t()})
        if who == "seller":
            self.turn += 1
            # independent cross-check with v1's detector (logged, not acted on)
            for s in self.detector.on_turn(text, None):
                hit = {"t_sec": self.t(), "turn": self.turn, "signal": s.name, "evidence": s.evidence,
                       "detector": "local detector (cross-check)", "change": {}, "reason": "detected locally"}
                self.detector_hits.append(hit)
                bus.emit(self.sid, "detector", hit)
                if s.name == "language_switch":
                    # Samvaad switches language by itself and sends no event for it,
                    # so the local detector is the record of this switch.
                    lang = (s.extra or {}).get("language_code", "?")
                    self.live["language_code"] = lang
                    self.record_switch({"signal": "language", "evidence": s.evidence,
                                        "change": f"reply language → {lang} (switched by Samvaad's language ID)",
                                        "reason": "seller spoke or asked for another language"},
                                       source="local detector (platform switched)")
                    bus.emit(self.sid, "state", self.live)

    async def on_raw(self, kind: str, msg: dict):
        if os.getenv("SAMVAAD_DEBUG"):
            print(f"  [raw {self.t()}s] {kind}: {json.dumps(msg, ensure_ascii=False)[:200]}")
        if "language_change" in kind:
            data = msg.get("data", msg)
            lang = data.get("language_name") or data.get("language") or data.get("new_language") or "?"
            self.live["language_code"] = lang
            self.record_switch({"signal": "language", "evidence": "seller spoke another language",
                                "change": f"call language → {lang}",
                                "reason": "Samvaad's language identification switched the call language"},
                               source="samvaad platform (language_change)")
            bus.emit(self.sid, "state", self.live)

    async def on_text(self, msg):
        if os.getenv("SAMVAAD_DEBUG"):
            print(f"  [text {self.t()}s] {type(msg).__name__}: {getattr(msg, 'text', '')[:80]}")

    async def on_event(self, ev):
        kind = getattr(ev, "type", "")
        if os.getenv("SAMVAAD_DEBUG"):
            print(f"  [event {self.t()}s] {kind}")
        if getattr(ev, "interaction_id", None):
            self.interaction_id = ev.interaction_id
            bus.emit(self.sid, "status", {"interaction_id": ev.interaction_id})
        if "interaction_end" in str(kind):
            bus.emit(self.sid, "status", {"ended": True})

    def record_switch(self, body: dict, source: str):
        sw = {
            "t_sec": self.t(), "turn": self.turn, "signal": str(body.get("signal", "?")).lower(),
            "evidence": body.get("evidence", ""), "detector": source,
            "change": {"delivery": ["", body.get("change", "")]}, "reason": body.get("reason", ""),
        }
        self.agent_switches.append(sw)
        bus.emit(self.sid, "switch", sw)
        return sw

    # ---- lifecycle -------------------------------------------------------------------------

    async def run(self):
        c = self.cfg
        config = InteractionConfig(
            org_id=os.environ["SAMVAAD_ORG_ID"], workspace_id=os.environ["SAMVAAD_WORKSPACE_ID"],
            app_id=self.target["app_id"], version=self.target["version"],
            user_identifier=f"seller-{self.seller_id}", user_identifier_type=UserIdentifierType.CUSTOM,
            interaction_type=InteractionType.CALL, sample_rate=16000,
            agent_variables=c["agent_variables"],
            initial_bot_message=c["initial_bot_message"],
            initial_language_name=SarvamToolLanguageName(c["initial_language_name"]),
            text_to_speech_config=TextToSpeechConfig(
                speaker_id=c["speaker"], speech_settings=SpeechSettings(pace=c["pace"])),
        )
        self.agent = LoggingSamvaadAgent(
            api_key=SecretStr(os.environ["SAMVAAD_API_KEY"]), config=config,
            audio_interface=self.audio or PipeWireAudioInterface(),
            transcript_callback=self.on_transcript, event_callback=self.on_event,
            text_callback=self.on_text,
        )
        self.agent.on_raw = self.on_raw
        bus.emit(self.sid, "persona", {"spec": self.spec, "live": self.live})
        try:
            await self.agent.start()
            if not await self.agent.wait_for_connect(15):
                bus.emit(self.sid, "status", {"error": "could not connect to Samvaad"})
                return
            await self.agent.wait_for_disconnect()
        except Exception as e:  # surface API/auth errors on the page
            bus.emit(self.sid, "status", {"error": f"{type(e).__name__}: {e}"})
            raise
        finally:
            # the SDK does not always stop the audio interface when the platform hangs up
            try:
                await (self.agent.audio_interface if self.agent else self.audio).stop()
            except Exception:
                pass
            self.save()

    async def stop(self):
        if self.agent:
            try:
                await self.agent.stop()
            except Exception:
                pass

    def save(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / f"samvaad_{self.seller_id}_{self.sid[:8]}.json"
        path.write_text(json.dumps({
            "platform": "samvaad", "seller_id": self.seller_id, "interaction_id": self.interaction_id,
            "call_settings": {k: v for k, v in self.cfg.items() if k != "agent_variables"},
            "agent": self.target["name"], "app_id": self.target["app_id"], "app_version": self.target["version"],
            "agent_switches": self.agent_switches, "local_detector_hits": self.detector_hits,
            "transcript": self.transcript,
        }, ensure_ascii=False, indent=2))
        bus.emit(self.sid, "ended", {"log": str(path.relative_to(ROOT))})


calls: dict[str, Call] = {}
current: dict[str, Call | None] = {"call": None}


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/mode")
async def mode():
    return {"mode": "samvaad"}


@app.get("/api/personas")
async def personas():
    return json.loads((PERSONA_DIR / "index.json").read_text())


@app.get("/api/persona/{seller_id}")
async def persona(seller_id: str):
    path = PERSONA_DIR / f"{seller_id}.json"
    if not path.is_file() or path.parent != PERSONA_DIR:
        raise HTTPException(404)
    return json.loads(path.read_text())


@app.post("/api/start")
async def start(body: dict):
    seller_id, sid = str(body.get("seller_id")), str(body.get("session_id") or uuid.uuid4())
    if not (PERSONA_DIR / f"{seller_id}.json").is_file():
        raise HTTPException(400, "unknown seller_id")
    prev = current["call"]
    if prev and prev.task and not prev.task.done():
        # e.g. the page was reloaded mid-call: end the old call before starting a new one
        await prev.stop()
        try:
            await asyncio.wait_for(asyncio.shield(prev.task), timeout=5)
        except Exception:
            prev.task.cancel()
    call = Call(seller_id, sid)
    calls[sid] = current["call"] = call
    call.task = asyncio.create_task(call.run())
    return {"session_id": sid}


@app.post("/api/stop")
async def stop():
    if current["call"]:
        await current["call"].stop()
    return {"ok": True}


@app.post("/samvaad/switch")
async def switch_webhook(request: Request):
    """Called by the Samvaad agent's `log_persona_switch` API tool."""
    body = await request.json()
    call = current["call"]
    if call is None or (call.task and call.task.done()):
        # no live voice call here (e.g. a text-chat test): still keep the record
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "samvaad_unattached.jsonl", "a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), **body}, ensure_ascii=False) + "\n")
        return {"persona_mode": str(body.get("signal", "base")), "logged": True}
    sw = call.record_switch(body, source="samvaad agent (tool)")
    return {"persona_mode": sw["signal"], "logged": True}


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
    uvicorn.run(app, host="127.0.0.1", port=7861)
