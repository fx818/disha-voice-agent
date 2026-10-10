"""Build the Hinglish voice-over for 'Disha: How a Call Works' in sync with the film.

  .venv/bin/python -I outputs/video/make_voiceover.py [--speaker ritu]

For each scene in voiceover_script.json: Sarvam Bulbul v3 TTS -> trim silence -> check it fits `max` seconds
(regenerate faster if not) -> place at `start` on one 237 s track. Writes outputs/video/vo/<id>.wav,
outputs/video/voiceover.wav and outputs/video/vo_timing.json.
"""
import argparse, base64, json, os, subprocess
from pathlib import Path
import httpx
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FILM_SEC = 237.0
load_dotenv(ROOT / ".env", override=True)

def sh(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True).stdout

def dur(p):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)))

ELEVEN = {"sarah": "EXAVITQu4vr4xnSDxMaL", "alice": "Xb7hH8MSUJpSbSDYk0k2", "jessica": "cgSgspJ2msm6clMCkdW9"}
ACCENT_TAG = "[calm, warm, Indian English accent] "


def tts_eleven(text, voice, speed, out):
    """ElevenLabs v3, a built-in voice told to speak Indian English (free plan: built-in voices only)."""
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN[voice]}", params={"output_format": "mp3_44100_128"},
                   headers={"xi-api-key": os.environ["ELEVEN_LABS_API_KEY"]},
                   json={"text": ACCENT_TAG + text, "model_id": "eleven_v3", "voice_settings": {"stability": 0.5}}, timeout=120)
    r.raise_for_status()
    raw = out.with_suffix(".raw.mp3")
    raw.write_bytes(r.content)
    tempo = f"atempo={speed}," if abs(speed - 1) > 1e-3 else ""  # v3 has no speed control: adjust tempo, pitch kept
    sh("ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
       tempo + "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.06",
       "-ac", "1", "-ar", "44100", str(out))
    raw.unlink()
    return dur(out)


LANG = "hi-IN"  # Sarvam target language; --lang en-IN for the English script


def tts(text, speaker, pace, out):
    if speaker in ELEVEN:
        return tts_eleven(text, speaker, pace, out)
    r = httpx.post("https://api.sarvam.ai/text-to-speech", headers={"api-subscription-key": os.environ["SARVAM_API_KEY"]},
                   json={"text": text, "target_language_code": LANG, "speaker": speaker, "model": "bulbul:v3",
                         "pace": pace, "speech_sample_rate": 44100}, timeout=90)
    r.raise_for_status()
    raw = out.with_suffix(".raw.wav")
    raw.write_bytes(base64.b64decode(r.json()["audios"][0]))
    # trim silence at both ends, keep a 60 ms tail, mono 44.1 kHz
    sh("ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
       "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.06",
       "-ac", "1", "-ar", "44100", str(out))
    raw.unlink()
    return dur(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--speaker", default="ritu"); ap.add_argument("--pace", type=float, default=1.05)
    ap.add_argument("--script", default="voiceover_script.json")
    ap.add_argument("--lang", default="hi-IN", help="Sarvam language: hi-IN (Hinglish) or en-IN")
    a = ap.parse_args()
    global LANG
    LANG = a.lang
    doc = json.loads((HERE / a.script).read_text())
    script = doc["scenes"]
    film_sec = float(doc.get("film_sec", FILM_SEC))  # the film's length, from the script
    vo = HERE / "vo"; vo.mkdir(exist_ok=True)
    timing = []
    for s in script:
        out = vo / f"{s['id']}.wav"
        pace = a.pace
        d = tts(s["text"], a.speaker, pace, out)
        while d > s["max"] and pace < 1.25:  # too long for its scene: say it a little faster
            pace = round(pace + 0.07, 2)
            d = tts(s["text"], a.speaker, pace, out)
        timing.append({"id": s["id"], "start": s["start"], "dur": round(d, 2), "end": round(s["start"] + d, 2),
                       "max": s["max"], "pace": pace, "fits": d <= s["max"]})
        print(f"{s['id']:7} start {s['start']:6.1f}s  len {d:5.2f}s  max {s['max']:4.1f}s  pace {pace}  {'ok' if d <= s['max'] else 'TOO LONG'}")
    # one track: every clip at its scene time
    inputs, filt = [], []
    for i, tm in enumerate(timing):
        inputs += ["-i", str(vo / f"{tm['id']}.wav")]
        ms = int(round(tm["start"] * 1000))
        filt.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(timing)))
    filt.append(f"{mix}amix=inputs={len(timing)}:normalize=0,apad=whole_dur={film_sec},atrim=0:{film_sec}[vo]")
    sh("ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[vo]", "-ac", "2", "-ar", "44100",
       str(HERE / "voiceover.wav"))
    (HERE / "vo_timing.json").write_text(json.dumps({"speaker": a.speaker, "pace": a.pace, "film_sec": film_sec, "clips": timing}, ensure_ascii=False, indent=1))
    print(f"voiceover.wav {dur(HERE / 'voiceover.wav'):.1f}s · all fit: {all(t['fits'] for t in timing)}")

if __name__ == "__main__":
    main()
