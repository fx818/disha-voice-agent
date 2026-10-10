"""Persona generator: seller data -> persona spec (see PERSONA_SPEC.md).

Deterministic and rule based. Every rule cites evidence ids from outputs/evidence.json; settings with no
evidence behind them are marked confidence "low" and say so.

  python -m generator.generate --seller-id 39323
  python -m generator.generate --sample            # writes outputs/personas/*.json + index.json
"""
import argparse
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from generator import fixed_script as FS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"

REGION = None  # filled lazily from data_prep.evidence to keep one source of truth

STATE_LANG = {
    "Tamil Nadu": "ta-IN", "Puducherry": "ta-IN", "Pondicherry": "ta-IN", "Karnataka": "kn-IN",
    "Kerala": "ml-IN", "Andhra Pradesh": "te-IN", "Telangana": "te-IN", "Gujarat": "gu-IN",
    "Maharashtra": "mr-IN", "Goa": "mr-IN", "West Bengal": "bn-IN", "Tripura": "bn-IN", "Odisha": "od-IN",
    "Punjab": "pa-IN",
}
LANG_NAME = {"hi-IN": "Hindi", "en-IN": "English", "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada",
             "ml-IN": "Malayalam", "gu-IN": "Gujarati", "mr-IN": "Marathi", "bn-IN": "Bengali",
             "pa-IN": "Punjabi", "od-IN": "Odia"}

# bulbul:v3 voices. Characterisation is our own listening-free assumption -> always confidence "low".
VOICES = {
    ("female", "brisk"): "neha", ("female", "warm"): "priya", ("female", "calm"): "ritu",
    ("female", "regional_south"): "kavya", ("female", "english"): "amelia",
    ("male", "formal"): "aditya", ("male", "calm"): "rahul", ("male", "regional_south"): "varun",
}


# ------------------------------------------------------------------------------------------- evidence
@lru_cache(maxsize=1)
def evidence():
    p = OUT / "evidence.json"
    if not p.exists():
        raise SystemExit("outputs/evidence.json missing: run `python -m data_prep.evidence` first")
    return json.loads(p.read_text())


@lru_cache(maxsize=1)
def ev_by_key():
    return {i["key"]: i for i in evidence()["items"]}


def E(key):
    """Evidence id for a key (or None if that analysis did not produce it)."""
    i = ev_by_key().get(key)
    return i["id"] if i else None


def ev_strength(key):
    i = ev_by_key().get(key)
    return i["strength"] if i else None


def ev_fmt(key, fmt="{value:.1%} vs {baseline:.1%}"):
    i = ev_by_key().get(key)
    if not i or i["value"] is None:
        return ""
    try:
        return fmt.format(value=i["value"], baseline=i["baseline"] if i["baseline"] is not None else float("nan"),
                          n=i["n"])
    except (TypeError, ValueError):
        return ""


def conf_from(*keys, have_data=True):
    """high if any cited evidence is strong and the seller field exists; medium if moderate; else low."""
    if not have_data:
        return "low"
    ss = [ev_strength(k) for k in keys if ev_strength(k)]
    if "strong" in ss:
        return "high"
    if "moderate" in ss:
        return "medium"
    return "low"


