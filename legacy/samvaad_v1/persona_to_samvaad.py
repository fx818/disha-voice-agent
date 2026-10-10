"""Generated persona spec → per-call Samvaad settings.

Everything a persona decides travels with the call:
- agent_variables      → filled into the agent's instruction template ({{var}})
- initial_bot_message  → the persona's opening line
- initial_language_name
- text_to_speech_config → voice + pace (fixed for the call on Samvaad)
"""

import os

from agent.persona_state import load_facts, load_persona

LANG_NAME = {
    "hi-IN": "Hindi", "en-IN": "English", "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "mr-IN": "Marathi", "gu-IN": "Gujarati", "bn-IN": "Bengali",
    "pa-IN": "Punjabi", "od-IN": "Odia",
}
PACE_MIN, PACE_MAX = 0.85, 2.0  # runtime clamp documented by the SDK

# Samvaad workspace voices (Sarvam TTS v4, ids from agents(list_voices)), chosen per persona profile.
# v4 has purpose-built sales/support voices that the plain TTS API key cannot use.
VOICES = {
    "brisk": ("Ritu - Sales Agent", "01a0cf16-dd5f-77fa-8a45-4a6c01663eb1"),
    "repair": ("Ritu - Warm Support Agent", "01a0cf16-d7da-7f22-b00b-b454c7a709ba"),
    "warm_engaged": ("Simran - Hindi Sales Agent", "01a0cf16-c494-7231-b33d-fc186090959f"),
    "friendly_default": ("Ishita - Hinglish Support Agent", "01a0cf17-0b6e-79f0-b8ab-7392cabc497b"),
    "consultative": ("Aditya - Sales Agent", "01a0cf16-fd75-7f65-ad57-d0ca08ad4d7a"),
    "male": ("Tarun - Sales Agent", "01a0cf16-8f90-7ce7-8059-40c0005070ee"),
    "tamil_male": ("Aravind - Ad Voice (Tamil)", "01a0e8fc-88de-704c-a515-7fd4e7963156"),
}


def pick_voice(spec: dict) -> tuple[str, str]:
    profile = (spec.get("delivery_profile") or {}).get("id", "friendly_default")
    male = spec.get("voice", {}).get("gender") == "male"
    if spec.get("language", {}).get("language_code") == "ta-IN" and male:
        return VOICES["tamil_male"]
    if male and profile != "consultative":
        return VOICES["male"]
    return VOICES.get(profile, VOICES["friendly_default"])

# Input variables the Samvaad agent must define (agent_config.json uses the same list).
VARIABLES = [
    "seller_company", "seller_city", "seller_state", "seller_nature", "seller_categories",
    "persona_profile", "language_label", "english_mix_pct", "formality", "warmth", "empathy",
    "energy", "max_sentences", "target_call_sec", "opening_approach", "personalisation_hooks",
    "objection_playbook", "escalation_rules", "facts", "persona_reasons", "seller_id",
]


def _lines(items, fmt):
    return "\n".join(f"- {fmt(x)}" for x in items) or "- (none)"


def agent_variables(spec: dict) -> dict:
    s, v, lang, tone, plan = (spec.get(k, {}) for k in ("seller_snapshot", "voice", "language", "tone", "plan"))
    max_sent = 3 if plan.get("target_call_sec", 60) >= 80 else 2
    return {
        "seller_id": str(spec["seller_id"]),
        "seller_company": s.get("company") or "aapki company",
        "seller_city": s.get("city", ""),
        "seller_state": s.get("state", ""),
        "seller_nature": s.get("nature", ""),
        "seller_categories": ", ".join(s.get("top_categories", [])[:3]),
        "persona_profile": (spec.get("delivery_profile") or {}).get("label", s.get("segment", "")),
        "language_label": LANG_NAME.get(lang.get("language_code"), "Hindi"),
        "english_mix_pct": str(int(round(float(lang.get("english_mix", 0.3)) * 100))),
        "formality": lang.get("formality", "formal"),
        "warmth": tone.get("warmth", "medium"),
        "empathy": tone.get("empathy", "medium"),
        "energy": tone.get("energy", "neutral"),
        "max_sentences": str(max_sent),
        "target_call_sec": str(plan.get("target_call_sec", 60)),
        "opening_approach": plan.get("opening", {}).get("approach", ""),
        "personalisation_hooks": _lines(plan.get("personalisation", []), lambda h: h.get("hook", "")),
        "objection_playbook": _lines(plan.get("objection_playbook", []),
                                     lambda o: f"If {o.get('objection')}: {o.get('approach')}"),
        "escalation_rules": _lines(plan.get("escalation_rules", []),
                                   lambda e: f"If {e.get('trigger')}: {e.get('action')}"),
        "facts": _lines(load_facts(spec), str),
        "persona_reasons": f"voice: {v.get('reason', '')} | language: {lang.get('reason', '')} | tone: {tone.get('reason', '')}",
    }


