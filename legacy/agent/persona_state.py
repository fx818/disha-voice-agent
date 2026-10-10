"""Live persona state: starts from the generated spec, changes on detected signals.

Only *delivery* changes here (voice, pace, language, tone, reply length, plan focus).
Facts, pricing and compliance text come from generator/fixed_script.py and never change.
"""

import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONA_DIR = ROOT / "outputs" / "personas"

PACE_MIN, PACE_MAX = 0.9, 1.6

LANG_NAMES = {
    "hi-IN": "Hindi", "en-IN": "Indian English", "bn-IN": "Bengali", "gu-IN": "Gujarati",
    "kn-IN": "Kannada", "ml-IN": "Malayalam", "mr-IN": "Marathi", "od-IN": "Odia",
    "pa-IN": "Punjabi", "ta-IN": "Tamil", "te-IN": "Telugu",
}

# Fallback facts until generator/fixed_script.py exists.
DEFAULT_FACTS = [
    "You are Vani, calling from IndiaMART.",
    "IndiaMART has seen buyer enquiries in the seller's category in their city.",
    "You are proposing a 15-20 minute in-person meeting with an IndiaMART sales executive "
    "to help the seller get more out of these enquiries.",
    "If the seller agrees, confirm a day, time and locality for the meeting.",
]


def load_facts(spec: dict | None = None) -> list[str]:
    facts = (spec or {}).get("facts")
    if not facts:
        try:
            from generator import fixed_script

            facts = getattr(fixed_script, "FACTS", None)
        except Exception:
            facts = None
    if isinstance(facts, dict):
        return [f"{k.replace('_', ' ')}: {v}" for k, v in facts.items()]
    return list(facts) if facts else DEFAULT_FACTS


def load_persona(seller_id: str) -> dict:
    path = PERSONA_DIR / f"{seller_id}.json"
    return json.loads(path.read_text())