# ------------------------------------------------------------------------------------------- helpers
def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _str(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    s = str(x).strip()
    return s or None


def region_of(state):
    global REGION
    if REGION is None:
        from data_prep.evidence import REGION as R
        REGION = R
    return REGION.get(state, "Other") if state else "Unknown"


TURNOVER_BAND = {"0 - 40 L": "micro", "40 L - 1.5 Cr": "small", "1.5 - 5 Cr": "mid", "5 - 25 Cr": "large",
                 "25 - 100 Cr": "large", "100 - 500 Cr": "large", "500 Cr & above": "large",
                 "> 500 Cr": "large"}  # the PS07 data writes the top band as "> 500 Cr"


def parse_counts(s):
    """'callback_requested (2); call_dropped (1)' -> {'callback_requested': 2, ...}"""
    out = {}
    for part in re.split(r";|,(?![^()]*\))", _str(s) or ""):
        m = re.match(r"\s*(.+?)\s*\((\d+)\)\s*$", part)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


# ------------------------------------------------------------------------------------------- features
def features(r):
    f = {}
    f["state"] = _str(r.get("seller_state"))
    f["city"] = _str(r.get("seller_city"))
    f["locality"] = _str(r.get("seller_locality"))
    f["region"] = region_of(f["state"])
    f["turnover"] = _str(r.get("annual_turnover"))
    f["band"] = TURNOVER_BAND.get(f["turnover"], "unknown")
    f["business_type"] = _str(r.get("business_type"))
    nat = _str(r.get("nature_of_business")) or ""
    f["nature_raw"] = nat or None
    f["nature"] = ("wholesaler" if "Wholesal" in nat else "retailer" if "Retail" in nat else
                   "manufacturer" if "Manufact" in nat else "service" if "Service" in nat else "unknown")
    f["categories"] = [c for c in (_str(r.get(f"top_category_{i}")) for i in (1, 2, 3)) if c]
    f["category_group"] = _str(r.get("top_category_group"))
    f["company"] = _str(r.get("company"))
    f["gst_year"] = _num(r.get("gst_registration_year"))

    f["pickup_1yr"] = _num(r.get("eng_pickup_ratio_1yr"))
    f["enq_90d"] = _num(r.get("eng_enq_received_90d"))
    f["enq_replies_90d"] = _num(r.get("eng_enq_replies_90d"))
    f["cqs"] = _num(r.get("eng_cqs"))
    f["products"] = _num(r.get("eng_product_count"))
    f["has_engagement"] = f["pickup_1yr"] is not None

    f["bot_answered"] = _num(r.get("bot_answered")) or 0
    f["bot_attempts"] = _num(r.get("bot_attempts")) or 0
    f["avg_sec"] = _num(r.get("avg_answered_call_sec"))
    f["mf"] = _num(r.get("calls_meeting_fixed")) or 0
    f["ni"] = _num(r.get("calls_not_interested")) or 0
    f["cl"] = _num(r.get("calls_call_later")) or 0
    f["early_calls"] = _num(r.get("ctx_early_calls")) or 0
    f["last_bucket"] = _str(r.get("ctx_last_bucket"))
    f["disp"] = parse_counts(r.get("past_dispositions_detailed"))
    f["objections"] = parse_counts(r.get("past_objections"))
    f["questions"] = parse_counts(r.get("past_questions_asked"))
    for k in ("asked_if_talking_to_bot", "showed_frustration", "already_in_touch_with_executive",
              "do_not_call_requested"):
        f[k] = (_num(r.get(k)) or 0) >= 1
    f["has_history"] = f["bot_answered"] > 0
    ans = max(f["bot_answered"], 1)
    f["fast_hangup"] = f["has_history"] and (
        (f["avg_sec"] is not None and f["avg_sec"] < 12) or
        (f["bot_answered"] >= 2 and f["early_calls"] / ans >= 0.5) or f["disp"].get("call_dropped", 0) >= 3)
    f["repeat_attempts"] = f["has_history"] and f["bot_attempts"] >= 5 and f["bot_answered"] / max(f["bot_attempts"], 1) < 0.4
    f["engaged"] = (f["pickup_1yr"] or 0) > 50 or (f["enq_replies_90d"] or 0) >= 3
    f["callback_seeker"] = f["cl"] >= 1 or f["disp"].get("callback_requested", 0) >= 1
    f["refuser"] = f["ni"] >= 2 and f["mf"] == 0 and f["ni"] / ans >= 0.5
    return f


def delivery_profile(f):
    """One headline profile per seller; drives voice/tone/plan jointly so personas are clearly distinct."""
    if f["do_not_call_requested"] or f["showed_frustration"] or f["refuser"]:
        return "repair"          # calm, apologetic, minimal ask
    if f["band"] in ("mid", "large") or f["business_type"] == "Limited Company":
        return "consultative"    # formal, measured, business-outcome framing
    if f["fast_hangup"] or f["repeat_attempts"]:
        return "brisk"           # hook-first, fast, short
    if f["engaged"] or f["callback_seeker"] or (f["last_bucket"] in ("PAM", "NUR", "SCHD")):
        return "warm_engaged"    # upbeat, detail-ready, scheduling-forward
    return "friendly_default"


PROFILE_LABEL = {
    "repair": "Calm repair: low pressure, empathy first, one soft ask",
    "brisk": "Brisk: hook in the first sentence, fast pace, short turns",
    "consultative": "Consultative: formal, measured, business-value framing",
    "warm_engaged": "Warm & engaged: upbeat, detail-ready, moves to scheduling",
    "friendly_default": "Friendly default: warm, clear, standard pace",
}


# ------------------------------------------------------------------------------------------- language
def choose_language(f, profile):
    ev = evidence()
    lbs = ev.get("language_by_state", {})
    state = f["state"]
    regional = STATE_LANG.get(state)
    refs = []
    if state is None:
        return dict(language_code="hi-IN", english_mix=0.25, formality="neutral",
                    reason="State unknown; Hindi is what 95%+ of transcribed sellers answered in.",
                    confidence="low", switch_ready=["en-IN"]), [E("lang_switch_rate")]
    stat = lbs.get(state)
    key = f"lang_{state.lower().replace(' ', '_')}"
    if regional and stat and stat.get(regional, 0) >= 0.4:
        code = regional
        reason = (f"{state} sellers answered our Hindi-opening bot in {LANG_NAME[regional]} in "
                  f"{stat[regional]:.0%} of {stat['n_calls']} transcribed calls, so open in {LANG_NAME[regional]}.")
        conf = "medium" if stat["n_calls"] >= 100 else "low"
        refs.append(E(key))
        switch = ["en-IN", "hi-IN"]
    elif regional and stat:
        code = "hi-IN"
        reason = (f"Although the regional language is {LANG_NAME[regional]}, {state} sellers replied in Hindi in "
                  f"{stat.get('hi-IN', 0):.0%} of {stat['n_calls']} transcribed calls; open in Hindi and switch to "
                  f"{LANG_NAME[regional]} live if the seller does.")
        conf = "medium" if stat["n_calls"] >= 100 else "low"
        refs.append(E(key))
        switch = [regional, "en-IN"]
    elif regional:
        # e.g. Karnataka / Kerala / AP: almost no transcripts
        code = "en-IN"
        reason = (f"Too few transcribed calls from {state} to know the preferred language; southern sellers use the "
                  f"most English of any region ({ev_fmt('english_south', '{value:.0%} vs {baseline:.0%} English words')}"
                  f"), so open in Indian English and switch to {LANG_NAME[regional]} or Hindi live.")
        conf = "low"
        refs.append(E("english_south"))
        switch = [regional, "hi-IN"]
    else:
        code = "hi-IN"
        hi = stat.get("hi-IN") if stat else None
        reason = (f"{state} is Hindi-speaking" + (f"; {hi:.0%} of {stat['n_calls']} transcribed calls were in Hindi."
                                                if hi else "."))
        conf = "high" if stat and stat["n_calls"] >= 300 else "medium"
        if stat:
            refs.append(E(key) or E("lang_switch_rate"))
        switch = ["en-IN"]
    refs.append(E("lang_switch_rate"))

    # English mix: region evidence + profile (informed guess for profile part)
    em = ev.get("english_mix", {}).get("by_region", {})
    reg_en = em.get(f["region"])
    base = {"hi-IN": 0.2, "en-IN": 0.85}.get(code, 0.1)
    if reg_en is not None and code == "hi-IN":
        base = round(min(0.5, 0.1 + reg_en * 2), 2)  # observed English-word share x2 -> code-mix target
    if profile == "consultative":
        base = min(0.6, base + 0.15)
    if f["region"] == "NCR_Punjab" and code == "hi-IN":
        base = min(0.6, base + 0.05)
    english_mix = round(base, 2)

    if profile == "consultative" or f["business_type"] in ("Limited Company", "Partnership"):
        formality = "formal"
    elif profile in ("brisk",) and f["band"] in ("micro", "unknown"):
        formality = "casual"
    else:
        formality = "neutral"
    reason += (f" English mix {english_mix:.0%}: based on the English-word share sellers in {f['region']} used"
               + (" plus a business-register bump for a consultative profile (guess)" if profile == "consultative"
                  else "") + f". Formality '{formality}': "
               + {"formal": "larger / incorporated business, so 'aap' and polite phrasing throughout; 'ji' at most once in the call, never as a tag on every line.",
                  "casual": "micro trader who hangs up fast; plain everyday Hindi, still 'aap'.",
                  "neutral": "respectful 'aap' without heavy honorifics."}[formality])
    return dict(language_code=code, english_mix=english_mix, formality=formality, reason=reason,
                confidence=conf, switch_ready=switch), refs


# ------------------------------------------------------------------------------------------- voice/tone
BASE_PACE = 1.2  # Sarvam's 1.0 sounds slow on a sales call; personas adjust from here


def choose_voice(f, profile, lang):
    pace = BASE_PACE
    why = []
    refs = []
    if profile == "brisk":
        pace += 0.15
        why.append("history of quick hang-ups / many attempts: early drops "
                   + ev_fmt("prior_early_drop", "{value:.0%} vs {baseline:.0%} for others") + " so faster delivery")
        refs += [E("prior_early_drop"), E("attempt_decay")]
    if profile == "repair":
        pace -= 0.1
        why.append("past frustration / refusals: slower, calmer delivery")
        refs += [E("prior_not_interested"), E("signal_frustration")]
    if profile == "consultative":
        pace -= 0.05
        why.append("larger business: measured pace for a formal register")
        refs.append(E("turnover_large"))
    if profile not in ("brisk", "repair") and f["fast_hangup"]:
        pace += 0.1
        why.append("also hangs up quickly: a little faster than the profile default")
        refs.append(E("prior_early_drop"))
    if lang["language_code"] not in ("hi-IN",):
        pace -= 0.05
        why.append("non-Hindi / second-language delivery: slightly slower for clarity")
    if f["region"] == "South":
        pace -= 0.05
        why.append("southern sellers speak slowest in transcripts ("
                   + ev_fmt("speech_rate", "{value:.2f} words/s overall; bot {baseline:.2f}") + ")")
        refs.append(E("speech_rate"))
    if f["region"] == "NCR_Punjab" and profile != "repair":
        pace += 0.05
        why.append("NCR/Punjab: highest not-interested rate and fast speech, keep it crisp")
        refs.append(E("region_NCR_Punjab"))
    pace = round(min(1.5, max(1.0, pace)), 2)

    # gender / speaker: no data -> informed guess, stated as such
    if profile == "consultative":
        gender, style = "male", "formal"
        gwhy = ("male, formal voice for a larger business (informed guess: no call varied the voice; all past "
                "calls used a female voice)")
    else:
        gender = "female"
        style = {"brisk": "brisk", "repair": "calm", "warm_engaged": "warm", "friendly_default": "warm"}[profile]
        gwhy = "female voice, as in all past VANI calls (keeps continuity; no data compares genders)"
    if lang["language_code"] in ("ta-IN", "te-IN", "kn-IN", "ml-IN"):
        style = "regional_south"
    elif lang["language_code"] == "en-IN" and gender == "female":
        style = "english"
    speaker = VOICES.get((gender, style)) or VOICES[(gender, "calm" if gender == "male" else "warm")]
    temperature = {"brisk": 0.5, "repair": 0.45, "consultative": 0.4, "warm_engaged": 0.75,
                   "friendly_default": 0.6}[profile]
    reason = (f"Speaker '{speaker}': {gwhy}. Pace {pace}: " + ("; ".join(why) if why else f"no history; standard pace {BASE_PACE}")
              + f". Expressiveness {temperature} to match the {profile.replace('_', ' ')} profile.")
    return dict(speaker=speaker, gender=gender, pace=pace, temperature=temperature, reason=reason,
                confidence="low" if not f["has_history"] else "medium" if refs else "low",
                note="Voice gender/timbre and pace effects are not evidenced by the data; live adaptation corrects pace."
                ), refs


def choose_tone(f, profile):
    t = {
        "repair": ("high", "high", "calm",
                   "Past frustration / not-interested / do-not-call: lead with empathy and an apology for repeat calls."),
        "brisk": ("medium", "medium", "neutral",
                  "Seller drops calls fast: respectful but business-like; warmth shown by brevity, not chit-chat."),
        "consultative": ("medium", "medium", "calm",
                         "Larger business: composed and professional, peer-to-peer rather than salesy."),
        "warm_engaged": ("high", "medium", "upbeat",
                         "Engaged seller (picks up, replies to enquiries, or asked for a callback): mirror the interest."),
        "friendly_default": ("high", "medium", "neutral", "No strong signal; warm and clear."),
    }[profile]
    keys = {"repair": ["prior_not_interested", "flag_showed_frustration"], "brisk": ["prior_early_drop"],
            "consultative": ["turnover_large"], "warm_engaged": ["engagement_high", "prior_call_later"],
            "friendly_default": []}[profile]
    return dict(warmth=t[0], empathy=t[1], energy=t[2], reason=t[3] + " (Tone levels are an informed guess; "
                "the data has no labelled tone.)", confidence="low"), [E(k) for k in keys]


# ------------------------------------------------------------------------------------------- plan
OPENINGS = {
    "hi-IN": {
        "brisk": "Namaste, IndiaMART se Vani. {city} mein aapki category ke buyers ke liye ek chhoti si baat thi, kya {company} se do minute baat ho sakti hai?",
        "callback": "Namaste {company} ji, IndiaMART se Vani. Aapne pichli baar baad mein call karne ko kaha tha — abhi baat ho sakti hai?",
        "repair": "Namaste ji, IndiaMART se Vani. Pehle ke calls se pareshani hui ho toh maafi chahti hoon — bas ek chhoti si baat hai, ek minute milega?",
        "consultative": "Namaste, main IndiaMART ki taraf se Vani. {city} mein {category} ke buyers ke liye aapke saath ek chhoti meeting fix karni thi, kya meri baat {company} se ho rahi hai?",
        "warm": "Namaste {company} ji! IndiaMART se Vani bol rahi hoon. {city} mein aapki category ke buyers ke liye ek chhoti si meeting rakhni thi, abhi do minute baat ho sakti hai?",
        "transparent": "Namaste, main IndiaMART ki AI assistant Vani hoon. {city} mein aapki category ke buyers ke liye executive se ek chhoti, free meeting fix karni thi, kya yeh {company} hai?",
    },
    "ta-IN": {
        "brisk": "Vanakkam, IndiaMART-la irundhu Vani. {city}-la unga category buyers pathi oru chinna vishayam. {company}-kitta rendu nimisham pesalaama?",
        "callback": "Vanakkam {company}, IndiaMART-la irundhu Vani. Neenga munnaadi apparam call pannunga sonneenga — ippo pesalaama?",
        "repair": "Vanakkam, IndiaMART-la irundhu Vani. Munnaadi calls-aala sirama irundha mannikkavum — oru nimisham mattum.",
        "consultative": "Vanakkam, naan IndiaMART saarbaaga Vani. {city}-la {category} buyers pathi oru chinna meeting arrange panna virumbugiren. {company}-la pesuradhu yaaru?",
        "warm": "Vanakkam {company}! IndiaMART-la irundhu Vani pesuren. {city}-la unga category buyers pathi oru chinna meeting arrange pannanum, ippo pesalaama?",
        "transparent": "Vanakkam, naan IndiaMART-oda AI assistant Vani. {city}-la unga category buyers pathi oru chinna free meeting fix pannanum. {company}-aa?",
    },
    "en-IN": {
        "brisk": "Hello, this is Vani from IndiaMART, calling about buyers in your category in {city}. Could {company} spare two minutes?",
        "callback": "Hello {company}, this is Vani from IndiaMART. You'd asked us to call back later — is now a good time?",
        "repair": "Hello, this is Vani from IndiaMART. Sorry if our earlier calls were a bother — this will take just a minute.",
        "consultative": "Good day, I'm Vani, calling on behalf of IndiaMART about buyers for {category} in {city} and a short meeting with our executive. Am I speaking with {company}?",
        "warm": "Hello {company}! Vani here from IndiaMART. I'd love to set up a quick meeting about buyers in your category in {city}. Is now a good time?",
        "transparent": "Hello, I'm Vani, IndiaMART's AI assistant, calling to set up a short, free meeting about buyers in your category in {city}. Am I speaking with {company}?",
    },
}


def opening(f, profile, lang):
    if f["asked_if_talking_to_bot"]:
        kind, reason, keys = ("transparent", "Seller previously asked if they were talking to a bot: disclose AI "
                              "identity up front instead of being caught out (honesty guardrail).",
                              ["flag_asked_if_talking_to_bot", "bot_identity_question"])
    elif profile == "repair":
        kind, reason, keys = ("repair", "Past frustration / refusals: acknowledge repeat calls before any ask; "
                              "prior not-interested sellers convert at only "
                              + ev_fmt("prior_not_interested", "{value:.1%} vs {baseline:.1%}") + ".",
                              ["prior_not_interested"])
    elif f["callback_seeker"] and profile != "brisk":
        kind, reason, keys = ("callback", "Seller asked for a callback before; follow-up calls to such sellers convert "
                              "better (" + ev_fmt("prior_call_later", "{value:.1%} vs {baseline:.1%}") + "), so "
                              "reference that request.", ["prior_call_later"])
    elif profile == "brisk":
        kind, reason, keys = ("brisk", "Fast hang-ups / repeat attempts: put the value hook in the first sentence. "
                              "Most drops happen at the opening (" + ev_fmt("drop_points", "{value:.0%} of calls dropped")
                              + ") and a cut-off pitch halves meetings ("
                              + ev_fmt("pitch_truncation", "{value:.0%} of pitches cut off") + ").",
                              ["drop_points", "pitch_truncation", "attempt_decay"])
    elif profile == "consultative":
        kind, reason, keys = ("consultative", "Larger business: formal identity check, then a business-demand framing "
                              "(category + city).", ["turnover_large"])
    else:
        kind, reason, keys = ("warm", "Lead with buyers in their city/category (no enquiry claim); enquiry responders "
                              "convert better (" + ev_fmt("enquiry_responders", "{value:.1%} vs {baseline:.1%}") + ").",
                              ["enquiry_responders"])
    tmpl_lang = lang["language_code"] if lang["language_code"] in OPENINGS else "hi-IN"
    line = OPENINGS[tmpl_lang][kind].format(company=f["company"] or "aapki company" if tmpl_lang == "hi-IN"
                                            else f["company"] or "your company",
                                            city=f["city"] or ("aapke shehar" if tmpl_lang == "hi-IN" else "your city"),
                                            category=(f["categories"][0] if f["categories"] else "your products"))
    if tmpl_lang != lang["language_code"]:
        reason += f" (Example shown in Hindi; delivered in {LANG_NAME[lang['language_code']]} at runtime.)"
    approach = {"brisk": "Hook-first one-liner, ask for two minutes, skip pleasantries.",
                "callback": "Reference their earlier callback request, then go straight to scheduling.",
                "repair": "Apologise for repeat calls, one soft ask, easy exit.",
                "consultative": "Formal identity check, category-buyers framing, request a meeting with the executive.",
                "warm": "Friendly greeting, category-buyers hook, invite a short meeting.",
                "transparent": "Disclose AI identity in the first line, then the category-buyers hook."}[kind]
    return dict(approach=approach, example_line=line, reason=reason,
                confidence=conf_from(*keys, have_data=f["has_history"] or kind in ("consultative", "warm"))), keys


OBJECTION_APPROACH = {
    "Seller Unavailability & Scheduling Constraints": {
        "brisk": "Don't re-pitch. Offer two concrete slots (tomorrow 12 / 4 PM) in one sentence; else book a callback.",
        "default": "Acknowledge they're busy, offer a slot on another day between 11 AM-5 PM or a phone meeting."},
    "Callback / Deferred Engagement (Neutral)": {
        "default": "Lock an exact callback day and time; confirm it back in one line."},
    "Explicit Disinterest / Refusal": {
        "repair": "Accept immediately, thank them, offer to share details by the executive later only if they want; close.",
        "default": "Ask one clarifying 'what would make it useful?' question; on second refusal close politely."},
    "Existing Engagement / Past Experience": {
        "default": "Acknowledge their executive / past meeting; position this visit as a follow-up on the profile; "
                   "if they had a bad experience, apologise and offer to route the complaint, no pitch."},
    "Not Ready / Needs Time / Early-Stage Seller": {
        "default": "Reassure the meeting is free and only guidance on the profile; offer a later date."},
    "Product / Service / Business Mismatch": {
        "default": "Confirm their current products; if truly mismatched, thank and close."},
    "Information / Trust / Privacy Concerns": {
        "default": "State who is calling and why (IndiaMART, about their listing), never ask for sensitive data."},
    "Wrong Contact / Business Not Applicable": {
        "default": "Apologise, ask if there is a better contact person; otherwise close."},
    "Pricing": {
        "default": "Do not quote any price; say the executive will explain plans in the meeting; return to scheduling."},
    "Bot identity": {
        "default": "Answer honestly: 'Main IndiaMART ki AI assistant hoon' and continue with the purpose."},
}


def objection_playbook(f, profile):
    ev = evidence()
    mix = ev.get("objection_mix", {})
    refs = []
    personal = {k: v for k, v in f["objections"].items() if k in OBJECTION_APPROACH}
    reg = mix.get("by_region", {}).get(f["region"]) or mix.get("overall", {})
    ranked = sorted(reg.items(), key=lambda kv: -kv[1])
    order = list(personal) + [k for k, _ in ranked if k in OBJECTION_APPROACH and k not in personal]
    order = order[:4]
    items = []
    for cat in order:
        key = "objection_" + re.sub(r"\W+", "_", cat.lower()).strip("_")[:40]
        refs.append(E(key))
        appr = OBJECTION_APPROACH[cat].get(profile) or OBJECTION_APPROACH[cat]["default"]
        share = reg.get(cat)
        src = (f"seller raised this before ({f['objections'][cat]}x)" if cat in personal
               else f"{share:.0%} of objections from {f['region']} sellers" if share else "common objection")
        items.append(dict(objection=cat, approach=appr, reason=src,
                          evidence=f"{E(key)}: meeting rate after this objection "
                                   + ev_fmt(key, "{value:.1%}") if E(key) else ""))
    items.append(dict(objection="Pricing question", approach=OBJECTION_APPROACH["Pricing"]["default"],
                      reason="Real bots quoted inconsistent prices; pricing is a guardrailed fact.",
                      evidence="fixed_script.GUARDRAILS"))
    items.append(dict(objection="'Are you a bot?'", approach=OBJECTION_APPROACH["Bot identity"]["default"],
                      reason="Sellers do ask; " + ev_fmt("bot_identity_question", "") +
                             "past bot answers often denied being AI (compliance risk).",
                      evidence=f"{E('bot_identity_question')}"))
    if f["already_in_touch_with_executive"]:
        items.insert(0, dict(objection="Already in touch with an IndiaMART executive",
                             approach=OBJECTION_APPROACH["Existing Engagement / Past Experience"]["default"],
                             reason="Seller said this on a past call.",
                             evidence=f"{E('flag_already_in_touch_with_executive')}: "
                                      + ev_fmt("flag_already_in_touch_with_executive", "{value:.1%} vs {baseline:.1%}")))
        refs.append(E("flag_already_in_touch_with_executive"))
    return items, refs


def escalation_rules(f, profile):
    rules = [
        dict(trigger="Seller asks not to be called again",
             action="Acknowledge, apologise, say the request will be passed on, close immediately.",
             reason="Compliance guardrail; DNC sellers convert at "
                    + ev_fmt("flag_do_not_call_requested", "{value:.1%}") + "."),
        dict(trigger="Second clear refusal (first if previously declined or a repair call)",
             action="At most one reframe after the first refusal, 2 nudges per call; then thank and close.",
             reason="Prior not-interested sellers rarely convert ("
                    + ev_fmt("prior_not_interested", "{value:.1%}") + "); pushing risks frustration."),
        dict(trigger="Frustration detected twice (keywords or repeated barge-in)",
             action="Apologise once, offer a callback at their chosen time, close.",
             reason="After a frustration turn the call ends within 2 turns "
                    + ev_fmt("signal_frustration", "{value:.0%} of the time vs {baseline:.0%}") + "."),
        dict(trigger="Seller asks for a human / the executive",
             action="Offer the executive's call-back at a time they pick; book it as the outcome.",
             reason="Keeps the meeting goal while respecting the request."),
        dict(trigger="Same pitch would be repeated",
             action="Never repeat a line verbatim; rephrase in fewer words or move to the scheduling question.",
             reason="Informed guess: repetition annoys callers. The data cannot test it fairly: calls the "
                    "evaluator flagged as repetitive are long calls, which convert more for that reason alone."),
    ]
    refs = [E("flag_do_not_call_requested"), E("prior_not_interested"), E("signal_frustration")]
    if profile == "brisk":
        rules.insert(0, dict(trigger="Two consecutive 1-2 word replies or a 'busy' cue",
                             action="Offer two concrete slots in one line; if neither works, take a callback time, confirm, close.",
                             reason="Short replies predict the call ending soon ("
                                    + ev_fmt("two_short_replies", "{value:.0%} vs {baseline:.0%}") + ")."))
        refs.append(E("two_short_replies"))
    if profile == "repair":
        rules.insert(0, dict(trigger="Any refusal",
                             action="Close politely on the first refusal; do not counter.",
                             reason="Seller has a history of frustration / refusal; protect the relationship."))
    rules.append(dict(trigger="Call placed between 11:00 and 13:00",
                      action="Offer an afternoon slot or callback early in the call.",
                      reason="Late-morning calls convert at " + ev_fmt("hour_late_morning", "{value:.1%} vs {baseline:.1%}")
                             + " (busiest trading hours)."))
    refs.append(E("hour_late_morning"))
    return rules, refs


def personalisation(f):
    hooks = []
    if f["company"]:
        hooks.append(dict(hook=f"Confirm the business by name: '{f['company']}'",
                          reason="Name taken from past call openings/summaries; confirms the right contact."))
    enq = f["enq_90d"]
    if f["city"] and f["categories"] and isinstance(enq, (int, float)) and enq > 0:
        hooks.append(dict(hook=f"Buyer enquiries for {f['categories'][0]} in {f['city']}",
                          reason="Seller's top category and city from the seller file; the enquiry hook is the "
                                 "standard VANI value line."))
    if isinstance(enq, (int, float)) and enq > 0:
        hooks.append(dict(hook=f"They received {int(f['enq_90d'])} enquiries in the last 90 days"
                               + (f" and replied to {int(f['enq_replies_90d'])}" if f["enq_replies_90d"] else ""),
                          reason="Engagement data; enquiry responders convert better ("
                                 + ev_fmt("enquiry_responders", "{value:.1%} vs {baseline:.1%}") + "). Use the number "
                                 "only as supplied."))
    if f["cqs"] is not None and f["cqs"] < 50:
        hooks.append(dict(hook=f"Catalogue quality score is {int(f['cqs'])}/100 — the executive can help improve it",
                          reason="Low catalogue score from engagement data; profile improvement is a common VANI hook."))
    if f["last_bucket"]:
        reason_key = FS.LEAD_REASON_BY_BUCKET.get(f["last_bucket"])
        if reason_key:
            warm = f["last_bucket"] in ("PAM", "NUR", "SCHD")
            hooks.append(dict(hook=FS.FACTS[reason_key],
                              reason=f"Lead bucket {f['last_bucket']} on the latest call"
                                     + ("; warm buckets convert at " + ev_fmt("bucket_warm", "{value:.1%} vs {baseline:.1%}")
                                        if warm else "; states why IndiaMART is calling") + "."))
    if f["locality"]:
        hooks.append(dict(hook=f"Offer the meeting at {f['locality']}, {f['city']}",
                          reason="Locality from the seller file; location confirmation is part of booking."))
    if f["callback_seeker"]:
        hooks.append(dict(hook="If it fits, mention softly that they had asked to talk later; drop it if they say they never asked",
                          reason="Past call-later outcome on record."))
    return hooks


# ------------------------------------------------------------------------------------------- main API
def generate_persona(seller_row: dict) -> dict:
    f = features(seller_row)
    profile = delivery_profile(f)
    lang, r_lang = choose_language(f, profile)
    voice, r_voice = choose_voice(f, profile, lang)
    tone, r_tone = choose_tone(f, profile)
    op, op_keys = opening(f, profile, lang)
    obj, r_obj = objection_playbook(f, profile)
    esc, r_esc = escalation_rules(f, profile)
    target = {"brisk": 45, "repair": 40, "consultative": 90, "warm_engaged": 90, "friendly_default": 70}[profile]

    missing = [k for k, v in (("turnover", f["turnover"]), ("nature_of_business", f["nature_raw"]),
                              ("engagement history", f["has_engagement"]), ("bot call history", f["has_history"]),
                              ("company name", f["company"]), ("state", f["state"])) if not v]
    seg = f"{f['region'].replace('_', ' ')} {f['band']} {f['nature']} · {profile.replace('_', ' ')}"
    refs = sorted({x for x in r_lang + r_voice + r_tone + [E(k) for k in op_keys] + r_obj + r_esc if x},
                  key=lambda s: int(s[1:]))
    spec = {
        "seller_id": str(seller_row.get("fk_glusr_usr_id")),
        "seller_snapshot": {
            "company": f["company"], "city": f["city"], "state": f["state"], "locality": f["locality"],
            "business_type": f["business_type"], "turnover": f["turnover"], "nature": f["nature_raw"],
            "top_categories": f["categories"], "segment": seg,
            "history": {"bot_answered": int(f["bot_answered"]), "meetings": int(f["mf"]), "not_interested": int(f["ni"]),
                        "call_later": int(f["cl"]), "early_drops": int(f["early_calls"]),
                        "avg_answered_sec": f["avg_sec"],
                        "flags": [k for k in ("asked_if_talking_to_bot", "showed_frustration",
                                              "already_in_touch_with_executive", "do_not_call_requested") if f[k]]},
            "missing_fields": missing,
        },
        "delivery_profile": {"id": profile, "label": PROFILE_LABEL[profile]},
        "voice": voice,
        "language": lang,
        "tone": tone,
        "plan": {
            "opening": op,
            "personalisation": personalisation(f),
            "objection_playbook": obj,
            "escalation_rules": esc,
            "target_call_sec": target,
        },
        "guardrails": FS.GUARDRAILS,
        "facts": FS.FACTS,
        "evidence_refs": refs,
    }
    if missing:
        spec["confidence_note"] = ("Missing " + ", ".join(missing) + ": defaults used, affected settings marked "
                                   "low confidence; live adaptation corrects them (brief FAQ Q6).")
    return spec


# ------------------------------------------------------------------------------------------- data access
@lru_cache(maxsize=1)
def seller_table():
    import pandas as pd

    from data_prep import load as L
    from data_prep.company import company_names

    def build():
        s = L.sellers()
        c = L.bot_calls().sort_values("call_start_time")
        c["early"] = c.lead_call_duration < 10
        ctx = c.groupby("fk_glusr_usr_id").agg(ctx_early_calls=("early", "sum"),
                                               ctx_last_bucket=("redis_bucket", "last"),
                                               ctx_last_call=("call_start_time", "last")).reset_index()
        df = s.merge(ctx, on="fk_glusr_usr_id", how="left").merge(
            company_names()[["fk_glusr_usr_id", "company"]], on="fk_glusr_usr_id", how="left")
        for col in ("past_objections", "past_questions_asked", "past_dispositions_detailed"):
            df[col] = df[col].astype("string")
        return df
    df = L._cached("seller_table", build)
    return df.set_index("fk_glusr_usr_id", drop=False)


def seller_row(seller_id):
    t = seller_table()
    sid = int(seller_id)
    if sid not in t.index:
        raise SystemExit(f"seller {seller_id} not found")
    r = t.loc[sid]
    if hasattr(r, "iloc") and getattr(r, "ndim", 1) > 1:
        r = r.iloc[0]
    import pandas as pd
    return {k: (None if (not isinstance(v, (list, dict)) and pd.isna(v)) else v) for k, v in r.to_dict().items()}


def write(spec, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{spec['seller_id']}.json"
    p.write_text(json.dumps(spec, indent=1, ensure_ascii=False, default=str))
    return p


def main():
    ap = argparse.ArgumentParser(description="Generate seller persona specs")
    ap.add_argument("--seller-id", help="GLID: builds the seller row from the local PS07 data")
    ap.add_argument("--row", help="path to a seller-row JSON file (see generator/seller_row.schema.json)")
    ap.add_argument("--sample", action="store_true", help="write specs for the curated sample set")
    ap.add_argument("--out", default=str(OUT / "personas"))
    a = ap.parse_args()
    if a.sample:
        from generator.sample import write_sample
        write_sample(a.out)
    elif a.seller_id or a.row:
        spec = generate_persona(json.loads(Path(a.row).read_text()) if a.row else seller_row(a.seller_id))
        print(write(spec, a.out))
        print(json.dumps({k: spec[k] for k in ("delivery_profile", "voice", "language", "tone")}, indent=1,
                         ensure_ascii=False))
    else:
        ap.error("pass --seller-id, --row or --sample")


if __name__ == "__main__":
    main()
