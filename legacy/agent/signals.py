"""Live signal detection on each finished seller turn.

Two kinds of cues, combined per turn:
- words: Hindi (Devanagari + Roman), English and a few regional phrases
- behaviour: barge-in on the bot, very short replies, seller repeating themselves,
  and the language the STT detected

Thresholds can be overridden by outputs/live_thresholds.json (built from past calls).
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "barge_ins_for_frustration": 2,   # interruptions of the bot within the call
    "short_reply_words": 2,           # replies this short count as curt
    "curt_replies_for_rush": 2,       # consecutive curt replies ...
    "curt_after_turn": 3,             # ... once past the greeting turns
    "repeat_similarity": 0.6,         # seller repeating own previous turn
    "lang_switch_min_words": 2,       # ignore one-word turns for language switches
    "lang_switch_turns": 2,           # consecutive turns in a new language (unless explicit)
    "cooldown_turns": 2,
    "barge_window_sec": 30,           # two barge-ins inside this window → frustration              # same signal can't re-fire within this many turns
}
EXTRA_KEYWORDS: dict[str, list[str]] = {}


def load_thresholds() -> dict:
    """Thresholds + romanized keyword lists mined from past calls (outputs/live_thresholds.json)."""
    t = dict(DEFAULTS)
    p = ROOT / "outputs" / "live_thresholds.json"
    if not p.exists():
        return t
    try:
        data = json.loads(p.read_text())
    except Exception:
        return t
    rush = data.get("rush", {})
    t["short_reply_words"] = rush.get("short_reply_max_words", t["short_reply_words"])
    t["curt_replies_for_rush"] = rush.get("consecutive_short_replies", t["curt_replies_for_rush"])
    t["curt_after_turn"] = rush.get("after_turn", t["curt_after_turn"])
    t["cooldown_turns"] = data.get("cooldown_turns", t["cooldown_turns"])
    for name in ("rush", "frustration", "confusion", "interest", "bot_question"):
        kws = data.get(name, {}).get("keywords")
        if kws:
            EXTRA_KEYWORDS[name] = kws
    return t


def _rx(words):
    return re.compile("|".join(words), re.IGNORECASE)


CUES = {
    "rush": _rx([
        r"\bjaldi\b", r"जल्दी", r"\bbusy\b", r"बिज़ी", r"बिजी", r"time nahi", r"टाइम नहीं", r"समय नहीं",
        r"short me", r"शॉर्ट में", r"point pe", r"पॉइंट पर", r"seedha", r"सीधा", r"\bquick", r"\bhurry",
        r"meeting me hu", r"मीटिंग में हूँ", r"drive kar", r"ड्राइव कर", r"gaadi chala", r"गाड़ी चला",
        r"baad me baat", r"बाद में बात", r"jaldi bolo", r"जल्दी बोलो", r"kaam bata", r"काम बताओ",
        r"what do you want", r"come to the point",
    ]),
    "confusion": _rx([
        r"samajh nahi", r"समझ नहीं", r"samjha nahi", r"समझा नहीं", r"\bmatlab\b", r"मतलब", r"kya bol rah",
        r"क्या बोल रह", r"phir se", r"फिर से", r"dobara", r"दोबारा", r"repeat", r"what\?", r"sorry\?",
        r"didn'?t understand", r"not clear", r"kaunsi meeting", r"कौन सी मीटिंग", r"kis baare", r"किस बारे",
        r"kya hai ye", r"ये क्या है", r"புரியல", r"అర్థం కాలేదు", r"ಅರ್ಥ ಆಗಲಿಲ್ಲ", r"સમજાયું નહીં",
    ]),
    "frustration": _rx([
        r"kitni baar", r"कितनी बार", r"baar baar", r"बार बार", r"pareshan", r"परेशान", r"faltu", r"फालतू",
        r"bakwas", r"बकवास", r"dimag", r"दिमाग", r"irritat", r"\bannoy", r"call mat", r"कॉल मत", r"phone mat",
        r"फोन मत", r"already bola", r"पहले ही बोला", r"bola na", r"बोला ना", r"mana kiya", r"मना किया",
        r"stop calling", r"don'?t call", r"kya yaar", r"क्या यार", r"band karo", r"बंद करो",
    ]),
    "interest": _rx([
        r"kitne buyer", r"कितने buyer", r"कितने बायर", r"kaun se buyer", r"कौन से", r"kaise hoga", r"कैसे होगा",
        r"kab aayenge", r"कब आएंगे", r"kab aa sakte", r"कब आ सकते", r"theek hai bata", r"ठीक है बता", r"achha bata",
        r"अच्छा बता", r"aur batao", r"और बताओ", r"detail", r"डिटेल", r"how many", r"tell me more",
        r"interested", r"इंटरेस्टेड", r"haan bolo", r"हाँ बोलो", r"kitna time", r"कितना टाइम",
        r"kya hoga", r"क्या होगा", r"कितने", r"\bkitne\b",
    ]),
    "bot_question": _rx([
        r"\bbot\b", r"बॉट", r"robot", r"रोबोट", r"\bai\b", r"computer", r"कंप्यूटर", r"recording",
        r"machine", r"मशीन", r"insaan", r"इंसान", r"real person", r"asli", r"असली",
    ]),
}

IDENTITY = re.compile(r"kaun|kon\b|कौन|who is|who'?s this", re.IGNORECASE)

# Explicit request to change language → switch on a single turn.
EXPLICIT_LANG = {
    "ta-IN": _rx([r"tamil", r"தமிழ"]), "te-IN": _rx([r"telugu", r"తెలుగు"]),
    "kn-IN": _rx([r"kannada", r"ಕನ್ನಡ"]), "ml-IN": _rx([r"malayalam", r"മലയാളം"]),
    "gu-IN": _rx([r"gujarati", r"ગુજરાતી"]), "mr-IN": _rx([r"marathi", r"मराठी"]),
    "bn-IN": _rx([r"bengali", r"bangla", r"বাংলা"]), "pa-IN": _rx([r"punjabi", r"ਪੰਜਾਬੀ"]),
    "en-IN": _rx([r"\benglish\b", r"इंग्लिश", r"hindi (nahi|nahin) aati", r"don'?t (know|speak|understand) hindi"]),
    "hi-IN": _rx([r"hindi (me|mein) bol", r"हिंदी में", r"hindi please", r"speak hindi"]),
}

SCRIPTS = {
    "hi-IN": r"[ऀ-ॿ]", "bn-IN": r"[ঀ-৿]", "pa-IN": r"[਀-੿]",
    "gu-IN": r"[઀-૿]", "od-IN": r"[଀-୿]", "ta-IN": r"[஀-௿]",
    "te-IN": r"[ఀ-౿]", "kn-IN": r"[ಀ-೿]", "ml-IN": r"[ഀ-ൿ]",
}


def script_language(text: str) -> str | None:
    """Language from the dominant script; Latin-only text with English words → en-IN."""
    counts = {code: len(re.findall(rx, text)) for code, rx in SCRIPTS.items()}
    code, n = max(counts.items(), key=lambda kv: kv[1])
    letters = len(re.findall(r"\w", text))
    if n and n >= 0.4 * letters:
        return code
    return None


def _similar(a: str, b: str) -> float:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return len(wa & wb) / max(1, min(len(wa), len(wb))) if wa and wb else 0.0


@dataclass
class Signal:
    name: str
    evidence: str
    detector: str
    extra: dict | None = None


class SignalDetector:
    def __init__(self, language_code: str):
        self.t = load_thresholds()
        self.cues = {name: CUES[name] for name in CUES}
        for name, kws in EXTRA_KEYWORDS.items():
            self.cues[name] = re.compile(CUES[name].pattern + "|" + "|".join(kws), re.IGNORECASE)
        self.language_code = language_code
        self.barge_ins = 0
        self.curt_streak = 0
        self.prev_text = ""
        self.turn = 0
        self.last_fired: dict[str, int] = {}
        self.pending_lang: tuple[str, int] | None = None  # (code, consecutive turns)
        self.identity_asks = 0

    def note_barge_in(self, t_sec: float):
        # count interruptions inside a sliding window
        self.barge_times = [t for t in getattr(self, "barge_times", []) if t_sec - t <= self.t["barge_window_sec"]]
        self.barge_times.append(t_sec)
        self.barge_ins = len(self.barge_times)

    def _language(self, text: str, stt_language: str | None) -> Signal | None:
        words = text.split()
        for code, rx in EXPLICIT_LANG.items():
            m = rx.search(text)
            if m and code != self.language_code:
                self.pending_lang = None
                return Signal("language_switch", f'asked for it: "{m.group(0)}"', "explicit request",
                              {"language_code": code})
        if len(words) < self.t["lang_switch_min_words"]:
            return None
        detected = script_language(text) or (stt_language if stt_language not in (None, "unknown") else None)
        if detected is None and re.fullmatch(r"[A-Za-z0-9 ,.'?!-]+", text) and len(words) >= 4:
            hinglish = re.search(r"\b(hai|hain|haan|nahi|kya|aap|main|mera|bhai|ji|bolo|karo|kaun|abhi)\b", text, re.I)
            detected = None if hinglish else "en-IN"
        if not detected or detected == self.language_code:
            self.pending_lang = None
            return None
        n = self.pending_lang[1] + 1 if self.pending_lang and self.pending_lang[0] == detected else 1
        self.pending_lang = (detected, n)
        if n >= self.t["lang_switch_turns"]:
            self.pending_lang = None
            return Signal("language_switch", f'{n} turns in {detected}: "{text[:40]}"', "script/STT",
                          {"language_code": detected})
        return None

    def on_turn(self, text: str, stt_language: str | None) -> list[Signal]:
        self.turn += 1
        out: list[Signal] = []
        words = text.split()

        # Word cues, in priority order
        for name in ("frustration", "rush", "confusion", "interest", "bot_question"):
            m = self.cues[name].search(text)
            if not m:
                continue
            if name == "confusion" and IDENTITY.search(m.group(0)):
                # "who is this?" is a normal first question; only a repeat signals confusion
                self.identity_asks += 1
                if self.identity_asks < 2:
                    continue
                out.append(Signal(name, f'asked "{m.group(0)}" again', "keyword+repeat"))
                continue
            out.append(Signal(name, f'said "{m.group(0)}"', "keyword"))

        # Seller repeating themselves → the bot isn't getting through
        if self.prev_text and len(words) >= 3 and _similar(text, self.prev_text) >= self.t["repeat_similarity"]:
            out.append(Signal("confusion", "seller repeated their previous turn", "repetition"))

        # Barge-ins → frustration; curt replies after the greeting → rush
        if self.barge_ins >= self.t["barge_ins_for_frustration"]:
            out.append(Signal("frustration", f"interrupted the bot {self.barge_ins} times in "
                              f"{self.t['barge_window_sec']}s", "barge-in"))
            self.barge_ins, self.barge_times = 0, []
        self.curt_streak = self.curt_streak + 1 if len(words) <= self.t["short_reply_words"] else 0
        if (self.turn > self.t["curt_after_turn"] and self.curt_streak >= self.t["curt_replies_for_rush"]
                and not any(s.name == "interest" for s in out)):
            out.append(Signal("rush", f"{self.curt_streak} very short replies in a row", "reply-length"))
            self.curt_streak = 0

        lang = self._language(text, stt_language)
        if lang:
            self.language_code = lang.extra["language_code"]
            out.append(lang)
        self.prev_text = text

        # one per kind per turn; same signal can't re-fire inside the cooldown
        # (frustration may, since a second one escalates to a polite exit)
        seen, keep = set(), []
        for s in out:
            if s.name in seen:
                continue
            last = self.last_fired.get(s.name)
            if (last is not None and self.turn - last <= self.t["cooldown_turns"]
                    and s.name not in ("frustration", "language_switch")):
                continue
            seen.add(s.name)
            self.last_fired[s.name] = self.turn
            keep.append(s)
        return keep
