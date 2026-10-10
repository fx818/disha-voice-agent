"""Disha code tools: per-seller persona at call start, live switch log, structured log at call end.

BUILT FILE: edit disha_tools_src.py and run tools/build_code_tool.py; do not edit disha_tools.py by hand.
Upload this single file to the Disha agent (Disha---Ind-85eb0f30-d809) (Tools -> Add tool -> Upload Python file).
Imports only the standard library, httpx, pydantic and sarvam_conv_ai_sdk.

Input: agent variable `seller_profile`, a JSON string exported by tools/export_profiles.py:
  {"v": 1, "seller_id": ..., "gen": {flat seller row}, "jev": {Jev state}, "rules": {"use_case", "contact_policy", ...}}
Secret: TYPESAFE_API_KEY (workspace secret) for Jev.
Agent variables written (must be declared on the agent): use_case, use_case_confidence, use_case_reason, jev_signals,
persona_style, seller_history, persona_notes, persona_spec, seller_id, company_name, city, call_calendar,
switch_log_json. Undeclared ones are skipped, never fatal.

OnStart     never raises. Installs a safe neutral opening, Hindi and a default pace first, then (all optional, each
            failure falls back to the base persona): validates the profile, honours the contact policy, categorises
            with Jev under one overall deadline (cross-checked with the rules), runs the persona generator
            (generator/generate.py, bundled below), and sets the use case, persona inputs, call calendar, opening
            line, start language and pace (voice stays the platform's). The full spec is saved in persona_spec.
persona_switch  mid-call: Disha calls it on rush / confusion / frustration / interest / language / bot question;
            records the switch (time, words, change, reason, language before/after, applied status) in internal
            variables and returns the delivery change to apply.
OnEnd       writes a base switch_log_json first, then checks each switch with Jev against a transcript window
            around its seller turn (bounded deadline) and writes it again.
"""
import asyncio
import difflib
import itertools
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import httpx
from pydantic import Field

from sarvam_conv_ai_sdk import (
    SarvamInteractionTurnRole,
    SarvamOnEndTool,
    SarvamOnEndToolContext,
    SarvamOnStartTool,
    SarvamOnStartToolContext,
    SarvamTool,
    SarvamToolContext,
    SarvamToolLanguageName,
    SarvamToolOutput,
    SpeechSettings,
    TextToSpeechConfig,
)

# @@PERSONA_GENERATOR@@

CONTRACT_VERSION = 2
JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_TIMEOUT_S = 4.0           # per HTTP operation; the overall deadlines below bound the whole call
JEV_DEADLINE_S = 1.5          # OnStart: whole Jev classification, then rules fallback
JEV_VERIFY_DEADLINE_S = 6.0   # OnEnd: whole switch verification, then the base log stands
DEFAULT_PACE = 1.1
MAX_SWITCHES = 50
KNOWN_VERSIONS = (1, 2)
IST = timezone(timedelta(hours=5, minutes=30))

# ---- Jev questions (copied from outputs/segmentation/scripts/j02_jev_validate_v2.py, validated run 2) ----------
NOULS = {
    "pending_commitment": "The seller has an open commitment with IndiaMART from a recent call: on one of the last calls "
                          "(roughly within the last 60 days) they agreed to a meeting or demo, or asked to be called back at a later time.",
    "ignores_leads": "The seller receives buyer enquiries or phone enquiries (PNS) through IndiaMART but mostly does not reply to "
                     "or answer them, or has said the leads they get are fake, irrelevant or useless.",
    "upgrade_intent": "The seller has shown interest in paying for IndiaMART services: they explored or asked about paid plans or "
                      "packages, tried to buy buy-leads or buyer contacts, or asked about prices of IndiaMART services.",
    "inactive_business": {
        "instructions": "The seller's business has gone quiet or closed.",
        "criteria": {
            "true": "The recorded data shows zero activity, zero buyer enquiries and zero catalog edits over the last "
                    "90 days, or the seller said on a call that the business has closed, stopped or no longer sells.",
            "false": "The data shows recent activity, enquiries, replies or catalog edits, or the activity data is "
                     "unknown. Unknown or missing data is not evidence that the business is inactive.",
        },
    },
}
CATALOG_LEVELS = [
    "The catalog is well built: plenty of products listed, a quality score well above the typical seller, and recent edits.",
    "The catalog is usable but basic: around the typical number of products and a typical quality score.",
    "The catalog is thin: only a handful of products, a quality score well below the typical seller, or business details missing.",
    "Almost nothing is set up: the seller is newly registered or has one or two products and no real catalog yet.",
]
CATALOG_INSTR = ("How much work does this seller's IndiaMART catalog need? Compare the products listed and the catalog "
                 "quality score with the typical seller values given. If catalog data is unknown, judge only from any "
                 "call history and profile details.")
REFERENCE = {"typical_seller_products_listed": 12, "typical_seller_catalog_quality_score_out_of_100": 15,
             "typical_seller_buyer_enquiries_last_year": 0}
ORDER = [("warm_followup", "pending_commitment"), ("lead_engagement", "ignores_leads"),
         ("free_to_paid", "upgrade_intent"), ("reactivation", "inactive_business")]
SIGNAL_WORDS = {"pending_commitment": "pending commitment", "ignores_leads": "not using leads",
                "upgrade_intent": "upgrade intent", "inactive_business": "inactive business"}

