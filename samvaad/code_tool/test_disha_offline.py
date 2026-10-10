"""Deterministic offline tests for disha_tools.py (no network, no .env): Jev is monkeypatched.

  .venv/bin/python -I samvaad/code_tool/test_disha_offline.py
"""
import asyncio
import importlib.util
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sarvam_conv_ai_sdk import (
    EngagementMetadata,
    SarvamInteractionTranscript,
    SarvamInteractionTurn,
    SarvamInteractionTurnRole,
    SarvamOnEndToolContext,
    SarvamOnStartToolContext,
    SarvamToolContext,
    SarvamToolLanguageName,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
_spec = importlib.util.spec_from_file_location("disha_tools", HERE / "disha_tools.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

SECRETS = {"TYPESAFE_API_KEY": "offline-test-key"}
VARS = ["seller_profile", "seller_id", "seller_name", "company_name", "city", "seller_phone", "gender", "persona_style",
        "seller_history", "persona_notes", "persona_switch_log", "use_case", "use_case_confidence", "use_case_reason",
        "jev_signals", "switch_log_json", "persona_spec", "call_calendar", "call_summary", "disposition",
        "meeting_date", "meeting_time", "seller_notes"]
META = EngagementMetadata(interaction_id="offline-test", app_id="Disha---Ind-85eb0f30-d809", app_version=1,
                          interaction_language=SarvamToolLanguageName.HINDI)
NEUTRAL = {"pending_commitment": 0.1, "ignores_leads": 0.1, "upgrade_intent": 0.1, "inactive_business": 0.1}


def answers(sig=None, catalog=2.0):
    sig = {**NEUTRAL, **(sig or {})}
    return {**{k: {"noul": v} for k, v in sig.items()}, "catalog_need": {"score": catalog}}


class FakeJev:
    """Replaces T.jev_call. `result` is returned (or raised if an exception); `delay` seconds of sleep first."""

    def __init__(self, result=None, delay=0.0):
        self.result, self.delay, self.calls = result if result is not None else answers(), delay, 0

    async def __call__(self, api_key, state, questions):
        self.calls += 1
        json.dumps(state, allow_nan=False)  # the real client would send strict JSON
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result(questions) if callable(self.result) else self.result


def start_ctx(profile):
    v = {k: "" for k in VARS}
    v["seller_profile"] = profile
    return SarvamOnStartToolContext(user_identifier="local", agent_variables=v, internal_variables={},
                                    engagement_metadata=META, initial_bot_message=None, initial_state_name="start",
                                    initial_language_name=SarvamToolLanguageName.HINDI, secrets=SECRETS)


async def on_start(profile, jev=None):
    T.jev_call = jev or FakeJev()
    t = time.time()
    ctx = await T.OnStart().run(start_ctx(profile))
    return ctx, time.time() - t


RESULTS = []


def check(cond, msg):
    RESULTS.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + msg)


def base_profile():
    return json.loads(json.loads((ROOT / "outputs" / "demo_profiles.json").read_text())[0]["profile"])


def valid_start(ctx, label):
    av = ctx.agent_variables
    ok = (bool(ctx.initial_bot_message) and av["use_case"] in T.USE_CASES and ctx.text_to_speech_config is not None
          and ctx.text_to_speech_config.speaker_id is None and ctx.text_to_speech_config.speaker_name is None
          and "nan" not in ctx.initial_bot_message.lower().split())
    for k in ("persona_spec", "jev_signals"):
        if av[k]:
            json.loads(av[k], parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    check(ok, f"{label}: safe opening, valid use case, platform voice, strict JSON")


async def test_envelopes():
    print("\nOnStart · malformed envelopes never raise")
    for raw in ["null", "[]", "1", '"hello"', '{"gen":[1]}', '{"rules":[1]}', '{"jev":"x","rules":{"use_case":["a"]}}',
                '{"v":99,"gen":{},"jev":{},"rules":{"use_case":"nonsense"}}', "", "{not json"]:
        ctx, _ = await on_start(raw)
        valid_start(ctx, f"seller_profile={raw!r}")
        check(ctx.agent_variables["use_case"] == "discovery", f"  {raw!r} -> discovery")
    ctx, _ = await on_start('{"v":99,"seller_id":5,"gen":{"company":"Acme"},"jev":{},"rules":{}}')
    spec = json.loads(ctx.agent_variables["persona_spec"])
    check(any("unknown profile version" in i for i in spec["input_issues"]), "unknown version accepted but recorded")


async def test_nonfinite():
    print("\nOnStart · NaN / inf / bool values treated as missing")
    p = base_profile()
    p["gen"].update(company=float("nan"), seller_city=float("inf"), bot_answered=float("inf"),
                    calls_meeting_fixed=float("nan"), eng_enq_received_90d=float("inf"), avg_answered_call_sec=True,
                    eng_cqs=float("-inf"))
    p["jev"]["catalog"]["products_listed"] = float("nan")
    raw = json.dumps(p)  # Python emits NaN/Infinity tokens, which json.loads accepts
    ctx, _ = await on_start(raw, FakeJev(answers({"upgrade_intent": 0.8})))
    valid_start(ctx, "NaN/inf company and counts")
    av = ctx.agent_variables
    check(av["company_name"] == "" and "nan" not in ctx.initial_bot_message.lower() and "inf" not in ctx.initial_bot_message.lower(),
          f"no NaN company spoken: {ctx.initial_bot_message!r}")
    spec = json.loads(av["persona_spec"])
    check(spec["spec"] is not None and spec["spec"]["seller_snapshot"]["company"] is None,
          "generator still ran with the bad fields treated as missing")
    check("Infinity" not in av["persona_spec"] and "NaN" not in av["persona_spec"], "persona_spec is strict JSON")
    gen_list = base_profile()
    gen_list["gen"]["company"] = ["A", "B"]
    gen_list["gen"]["seller_city"] = None
    ctx, _ = await on_start(json.dumps(gen_list))
    check(ctx.agent_variables["company_name"] == "" and "['A'" not in ctx.initial_bot_message, "list company treated as missing")


async def test_invalid_jev():
    print("\nOnStart · invalid Jev answers -> rules fallback, low confidence")
    rule = base_profile()["rules"]["use_case"]
    bad = [answers({"upgrade_intent": float("nan")}), answers({"ignores_leads": 1.7}), answers(catalog=float("inf")),
           answers(catalog=3.5), {"pending_commitment": {"noul": 0.2}}, {"answers": 1}, [], answers({"upgrade_intent": True}),
           answers({"upgrade_intent": "0.9"}), RuntimeError("HTTP 500")]
    for i, b in enumerate(bad):
        ctx, _ = await on_start(json.dumps(base_profile()), FakeJev(b))
        av = ctx.agent_variables
        sig = json.loads(av["jev_signals"])
        check(av["use_case"] == rule and av["use_case_confidence"] == "low" and sig["source"] == "rules_fallback",
              f"bad answer #{i} -> rules {rule}, low confidence")


async def test_slow_jev():
    print("\nOnStart · Jev slower than the deadline")
    ctx, dt = await on_start(json.dumps(base_profile()), FakeJev(answers(), delay=5.0))
    check(json.loads(ctx.agent_variables["jev_signals"])["source"] == "rules_fallback" and dt < T.JEV_DEADLINE_S + 0.15,
          f"fallback after {dt:.2f}s (deadline {T.JEV_DEADLINE_S}s)")


def test_decide():
    print("\ndecide · joint margins and exact boundaries")
    sig = {**NEUTRAL, "pending_commitment": 0.51, "ignores_leads": 0.51}
    d = T.decide_detail(sig, 2.0, "profile_onboarding")
    check(T.decide(sig, 2.0, "profile_onboarding") == ("profile_onboarding", True) and d["rule_used"]
          and "profile_onboarding" in d["candidates"] and d["jev_label"] == "warm_followup",
          f"two signals at 0.51 can both flip: rules decide ({d})")
    check(T.decide({**NEUTRAL, "upgrade_intent": 0.55}, 2.5, "profile_onboarding") == ("profile_onboarding", True),
          "exactly 0.55 is inside the margin")
    check(T.decide({**NEUTRAL, "upgrade_intent": 0.45}, 2.5, "free_to_paid") == ("free_to_paid", True),
          "exactly 0.45 is inside the margin")
    check(T.decide({**NEUTRAL, "upgrade_intent": 0.56}, 2.5, "profile_onboarding") == ("free_to_paid", False),
          "0.56 is outside the margin")
    d = T.decide_detail({**NEUTRAL, "upgrade_intent": 0.51}, 2.5, "lead_engagement")
    check(d["use_case"] == "free_to_paid" and d["borderline"] and not d["rule_used"],
          "borderline but rule not plausible: Jev label, rule_used False")
    check(T.decide({**NEUTRAL}, 1.35, "profile_onboarding") == ("profile_onboarding", True), "catalog 1.35 within 0.15 of 1.5")
    check(T.decide({**NEUTRAL, "upgrade_intent": 0.504}, 2.5, "profile_onboarding")[0] == "profile_onboarding",
          "unrounded scores used (0.504)")


async def test_reason_text():
    print("\nOnStart · reason says 'the rules decided' only when they did")
    p = base_profile()
    p["rules"]["use_case"] = "lead_engagement"
    ctx, _ = await on_start(json.dumps(p), FakeJev(answers({"upgrade_intent": 0.51}, 2.5)))
    r = ctx.agent_variables["use_case_reason"]
    check(ctx.agent_variables["use_case"] == "free_to_paid" and "the rules decided" not in r and "stands" in r, r)
    p["rules"]["use_case"] = "profile_onboarding"
    ctx, _ = await on_start(json.dumps(p), FakeJev(answers({"upgrade_intent": 0.51}, 2.5)))
    check(ctx.agent_variables["use_case"] == "profile_onboarding" and "the rules decided" in ctx.agent_variables["use_case_reason"],
          "rule used -> 'the rules decided'")


async def test_contact_policy():
    print("\nOnStart · contact policy")
    for pol in ("SUPPRESS", "ROUTE_TO_HUMAN"):
        p = base_profile()
        p["rules"].update(contact_policy=pol, gate_reason="dnc_requested")
        jev = FakeJev(answers({"upgrade_intent": 0.9}))
        ctx, _ = await on_start(json.dumps(p), jev)
        av = ctx.agent_variables
        notes = av["persona_notes"]
        want = ("placed by mistake and they will not be called again" if pol == "SUPPRESS"
                else "an IndiaMART executive will contact them personally")
        check(notes.startswith(f"Contact policy: {pol} (dnc_requested). Do not pitch.") and want in notes.splitlines()[0]
              and "called to apologise" not in notes.replace("Never say you called to apologise", ""),
              f"{pol}: notes start with the policy line and its own close")
        check(av["use_case"] == "discovery" and jev.calls == 0, f"{pol}: discovery, Jev not called")
        check("Objection playbook" not in notes and "paid services" not in ctx.initial_bot_message
              and "do minute" not in ctx.initial_bot_message, f"{pol}: no pitch: {ctx.initial_bot_message!r}")
    p = base_profile()
    p["rules"].update(contact_policy="COOL_OFF", gate_reason="recent_refusal")
    ctx, _ = await on_start(json.dumps(p), FakeJev(answers({"upgrade_intent": 0.9})))
    check("Contact policy: COOL_OFF; keep it to one soft ask." in ctx.agent_variables["persona_notes"], "COOL_OFF note line")


async def test_calendar():
    print("\ncall_calendar · fixed Friday 2026-10-09")
    real = T._now_ist
    T._now_ist = lambda: datetime(2026, 10, 9, 14, 30, tzinfo=T.IST)
    try:
        ctx, _ = await on_start(json.dumps(base_profile()))
    finally:
        T._now_ist = real
    cal = ctx.agent_variables["call_calendar"]
    print("  " + cal[:300])
    check("aaj / today = Friday (Shukravaar) 09 Oct 2026" in cal, "today is Friday 09 Oct 2026")
    check("kal / tomorrow = Saturday (Shanivaar) 10 Oct 2026" in cal, "tomorrow is Saturday 10 Oct")
    check("parson / day after tomorrow = Sunday (Ravivaar) 11 Oct 2026" in cal, "day after tomorrow is Sunday 11 Oct")
    check("Sunday falls on Sunday (Ravivaar) 11 Oct 2026" in cal and "never move a date silently" in cal, "Sunday rule")
    check(cal.count(" = ") == 8, "today plus the next 7 days")
    utc_late = T.call_calendar(datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc))  # 01:30 IST on the 10th
    check("aaj / today = Saturday (Shanivaar) 10 Oct 2026" in utc_late, "UTC evening is the next IST day")
    check("Sunday" in T.call_calendar(datetime(2026, 12, 29, 10, 0, tzinfo=T.IST)).split("in 7 days")[0]
          and "Jan 2027" in T.call_calendar(datetime(2026, 12, 29, 10, 0, tzinfo=T.IST)), "year rollover")


async def test_openings_and_language():
    print("\nOnStart · openings assert only facts on record; language start")
    p = base_profile()
    p["gen"].update(ctx_last_bucket="PUA", calls_call_later=0, past_dispositions_detailed=None, eng_enq_received_90d=0)
    p["jev"]["indiamart_call_history"]["why_indiamart_called_most_recent_first"] = ["Profile improvement"]
    for k in list(p["jev"]["buyer_demand_and_response"]):
        if "enquiries_received" in k:
            p["jev"]["buyer_demand_and_response"][k] = 0
    for uc, sig, phrase in (("free_to_paid", {"upgrade_intent": 0.9}, "paid services"),
                            ("warm_followup", {"pending_commitment": 0.9}, "aapke kehne par"),
                            ("lead_engagement", {"ignores_leads": 0.9}, "aa rahi hain")):
        p["rules"]["use_case"] = uc
        ctx, _ = await on_start(json.dumps(p), FakeJev(answers(sig)))
        check(ctx.agent_variables["use_case"] == uc and phrase not in ctx.initial_bot_message,
              f"{uc} without evidence: neutral hook ({ctx.initial_bot_message})")
    p2 = base_profile()
    p2["gen"].update(calls_call_later=2)
    p2["rules"]["use_case"] = "warm_followup"
    ctx, _ = await on_start(json.dumps(p2), FakeJev(answers({"pending_commitment": 0.9})))
    notes = ctx.agent_variables["persona_notes"]
    check(("aapke kehne par" in notes.lower() or "asked to talk later" in notes) and len(ctx.initial_bot_message) < 110,
          f"warm_followup with a callback on record: short opening, callback referenced in the briefing ({ctx.initial_bot_message})")
    # Tamil Nadu seller -> generator Tamil template exists -> Tamil start, purpose stated, no meeting pitch for reactivation
    p3 = base_profile()
    p3["gen"].update(seller_state="Tamil Nadu", seller_city="Chennai", business_type="Proprietorship",
                     annual_turnover="0 - 40 L")
    p3["rules"]["use_case"] = "reactivation"
    ctx, _ = await on_start(json.dumps(p3), FakeJev(answers({"inactive_business": 0.9})))
    lang = str(ctx.initial_language_name)
    print(f"  start={lang} opening={ctx.initial_bot_message!r}")
    if "Tamil" in lang or "English" in lang:
        check("meeting" not in ctx.initial_bot_message.lower(), "non-Hindi reactivation opening has no meeting pitch")
    else:
        check("Tamil" in ctx.agent_variables["persona_notes"], "Hindi start notes say ready to switch to Tamil")
    # Gujarat seller: no Gujarati template -> Hindi start, ready to switch to Gujarati
    p4 = base_profile()
    p4["gen"].update(seller_state="Gujarat", seller_city="Surat")
    ctx, _ = await on_start(json.dumps(p4), FakeJev(answers({"upgrade_intent": 0.9})))
    check(ctx.initial_language_name == SarvamToolLanguageName.HINDI, "Gujarat seller starts in Hindi")
    spec = json.loads(ctx.agent_variables["persona_spec"])["spec"]
    if spec["language"]["language_code"] == "gu-IN":
        check("ready to switch to Gujarati" in ctx.agent_variables["persona_notes"], "notes: ready to switch to Gujarati")


async def test_notes_delivery():
    print("\nOnStart · notes carry only final delivery values")
    p = base_profile()
    p["rules"]["use_case"] = "reactivation"
    ctx, _ = await on_start(json.dumps(p), FakeJev(answers({"inactive_business": 0.9})))
    notes = ctx.agent_variables["persona_notes"]
    ps = json.loads(ctx.agent_variables["persona_spec"])
    pace = ctx.text_to_speech_config.speech_settings.pace
    gen_pace = ps["spec"]["voice"]["pace"]
    delivery = [l for l in notes.splitlines() if l.startswith("Delivery:")]
    check(len(delivery) == 1 and f"pace {pace}" in delivery[0] and "Pacing:" not in notes, delivery[0][:160] if delivery else "no Delivery line")
    check(f"pace {gen_pace} " not in notes or gen_pace == pace, "pre-adjustment pace not printed")
    check("(adjusted for call purpose)" in notes and ps["applied"]["pace"] == pace and ps["contract_version"] == 2
          and ps["applied"]["call_calendar"], "profile label marked adjusted; spec applied = final values")


def tool_ctx(allowed=(SarvamToolLanguageName.HINDI, SarvamToolLanguageName.ENGLISH), internal=None):
    return SarvamToolContext(language=SarvamToolLanguageName.HINDI, allowed_languages=list(allowed), state="start",
                             next_valid_states=[], user_identifier="local", agent_variables={k: "" for k in VARS},
                             internal_variables=internal if internal is not None else {"t0": time.time() - 12, "switches": []},
                             engagement_metadata=META)


async def switch(ctx, **kw):
    kw.setdefault("seller_words", "words")
    kw.setdefault("change", "a change")
    kw.setdefault("reason", "a reason")
    return await T.PersonaSwitch.model_validate(kw).run(ctx)


async def test_persona_switch():
    print("\npersona_switch · all signals and language targets")
    ctx = tool_ctx()
    for s in ("rush", "confusion", "frustration", "interest", "bot_question"):
        out = await switch(ctx, signal=s)
        ctx = out.context
        check(out.message_to_llm and ctx.internal_variables["switches"][-1]["status"] == "logged", f"{s} logged")
    out = await switch(ctx, signal="language", new_language="en-IN", seller_words="English please")
    e = out.context.internal_variables["switches"][-1]
    check(e["applied"] and e["status"] == "applied" and e["language_before"] == "Hindi" and e["language_after"] == "English"
          and out.context.language == SarvamToolLanguageName.ENGLISH, "en-IN applied")
    out = await switch(tool_ctx(), signal="language", new_language="english")
    check(out.context.language == SarvamToolLanguageName.ENGLISH, "alias 'english' applied")
    out = await switch(tool_ctx(), signal="language", new_language="Gujarati")
    e = out.context.internal_variables["switches"][-1]
    check(not e["applied"] and e["status"] == "language_not_allowed" and out.context.language == SarvamToolLanguageName.HINDI
          and "could not be switched" in out.message_to_llm and "Keep speaking Hindi" in out.message_to_llm,
          "Gujarati not allowed: not applied, Hindi kept, model told explicitly")
    out = await switch(tool_ctx(), signal="language")
    check(out.context.internal_variables["switches"][-1]["status"] == "no_target", "language without target -> no_target")
    out = await switch(tool_ctx(), signal="language", new_language="Klingon")
    check(out.context.internal_variables["switches"][-1]["status"] == "no_target", "unknown language -> no_target")
    allowed = [SarvamToolLanguageName.HINDI, SarvamToolLanguageName.ODIA, SarvamToolLanguageName.TAMIL]
    out = await switch(tool_ctx(allowed), signal="language", new_language="oriya")
    check(out.context.language == SarvamToolLanguageName.ODIA, "alias 'oriya' -> Odia")
    out = await switch(tool_ctx(allowed), signal="frustration", new_language="ta-IN")
    e = out.context.internal_variables["switches"][-1]
    check(e["applied"] and e["signal"] == "frustration" and e["language_after"] == "Tamil", "combined signal + language")
    for bad in ({"t0": None, "switches": None}, {"t0": "x", "switches": "corrupt"}, {}):
        out = await switch(tool_ctx(internal=dict(bad)), signal="rush")
        sw = out.context.internal_variables["switches"]
        check(len(sw) == 1 and sw[0]["t_sec"] is None, f"corrupt internal state {bad} tolerated")
    try:
        T.PersonaSwitch.model_validate({"signal": "rush", "seller_words": "x", "change": "y"})
        check(False, "reason is required")
    except Exception:
        check(True, "reason is required")


def end_ctx(internal, turns, start, end):
    return SarvamOnEndToolContext(
        user_identifier="local", agent_variables={k: "" for k in VARS}, internal_variables=internal,
        engagement_metadata=META, secrets=SECRETS,
        interaction_transcript=SarvamInteractionTranscript(
            interaction_transcript=[SarvamInteractionTurn(role=r, en_text=t) for r, t in turns] if turns is not None else None,
            interaction_start_time=start, interaction_end_time=end))


TURNS = [(SarvamInteractionTurnRole.AGENT, "Namaste, this is Disha from IndiaMART."),
         (SarvamInteractionTurnRole.USER, "I am very busy, tell me quickly."),
         (SarvamInteractionTurnRole.AGENT, "Tomorrow 11 am or 4 pm?"),
         (SarvamInteractionTurnRole.USER, "Please speak in English."),
         (SarvamInteractionTurnRole.AGENT, "Sure, tomorrow 11 am works?")]
SW = [{"t_sec": 3.0, "signal": "rush", "seller_words": "very busy, tell me quickly", "change": "one line", "reason": "busy"},
      {"t_sec": 9.0, "signal": "language", "seller_words": "speak in English", "change": "English", "reason": "asked"}]


async def test_on_end():
    print("\nOnEnd · base log always written")
    now = datetime.now(timezone.utc)
    cases = [
        ("switches None", {"switches": None, "use_case": None}, TURNS, now - timedelta(minutes=1), now, FakeJev()),
        ("empty transcript", {"switches": SW}, [], now - timedelta(minutes=1), now, FakeJev()),
        ("no transcript", {"switches": SW}, None, now - timedelta(minutes=1), now, FakeJev()),
        ("tz mismatch", {"switches": SW, "use_case": "free_to_paid"}, TURNS, datetime.now() - timedelta(minutes=1), now,
         FakeJev(RuntimeError("down"))),
        ("verification raises", {"switches": SW, "use_case": "reactivation"}, TURNS, now - timedelta(minutes=1), now,
         FakeJev(RuntimeError("down"))),
        ("verification slow", {"switches": SW}, TURNS, now - timedelta(minutes=1), now, FakeJev({}, delay=60)),
        ("verification invalid", {"switches": SW}, TURNS, now - timedelta(minutes=1), now,
         FakeJev({"s0_signal": {"noul": float("nan")}, "s0_applied": {"noul": 0.9}})),
    ]
    real_deadline = T.JEV_VERIFY_DEADLINE_S
    T.JEV_VERIFY_DEADLINE_S = 0.3
    try:
        for name, internal, turns, start, end, jev in cases:
            T.jev_call = jev
            ctx = await T.OnEnd().run(end_ctx(internal, turns, start, end))
            log = json.loads(ctx.agent_variables["switch_log_json"])
            exp_sw = len(internal["switches"] or [])
            statuses = {s.get("verification_status") for s in log["switches"]}
            check(len(log["switches"]) == exp_sw and log["turns"] == len(turns or [])
                  and statuses <= {"unavailable", "invalid_response"},
                  f"{name}: base log kept ({len(log['switches'])} switches, {log['turns']} turns, "
                  f"duration {log['duration_sec']}, {statuses or '-'})")
            if name == "tz mismatch":
                check(log["duration_sec"] is None and "duration_unavailable" in log, "tz mismatch -> duration_unavailable")
            if name == "verification invalid":
                check(statuses == {"invalid_response"}, "invalid answers -> invalid_response")
    finally:
        T.JEV_VERIFY_DEADLINE_S = real_deadline

    def ok_answers(questions):
        return {q: {"noul": 0.8} for q in questions}
    T.jev_call = FakeJev(ok_answers)
    ctx = await T.OnEnd().run(end_ctx({"switches": SW, "use_case": "free_to_paid"}, TURNS, now - timedelta(seconds=75), now))
    log = json.loads(ctx.agent_variables["switch_log_json"])
    check(all(s["verification_status"] == "verified" and s["verified_signal"] == 0.8 and s["verified_applied"] == 0.8
              for s in log["switches"]) and log["duration_sec"] == 75.0, "verified switches with turn anchors")
    check([s["anchor_turn"] for s in log["switches"]] == [1, 3], f"anchors {[s.get('anchor_turn') for s in log['switches']]}")


def test_static():
    print("\nbundle · platform constraints")
    src = (HERE / "disha_tools.py").read_text()
    check('context.get_secret("TYPESAFE_API_KEY")' in src, "secret name stays a literal")
    check("speaker_id=" not in src and "speaker_name=" not in src, "never sets speaker_id / speaker_name")
    imports = {l.split()[1].split(".")[0] for l in src.splitlines() if l.startswith(("import ", "from "))}
    check(imports <= {"asyncio", "difflib", "itertools", "json", "math", "time", "datetime", "typing", "httpx", "pydantic",
                      "sarvam_conv_ai_sdk", "re", "functools"}, f"imports: {sorted(imports)}")
    for name in ("decide", "no_data", "_unknownify", "REFERENCE", "NOULS", "jev_questions", "jev_call", "label_from_signals",
                 "decide_detail"):
        check(hasattr(T, name), f"public name {name}")


async def main():
    await test_envelopes()
    await test_nonfinite()
    await test_invalid_jev()
    await test_slow_jev()
    test_decide()
    await test_reason_text()
    await test_contact_policy()
    await test_calendar()
    await test_openings_and_language()
    await test_notes_delivery()
    await test_persona_switch()
    await test_on_end()
    test_static()
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} checks passed")
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
