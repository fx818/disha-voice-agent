"""Simulated seller: calls the running demo server over WebRTC, speaks scripted lines
(synthesised with Sarvam TTS), records VANI's audio and prints the live events.

Usage (server must be running: python -m agent.server):
  python -m tools.sim_call --seller 56730 --scenario hindi_mix
"""

import argparse
import asyncio
import base64
import fractions
import json
import os
import threading
import time
import urllib.request
import uuid
import wave
from pathlib import Path

import av
import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
SERVER = "http://127.0.0.1:7860"
RATE = 48000

SCENARIOS = {
    # (text, language, speaker, wait_after_sec)
    "hindi_mix": [
        ("हाँ जी, बोलिए।", "hi-IN", "rahul", 9),
        ("मतलब? मुझे समझ नहीं आया, आप किस बारे में बात कर रहे हो?", "hi-IN", "rahul", 11),
        ("अच्छा, कितने buyers की enquiry आई है? और meeting में क्या होगा?", "hi-IN", "rahul", 12),
        ("देखो मैं अभी बहुत busy हूँ, जल्दी बोलो क्या काम है।", "hi-IN", "rahul", 9),
        ("தமிழ்ல பேசுங்க, எனக்கு ஹிந்தி சரியா வராது.", "ta-IN", "rahul", 11),
    ],
    "frustrated": [
        ("हाँ, कौन?", "hi-IN", "amit", 9),
        ("क्या आप bot हो? सच बताओ।", "hi-IN", "amit", 10),
        ("कितनी बार बोला है, बार बार call मत करो।", "hi-IN", "amit", 10),
    ],
}


def tts(text, lang, speaker) -> np.ndarray:
    req = urllib.request.Request(
        "https://api.sarvam.ai/text-to-speech",
        data=json.dumps({"text": text, "target_language_code": lang, "speaker": speaker,
                         "model": "bulbul:v3", "speech_sample_rate": RATE}).encode(),
        headers={"api-subscription-key": os.environ["SARVAM_API_KEY"], "Content-Type": "application/json"})
    wav = base64.b64decode(json.load(urllib.request.urlopen(req))["audios"][0])
    tmp = ROOT / "outputs" / "cache" / f"sim_{uuid.uuid4().hex[:6]}.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(wav)
    with wave.open(str(tmp)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        assert w.getframerate() == RATE, w.getframerate()
    tmp.unlink()
    return pcm


class SellerMic(MediaStreamTrack):
    """Plays queued PCM, silence otherwise (20 ms frames at 48 kHz)."""
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.buf = np.zeros(0, dtype=np.int16)
        self.pts = 0
        self.start = None

    def say(self, pcm):
        self.buf = np.concatenate([self.buf, pcm])

    async def recv(self):
        n = RATE // 50
        if self.start is None:
            self.start = time.time()
        wait = self.start + self.pts / RATE - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        chunk, self.buf = self.buf[:n], self.buf[n:]
        if len(chunk) < n:
            chunk = np.concatenate([chunk, np.zeros(n - len(chunk), dtype=np.int16)])
        frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate, frame.pts, frame.time_base = RATE, self.pts, fractions.Fraction(1, RATE)
        self.pts += n
        return frame


def watch_events(session_id, stop):
    with urllib.request.urlopen(f"{SERVER}/api/events/{session_id}") as r:
        for raw in r:
            if stop.is_set():
                return
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            k, d = ev["kind"], ev["data"]
            if k == "transcript":
                print(f"  [{d['t']:>5}s] {'VANI ' if d['who'] == 'bot' else 'SELLER'}: {d['text']}")
            elif k == "switch":
                print(f"  [{d['t_sec']:>5}s] ⇄ SWITCH {d['signal']} ({d['evidence']}): {d['change']}")
            elif k == "ended":
                print("  call ended, log:", d["log"])
                return


async def main(seller, scenario):
    lines = SCENARIOS[scenario]
    print("synthesising seller lines…")
    pcms = [(tts(t, l, s), t, w) for t, l, s, w in lines]

    session_id = str(uuid.uuid4())
    stop = threading.Event()
    threading.Thread(target=watch_events, args=(session_id, stop), daemon=True).start()

    pc = RTCPeerConnection()
    mic = SellerMic()
    pc.addTrack(mic)
    recorded = []
    voice = {"last": time.time()}  # last time VANI's audio was non-silent

    @pc.on("track")
    def on_track(track):
        async def drain():
            res = av.AudioResampler(format="s16", layout="mono", rate=24000)
            try:
                while True:
                    f = await track.recv()
                    for r in res.resample(f):
                        a = r.to_ndarray().reshape(-1)
                        recorded.append(a)
                        if a.size and np.sqrt(np.mean(a.astype(np.float32) ** 2)) > 300:
                            voice["last"] = time.time()
            except Exception:
                pass
        asyncio.ensure_future(drain())

    await pc.setLocalDescription(await pc.createOffer())
    body = json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type,
                       "request_data": {"seller_id": seller, "session_id": session_id}}).encode()
    ans = json.load(urllib.request.urlopen(urllib.request.Request(
        f"{SERVER}/api/offer", data=body, headers={"Content-Type": "application/json"})))
    await pc.setRemoteDescription(RTCSessionDescription(sdp=ans["sdp"], type=ans["type"]))

    async def wait_for_vani(max_wait):
        # like a polite seller: wait until VANI has been silent for 1.2 s
        await asyncio.sleep(2.5)
        t0 = time.time()
        while time.time() - voice["last"] < 1.2 and time.time() - t0 < max_wait:
            await asyncio.sleep(0.1)

    await wait_for_vani(20)  # let VANI open
    for pcm, text, wait in pcms:
        mic.say(pcm)
        await asyncio.sleep(len(pcm) / RATE)
        await wait_for_vani(wait + 15)

    await pc.close()
    await asyncio.sleep(3)
    stop.set()
    out = ROOT / "outputs" / "sim_calls" / f"{seller}_{scenario}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(np.concatenate(recorded).astype(np.int16).tobytes() if recorded else b"")
    print("bot audio →", out.relative_to(ROOT))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seller", default="56730")
    ap.add_argument("--scenario", default="hindi_mix", choices=SCENARIOS)
    a = ap.parse_args()
    asyncio.run(main(a.seller, a.scenario))