# ---- persona per use case --------------------------------------------------------------------------------------
# The voice stays the one set on the platform; only pace changes per use case. `hook` is the neutral Hindi hook;
# OPENING_HOOKS holds the per-language hooks, with an "evidence" variant used only when the profile proves the fact.
USE_CASES = {
    "warm_followup": {
        "pace": 1.1, "style": "friendly_casual",
        "hook": "pichli baat ke silsile mein call kiya hai, kya abhi do minute baat ho sakti hai?",
        "goal": "Confirm the meeting or callback the seller agreed to and lock one concrete slot; check the meeting really exists.",
        "approach": "Refer to the earlier conversation only as far as the seller history shows; if unsure, ask. If busy "
                    "again, offer two concrete slots, never 'rough time bata dijiye'. If already met an executive, ask "
                    "whether new enquiries came since.",
    },
    "lead_engagement": {
        "pace": 1.0, "style": "warm_formal",
        "hook": "IndiaMART par sahi buyer enquiries paane ke baare mein do minute baat ho sakti hai?",
        "goal": "Get the seller replying to the enquiries and phone enquiries they already receive; offer a free profile fix so leads are relevant.",
        "approach": "Calm, empathetic, longer listening turns. Ask whether the enquiries they get are relevant; never invent "
                    "a specific enquiry or a count that is not in the facts on record. If leads are called fake or "
                    "irrelevant: acknowledge, mention a possible reason (missing profile details can bring mismatched "
                    "enquiries), offer the free fix.",
    },
    "free_to_paid": {
        "pace": 1.2, "style": "brief_direct",
        "hook": "IndiaMART ki services se zyada buyer enquiries ke baare mein do minute baat ho sakti hai?",
        "goal": "Turn the shown interest into a free meeting where an executive explains plans. Never quote or negotiate price.",
        "approach": "Value first in the first sentence. Do not claim the seller looked at paid services unless the facts on "
                    "record say so. Never mention a failed payment. On cost pushback say only the meeting is free and "
                    "the executive will explain the plans, then offer two slots. On buying cues (address, kitne baje, aa "
                    "jaiye) confirm the slot at once.",
    },
    "reactivation": {
        "pace": 0.95, "style": "patient_gentle",
        "hook": "bas yeh jaanna tha ki aapka kaam kaisa chal raha hai, do minute baat ho sakti hai?",
        "goal": "Find out whether the business is slow, has changed line, or has closed. One ask only; information, not a sale.",
        "approach": "One question only, respectful (aap), polite and unhurried. If closed: one empathetic question, then close politely. If seasonal: take a "
                    "callback date. If a new line of business: offer a free catalog update visit.",
    },
    "profile_onboarding": {
        "pace": 1.05, "style": "friendly_casual",
        "hook": "aapki IndiaMART profile behtar karne mein free madad ke liye call kiya hai, do minute?",
        "goal": "Book the free executive visit to complete the catalog: photos, products, business details.",
        "approach": "Warm, simple words. Use the seller's own gap only as far as the facts on record show (few products, "
                    "low catalog score). Treat 'yeh product hamara nahi' or 'hum retail hai' as a catalog fix, not a "
                    "refusal. On cost: the visit is free.",
    },
    "discovery": {
        "pace": 1.1, "style": "friendly_casual",
        "hook": "aapke IndiaMART account ke baare mein do minute baat ho sakti hai?",
        "goal": "Ask what the seller sells and whether enquiries are coming, then offer the matching free next step.",
        "approach": "Neutral defaults; let live adaptation lead.",
    },
}
# Opening hooks per start language. "evidence" is used only when the profile shows the fact the hook states.
OPENING_HOOKS = {
    "hi-IN": {
        "warm_followup": {"default": USE_CASES["warm_followup"]["hook"],
                          "evidence": "aapke kehne par call kiya hai, kya abhi do minute baat ho sakti hai?"},
        "lead_engagement": {"default": USE_CASES["lead_engagement"]["hook"],
                            "evidence": "aapko IndiaMART par jo buyer enquiries aa rahi hain, unke baare mein do minute baat ho sakti hai?"},
        "free_to_paid": {"default": USE_CASES["free_to_paid"]["hook"],
                         "evidence": "aap IndiaMART ki paid services dekh rahe the, do minute baat ho sakti hai?"},
        "reactivation": {"default": USE_CASES["reactivation"]["hook"]},
        "profile_onboarding": {"default": USE_CASES["profile_onboarding"]["hook"]},
        "discovery": {"default": USE_CASES["discovery"]["hook"]},
    },
    "en-IN": {
        "warm_followup": {"default": "I'm calling as a follow-up to our earlier conversation; do you have two minutes?",
                          "evidence": "you had asked us to call back, so do you have two minutes now?"},
        "lead_engagement": {"default": "it's about getting more relevant buyer enquiries on IndiaMART; do you have two minutes?",
                            "evidence": "it's about the buyer enquiries coming to your IndiaMART account; do you have two minutes?"},
        "free_to_paid": {"default": "it's about getting more buyer enquiries through IndiaMART's services; do you have two minutes?",
                         "evidence": "you had looked at IndiaMART's paid services; do you have two minutes?"},
        "reactivation": {"default": "I just wanted to check how your business is doing; do you have two minutes?"},
        "profile_onboarding": {"default": "I'm calling to offer free help improving your IndiaMART profile; do you have two minutes?"},
        "discovery": {"default": "it's about your IndiaMART account; do you have two minutes?"},
    },
    "ta-IN": {
        "warm_followup": {"default": "munnaadi pesinadhu sambandhamaa call panninen, rendu nimisham pesalaama?",
                          "evidence": "neenga apparam call pannunga sonneenga, ippo rendu nimisham pesalaama?"},
        "lead_engagement": {"default": "IndiaMART-la sariyaana buyer enquiries varradhu pathi rendu nimisham pesalaama?",
                            "evidence": "unga IndiaMART account-ku varra buyer enquiries pathi rendu nimisham pesalaama?"},
        "free_to_paid": {"default": "IndiaMART services moolama adhigama buyer enquiries varradhu pathi rendu nimisham pesalaama?",
                         "evidence": "neenga IndiaMART paid services paathuttu irundheenga, rendu nimisham pesalaama?"},
        "reactivation": {"default": "unga business eppadi poyittu irukku-nu therinjukka dhaan call panninen, rendu nimisham pesalaama?"},
        "profile_onboarding": {"default": "unga IndiaMART profile-a free-aa improve panna udhavi panna call panninen, rendu nimisham pesalaama?"},
        "discovery": {"default": "unga IndiaMART account pathi rendu nimisham pesalaama?"},
    },
}
# Openings are one short line: greeting, the caller's name, IndiaMART, one identity question. No pitch and no AI
# mention in the opening; the purpose line is given in Phase 2 (it is passed to the agent in persona_notes).
OPENING_PARTS = {
    "hi-IN": {"me": "Namaste, main Disha bol rahi hoon IndiaMART se.", "who": "{company} se baat ho rahi hai?",
              "who_anon": "Aap IndiaMART seller bol rahe hain?"},
    "en-IN": {"me": "Hello, I'm Disha, calling from IndiaMART.", "who": "Am I speaking with {company}?",
              "who_anon": "Am I speaking with the IndiaMART seller?"},
    "ta-IN": {"me": "Vanakkam, naan Disha pesuren IndiaMART-la irundhu.", "who": "{company}-aa pesuradhu?",
              "who_anon": "IndiaMART seller-aa pesuradhu?"},
    # Regional openings below are not chosen by default (past calls from these states were 97%+ in Hindi); they are
    # used when a call review or an approved rule sets the start language. Native-speaker review pending.
    "bn-IN": {"me": "Nomoskar, ami Disha bolchhi IndiaMART theke.", "who": "{company} theke bolchhen?",
              "who_anon": "Apni ki IndiaMART seller bolchhen?"},
    "gu-IN": {"me": "Namaste, hu Disha bolu chhu IndiaMART thi.", "who": "{company} sathe vaat thai rahi chhe?",
              "who_anon": "Tame IndiaMART seller bolo chho?"},
    "kn-IN": {"me": "Namaskara, naanu Disha maathaadtha iddini IndiaMART inda.", "who": "{company} jothe maathaadtha iddeena?",
              "who_anon": "Neevu IndiaMART seller-aa?"},
    "ml-IN": {"me": "Namaskaram, njan Disha aanu, IndiaMART-il ninnu vilikkunnu.", "who": "{company} alle samsarikkunnathu?",
              "who_anon": "IndiaMART seller alle samsarikkunnathu?"},
    "mr-IN": {"me": "Namaskar, mi Disha boltey IndiaMART madhun.", "who": "{company} shi bolat aahe ka?",
              "who_anon": "Aapan IndiaMART seller bolat aahat ka?"},
    "od-IN": {"me": "Namaskar, mu Disha kahuchhi IndiaMART ru.", "who": "{company} sahita katha heuchhi ki?",
              "who_anon": "Aapana IndiaMART seller kahuchhanti ki?"},
    "pa-IN": {"me": "Sat Sri Akal, main Disha bol rahi haan IndiaMART ton.", "who": "{company} naal gall ho rahi hai?",
              "who_anon": "Tusi IndiaMART seller bol rahe ho?"},
    "te-IN": {"me": "Namaskaram, nenu Disha maatladutunnanu IndiaMART nundi.", "who": "{company} tho maatladutunnana?",
              "who_anon": "Meeru IndiaMART seller-aa?"},
}
NEUTRAL_OPENING = "Namaste, main Disha bol rahi hoon IndiaMART se. Aap IndiaMART seller bol rahe hain?"
TEMPLATE_LANGS = tuple(OPENING_PARTS)  # languages with an opening line (the generator picks only hi/ta/en today)
PAID_BUCKETS = ("PIM", "PAM", "PANF", "PNCHF", "OLP")

SWITCH_GUIDANCE = {
    "rush": "The seller is short on time. Drop pleasantries, one short line, offer two concrete slots from the call calendar (for example tomorrow 11 am or 4 pm). Never go silent.",
    "confusion": "The seller is confused. Slow down, use simpler and shorter sentences, one option at a time, say IndiaMART and the reason for the call in one line, confirm understanding.",
    "frustration": "The seller is frustrated. No persuasion. Acknowledge briefly and respectfully, offer one easy next step; if it continues, thank and close.",
    "interest": "The seller is interested. Acknowledge in a few words and move straight to fixing the slot; do not re-explain benefits.",
    "language": "The seller switched language. Reply in the language of the seller's latest turn, and switch back if they do; do not repeat the purpose or re-pitch.",
    "bot_question": "The seller asked if this is a bot. Answer honestly in one line that this is IndiaMART's AI assistant and the reason for the call, then continue.",
}
SignalName = Literal["rush", "confusion", "frustration", "interest", "language", "bot_question"]

# Language targets: SDK display names, codes and common aliases -> SDK enum value.
LANG_ALIASES = {
    "english": "English", "en": "English", "en-in": "English", "angrezi": "English",
    "hindi": "Hindi", "hi": "Hindi", "hi-in": "Hindi", "hinglish": "Hindi",
    "gujarati": "Gujarati", "gu": "Gujarati", "gu-in": "Gujarati",
    "tamil": "Tamil", "ta": "Tamil", "ta-in": "Tamil",
    "marathi": "Marathi", "mr": "Marathi", "mr-in": "Marathi",
    "bengali": "Bengali", "bangla": "Bengali", "bn": "Bengali", "bn-in": "Bengali",
    "kannada": "Kannada", "kn": "Kannada", "kn-in": "Kannada",
    "malayalam": "Malayalam", "ml": "Malayalam", "ml-in": "Malayalam",
    "telugu": "Telugu", "te": "Telugu", "te-in": "Telugu",
    "punjabi": "Punjabi", "pa": "Punjabi", "pa-in": "Punjabi",
    "odia": "Odia", "oriya": "Odia", "od": "Odia", "or": "Odia", "od-in": "Odia", "or-in": "Odia",
    "assamese": "Assamese", "as-in": "Assamese", "konkani": "Konkani", "kok-in": "Konkani",
}


# ---- helpers -----------------------------------------------------------------------------------------------------
def _set(context, name, value):
    """Set an agent variable if the agent declares it; never fail the call over a missing variable."""
    try:
        context.set_agent_variable(name, value)
    except ValueError as e:
        print(f"[disha] skip variable {name}: {e}")


def _get(context, name, default=None):
    try:
        v = context.get_agent_variable(name)
    except ValueError:
        return default
    return default if v in (None, "") else v


def _internal(context, name, default):
    """Internal variable, or the default when it is missing or None."""
    try:
        v = context.get_internal_variable(name)
    except ValueError:
        return default
    return default if v is None else v


def _finite(x, lo=None, hi=None):
    """A finite real number (not a bool) within [lo, hi], else None."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    if not math.isfinite(x) or (lo is not None and x < lo) or (hi is not None and x > hi):
        return None
    return x


def _text(x):
    """A non-empty string, else None (NaN, None, numbers, lists and 'nan'/'null' placeholders count as missing)."""
    if not isinstance(x, str):
        return None
    s = x.strip()
    return None if not s or s.lower() in ("nan", "none", "null", "undefined") else s


def _scrub(x):
    """Recursively replace non-finite floats with None so strict JSON never fails."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {str(k): _scrub(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_scrub(v) for v in x]
    return x


def _dumps(obj) -> str:
    """Strict JSON (no NaN/Infinity) for every artifact, with a scrubbed fallback."""
    try:
        return json.dumps(obj, ensure_ascii=False, allow_nan=False, default=str)
    except (ValueError, TypeError):
        try:
            return json.dumps(_scrub(obj), ensure_ascii=False, allow_nan=False, default=str)
        except (ValueError, TypeError) as e:
            return json.dumps({"error": f"unserialisable artifact: {type(e).__name__}"})


def _clean_gen(gen: dict) -> dict:
    """The flat seller row with impossible values treated as missing: non-finite numbers, booleans, lists/dicts and
    numeric-looking strings that are NaN/inf all become None; string names/cities must be non-empty."""
    out = {}
    for k, v in gen.items():
        if isinstance(v, bool) or isinstance(v, (list, dict)):
            v = None
        elif isinstance(v, float) and not math.isfinite(v):
            v = None
        elif isinstance(v, str):
            s = v.strip()
            try:
                if not math.isfinite(float(s)):
                    v = None
            except ValueError:
                pass
            if v is not None and _text(v) is None:
                v = None
        out[str(k)] = v
    return out