def call_overrides(spec: dict, speaker_override: str | None = None) -> dict:
    v, lang = spec["voice"], spec["language"]
    pace = round(min(PACE_MAX, max(PACE_MIN, float(v.get("pace", 1.2)))), 2)
    return {
        "agent_variables": agent_variables(spec),
        "initial_bot_message": spec.get("plan", {}).get("opening", {}).get("example_line"),
        "initial_language_name": LANG_NAME.get(lang.get("language_code"), "Hindi"),
        "speaker": speaker_override or pick_voice(spec)[1],
        "speaker_label": pick_voice(spec)[0],
        "pace": pace,
    }


# ---- Paayal agent ("Paayal - IndiaMART Profile Enrichment Scheduler") -------------------------
# Paayal takes the persona as three inputs (persona_style, seller_history, persona_notes) on top of
# its own scheduling flow. Paayal is a woman, so only female voices are used.

PAAYAL_VOICES = {
    "brisk": ("Ritu - Sales Agent", "01a0cf16-dd5f-77fa-8a45-4a6c01663eb1"),
    "repair": ("Ritu - Warm Support Agent", "01a0cf16-d7da-7f22-b00b-b454c7a709ba"),
    "warm_engaged": ("Simran - Hindi Sales Agent", "01a0cf16-c494-7231-b33d-fc186090959f"),
    "friendly_default": ("Ishita - Hinglish Support Agent", "01a0cf17-0b6e-79f0-b8ab-7392cabc497b"),
    "consultative": ("Aparna - Support Agent", "01a0cf16-8d27-75e7-a4f8-f71f57f86443"),
}

PERSONA_STYLE = {
    "brisk": "brief_direct", "repair": "patient_gentle", "consultative": "warm_formal",
    "warm_engaged": "friendly_casual", "friendly_default": "friendly_casual",
}


def paayal_voice(spec: dict) -> tuple[str, str]:
    profile = (spec.get("delivery_profile") or {}).get("id", "friendly_default")
    return PAAYAL_VOICES.get(profile, PAAYAL_VOICES["friendly_default"])


def seller_history(spec: dict) -> tuple[str, str]:
    """Paayal's seller_history enum from the seller's past bot calls, with the reason."""
    h = spec.get("seller_snapshot", {}).get("history", {}) or {}
    flags = " ".join(h.get("flags", []))
    if "do_not_call" in flags:
        return "previously_declined", "seller asked not to be called on a past call"
    if h.get("meetings"):
        return "previously_contacted_interested", f"agreed to a meeting on {h['meetings']} past call(s)"
    if h.get("call_later"):
        return "callback_pending", f"asked to be called later on {h['call_later']} past call(s)"
    if h.get("not_interested"):
        return "previously_declined", f"said not interested on {h['not_interested']} past call(s)"
    return "new_seller", "no past interest, callback or refusal on record"


