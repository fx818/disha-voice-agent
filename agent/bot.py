"""Live VANI call: Sarvam STT → signal monitor → LLM → Sarvam TTS, over local WebRTC.

The signal monitor sits between STT and the LLM. On each finished seller turn it runs the
detector; on a switch it (1) rewrites the system prompt before the LLM answers that turn and
(2) pushes a TTS settings update, so the very next sentence already uses the new delivery.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    EndFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    TTSUpdateSettingsFrame,
    UserStartedSpeakingFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from agent.events import bus
from agent.persona_state import ROOT, PersonaState, load_persona
from agent.signals import SignalDetector
from agent.speech_text import SpokenNumbersFilter

load_dotenv(ROOT / ".env", override=True)

LLM_MODEL = os.getenv("LLM_MODEL", "sarvam-105b-conversations")
VAD_STOP_SECS = float(os.getenv("VAD_STOP_SECS", "0.7"))  # pause that ends a seller turn
STT_MODEL = os.getenv("STT_MODEL", "saaras:v4")
TTS_MODEL = os.getenv("TTS_MODEL", "bulbul:v3")
BARGE_IN_MIN_BOT_SEC = 1.5
LOG_DIR = ROOT / "outputs" / "switch_logs"


class SignalMonitor(FrameProcessor):
    """Watches the seller, detects signals, switches the persona live."""

    def __init__(self, state: PersonaState, context: LLMContext, session_id: str):
        super().__init__()
        self.state = state
        self.context = context
        self.sid = session_id
        self.detector = SignalDetector(state.live["language_code"])
        self.bot_started: float | None = None
        self.turn = 0

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, BotStartedSpeakingFrame):
            self.bot_started = self.bot_started or time.time()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.bot_started = None
        elif isinstance(frame, UserStartedSpeakingFrame) and self.bot_started:
            # only a real interruption: the bot had been talking for a while
            if time.time() - self.bot_started >= BARGE_IN_MIN_BOT_SEC:
                self.detector.note_barge_in(self._t())
                bus.emit(self.sid, "barge_in", {"t": self._t()})
        elif isinstance(frame, TranscriptionFrame) and frame.text.strip():
            self.turn += 1
            lang = str(frame.language.value) if getattr(frame, "language", None) else None
            bus.emit(self.sid, "transcript", {"who": "seller", "text": frame.text, "lang": lang, "t": self._t()})
            await self._handle_turn(frame.text, lang)

        await self.push_frame(frame, direction)

    async def _handle_turn(self, text: str, lang: str | None):
        switched = False
        for sig in self.detector.on_turn(text, lang):
            sw = self.state.apply(sig.name, self.turn, sig.evidence, sig.detector, sig.extra)
            if not sw:
                continue
            switched = True
            delta = self.state.tts_delta(sw)
            if delta:
                await self.push_frame(TTSUpdateSettingsFrame(delta=SarvamTTSService.Settings(**delta)))
            bus.emit(self.sid, "switch", sw.as_dict())
            logger.info(f"SWITCH {sw.signal}: {sw.change} ({sw.evidence})")
        if switched:
            msgs = list(self.context.messages)
            msgs[0] = {"role": "system", "content": self.state.system_prompt()}
            self.context.set_messages(msgs)
            bus.emit(self.sid, "state", self.state.live)

    def _t(self):
        return round(time.time() - self.state.started, 1)


class BotTextTap(FrameProcessor):
    """Collects the LLM reply text for the live transcript panel."""

    def __init__(self, state: PersonaState, session_id: str):
        super().__init__()
        self.state, self.sid, self.buf = state, session_id, []

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMTextFrame):
            self.buf.append(frame.text)
        elif isinstance(frame, LLMFullResponseEndFrame) and self.buf:
            bus.emit(self.sid, "transcript", {"who": "bot", "text": "".join(self.buf).strip(),
                                              "t": round(time.time() - self.state.started, 1)})
            self.buf = []
        await self.push_frame(frame, direction)


def opening_line(spec: dict) -> str:
    line = spec.get("plan", {}).get("opening", {}).get("example_line")
    if line:
        return line
    company = spec.get("seller_snapshot", {}).get("company")
    return f"नमस्ते, क्या मैं {company} से बात कर रही हूँ?" if company else "नमस्ते, मैं IndiaMART से वाणी बोल रही हूँ।"


def save_log(state: PersonaState, session_id: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{state.spec['seller_id']}_{session_id[:8]}.json"
    path.write_text(json.dumps({
        "seller_id": state.spec["seller_id"],
        "session_id": session_id,
        "initial_persona": state.initial,
        "final_persona": state.live,
        "switches": [s.as_dict() for s in state.switches],
    }, ensure_ascii=False, indent=2))
    return path


async def run_call(webrtc_connection, seller_id: str, session_id: str):
    api_key = os.environ["SARVAM_API_KEY"]
    spec = load_persona(seller_id)
    state = PersonaState(spec)
    L = state.live
    bus.emit(session_id, "persona", {"spec": spec, "live": L})

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    stt = SarvamSTTService(api_key=api_key, settings=SarvamSTTService.Settings(model=STT_MODEL))
    llm = SarvamLLMService(api_key=api_key, settings=SarvamLLMService.Settings(
        model=LLM_MODEL, temperature=0.5, max_tokens=160,
        **({"reasoning_effort": "low"} if LLM_MODEL == "sarvam-105b" else {})))
    tts = SarvamTTSService(api_key=api_key, text_filters=[SpokenNumbersFilter(state)], settings=SarvamTTSService.Settings(
        model=TTS_MODEL, voice=L["speaker"], language=L["language_code"],
        pace=L["pace"], temperature=L["temperature"]))

    first = opening_line(spec)
    context = LLMContext([
        {"role": "system", "content": state.system_prompt()},
        {"role": "assistant", "content": first},
    ])
    pair = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=VAD_STOP_SECS))))
    monitor = SignalMonitor(state, context, session_id)

    pipeline = Pipeline([
        transport.input(), stt, monitor, pair.user(), llm, BotTextTap(state, session_id),
        tts, transport.output(), pair.assistant(),
    ])
    task = PipelineTask(pipeline, params=PipelineParams(enable_metrics=True))

    @transport.event_handler("on_client_connected")
    async def _connected(_t, _c):
        bus.emit(session_id, "transcript", {"who": "bot", "text": first, "t": 0.0})
        await task.queue_frames([TTSSpeakFrame(first, append_to_context=False)])

    @transport.event_handler("on_client_disconnected")
    async def _disconnected(_t, _c):
        await task.queue_frames([EndFrame()])

    try:
        await PipelineRunner(handle_sigint=False).run(task)
    finally:
        path = save_log(state, session_id)
        bus.emit(session_id, "ended", {"log": str(path.relative_to(ROOT))})
        logger.info(f"switch log → {path}")