def _clean_tree(x):
    """Jev state with non-finite numbers made None (Jev then sees 'unknown')."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {str(k): _clean_tree(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean_tree(v) for v in x]
    return x


def parse_profile(raw) -> tuple[dict, dict, dict, dict, list]:
    """seller_profile -> (envelope, gen, jev, rules, issues). Every part is a dict; malformed parts become {} and are
    recorded in issues, never raised."""
    issues = []
    prof = raw
    if isinstance(raw, (str, bytes)):
        try:
            prof = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            prof, issues = {}, ["seller_profile is not valid JSON"]
    if not isinstance(prof, dict):
        issues.append(f"seller_profile is a {type(prof).__name__}, not an object")
        prof = {}
    parts = []
    for key in ("gen", "jev", "rules"):
        v = prof.get(key)
        if v is not None and not isinstance(v, dict):
            issues.append(f"{key} is a {type(v).__name__}, not an object")
        parts.append(v if isinstance(v, dict) else {})
    gen, jstate, rules = _clean_gen(parts[0]), _clean_tree(parts[1]), parts[2]
    if prof and prof.get("v") not in KNOWN_VERSIONS:
        issues.append(f"unknown profile version {prof.get('v')!r} (accepted)")
    uc = rules.get("use_case")
    if uc is not None and not (isinstance(uc, str) and uc in USE_CASES):
        issues.append(f"rules.use_case {uc!r} is not a known use case")
    pol = _text(rules.get("contact_policy"))
    rules = {"use_case": uc if isinstance(uc, str) and uc in USE_CASES else None,
             "contact_policy": pol.upper() if pol else None,
             "gate_reason": _text(rules.get("gate_reason"))}
    return prof, gen, jstate, rules, issues


def parse_overrides(prof: dict) -> dict:
    """Fixes learned from earlier call reviews (the optional `overrides` block), validated. Only delivery and call
    purpose can be overridden; the contact policy never can."""
    ov = prof.get("overrides") if isinstance(prof, dict) else None
    if not isinstance(ov, dict):
        return {}
    out = {"why": (_text(ov.get("why")) or "an earlier call review")[:200]}
    uc = ov.get("use_case")
    if isinstance(uc, str) and uc in USE_CASES:
        out["use_case"] = uc
    lang = ov.get("start_language")
    if isinstance(lang, str) and lang in TEMPLATE_LANGS:
        out["start_language"] = lang
    d = _finite(ov.get("pace_delta"), -0.2, 0.2)
    if d:
        out["pace_delta"] = round(d, 2)
    if ov.get("simpler") is True:
        out["simpler"] = True
    nb = ov.get("nudge_budget")
    if isinstance(nb, int) and not isinstance(nb, bool) and 0 <= nb <= NUDGE_CAP:
        out["nudge_budget"] = nb
    notes = ov.get("notes") if isinstance(ov.get("notes"), list) else []
    notes = [n[:200] for n in (_text(x) for x in notes) if n][:4]
    if notes:
        out["notes"] = notes
    return out if len(out) > 1 else {}


def profile_contact(prof: dict) -> tuple[str, str]:
    """(seller_name, seller_phone) from the optional `contact` block of the profile, else ("", ""). The PS07 data
    has no contact name or phone, so these are filled only when a source provides them."""
    c = prof.get("contact") if isinstance(prof, dict) else None
    if not isinstance(c, dict):
        return "", ""
    name = (_text(c.get("name")) or "")[:80]
    phone = _text(c.get("phone")) or ""
    phone = phone if re.fullmatch(r"\+?[0-9 ()-]{6,20}", phone) else ""
    return name, phone


def _unknownify(x):
    if isinstance(x, dict):
        return {k: _unknownify(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_unknownify(v) for v in x]
    return "unknown" if x is None else x


def no_data(jev_state: dict) -> bool:
    try:
        return (not jev_state["catalog"]["has_catalog_data"] and not jev_state["buyer_demand_and_response"]["has_engagement_data"]
                and jev_state["indiamart_call_history"]["answered_calls"] == 0)
    except (KeyError, TypeError):
        return True


def jev_questions() -> dict:
    qs = {}
    for k, v in NOULS.items():
        qs[k] = {"type": "noul", **v} if isinstance(v, dict) else {"type": "noul", "instructions": v}
    qs["catalog_need"] = {"type": "score", "instructions": CATALOG_INSTR, "criteria": CATALOG_LEVELS}
    return qs


async def jev_call(api_key: str, state, questions: dict) -> dict:
    async with httpx.AsyncClient(timeout=JEV_TIMEOUT_S) as client:
        r = await client.post(JEV_URL, headers={"Authorization": f"Bearer {api_key}"},
                              json={"model": JEV_MODEL, "state": state, "questions": questions})
        r.raise_for_status()
        return r.json()["answers"]


def parse_jev_answers(ans) -> tuple[dict, float]:
    """Validated (signals, catalog_need): every probability finite in [0, 1], the catalog score finite in [0, 3].
    Raises ValueError on anything else so the caller falls back to the rules."""
    if not isinstance(ans, dict):
        raise ValueError("answers is not an object")
    sig = {}
    for k in NOULS:
        a = ans.get(k)
        v = _finite(a.get("noul"), 0.0, 1.0) if isinstance(a, dict) else None
        if v is None:
            raise ValueError(f"invalid answer for {k}: {a!r}")
        sig[k] = v
    a = ans.get("catalog_need")
    c = _finite(a.get("score"), 0.0, 3.0) if isinstance(a, dict) else None
    if c is None:
        raise ValueError(f"invalid catalog_need: {a!r}")
    return sig, c


def label_from_signals(sig: dict, catalog_need: float) -> str:
    for cat, q in ORDER:
        if (sig.get(q) or 0) >= 0.5:
            return cat
    return "profile_onboarding" if (catalog_need or 0) >= 1.5 else "discovery"


MARGIN = 0.05  # Jev's probabilities move a few points between calls; decisions this close to a cut-off are borderline
EPS = 1e-9     # inclusive margin despite binary floating point (0.55 - 0.5 > 0.05 in floats)


def decide_detail(sig: dict, catalog_need: float, rule_uc) -> dict:
    """Use case from unrounded Jev signals. Every signal within MARGIN of its cut-off (catalog: 3 x MARGIN of 1.5) is
    treated as uncertain and all joint outcomes of the uncertain signals are enumerated (at most 5 dimensions, 3^5
    combinations). If more than one label is plausible the decision is borderline; then the rules' label is used if it
    is one of the plausible labels (rule_used), otherwise Jev's label stands."""
    sig = {q: float(sig.get(q) or 0) for _, q in ORDER}
    c = float(catalog_need or 0)
    jev_uc = label_from_signals(sig, c)
    options = []
    for q in [q for _, q in ORDER] + ["catalog_need"]:
        v, cut, m = (c, 1.5, MARGIN * 3) if q == "catalog_need" else (sig[q], 0.5, MARGIN)
        options.append((q, [v, cut - 0.01, cut + 0.01] if abs(v - cut) <= m + EPS else [v]))
    candidates = set()
    for combo in itertools.product(*(o for _, o in options)):
        vals = dict(zip((q for q, _ in options), combo))
        candidates.add(label_from_signals({q: vals[q] for _, q in ORDER}, vals["catalog_need"]))
    borderline = len(candidates) > 1
    rule_used = borderline and rule_uc in candidates
    return {"use_case": rule_uc if rule_used else jev_uc, "borderline": borderline, "rule_used": rule_used,
            "jev_label": jev_uc, "candidates": sorted(candidates)}


def decide(sig: dict, catalog_need: float, rule_uc) -> tuple[str, bool]:
    """(use_case, borderline); see decide_detail."""
    d = decide_detail(sig, catalog_need, rule_uc)
    return d["use_case"], d["borderline"]