@dataclass
class Switch:
    t_sec: float
    turn: int
    signal: str
    evidence: str
    detector: str
    change: dict
    reason: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class PersonaState:
    spec: dict
    started: float = field(default_factory=time.time)
    live: dict = field(default_factory=dict)
    switches: list[Switch] = field(default_factory=list)
    active_signals: dict = field(default_factory=dict)  # signal -> turn it fired

    def __post_init__(self):
        v, lang, tone = self.spec["voice"], self.spec["language"], self.spec["tone"]
        self.live = {
            "speaker": v["speaker"],
            "pace": float(v.get("pace", 1.2)),
            "temperature": float(v.get("temperature", 0.6)),
            "language_code": lang["language_code"],
            "english_mix": float(lang.get("english_mix", 0.3)),
            "formality": lang.get("formality", "formal"),
            "warmth": tone.get("warmth", "medium"),
            "empathy": tone.get("empathy", "medium"),
            "energy": tone.get("energy", "neutral"),
            "max_sentences": 3 if self.spec.get("plan", {}).get("target_call_sec", 60) >= 80 else 2,
            "focus": "pitch",  # pitch | simplify | close | exit
            "ai_disclosed": False,
        }
        self.initial = copy.deepcopy(self.live)

    # ---- switching -------------------------------------------------------

    def apply(self, signal: str, turn: int, evidence: str, detector: str, extra: dict | None = None):
        """Apply a detected signal. Returns a Switch, or None if nothing changed."""
        before = copy.deepcopy(self.live)
        reason = ""
        L = self.live

        if signal == "rush":
            L["pace"] = min(PACE_MAX, round(L["pace"] + 0.2, 2))
            L["max_sentences"] = 1
            L["focus"] = "close"
            L["energy"] = "neutral"
            reason = ("Seller wants it quick: speed up, one sentence per reply, skip the explanation "
                      "and go straight to the meeting ask or a callback slot.")
        elif signal == "confusion":
            L["pace"] = max(PACE_MIN, round(L["pace"] - 0.15, 2))
            L["english_mix"] = round(max(0.0, L["english_mix"] - 0.2), 2) if L["language_code"] != "en-IN" else L["english_mix"]
            L["max_sentences"] = 2
            L["focus"] = "simplify"
            reason = ("Seller is confused: slow down, simpler everyday words (less English), "
                      "re-explain once in one idea per sentence, then check understanding.")
        elif signal == "frustration":
            L["pace"] = max(PACE_MIN, round(L["pace"] - 0.1, 2))
            L["warmth"], L["empathy"], L["energy"] = "high", "high", "calm"
            L["temperature"] = max(0.3, round(L["temperature"] - 0.15, 2))
            L["max_sentences"] = 1
            L["focus"] = "exit" if self.active_signals.get("frustration") is not None else "close"
            reason = ("Seller is irritated: calm and warm, acknowledge briefly, stop pitching; "
                      + ("second frustration signal, so offer a callback and end politely."
                         if L["focus"] == "exit" else "make one short, easy ask."))
        elif signal == "interest":
            L["energy"] = "upbeat"
            L["temperature"] = min(0.9, round(L["temperature"] + 0.1, 2))
            L["max_sentences"] = 3
            L["focus"] = "close"
            reason = ("Seller is engaged: a bit more energy, answer their question fully, "
                      "then move to fixing the meeting time.")
        elif signal == "bot_question":
            L["ai_disclosed"] = True
            L["warmth"] = "high"
            reason = ("Seller asked if this is a bot: answer honestly that Vani is IndiaMART's AI assistant, "
                      "warmly, then continue (61% of past bot answers denied it; guardrail forbids that).")
        elif signal == "language_switch":
            new = (extra or {}).get("language_code")
            if not new or new == L["language_code"]:
                return None
            L["language_code"] = new
            L["english_mix"] = 0.6 if new == "en-IN" else 0.2
            reason = f"Seller switched to {LANG_NAMES.get(new, new)}: reply in the seller's language."
        else:
            return None

        change = {k: [before[k], L[k]] for k in L if before[k] != L[k]}
        self.active_signals[signal] = turn
        if not change:
            return None
        sw = Switch(round(time.time() - self.started, 1), turn, signal, evidence, detector, change, reason)
        self.switches.append(sw)
        return sw

    def tts_delta(self, sw: Switch) -> dict:
        """Settings the TTS service must change for this switch."""
        keys = {"pace": "pace", "temperature": "temperature", "language_code": "language", "speaker": "voice"}
        return {keys[k]: v[1] for k, v in sw.change.items() if k in keys}

    # ---- prompt ----------------------------------------------------------

    def system_prompt(self) -> str:
        s, L = self.spec, self.live
        snap = s.get("seller_snapshot", {})
        plan = s.get("plan", {})
        lang = LANG_NAMES.get(L["language_code"], L["language_code"])
        facts = "\n".join(f"- {f}" for f in load_facts(s))
        guard = "\n".join(f"- {g}" for g in s.get("guardrails", []))
        playbook = "\n".join(
            f"- If {o.get('objection')}: {o.get('approach')}" for o in plan.get("objection_playbook", [])
        )
        escal = "\n".join(f"- If {e.get('trigger')}: {e.get('action')}" for e in plan.get("escalation_rules", []))
        hooks = "\n".join(f"- {h.get('hook')}" for h in plan.get("personalisation", []))
        script_note = (
            "Write Hindi in Devanagari; keep common English business words (meeting, buyer, enquiry, "
            "profile) in Latin script." if L["language_code"] == "hi-IN" else
            f"Write in {lang} using its native script; keep common English business words in Latin script."
            if L["language_code"] != "en-IN" else "Write in simple Indian English."
        )
        focus = {
            "pitch": "Introduce yourself and the reason for the call, then propose the meeting.",
            "simplify": "Re-explain the purpose in the simplest words, one idea per sentence, then ask if it is clear.",
            "close": "Skip extra explanation. Ask directly for a meeting day/time, or offer a callback slot.",
            "exit": "Apologise briefly, offer a callback at a time they choose, thank them and close the call.",
        }[L["focus"]]
        if L["ai_disclosed"]:
            focus = "First say plainly that you are IndiaMART's AI assistant (not a human). Then: " + focus

        return f"""You are Vani, a voice agent from IndiaMART, on a live phone call with a seller.

SELLER: {snap.get('company') or 'the seller'} — {snap.get('nature', '')}, {snap.get('city', '')}, {snap.get('state', '')}; \
categories: {', '.join(snap.get('top_categories', [])[:3])}.

FACTS YOU MAY STATE (never add, change or invent any fact, price, offer or promise):
{facts}

GUARDRAILS:
{guard or '- Personas change delivery only, never facts, pricing or compliance statements.'}
- Never claim to be human. If asked whether you are a bot, say honestly that you are IndiaMART's AI assistant.
- If asked about price or packages, say the sales executive will explain in the meeting.
- If the seller asks not to be called again, apologise, confirm, and end the call.

CURRENT DELIVERY (this can change during the call — always follow the latest):
- Language: {lang}. English share in your words: about {int(L['english_mix'] * 100)}%. {script_note}
- Formality: {L['formality']}. Warmth: {L['warmth']}. Empathy: {L['empathy']}. Energy: {L['energy']}.
- HARD LIMIT: at most {L['max_sentences']} sentence(s) and about {self.word_budget()} words per reply. Spoken phone call: short, one question at a time, no lists, no emojis, no markdown. Write number ranges with words ("15 se 20 minute"), never with a hyphen.
- Right now: {focus}

OPENING APPROACH: {plan.get('opening', {}).get('approach', 'Confirm you are speaking to the right business, then introduce yourself.')}
PERSONALISATION:
{hooks or '- Mention their city and category.'}
OBJECTION PLAYBOOK:
{playbook or '- Busy: offer a callback time.'}
ESCALATION:
{escal or '- Seller asks for a human: say an executive will call back.'}

Reply with only the words Vani speaks next."""

    def word_budget(self) -> int:
        return {1: 12, 2: 22, 3: 32}.get(self.live["max_sentences"], 22)

    def snapshot(self) -> dict:
        return {"live": self.live, "initial": self.initial, "switches": [s.as_dict() for s in self.switches]}
