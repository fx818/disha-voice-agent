"""Simulated seller for the Samvaad version: runs a real Samvaad voice call with scripted
seller lines (Sarvam TTS) instead of a microphone, records VANI's audio, prints the
transcript and the switch log. Hosts the switch webhook itself on :7861 (stop samvaad.server first); the tunnel must be up.

  python -m tools.sim_samvaad --seller 56730 --scenario hindi_mix
"""

import argparse
import asyncio
import json
import time
import uuid
import wave
from typing import Optional

import numpy as np

from agent.events import bus
import uvicorn

from samvaad.server import ROOT, Call, app, current
from sarvam_conv_ai_sdk.audio_interface import AsyncAudioInterface
from tools.sim_call import SCENARIOS, tts

RATE = 16000


class SimAudio(AsyncAudioInterface):
    def __init__(self):
        self.queue = np.zeros(0, dtype=np.int16)
        self.bot = []
        self.bot_rate = 16000
        self.last_bot = time.time()
        self.play_end = time.time()  # when the agent's buffered audio finishes playing

    async def start(self, input_callback):
        self.input_callback = input_callback
        self.task = asyncio.create_task(self._pump())

    async def _pump(self):
        n = RATE // 50  # 20 ms
        t0 = time.time()
        sent = 0
        while True:
            chunk, self.queue = self.queue[:n], self.queue[n:]
            if len(chunk) < n:
                chunk = np.concatenate([chunk, np.zeros(n - len(chunk), dtype=np.int16)])
            await self.input_callback(chunk.tobytes(), n)
            sent += n
            await asyncio.sleep(max(0, t0 + sent / RATE - time.time()))

    def say(self, pcm):
        print(f"  [sim {time.strftime('%H:%M:%S')}] seller speaks {len(pcm)/RATE:.1f}s, rms {np.sqrt(np.mean(pcm.astype(np.float32)**2)):.0f}")
        self.queue = np.concatenate([self.queue, pcm])

    async def output(self, audio: bytes, sample_rate: Optional[int] = None):
        self.bot_rate = sample_rate or self.bot_rate
        a = np.frombuffer(audio, dtype=np.int16)
        self.bot.append(a)
        # audio arrives faster than real time and includes quiet background ambience:
        # keep a playback clock, and remember where the last *speech* chunk ends
        self.play_pos = max(getattr(self, "play_pos", 0.0), time.time()) + len(a) / self.bot_rate
        if a.size and np.sqrt(np.mean(a.astype(np.float32) ** 2)) > 1000:
            self.play_end = self.play_pos

    def interrupt(self):
        pass

    async def stop(self):
        self.task.cancel()


def resample(pcm48: np.ndarray) -> np.ndarray:
    return pcm48[::3]  # 48 kHz → 16 kHz (TTS is clean speech; plain decimation is fine for a test)


async def main(seller, scenario):
    lines = [(resample(tts(t, l, s)), t) for t, l, s, _ in SCENARIOS[scenario]]
    # host the switch webhook in this process so the agent's reports reach this call
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=7861, log_level="warning"))
    srv = asyncio.create_task(server.serve())
    await asyncio.sleep(1.5)
    audio = SimAudio()
    sid = str(uuid.uuid4())
    call = Call(seller, sid, audio=audio)
    current["call"] = call
    q = bus.subscribe(sid)

    async def printer():
        while True:
            ev = await q.get()
            k, d = ev["kind"], ev["data"]
            if k == "transcript":
                print(f"  [{d['t']:>5}s] {'VANI ' if d['who'] == 'bot' else 'SELLER'}: {d['text']}")
            elif k == "switch":
                print(f"  [{d['t_sec']:>5}s] ⇄ SWITCH {d['signal']} ({d['detector']}): {d['change']['delivery'][1]} | {d['reason']}")
            elif k == "detector":
                print(f"  [{d['t_sec']:>5}s]   (local detector: {d['signal']})")
            elif k == "status" and d.get("error"):
                print("  ERROR", d["error"])

    p = asyncio.create_task(printer())
    call.task = asyncio.create_task(call.run())

    async def wait_quiet(max_wait):
        # a polite seller: wait for the agent to START replying, then for its speech to end
        t0 = time.time()
        while audio.play_end < t0 and time.time() - t0 < 12:
            await asyncio.sleep(0.1)
        while time.time() < audio.play_end + 1.0 and time.time() - t0 < max_wait:
            await asyncio.sleep(0.1)

    await wait_quiet(15)
    for pcm, text in lines:
        audio.say(pcm)
        await asyncio.sleep(len(pcm) / RATE)
        await wait_quiet(15)
    await wait_quiet(12)  # hear the agent's last reply
    print("  [sim] chunks sent by SDK:", getattr(call.agent, "_client_audio_chunks_sent", "?"),
          "| server audio chunks:", getattr(call.agent, "_server_audio_chunks_received", "?"))
    await call.stop()
    await asyncio.sleep(2)
    p.cancel()
    server.should_exit = True
    await srv
    out = ROOT / "outputs" / "sim_calls" / f"samvaad_{seller}_{scenario}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(audio.bot_rate)
        w.writeframes(np.concatenate(audio.bot).tobytes() if audio.bot else b"")
    print("bot audio →", out.relative_to(ROOT))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seller", default="56730")
    ap.add_argument("--scenario", default="hindi_mix", choices=SCENARIOS)
    a = ap.parse_args()
    asyncio.run(main(a.seller, a.scenario))