# ---- calendar (Asia/Kolkata) -------------------------------------------------------------------------------------
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS_HI = ["Somvaar", "Mangalvaar", "Budhvaar", "Guruvaar", "Shukravaar", "Shanivaar", "Ravivaar"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RELATIVE_DAYS = ["aaj / today", "kal / tomorrow", "parson / day after tomorrow", "narson / in 3 days",
                 "4 din baad / in 4 days", "5 din baad / in 5 days", "6 din baad / in 6 days", "agle hafte isi din / in 7 days"]


def _now_ist() -> datetime:
    return datetime.now(IST)


def _day(d) -> str:
    return f"{WEEKDAYS[d.weekday()]} ({WEEKDAYS_HI[d.weekday()]}) {d.day:02d} {MONTHS[d.month - 1]} {d.year}"


def call_calendar(now: Optional[datetime] = None) -> str:
    """Deterministic date table for the call: today plus the next 7 days in Asia/Kolkata (UTC+5:30)."""
    now = now or _now_ist()
    now = now.astimezone(IST) if now.tzinfo else now.replace(tzinfo=IST)
    days = [now.date() + timedelta(days=i) for i in range(8)]
    sunday = next(d for d in days if d.weekday() == 6)
    return (f"Now: {_day(days[0])}, {now:%H:%M} IST. "
            + "; ".join(f"{w} = {_day(d)}" for w, d in zip(RELATIVE_DAYS, days)) + ". "
            + f"Sunday falls on {_day(sunday)}; if a requested day is a Sunday or otherwise not possible, say so and "
              "ask for another day; never move a date silently.")


# ---- persona spec -> Disha inputs --------------------------------------------------------------------------------
PACE_MIN, PACE_MAX = 0.85, 2.0  # runtime clamp documented by the SDK
PERSONA_STYLE = {
    "brisk": "brief_direct", "repair": "patient_gentle", "consultative": "warm_formal",
    "warm_engaged": "friendly_casual", "friendly_default": "friendly_casual",
}
STYLE_TONE = {"patient_gentle": "warmth high, empathy high, energy calm"}
SPOKEN_FIXES = (("15 minute ki meeting", "ek chhoti si meeting"), ("15 nimisha meeting", "chinna meeting"),
                ("a 15-minute meeting", "a short meeting"),
                # name before company, as in Paayal's intro (generator templates say "IndiaMART se Vani")
                ("IndiaMART se Vani bol rahi hoon", "main Disha, IndiaMART se bol rahi hoon"),
                ("IndiaMART se Vani", "main Disha, IndiaMART se bol rahi hoon"),
                ("IndiaMART-la irundhu Vani pesuren", "naan Disha, IndiaMART-la irundhu pesuren"),
                ("IndiaMART-la irundhu Vani", "naan Disha, IndiaMART-la irundhu pesuren"),
                ("Vani", "Disha"), (" — ", ", "), ("—", ", "))


def _get_path(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def profile_facts(gen: dict, jstate: dict) -> dict:
    """What the profile actually shows, so openings and notes only assert observed facts."""
    disp = gen.get("past_dispositions_detailed") or ""
    callback = ((_finite(gen.get("calls_call_later")) or 0) > 0 or "callback_requested" in str(disp)
                or (_finite(_get_path(jstate, "indiamart_call_history", "outcome_counts", "Call Later / Busy")) or 0) > 0)
    bd = _get_path(jstate, "buyer_demand_and_response") or {}
    enq_keys = ("buyer_enquiries_received_last_90_days", "buyer_enquiries_received_last_year",
                "phone_enquiries_received_last_90_days", "phone_enquiries_received_last_year")
    enquiries = (any((_finite(bd.get(k)) or 0) > 0 for k in enq_keys) if isinstance(bd, dict) else False) \
        or (_finite(gen.get("eng_enq_received_90d")) or 0) > 0
    why = _get_path(jstate, "indiamart_call_history", "why_indiamart_called_most_recent_first")
    why_txt = " ".join(w for w in why if isinstance(w, str)).lower() if isinstance(why, list) else ""
    paid = (_text(gen.get("ctx_last_bucket")) or "") in PAID_BUCKETS or any(
        w in why_txt for w in ("paid", "package", "buylead", "buy-lead", "buy lead"))
    return {"callback_requested": bool(callback), "enquiries_received": bool(enquiries), "paid_interest": bool(paid)}


EVIDENCE_HOOK_FACT = {"warm_followup": "callback_requested", "lead_engagement": "enquiries_received",
                      "free_to_paid": "paid_interest"}


def seller_history(spec, jstate=None, facts=None) -> tuple[str, str]:
    """seller_history enum, latest outcome first, then the lifetime counts. Never 'interested' after a refusal."""
    h = _get_path(spec, "seller_snapshot", "history") or {}
    flags = " ".join(x for x in (h.get("flags") or []) if isinstance(x, str))
    if "do_not_call" in flags:
        return "previously_declined", "seller asked not to be called on a past call"
    last = _text(_get_path(jstate, "indiamart_call_history", "last_call_outcome"))
    if last == "Not Interested":
        return "previously_declined", "the latest call outcome was Not Interested"
    if last == "Meeting Fixed":
        return "previously_contacted_interested", "the latest call outcome was Meeting Fixed"
    if last == "Call Later / Busy":
        return "callback_pending", "the latest call outcome was Call Later / Busy"
    if h.get("meetings"):
        return "previously_contacted_interested", f"agreed to a meeting on {h['meetings']} past call(s)"
    if h.get("call_later") or (facts or {}).get("callback_requested"):
        return "callback_pending", "asked to be called later on a past call"
    if h.get("not_interested"):
        return "previously_declined", f"said not interested on {h['not_interested']} past call(s)"
    return "new_seller", "no past interest, callback or refusal on record"


spec_history = seller_history  # old name


def _lines(items, fmt):
    return "\n".join(f"- {fmt(x)}" for x in items if isinstance(x, dict)) or "- (none)"


def _fix(line: str) -> str:
    for a, b in SPOKEN_FIXES:
        line = line.replace(a, b)
    return line


def uc_hook(use_case: str, lang: str, facts: dict) -> tuple[str, bool]:
    hooks = OPENING_HOOKS.get(lang, OPENING_HOOKS["hi-IN"])[use_case]
    fact = EVIDENCE_HOOK_FACT.get(use_case)
    if fact and facts.get(fact) and "evidence" in hooks:
        return hooks["evidence"], True
    return hooks["default"], False


def short_opening(company, lang: str = "hi-IN") -> str:
    p = OPENING_PARTS.get(lang, OPENING_PARTS["hi-IN"])
    return f"{p['me']} {p['who'].format(company=company) if company else p['who_anon']}"


def choose_opening(spec, company, use_case, lang="hi-IN", facts=None, policy_block=False) -> tuple[str, str, str]:
    """(line, why, kind). The spoken opening is always one short identity line. `why` carries what Phase 1 and 2
    should do next: the purpose line (only facts on record), and the generator's opening approach (apology for repeat
    calls, referencing a requested callback, AI identity if asked earlier)."""
    facts = facts or {}
    line = short_opening(company, lang)
    if policy_block:
        return line, "contact policy blocks a pitch: identity check only, then apologise and close", "contact_policy"
    op = _get_path(spec, "plan", "opening") or {}
    approach = op.get("approach") if isinstance(op.get("approach"), str) else ""
    hook, _ = uc_hook(use_case, lang, facts)
    notes = []
    if approach.startswith("Apologise for repeat calls"):
        notes.append("in the first reply, a short apology for the earlier calls before anything else")
    if approach.startswith("Reference their earlier callback") and facts.get("callback_requested"):
        notes.append("if it fits naturally, one short phrase that the seller had asked to talk later; drop it at once if the "
                     "seller says they never asked, and never insist")
    if approach.startswith("Disclose AI identity"):
        notes.append("the seller asked about a bot before: if asked again, answer honestly at once")
    why = (f"short identity opening; purpose line for Phase 2: {hook}"
           + ("; " + "; ".join(notes) if notes else "") + f" (generator approach: {approach or 'n/a'})")
    return line, why, "short"


def disha_notes(spec, use_case, uc, reason, conf, opening_why, delivery, lang_info, facts, history, policy) -> str:
    """Everything Disha needs for this seller as compact text for {{persona_notes}}: only final, applied values, each
    choice with its reason and confidence. Sections follow the call phases so the prompt can apply them in order."""
    parts = []
    pol, gate = policy
    if pol in ("SUPPRESS", "ROUTE_TO_HUMAN"):
        parts.append(f"Contact policy: {pol} ({gate or 'no reason given'}). Do not pitch. " + (
            "This seller asked not to be called: confirm identity, say in one line the call was placed by mistake and "
            "they will not be called again, say sorry, and close. Never say you called to apologise."
            if pol == "SUPPRESS" else
            "A person should handle this seller: confirm identity, say an IndiaMART executive will contact them "
            "personally, thank them, and close."))
    elif str(pol or "").startswith("COOL_OFF"):
        parts.append("Contact policy: COOL_OFF; keep it to one soft ask.")
    parts += [f"Call purpose: {use_case}. Goal: {uc['goal']}",
              f"Purpose approach: {uc['approach']}",
              f"Why this purpose: {reason} [confidence {conf}]"]
    parts.append(f"Delivery: style {delivery['style']}, pace {delivery['pace']} (the voice itself is fixed on the "
                 f"platform). Why: {delivery['why']} [confidence {delivery['confidence']}]")
    parts.append(lang_info["note"])
    fact_txt = ", ".join(k.replace("_", " ") for k, v in facts.items() if v) or "none"
    parts.append(f"Facts on record you may mention: {fact_txt}. Do not state anything else about the seller's "
                 "enquiries, interest or past requests as fact; ask instead.")
    if pol in ("SUPPRESS", "ROUTE_TO_HUMAN"):
        return "\n".join(parts)
    if not spec:
        parts.append("No seller data for a persona: base persona, live adaptation leads.")
        return "\n".join(parts)
    tone, plan = (spec.get(k) or {} for k in ("tone", "plan"))
    max_sent = 3 if (_finite(plan.get("target_call_sec")) or 60) >= 80 else 2
    label = (spec.get("delivery_profile") or {}).get("label", "")
    tone_txt = STYLE_TONE.get(delivery["style"]) if delivery["adjusted"] and delivery["style"] in STYLE_TONE else None
    parts += [
        f"Profile: {label}" + (" (adjusted for call purpose)" if delivery["adjusted"] else ""),
        (f"Tone: {tone_txt} (set by the call purpose)." if tone_txt else
         f"Tone: warmth {tone.get('warmth')}, empathy {tone.get('empathy')}, energy {tone.get('energy')}. "
         f"Why: {tone.get('reason', '')} [confidence {tone.get('confidence', 'low')}]"),
        f"Turn length: at most {max_sent} short sentences; aim to finish in about {plan.get('target_call_sec', 60)} seconds.",
        f"Opening: {opening_why} [confidence {(plan.get('opening') or {}).get('confidence', 'low')}]",
        f"Seller history: {history[0]} ({history[1]}).",
        "Personalisation hooks:\n" + _lines(plan.get("personalisation") or [], lambda h: h.get("hook", "")),
        "Objection playbook:\n" + _lines(plan.get("objection_playbook") or [],
                                         lambda o: f"If {o.get('objection')}: {o.get('approach')} "
                                                   f"(evidence {o.get('evidence') or 'none'})"),
        "Escalation rules:\n" + _lines(plan.get("escalation_rules") or [], lambda e: f"If {e.get('trigger')}: {e.get('action')}"),
    ]
    missing = (spec.get("seller_snapshot") or {}).get("missing_fields") or []
    if missing:
        parts.append(f"Missing seller data (lower confidence): {', '.join(map(str, missing))}")
    return "\n".join(parts)


# How the call purpose adjusts the seller's persona: (pace change, style override or None, reason with evidence).
USE_CASE_DELIVERY = {
    "reactivation": (-0.15, "patient_gentle", "checking on a quiet business: slower and softer; past 'not using / "
                     "closed' calls converted at 4% with 57% not interested, so the aim is information, not a sale"),
    "lead_engagement": (-0.05, None, "sellers sceptical about lead quality are the most talkative and frustrated "
                        "(14% frustration): listen more, slightly slower"),
    "free_to_paid": (0.05, None, "free to paid sellers hang up fastest (25.6% early drop on the Sept holdout): a "
                     "little quicker"),
}


# Nudges allowed after a seller refuses, per call purpose. From 12,354 past calls with transcripts (1,221 with a
# refusal; outputs/segmentation/N01_nudges.csv): share of nudges that led to a booking with no further refusal.
NUDGE_BY_USE_CASE = {
    "warm_followup": (2, "warm follow-up: 1st nudge booked 25.5% of refusers (n=204), 2nd 5.1% (n=39), no irritation"),
    "free_to_paid": (2, "free to paid: 1st nudge 5.5% (n=488), 2nd 4.5% (n=111), irritation under 3%"),
    "profile_onboarding": (1, "profile onboarding: 1st nudge 5.0% (n=140); after a 2nd, hang-ups rose to 37%"),
    "discovery": (1, "discovery: 1st nudge 2.0% (n=50), 2nd 0% (n=12)"),
    "lead_engagement": (0, "lead engagement: nudges booked 0% (1st n=84, 2nd n=19) and irritation reached 10.5%; "
                           "answer the lead-quality concern instead of pushing"),
    "reactivation": (0, "reactivation: 1st nudge booked 0% (n=100); this call gathers information, not a sale"),
}
NUDGE_CAP = 2  # a 3rd nudge never proved itself in the data (best cases n=13 and n=27)


def nudge_budget(use_case, policy, history, profile_id, learned=None) -> tuple[int, str]:
    """(budget, why): nudges allowed after a refusal in this call. The lowest applicable limit wins."""
    budget, why = NUDGE_BY_USE_CASE.get(use_case, (1, "unknown purpose: one nudge"))
    limits = [(budget, why)]
    if policy in ("SUPPRESS", "ROUTE_TO_HUMAN"):
        limits.append((0, f"contact policy {policy}: no pitch at all"))
    elif str(policy or "").startswith("COOL_OFF"):
        limits.append((1, "contact policy COOL_OFF: one soft ask (2nd nudge booked 0%, n=43)"))
    if history == "previously_declined":
        limits.append((1, "declined before: 1st nudge 3.6% (n=416) vs 11.1% for sellers with no refusal history"))
    if profile_id == "repair":
        limits.append((0, "frustrated on earlier calls: accept the first refusal"))
    if isinstance(learned, int) and not isinstance(learned, bool) and 0 <= learned <= NUDGE_CAP:
        limits.append((learned, "lowered by an earlier call review: pushing irritated this seller"))
    b, w = min(limits, key=lambda x: x[0])
    return min(b, NUDGE_CAP), w


def final_delivery(spec, use_case) -> dict:
    """Final applied style and pace (generator persona + call-purpose adjustment) with one combined reason."""
    uc = USE_CASES[use_case]
    profile_id = _get_path(spec, "delivery_profile", "id")
    voice = (spec or {}).get("voice") or {}
    style = PERSONA_STYLE.get(profile_id, uc["style"])
    base_pace = _finite(voice.get("pace"), PACE_MIN, PACE_MAX) if spec else None
    d_pace, d_style, d_why = USE_CASE_DELIVERY.get(use_case, (0.0, None, ""))
    adjusted = bool(spec and d_why)
    if spec and d_style and profile_id != "repair":  # a repair persona (past frustration) keeps its own style
        style = d_style
    pace = round(min(PACE_MAX, max(PACE_MIN, (base_pace if base_pace is not None else uc["pace"])
                                   + (d_pace if adjusted else 0.0))), 2)
    v_reason = voice.get("reason", "") if isinstance(voice.get("reason"), str) else ""
    gen_why = v_reason[v_reason.find("Pace"):] if "Pace" in v_reason else v_reason
    if spec:
        why = f"persona {profile_id}: {gen_why or 'generator default'}"
        if adjusted:
            why += f"; call purpose {use_case} adjusts pace by {d_pace:+.2f}" + (
                f" and style to {style}" if d_style and style == d_style else "") + f" because {d_why}"
    else:
        why = f"no seller persona; {use_case} default delivery"
    return {"style": style, "pace": pace, "why": why, "adjusted": adjusted,
            "confidence": voice.get("confidence", "low") if spec else "low", "profile_id": profile_id}


def start_language(spec) -> dict:
    """Start language: only one the generator has an opening template for (hi/ta/en); otherwise Hindi, ready to
    switch to the regional language."""
    lang = (spec or {}).get("language") or {}
    code = lang.get("language_code") if isinstance(lang.get("language_code"), str) else "hi-IN"
    switch = [c for c in (lang.get("switch_ready") or []) if isinstance(c, str)]
    why = lang.get("reason", "") if isinstance(lang.get("reason"), str) else ""
    if code not in TEMPLATE_LANGS:
        switch = [code] + [c for c in switch if c != code]
        why = (f"{why} No reviewed {LANG_NAME.get(code, code)} opening exists, so the call starts in Hindi and is "
               f"ready to switch to {LANG_NAME.get(code, code)}.").strip()
        code = "hi-IN"
    switch = [c for c in switch if c != code]
    name = LANG_NAME.get(code, "Hindi")
    mix = _finite(lang.get("english_mix"), 0.0, 1.0)
    note = (f"Language: start in {name}, about {int(round((mix if mix is not None else 0.3) * 100))} percent English "
            f"business words, {lang.get('formality', 'formal') if isinstance(lang.get('formality'), str) else 'formal'} "
            f"register; ready to switch to {', '.join(LANG_NAME.get(c, c) for c in switch) or 'English'}. "
            f"Why: {why or 'default'} [confidence {lang.get('confidence', 'low') if spec else 'low'}]")
    return {"code": code, "name": name, "switch_ready": switch, "note": note}


def _apply_safe_defaults(context, t0):
    """Neutral opening, Hindi and default pace before anything optional can fail."""
    context.set_internal_variable("t0", t0)
    context.set_internal_variable("switches", [])
    context.set_internal_variable("use_case", "discovery")
    _set(context, "nudge_budget", "1")
    context.set_initial_bot_message(NEUTRAL_OPENING)
    context.set_initial_language_name(SarvamToolLanguageName.HINDI)
    context.text_to_speech_config = TextToSpeechConfig(speech_settings=SpeechSettings(pace=DEFAULT_PACE))


def _base_persona(context, why: str):
    """Last-resort persona: discovery, no seller data reused."""
    uc = USE_CASES["discovery"]
    notes = (f"Call purpose: discovery. Goal: {uc['goal']}\nPurpose approach: {uc['approach']}\n"
             f"Why this purpose: {why} [confidence low]\nDelivery: style {uc['style']}, pace {DEFAULT_PACE} (the voice "
             "itself is fixed on the platform). Why: base persona [confidence low]\n"
             "No seller data for a persona: base persona, live adaptation leads.")
    for name, value in [("use_case", "discovery"), ("use_case_confidence", "low"), ("use_case_reason", why),
                        ("persona_style", uc["style"]), ("seller_history", "new_seller"), ("persona_notes", notes),
                        ("jev_signals", _dumps({"source": "fallback", "error": why}))]:
        _set(context, name, value)


# ---- tools -------------------------------------------------------------------------------------------------------
class OnStart(SarvamOnStartTool):
    async def run(self, context: SarvamOnStartToolContext) -> SarvamOnStartToolContext:
        t0 = time.time()
        try:
            _apply_safe_defaults(context, t0)
        except Exception as e:
            print(f"[disha] safe defaults failed: {type(e).__name__}: {e}")
        calendar = ""
        try:
            calendar = call_calendar(_now_ist())
            _set(context, "call_calendar", calendar)
        except Exception as e:
            print(f"[disha] calendar failed: {type(e).__name__}: {e}")
        try:
            await self._personalise(context, t0, calendar)
        except Exception as e:  # never fail the call: base persona, invalid data not reused
            print(f"[disha] OnStart fell back to the base persona: {type(e).__name__}: {e}")
            try:
                _apply_safe_defaults(context, t0)
                _base_persona(context, f"Persona setup failed ({type(e).__name__}); base persona used.")
            except Exception as e2:
                print(f"[disha] base persona failed: {type(e2).__name__}: {e2}")
        return context

    async def _personalise(self, context, t0, calendar):
        prof, gen, jstate, rules, issues = parse_profile(_get(context, "seller_profile", ""))
        rule_uc, policy, gate = rules["use_case"], rules["contact_policy"], rules["gate_reason"]
        policy_block = policy in ("SUPPRESS", "ROUTE_TO_HUMAN")
        if issues:
            print(f"[disha] profile issues: {issues}")

        # 1. Call purpose: contact policy first, then Jev signals cross-checked with the rules
        signals, catalog_need, source, detail = {}, None, "none", None
        if policy_block:
            use_case, conf, source = "discovery", "high", "contact_policy"
            reason = f"Contact policy {policy} ({gate or 'no reason given'}): no pitch on this call."
        elif not gen and not jstate:
            use_case, conf, reason = "discovery", "low", "No usable seller profile was provided; base persona used."
        elif no_data(jstate):
            use_case, conf, reason = "discovery", "medium", "No engagement, catalog or call history on record."
            source = "code"
        else:
            try:
                state = _unknownify(jstate)
                state["reference_typical_seller"] = REFERENCE
                ans = await asyncio.wait_for(jev_call(context.get_secret("TYPESAFE_API_KEY"), state, jev_questions()),
                                             JEV_DEADLINE_S)
                signals, catalog_need = parse_jev_answers(ans)
                detail = decide_detail(signals, catalog_need, rule_uc)
                use_case = detail["use_case"]
                source = "jev_borderline" if detail["borderline"] else "jev"
            except Exception as e:  # Jev down, slow or invalid: fall back to the rules label
                print(f"[disha] Jev failed after {time.time() - t0:.2f}s: {type(e).__name__}: {e}")
                signals, catalog_need, detail = {}, None, None
                use_case, source = (rule_uc or "discovery"), "rules_fallback"
            agree = rule_uc == use_case
            conf = ("high" if source == "jev" and agree else "medium" if source in ("jev", "jev_borderline") else "low")
            top = sorted(signals.items(), key=lambda kv: -kv[1])[:3]
            sig_txt = ", ".join(f"{SIGNAL_WORDS[k]} {v:.2f}" for k, v in top)
            reason = (f"Jev signals: {sig_txt}; catalog need {catalog_need:.2f} of 3. " if signals
                      else "Jev unavailable; the rules label is used. ") + \
                     f"Rules say {rule_uc or 'n/a'} ({'agree' if agree else 'differ'})."
            if detail and detail["borderline"]:
                reason += (f" Jev was borderline (plausible: {', '.join(detail['candidates'])}), so the rules decided."
                           if detail["rule_used"] else
                           f" Jev was borderline (plausible: {', '.join(detail['candidates'])}) and the rules' label "
                           f"was not among them, so Jev's label {detail['jev_label']} stands.")
        if str(policy or "").startswith("COOL_OFF"):
            reason += " Contact policy COOL_OFF: one soft ask only."
        # fixes learned from this seller's earlier calls (never the contact policy)
        ov, ov_applied = parse_overrides(prof), []
        if ov.get("use_case") and not policy_block and ov["use_case"] != use_case:
            ov_applied.append(f"use case {use_case} -> {ov['use_case']}")
            reason = f"Last call review: {ov['why']}. Before the review this was {use_case}: {reason}"
            use_case, conf, source = ov["use_case"], "high", "last_call_review"
        uc = USE_CASES[use_case]

        # 2. Persona and conversation plan for this seller: the persona generator (generator/generate.py)
        spec = None
        if gen:
            try:
                spec = generate_persona(gen)
                json.dumps(spec, allow_nan=False, default=str)  # reject non-finite values in the spec
            except Exception as e:  # never fail the call over the persona; the use-case template still applies
                print(f"[disha] persona generator failed: {type(e).__name__}: {e}")
                spec = None
        snap = (spec or {}).get("seller_snapshot") or {}
        company = _text(snap.get("company")) or _text(_get(context, "company_name"))
        city = _text(snap.get("city")) or _text(_get(context, "city"))
        facts = profile_facts(gen, jstate)
        lang = start_language(spec)
        if ov.get("start_language") and ov["start_language"] != lang["code"]:
            code = ov["start_language"]
            ov_applied.append(f"start language {lang['name']} -> {LANG_NAME.get(code, code)}")
            lang = {"code": code, "name": LANG_NAME.get(code, code), "switch_ready": [lang["code"]],
                    "note": f"Language: start in {LANG_NAME.get(code, code)} (learned from the last call: {ov['why']}); "
                            f"switch back to {lang['name']} if the seller uses it."}
        line, opening_why, opening_kind = choose_opening(spec, company, use_case, lang["code"], facts, policy_block)
        history = seller_history(spec, jstate, facts)
        delivery = final_delivery(spec, use_case)
        if ov.get("pace_delta"):
            new = round(min(PACE_MAX, max(PACE_MIN, delivery["pace"] + ov["pace_delta"])), 2)
            ov_applied.append(f"pace {delivery['pace']} -> {new}")
            delivery = dict(delivery, pace=new, why=f"{delivery['why']}; last call review {ov['pace_delta']:+.2f}")
        notes = disha_notes(spec, use_case, uc, reason, conf, opening_why, delivery, lang, facts, history, (policy, gate))
        nudges, nudge_why = nudge_budget(use_case, policy, history[0], delivery.get("profile_id"), ov.get("nudge_budget"))
        if ov.get("nudge_budget") is not None:
            ov_applied.append(f"nudge budget at most {ov['nudge_budget']}")
        notes += (f"\nNudge budget: {nudges} nudge{'s' if nudges != 1 else ''} after a refusal in this call. Why: "
                  f"{nudge_why}.")
        learned = (["Use simple, everyday words and one idea per sentence."] if ov.get("simpler") else []) \
            + ov.get("notes", [])
        if learned and not policy_block:
            ov_applied += ["simpler wording"] if ov.get("simpler") else []
            ov_applied += [f"note: {n}" for n in ov.get("notes", [])]
            notes += "\nLearned from earlier calls with this seller (" + ov["why"] + "):\n" + "\n".join(f"- {n}" for n in learned)
        seller_id = prof.get("seller_id")
        seller_id = str(seller_id) if isinstance(seller_id, (int, str)) and not isinstance(seller_id, bool) \
            else str(_get(context, "seller_id", "") or "")
        persona_spec = {"contract_version": CONTRACT_VERSION, "profile_version": prof.get("v"), "input_issues": issues,
                        "use_case": {"id": use_case, "confidence": conf, "reason": reason, "source": source,
                                     "decision": detail, "goal": uc["goal"], "approach": uc["approach"]},
                        "contact_policy": {"policy": policy, "gate_reason": gate, "blocks_pitch": policy_block},
                        "facts_on_record": facts,
                        "applied": {"opening_line": line, "opening_kind": opening_kind, "opening_why": opening_why,
                                    "persona_style": delivery["style"], "pace": delivery["pace"],
                                    "delivery_why": delivery["why"], "adjusted_for_purpose": delivery["adjusted"],
                                    "seller_history": history[0], "start_language": lang["name"],
                                    "switch_ready": [LANG_NAME.get(c, c) for c in lang["switch_ready"]],
                                    "call_calendar": calendar, "voice": "platform voice (unchanged)",
                                    "learned_overrides": ov_applied,
                                    "nudge_budget": nudges, "nudge_budget_why": nudge_why},
                        "spec": spec}
        jev_signals = {"source": source, "signals": {k: round(v, 2) for k, v in signals.items()},
                       "catalog_need": None if catalog_need is None else round(catalog_need, 2),
                       "decision": detail, "rules_use_case": rule_uc, "contact_policy": policy, "issues": issues}

        # 3. Apply: variables first, then the call settings
        for name, value in [("use_case", use_case), ("use_case_confidence", conf), ("use_case_reason", reason),
                            ("jev_signals", _dumps(jev_signals)), ("persona_style", delivery["style"]),
                            ("seller_history", history[0]), ("persona_notes", notes),
                            ("persona_spec", _dumps(persona_spec)), ("seller_id", seller_id),
                            ("company_name", company or ""), ("city", city or ""),
                            ("nudge_budget", str(nudges))]:
            _set(context, name, value)
        seller_name, seller_phone = profile_contact(prof)
        for name, value in (("seller_name", seller_name), ("seller_phone", seller_phone)):
            if value:  # empty means unknown; the prompt then confirms the business instead
                _set(context, name, value)
        context.set_initial_bot_message(line)
        try:
            context.set_initial_language_name(SarvamToolLanguageName(lang["name"]))
        except ValueError:
            context.set_initial_language_name(SarvamToolLanguageName.HINDI)
        context.text_to_speech_config = TextToSpeechConfig(speech_settings=SpeechSettings(pace=delivery["pace"]))
        context.set_internal_variable("use_case", use_case)
        context.set_internal_variable("call1", {
            "use_case": use_case, "use_case_confidence": conf, "use_case_reason": reason[:400], "source": source,
            "persona_style": delivery["style"], "pace": delivery["pace"], "start_language": lang["name"],
            "opening_line": line, "contact_policy": policy, "learned_overrides": ov_applied,
            "nudge_budget": nudges})
        print(f"[disha] OnStart {use_case} ({conf}, {source}) profile={delivery['profile_id']} pace={delivery['pace']} "
              f"{lang['name']} in {time.time() - t0:.2f}s")


def _lang_enum(text) -> Optional[SarvamToolLanguageName]:
    """SDK language for a display name, code (en-IN) or alias (english, oriya ...), else None."""
    s = _text(text)
    if not s:
        return None
    s = s.lower().replace("_", "-")
    name = LANG_ALIASES.get(s) or LANG_ALIASES.get(s.split()[0])
    try:
        return SarvamToolLanguageName(name) if name else None
    except ValueError:
        return None


def _switch_list(context) -> list:
    v = _internal(context, "switches", [])
    return [s for s in v if isinstance(s, dict)] if isinstance(v, list) else []


def _lang_name(lang) -> str:
    """Display name of a language enum (plain type check, no dynamic attribute access)."""
    return lang.value if isinstance(lang, SarvamToolLanguageName) else str(lang)


class PersonaSwitch(SarvamTool):
    """Call this silently the moment the seller shows rush, confusion, frustration, interest, a language switch, or asks
    whether they are talking to a bot. For a language switch pass new_language: this tool switches the speaking language
    itself, so no other tool is needed. It records the switch and returns how to change delivery. If it says the
    language could not be applied, keep the current language. Never mention it."""

    signal: SignalName = Field(description="Which signal the seller just showed")
    seller_words: str = Field(description="The seller's exact words that showed the signal")
    change: str = Field(description="The delivery change being made, in a few words")
    reason: str = Field(description="Why this delivery change suits the signal, in one short sentence")
    new_language: Optional[str] = Field(default=None, description="For signal 'language' (or any signal that comes with "
                                        "a language change): the language to switch to, e.g. English, Hindi, Gujarati, "
                                        "Marathi, Tamil, Bengali, Kannada, Malayalam, Telugu, Punjabi, Odia, or a code "
                                        "such as en-IN")

    async def run(self, context: SarvamToolContext) -> SarvamToolOutput:
        guidance = SWITCH_GUIDANCE.get(self.signal, "")
        try:
            guidance = self._record(context, guidance)
        except Exception as e:  # never break the conversation over the log
            print(f"[disha] persona_switch logging failed: {type(e).__name__}: {e}")
        return SarvamToolOutput(message_to_llm=guidance + " Reply now in the new style; do not mention this.",
                                context=context)

    def _record(self, context, guidance: str) -> str:
        t0 = _finite(_internal(context, "t0", None))
        before = context.get_current_language()
        before_name = _lang_name(before)
        requested = _text(self.new_language)
        wants_language = self.signal == "language" or requested is not None
        applied, status = False, "logged"
        if wants_language:
            target = _lang_enum(requested)
            allowed = list(context.allowed_languages or [])
            allowed_txt = ", ".join(_lang_name(l) for l in allowed) or before_name
            if target is None:
                status = "no_target"
                guidance = (f"The language could not be switched: {'no target language was given' if not requested else repr(requested) + ' is not a known language'}. "
                            f"Keep speaking {before_name}. Available languages: {allowed_txt}.")
            elif target == before:
                status = "logged"
                guidance = f"The speaking language is already {target.value}; continue in {target.value}."
            elif target not in allowed:
                status = "language_not_allowed"
                guidance = (f"The language could not be switched to {target.value}: it is not enabled for this call. "
                            f"Keep speaking {before_name}. Politely tell the seller you can continue in {allowed_txt}.")
            else:
                try:
                    context.change_language(target)
                    applied, status = True, "applied"
                    guidance = (f"Speaking language is now {target.value}. Continue in {target.value} from where the "
                                "call was; do not repeat the purpose or re-pitch.")
                    if self.signal != "language":
                        guidance += " " + SWITCH_GUIDANCE.get(self.signal, "")
                except ValueError as e:
                    status = "language_not_allowed"
                    guidance = (f"The language could not be switched to {target.value} ({e}). Keep speaking "
                                f"{before_name}. Politely tell the seller you can continue in {allowed_txt}.")
        if wants_language and self.signal != "language" and status != "applied":
            guidance = SWITCH_GUIDANCE.get(self.signal, "") + " " + guidance
        after = context.get_current_language()
        switches = _switch_list(context)
        entry = {"t_sec": round(time.time() - t0, 1) if t0 is not None else None,
                 "turn_hint": len(switches) + 1, "signal": self.signal,
                 "seller_words": (self.seller_words or "")[:200], "change": (self.change or "")[:200],
                 "reason": (self.reason or "")[:200], "language_before": before_name,
                 "language_after": _lang_name(after), "requested_language": requested,
                 "applied": applied, "status": status}
        if len(switches) < MAX_SWITCHES or applied:  # a real language transition is always kept
            switches.append(entry)
        context.set_internal_variable("switches", switches)
        return guidance


def _duration(start, end) -> tuple[Optional[float], Optional[str]]:
    """Call duration in seconds, or (None, why) when the timestamps cannot be compared."""
    try:
        if (start.tzinfo is None) != (end.tzinfo is None):
            return None, "naive and timezone-aware timestamps cannot be compared"
        if start.tzinfo is not None:
            start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        d = (end - start).total_seconds()
        return (round(d, 1), None) if d >= 0 else (None, "end time before start time")
    except Exception as e:
        return None, f"{type(e).__name__}"


def _match_turn(words: str, turns: list) -> Optional[int]:
    """Index of the seller turn that best matches the quoted words, or None if nothing matches well."""
    w = (words or "").lower().strip()
    if not w:
        return None
    best, best_i = 0.0, None
    wt = set(w.split())
    for t in turns:
        if t["role"] != "seller":
            continue
        txt = t["text"].lower()
        score = max(difflib.SequenceMatcher(None, w, txt).ratio(),
                    len(wt & set(txt.split())) / max(len(wt), 1))
        if score > best:
            best, best_i = score, t["i"]
    return best_i if best >= 0.35 else None


VERIFY_SIGNAL_Q = ("In the transcript window of switch {i}, did the seller turn marked anchor (or, if none is marked, "
                   "any seller turn) actually show the signal '{signal}'?")
VERIFY_APPLIED_Q = ("In the transcript window of switch {i}, did the first agent turn after the anchor apply the stated "
                    "delivery change ('{change}')?")


def switch_questions(switches: list, turns: list) -> tuple[list, dict]:
    """Jev state items and questions for checking each logged switch against its transcript window."""
    items, qs = [], {}
    for i, s in enumerate(switches):
        anchor = _match_turn(s.get("seller_words", ""), turns)
        if anchor is None:
            window, s["anchor_turn"], s["anchor_method"] = turns[-40:], None, "whole_transcript"
        else:
            window = [dict(t, anchor=True) if t["i"] == anchor else t for t in turns[max(0, anchor - 2):anchor + 4]]
            s["anchor_turn"], s["anchor_method"] = anchor, "fuzzy_match"
        items.append({"switch": i, "signal": s.get("signal"), "seller_words": s.get("seller_words"),
                      "change": s.get("change"), "reason": s.get("reason"), "window": window})
        qs[f"s{i}_signal"] = {"type": "noul", "instructions": VERIFY_SIGNAL_Q.format(i=i, signal=s.get("signal"))}
        qs[f"s{i}_applied"] = {"type": "noul", "instructions": VERIFY_APPLIED_Q.format(i=i, change=s.get("change"))}
    return items, qs


def apply_switch_answers(switches: list, ans) -> None:
    """Fills verified_signal / verified_applied / verification_status on each switch, in place."""
    for i, s in enumerate(switches):
        a = ans.get(f"s{i}_signal") if isinstance(ans, dict) else None
        b = ans.get(f"s{i}_applied") if isinstance(ans, dict) else None
        vs = _finite(a.get("noul"), 0.0, 1.0) if isinstance(a, dict) else None
        va = _finite(b.get("noul"), 0.0, 1.0) if isinstance(b, dict) else None
        if vs is None or va is None:
            s["verification_status"] = "invalid_response"
        else:
            s.update(verified_signal=round(vs, 2), verified_applied=round(va, 2), verification_status="verified")


async def verify_switches(api_key: str, switches: list, turns: list) -> None:
    """Switch check on its own (used when the call is too short to review)."""
    items, qs = switch_questions(switches, turns)
    apply_switch_answers(switches, await jev_call(api_key, {"switches": items}, qs))


# ---- call review: did Call 1 (OnStart) pick the right purpose and persona? -------------------------------------
# Asked in the same Jev request as the switch check. Fixes marked auto are applied to this seller's next call by
# whoever builds the next seller_profile (its `overrides` block); the rest are suggestions for a human.

REVIEW_MIN_SELLER_TURNS = 3   # shorter calls say too little about the seller to judge Call 1
REVIEW_LANGS = ["Hindi", "English", "Tamil", "Telugu", "Kannada", "Malayalam", "Bengali", "Marathi", "Gujarati",
                "Punjabi", "Odia"]
LANG_CODE_BY_NAME = {"Hindi": "hi-IN", "English": "en-IN", "Tamil": "ta-IN", "Bengali": "bn-IN", "Gujarati": "gu-IN",
                     "Kannada": "kn-IN", "Malayalam": "ml-IN", "Marathi": "mr-IN", "Odia": "od-IN",
                     "Punjabi": "pa-IN", "Telugu": "te-IN"}  # every review language has an opening line
REVIEW_QS = {
    "review_wanted_faster": "Did the seller show they wanted a faster or shorter conversation (hurried, impatient, "
                            "asked to get to the point) that the agent's pace and length did not fully match?",
    "review_wanted_slower": "Did the seller show they needed a slower, more patient conversation (struggled to "
                            "follow, asked to repeat, sounded overwhelmed) that the agent did not fully give?",
    "review_wanted_simpler": "Did the seller show confusion about what the agent meant (asked what, asked to repeat, "
                             "misunderstood the reason for the call)?",
    "review_opening_ok": "Did the seller engage with the opening (confirmed who they are and let the agent continue) "
                         "rather than being confused, suspicious or put off by it?",
    "review_goal_met": "Did the call end with a concrete next step: a meeting booked, a callback time agreed, or the "
                       "information the agent asked for clearly given?",
    "review_persona_fit": "Overall, did the agent's tone, pace and language suit this particular seller?",
    "review_irritated_by_push": "Did the seller get irritated or annoyed because the agent kept persuading after the "
                                "seller had already refused?",
}
REFUSAL_RE = re.compile(
    r"not interested|don'?t need|do not need|don'?t want|do not want|no need|not required|no thanks|no, thank|"
    r"interest(ed)? nahi|nahi+n? chahiye|nahi chaiye|zaru?o?rat nahi|need nahi|nahi karna|nahi lena|mat karo|band karo|"
    r"नहीं चाहिए|नहीं चाहिये|इंटरेस्ट नहीं|interest नहीं|ज़रूरत नहीं|जरूरत नहीं|नहीं करना|नहीं लेना|मत करो", re.I)
CLOSE_RE = re.compile(r"dhanya?wa?a?d|shukriya|thank|धन्यवाद|शुक्रिया|have a (good|nice)|take care|bye|alvida", re.I)


def count_nudges(turns: list) -> tuple[int, int]:
    """(refusals, nudges): seller refusals, and agent turns that kept persuading right after one (not a close)."""
    refusals = nudges = 0
    for i, t in enumerate(turns):
        if t["role"] == "seller" and REFUSAL_RE.search(t["text"] or ""):
            refusals += 1
            nxt = next((u for u in turns[i + 1:] if u["role"] == "agent"), None)
            if nxt and not CLOSE_RE.search(nxt["text"] or ""):
                nudges += 1
    return refusals, nudges


def _review_questions() -> dict:
    qs = {"review_use_case": {
        "type": "choice",
        "instructions": "Judging only from what the seller said in this call, which call purpose would have fitted "
                        "this seller best? Use call_1.use_case only as context, not as the answer.",
        "criteria": {k: v["goal"] for k, v in USE_CASES.items()}},
        "review_seller_language": {
            "type": "choice",
            "instructions": "Which language was the seller most comfortable speaking in this call?",
            "criteria": {n: f"The seller mostly spoke or asked for {n}." for n in REVIEW_LANGS}}}
    qs.update({k: {"type": "noul", "instructions": v} for k, v in REVIEW_QS.items()})
    return qs


def _choice(a) -> tuple[Optional[str], Optional[float], dict]:
    if not isinstance(a, dict) or not isinstance(a.get("choice"), str):
        return None, None, {}
    probs = a.get("probabilities") if isinstance(a.get("probabilities"), dict) else {}
    return a["choice"], _finite(a.get("confidence"), 0.0, 1.0), {
        k: round(v, 2) for k, v in probs.items() if isinstance(v, (int, float)) and math.isfinite(v)}


def review_fixes(call1: dict, r: dict) -> list:
    """Deterministic fixes from the review answers. auto=True: safe to apply to this seller's next call."""
    fixes, p = [], r.get("persona") or {}
    blocked = call1.get("contact_policy") in ("SUPPRESS", "ROUTE_TO_HUMAN")
    hu, hc = r.get("hindsight_use_case"), r.get("hindsight_confidence") or 0
    goal = p.get("goal_met")
    if not blocked and hu and hu in USE_CASES and hu != call1.get("use_case") and hc >= 0.6:
        fixes.append({"kind": "use_case", "value": hu, "probability": hc,
                      "auto": hc >= 0.7 and (goal is None or goal < 0.5),
                      "why": f"the seller's needs fitted {hu} better than {call1.get('use_case')}"
                             + ("" if goal is None or goal < 0.5 else "; the call still reached a next step, so "
                                "this is only a suggestion")})
    lang, lc = r.get("seller_language"), r.get("seller_language_confidence") or 0
    if lang and lc >= 0.6 and lang != call1.get("start_language"):
        code = LANG_CODE_BY_NAME.get(lang)
        fixes.append({"kind": "start_language" if code else "note", "value": code or
                      f"The seller is most comfortable in {lang}; switch to {lang} as soon as they use it.",
                      "probability": lc, "auto": True,
                      "why": f"the seller was most comfortable in {lang}, the call started in {call1.get('start_language')}"})
    fast, slow = p.get("wanted_faster") or 0, p.get("wanted_slower") or 0
    if fast >= 0.6 and slow < 0.4:
        fixes.append({"kind": "pace_delta", "value": 0.1, "probability": fast, "auto": True,
                      "why": "the seller wanted a faster, shorter call"})
    elif slow >= 0.6 and fast < 0.4:
        fixes.append({"kind": "pace_delta", "value": -0.1, "probability": slow, "auto": True,
                      "why": "the seller needed a slower, more patient call"})
    if (p.get("wanted_simpler") or 0) >= 0.6:
        fixes.append({"kind": "simpler", "value": True, "probability": p["wanted_simpler"], "auto": True,
                      "why": "the seller was confused by what Disha meant"})
    nd = r.get("nudges") or {}
    if (p.get("irritated_by_push") or 0) >= 0.6 and nd.get("used", 0) >= 1:
        lower = max(0, min(call1.get("nudge_budget", NUDGE_CAP), nd["used"]) - 1)
        fixes.append({"kind": "nudge_budget", "value": lower, "probability": p["irritated_by_push"], "auto": True,
                      "why": f"the seller got irritated after {nd['used']} nudge(s); allow at most {lower} next time"})
    if p.get("opening_ok") is not None and p["opening_ok"] < 0.4:
        fixes.append({"kind": "note", "value": "Last time the opening did not land: confirm the business first, then "
                      "give the reason for the call in one plain line.", "probability": round(1 - p["opening_ok"], 2),
                      "auto": True, "why": "the seller did not engage with the opening"})
    return fixes


def language_trail(switches: list) -> list:
    """The languages Disha switched to during the call, in order (from the switch log)."""
    return [{"t_sec": s.get("t_sec"), "to": s.get("language_after"), "seller_words": s.get("seller_words")}
            for s in switches or [] if isinstance(s, dict) and s.get("signal") == "language"
            and isinstance(s.get("language_after"), str) and s.get("language_after")]


async def review_call(api_key: str, call1: dict, turns: list, extra_state=None, extra_qs=None, trail=None,
                      translated=True):
    """One Jev request: the call review plus any extra questions (the switch check). Returns (review, answers).
    On Samvaad the transcript is an English translation, so the seller's language is judged from the switch log's
    language trail; when Disha switched language and stayed there, that language wins over Jev's guess."""
    state = {"call_1": {k: call1.get(k) for k in ("use_case", "use_case_confidence", "use_case_reason",
                                                   "persona_style", "pace", "start_language", "opening_line")},
             "call_purposes": {k: v["goal"] for k, v in USE_CASES.items()},
             "transcript": [{"i": t["i"], "role": t["role"], "text": t["text"]} for t in turns[-60:]],
             "language_trail": trail or [],
             "note": ("The transcript text is an English translation of what was said. Judge the seller's language "
                      "from language_trail and the seller_words in it, not from the transcript's language.")
             if translated else "The transcript is in the original languages spoken."}
    qs = _review_questions()
    if extra_state:
        state.update(extra_state)
    if extra_qs:
        qs.update(extra_qs)
    ans = await jev_call(api_key, state, qs)
    ans = ans if isinstance(ans, dict) else {}
    hu, hc, hp = _choice(ans.get("review_use_case"))
    lang, lc, _ = _choice(ans.get("review_seller_language"))
    persona = {}
    for k in REVIEW_QS:
        a = ans.get(k)
        v = _finite(a.get("noul"), 0.0, 1.0) if isinstance(a, dict) else None
        persona[k.replace("review_", "")] = None if v is None else round(v, 2)
    r = {"version": 1, "status": "reviewed", "call_1": call1, "hindsight_use_case": hu,
         "hindsight_confidence": None if hc is None else round(hc, 2), "use_case_probabilities": hp,
         "agrees": None if hu is None else hu == call1.get("use_case"), "seller_language": lang,
         "seller_language_confidence": None if lc is None else round(lc, 2), "persona": persona}
    last = (trail or [{}])[-1].get("to") if trail else None
    if last in REVIEW_LANGS and last != call1.get("start_language"):
        r.update(seller_language=last, seller_language_confidence=max(r["seller_language_confidence"] or 0, 0.9),
                 seller_language_source="switch log: Disha switched to " + last + " and stayed")
    refusals, used = count_nudges(turns)
    budget = call1.get("nudge_budget")
    r["nudges"] = {"refusals": refusals, "used": used, "budget": budget,
                   "over_budget": isinstance(budget, int) and used > budget}
    r["fixes"] = review_fixes(call1, r)
    return r, ans


class OnEnd(SarvamOnEndTool):
    async def run(self, context: SarvamOnEndToolContext) -> SarvamOnEndToolContext:
        log = {"contract_version": CONTRACT_VERSION, "use_case": None, "switches": [], "turns": 0,
               "duration_sec": None}
        turns = []
        try:
            uc = _internal(context, "use_case", None)
            log["use_case"] = uc if isinstance(uc, str) else None
            log["switches"] = [dict(s, verification_status="unavailable") for s in _switch_list(context)]
            tr = context.get_interaction_transcript()
            for i, t in enumerate(tr.interaction_transcript or []):
                turns.append({"i": i, "role": "seller" if t.role == SarvamInteractionTurnRole.USER else "agent",
                              "text": t.en_text or ""})
            log["turns"] = len(turns)
            log["duration_sec"], why = _duration(tr.interaction_start_time, tr.interaction_end_time)
            if why:
                log["duration_unavailable"] = why
        except Exception as e:
            log["error"] = f"{type(e).__name__}: {e}"[:200]
        _set(context, "switch_log_json", _dumps(log))  # base log first: it survives any verification failure

        call1 = _internal(context, "call1", None)
        call1 = call1 if isinstance(call1, dict) else {"use_case": log["use_case"]}
        seller_turns = sum(1 for t in turns if t["role"] == "seller")
        review = {"version": 1, "status": "skipped", "call_1": call1,
                  "why": f"only {seller_turns} seller turns; at least {REVIEW_MIN_SELLER_TURNS} are needed to judge "
                         "the call"}
        if turns and (log["switches"] or seller_turns >= REVIEW_MIN_SELLER_TURNS):
            try:
                key = context.get_secret("TYPESAFE_API_KEY")
                if seller_turns >= REVIEW_MIN_SELLER_TURNS:
                    # one Jev request: the switch check and the call review together
                    items, sqs = switch_questions(log["switches"], turns)
                    review, ans = await asyncio.wait_for(
                        review_call(key, call1, turns, {"switches": items} if items else None, sqs,
                                    trail=language_trail(log["switches"])),
                        JEV_VERIFY_DEADLINE_S)
                    apply_switch_answers(log["switches"], ans)
                else:
                    await asyncio.wait_for(verify_switches(key, log["switches"], turns), JEV_VERIFY_DEADLINE_S)
                log["verification"] = "done"
            except Exception as e:
                print(f"[disha] Jev check after the call failed: {type(e).__name__}: {e}")
                for s in log["switches"]:
                    if s.get("verification_status") != "verified":
                        s["verification_status"] = "unavailable"
                log["verification"] = f"unavailable ({type(e).__name__})"
                if review.get("status") != "reviewed":
                    review = {"version": 1, "status": "unavailable", "call_1": call1, "why": type(e).__name__}
            _set(context, "switch_log_json", _dumps(log))
        _set(context, "call_review", _dumps(review))
        return context