def persona_notes(spec: dict) -> str:
    """The persona spec as compact text for Paayal's {{persona_notes}}: each choice with its reason
    and confidence, so live adaptation can override low-confidence choices."""
    v, lang, tone, plan = (spec.get(k, {}) for k in ("voice", "language", "tone", "plan"))
    op = plan.get("opening", {})
    max_sent = 3 if plan.get("target_call_sec", 60) >= 80 else 2
    hist, hist_why = seller_history(spec)
    profile = (spec.get("delivery_profile") or {}).get("id", "friendly_default")
    # the generator's reason names its own speaker; Paayal keeps one female identity, so keep only the pace part
    v_reason = v.get("reason", "")
    pace_why = v_reason[v_reason.find("Pace"):] if "Pace" in v_reason else v_reason
    parts = [
        f"Profile: {(spec.get('delivery_profile') or {}).get('label', '')}",
        f"Voice and pacing: {paayal_voice(spec)[0]}, pace {v.get('pace')}. Why: Paayal is always a female voice; "
        f"this voice style suits the {profile.replace('_', ' ')} profile (informed guess, no call data compares "
        f"voices). {pace_why} [confidence {v.get('confidence', 'low')}]",
        f"Language: start in {LANG_NAME.get(lang.get('language_code'), 'Hindi')}, about "
        f"{int(round(float(lang.get('english_mix', 0.3)) * 100))} percent English business words, "
        f"{lang.get('formality', 'formal')} register. Why: {lang.get('reason', '')} "
        f"[confidence {lang.get('confidence', 'low')}]",
        f"Tone: warmth {tone.get('warmth')}, empathy {tone.get('empathy')}, energy {tone.get('energy')}. "
        f"Why: {tone.get('reason', '')} [confidence {tone.get('confidence', 'low')}]",
        f"Turn length: at most {max_sent} short sentences; aim to finish in about "
        f"{plan.get('target_call_sec', 60)} seconds.",
        f"Opening style: {op.get('approach', '')} Why: {op.get('reason', '')} "
        f"[confidence {op.get('confidence', 'low')}]",
        f"Seller history: {hist} ({hist_why}).",
        "Personalisation hooks:\n" + _lines(plan.get("personalisation", []), lambda h: h.get("hook", "")),
        "Objection approach:\n" + _lines(plan.get("objection_playbook", []),
                                         lambda o: f"If {o.get('objection')}: {o.get('approach')} "
                                                   f"(evidence {o.get('evidence', 'none')})"),
        "Escalation rules:\n" + _lines(plan.get("escalation_rules", []),
                                       lambda e: f"If {e.get('trigger')}: {e.get('action')}"),
    ]
    missing = spec.get("seller_snapshot", {}).get("missing_fields") or []
    if missing:
        parts.append(f"Missing seller data (lower confidence): {', '.join(missing)}")
    return "\n".join(parts)


def paayal_opening(spec: dict) -> str | None:
    """The persona's opening line, spoken as Paayal. Meeting length is left to Paayal's own facts."""
    line = spec.get("plan", {}).get("opening", {}).get("example_line")
    if not line:
        return None
    for old, new in (("15 minute ki meeting", "ek chhoti si meeting"), ("15 nimisha meeting", "chinna meeting"),
                     ("a 15-minute meeting", "a short meeting"), ("Vani", "Paayal")):
        line = line.replace(old, new)
    return line


def paayal_overrides(spec: dict, speaker_override: str | None = None) -> dict:
    s, lang = spec.get("seller_snapshot", {}), spec["language"]
    pace = round(min(PACE_MAX, max(PACE_MIN, float(spec["voice"].get("pace", 1.2)))), 2)
    label, speaker = paayal_voice(spec)
    profile = (spec.get("delivery_profile") or {}).get("id", "friendly_default")
    return {
        "agent_variables": {
            "seller_id": str(spec["seller_id"]),
            "seller_name": "",  # the seller file has no contact name; Paayal confirms the business instead
            "company_name": s.get("company") or "",
            "city": s.get("city", ""),
            "seller_phone": "",
            "gender": "Female",
            "persona_style": PERSONA_STYLE.get(profile, "friendly_casual"),
            "seller_history": seller_history(spec)[0],
            "persona_notes": persona_notes(spec),
        },
        "initial_bot_message": paayal_opening(spec),
        "initial_language_name": LANG_NAME.get(lang.get("language_code"), "Hindi"),
        "speaker": speaker_override or speaker,
        "speaker_label": label,
        "pace": pace,
    }


# ---- agent selection --------------------------------------------------------------------------

def target() -> dict:
    """Which Samvaad agent calls go to: SAMVAAD_AGENT=paayal (default) or vani."""
    if os.getenv("SAMVAAD_AGENT", "paayal").lower() == "vani":
        return {"name": "vani", "app_id": os.environ["SAMVAAD_APP_ID"],
                "version": int(os.getenv("SAMVAAD_APP_VERSION", "1")), "overrides": call_overrides}
    return {"name": "paayal", "app_id": os.environ["SAMVAAD_PAAYAL_APP_ID"],
            "version": int(os.getenv("SAMVAAD_PAAYAL_APP_VERSION", "1")), "overrides": paayal_overrides}


def for_seller(seller_id: str, speaker_override: str | None = None) -> dict:
    return target()["overrides"](load_persona(seller_id), speaker_override)


if __name__ == "__main__":
    import json

    for sid in ("56730", "22871081", "181758742"):
        c = paayal_overrides(load_persona(sid))
        av = c.pop("agent_variables")
        print(sid, json.dumps(c, ensure_ascii=False))
        print("   vars:", {k: av[k] for k in ("company_name", "persona_style", "seller_history")},
              f"persona_notes {len(av['persona_notes'])} chars")
