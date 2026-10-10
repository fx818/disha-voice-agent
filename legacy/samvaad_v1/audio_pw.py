"""Laptop mic/speaker for the Samvaad SDK via PipeWire CLI tools (no portaudio needed).

pw-record streams 16 kHz mono s16 from the default mic; pw-play plays the agent's audio.
"""

import asyncio
from typing import Awaitable, Callable, Optional

from sarvam_conv_ai_sdk.audio_interface import AsyncAudioInterface

IN_RATE = 16000
CHUNK_MS = 20


class PipeWireAudioInterface(AsyncAudioInterface):
    def __init__(self, on_bot_audio: Callable[[float], None] | None = None):
        self.rec: asyncio.subprocess.Process | None = None
        self.play: asyncio.subprocess.Process | None = None
        self.play_rate: int | None = None
        self.reader: asyncio.Task | None = None
        self.on_bot_audio = on_bot_audio

    async def start(self, input_callback: Callable[[bytes, int], Awaitable[None]]):
        self.input_callback = input_callback
        self.rec = await asyncio.create_subprocess_exec(
            "pw-record", "--rate", str(IN_RATE), "--channels", "1", "--format", "s16", "-",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        self.reader = asyncio.create_task(self._read_mic())

    async def _read_mic(self):
        n = IN_RATE * CHUNK_MS // 1000 * 2
        while self.rec and self.rec.stdout:
            data = await self.rec.stdout.readexactly(n)
            await self.input_callback(data, n // 2)

    async def _ensure_player(self, rate: int):
        if self.play and self.play_rate == rate and self.play.returncode is None:
            return
        await self._kill_player()
        self.play = await asyncio.create_subprocess_exec(
            "pw-play", "--rate", str(rate), "--channels", "1", "--format", "s16", "-",
            stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        self.play_rate = rate

    async def output(self, audio: bytes, sample_rate: Optional[int] = None):
        await self._ensure_player(sample_rate or 22050)
        if self.on_bot_audio:
            self.on_bot_audio(len(audio) / 2 / (sample_rate or 22050))
        try:
            self.play.stdin.write(audio)
        except (BrokenPipeError, ConnectionResetError, AttributeError):
            self.play = None

    def interrupt(self):
        # seller barged in: drop whatever is still buffered in the player
        if self.play and self.play.returncode is None:
            self.play.kill()
        self.play = None

    async def _kill_player(self):
        if self.play and self.play.returncode is None:
            self.play.kill()
            await self.play.wait()
        self.play = None

    async def stop(self):
        if self.reader:
            self.reader.cancel()
        if self.rec and self.rec.returncode is None:
            self.rec.kill()
        await self._kill_player()
