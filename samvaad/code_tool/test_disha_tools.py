"""Local tests for disha_tools.py with the Sarvam SDK harness (no platform needed).

  .venv/bin/python -I samvaad/code_tool/test_disha_tools.py

Live tests call Jev with TYPESAFE_API_KEY from persona-agent/.env.
"""
import asyncio
import importlib.util
import json
import time
from datetime import datetime, timedelta
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

import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
import generator.generate as GEN  # noqa: E402

KEY = next((l.split("=", 1)[1].strip().strip("'\"") for l in (ROOT / ".env").read_text().splitlines()
            if l.startswith("TYPESAFE_API_KEY=")), "")
SECRETS = {"TYPESAFE_API_KEY": KEY}
# Disha's variables plus the ones the code tool adds (set_agent_variable refuses undeclared names).
VARS = ["seller_profile", "seller_id", "seller_name", "company_name", "city", "seller_phone", "gender", "persona_style",
        "seller_history", "persona_notes", "persona_switch_log", "use_case", "use_case_confidence", "use_case_reason",
        "jev_signals", "switch_log_json", "persona_spec", "call_calendar", "call_summary", "disposition", "meeting_date", "meeting_time", "seller_notes", "call_review", "nudge_budget"]
META = EngagementMetadata(interaction_id="local-test", app_id="Disha---Ind-85eb0f30-d809", app_version=1,
                          interaction_language=SarvamToolLanguageName.HINDI)


def start_ctx(profile: str, secrets=SECRETS):
    v = {k: "" for k in VARS}
    v["seller_profile"] = profile
    return SarvamOnStartToolContext(user_identifier="local", agent_variables=v, internal_variables={},
                                    engagement_metadata=META, initial_bot_message=None, initial_state_name="start",
                                    initial_language_name=SarvamToolLanguageName.HINDI, secrets=secrets)


async def on_start(profile: str, secrets=SECRETS):
    t = time.time()
    ctx = await T.OnStart().run(start_ctx(profile, secrets))
    return ctx, time.time() - t


def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    return bool(cond)


async def main():
    ok = True
    profiles = json.loads((ROOT / "outputs" / "demo_profiles.json").read_text())
    last_ctx = None
    for p in profiles:
        print(f"\nOnStart · {p['seller_id']} · {p['label']}")
        ctx, dt = await on_start(p["profile"])
        av = ctx.agent_variables
        sig = json.loads(av["jev_signals"])
        print(f"  use_case={av['use_case']} conf={av['use_case_confidence']} source={sig['source']} {dt:.2f}s")
        print(f"  reason: {av['use_case_reason']}")
        print(f"  opening: {ctx.initial_bot_message}")
        ok &= check(ctx.text_to_speech_config.speaker_id is None and ctx.text_to_speech_config.speaker_name is None,
                    "keeps the platform voice")
        print(f"  pace={ctx.text_to_speech_config.speech_settings.pace} "
              f"style={av['persona_style']} history={av['seller_history']}")
        ok &= check(sig["source"] in ("jev", "jev_borderline"), "Jev answered")
        ps = json.loads(av["persona_spec"])
        prof = json.loads(p["profile"])
        ok &= check(ps["spec"] == json.loads(json.dumps(GEN.generate_persona(GEN.seller_row(prof["seller_id"])), default=str)),
                    "bundled generator == generator/generate.py on the full seller row")
        ap = ps["applied"]
        print(f"  persona: profile={ps['spec']['delivery_profile']['id']} style={ap['persona_style']} pace={ap['pace']} "
              f"lang={ap['start_language']} history={ap['seller_history']} notes={len(av['persona_notes'])} chars "
              f"spec={len(av['persona_spec'])} chars")
        ok &= check(av["use_case"] == json.loads(p["profile"])["rules"]["use_case"] or av["use_case_confidence"] != "high",
                    "high confidence only when Jev and rules agree")
        ok &= check(av["use_case"] in T.USE_CASES, "valid use case")
        kind = ap["opening_kind"]
        ok &= check(ctx.initial_bot_message and (av["company_name"] in ctx.initial_bot_message
                                                 or kind in ("repair", "contact_policy")),
                    f"opening names the company (or is a {kind} opening that leaves identity to phase 1)")
        ok &= check(ps["contract_version"] == 2 and ap["call_calendar"] == av["call_calendar"] and av["call_calendar"],
                    "spec contract v2 with the call calendar")
        ok &= check("Pacing:" not in av["persona_notes"] and f"pace {ap['pace']}" in av["persona_notes"],
                    "notes carry only the final applied pace")
        ok &= check(dt < 3.0, f"OnStart under 3 s ({dt:.2f}s)")
        last_ctx = ctx

    print("\nOnStart · empty profile")
    ctx, _ = await on_start("")
    ok &= check(ctx.agent_variables["use_case"] == "discovery" and ctx.agent_variables["use_case_confidence"] == "low",
                "falls back to discovery, low confidence")
    ok &= check(bool(ctx.initial_bot_message), "still sets an opening line")

    print("\nOnStart · malformed profile")
    ctx, _ = await on_start("{not json")
    ok &= check(ctx.agent_variables["use_case"] == "discovery", "malformed JSON handled")

    print("\nOnStart · Jev unreachable (falls back to rules)")
    url = T.JEV_URL
    T.JEV_URL, T.JEV_TIMEOUT_S = "https://10.255.255.1/v1/systemone", 1.0
    ctx, dt = await on_start(profiles[0]["profile"])
    T.JEV_URL, T.JEV_TIMEOUT_S = url, 4.0
    ok &= check(dt < T.JEV_DEADLINE_S + 0.5, f"fallback within the overall Jev deadline ({dt:.2f}s)")
    rule_uc = json.loads(profiles[0]["profile"])["rules"]["use_case"]
    ok &= check(ctx.agent_variables["use_case"] == rule_uc and ctx.agent_variables["use_case_confidence"] == "low",
                f"uses rules label {rule_uc}, low confidence ({dt:.2f}s)")

    print("\npersona_switch · rush then language")
    tctx = SarvamToolContext(language=SarvamToolLanguageName.HINDI,
                             allowed_languages=[SarvamToolLanguageName.HINDI, SarvamToolLanguageName.ENGLISH],
                             state="start", next_valid_states=[], user_identifier="local",
                             agent_variables=dict(last_ctx.agent_variables),
                             internal_variables=dict(last_ctx.internal_variables), engagement_metadata=META)
    out = await T.PersonaSwitch.model_validate({"signal": "rush", "seller_words": "jaldi bolo, busy hoon",
                                                "change": "one line, two slots",
                                                "reason": "seller is busy, so shortest path to a slot"}).run(tctx)
    out = await T.PersonaSwitch.model_validate({"signal": "language", "seller_words": "Please speak in English",
                                                "change": "switch to English", "reason": "seller asked for English",
                                                "new_language": "english"}).run(out.context)
    ok &= check(str(out.context.get_current_language()) in ("English", "SarvamToolLanguageName.ENGLISH")
                and out.context.internal_variables["switches"][-1].get("language_after") == "English"
                and out.context.internal_variables["switches"][-1].get("status") == "applied",
                "language switch changes the speaking language and is logged")
    sw = out.context.internal_variables["switches"]
    ok &= check(len(sw) == 2 and sw[0]["signal"] == "rush" and sw[0]["t_sec"] is not None, "two timed switches recorded")
    ok &= check(bool(out.message_to_llm), "returns delivery guidance to the model")

    print("\nOnEnd · structured switch log with Jev check")
    turns = [(SarvamInteractionTurnRole.AGENT, "Namaste ji, am I speaking with the company? This is Disha from IndiaMART."),
             (SarvamInteractionTurnRole.USER, "Yes, but I am very busy, tell me quickly."),
             (SarvamInteractionTurnRole.AGENT, "Shall the executive visit tomorrow at 11 am or 4 pm?"),
             (SarvamInteractionTurnRole.USER, "Please speak in English, my Hindi is not good."),
             (SarvamInteractionTurnRole.AGENT, "Sure. Would tomorrow 11 am work?"),
             (SarvamInteractionTurnRole.USER, "Yes, 11 am tomorrow is fine. Bye.")]
    ectx = SarvamOnEndToolContext(
        user_identifier="local", agent_variables=dict(out.context.agent_variables),
        internal_variables=dict(out.context.internal_variables), engagement_metadata=META, secrets=SECRETS,
        interaction_transcript=SarvamInteractionTranscript(
            interaction_transcript=[SarvamInteractionTurn(role=r, en_text=t) for r, t in turns],
            interaction_start_time=datetime.now() - timedelta(minutes=1), interaction_end_time=datetime.now()))
    ectx = await T.OnEnd().run(ectx)
    log = json.loads(ectx.agent_variables["switch_log_json"])
    print("  " + json.dumps(log, ensure_ascii=False)[:600])
    ok &= check(len(log["switches"]) == 2 and all(s.get("verification_status") == "verified" for s in log["switches"]),
                "switches verified by Jev (signal and applied change, anchored to a turn window)")
    ok &= check(log["switches"][1].get("anchor_method") == "fuzzy_match" and log["switches"][1].get("anchor_turn") == 3
                and all(s.get("anchor_method") in ("fuzzy_match", "whole_transcript") for s in log["switches"]),
                "English quote anchored to its seller turn; a Hindi quote of an English transcript falls back to the whole transcript")
    ok &= check(log["turns"] == 6, "turn count")
    review = json.loads(ectx.agent_variables["call_review"])
    print("  review: " + json.dumps({k: review.get(k) for k in ("status", "hindsight_use_case", "agrees",
                                                                  "seller_language", "persona", "fixes")})[:700])
    ok &= check(review["status"] == "reviewed" and review["call_1"].get("use_case") == ectx.internal_variables["use_case"],
                "call reviewed in the same Jev request, against what Call 1 decided")
    ok &= check(review["seller_language"] == "English", "review sees the seller preferred English")
    ok &= check(all(f["kind"] != "contact_policy" for f in review["fixes"]), "fixes never touch the contact policy")

    print("\ndecide · borderline handling")
    base = {"pending_commitment": 0.1, "ignores_leads": 0.2, "upgrade_intent": 0.51, "inactive_business": 0.2}
    ok &= check(T.decide(base, 2.5, "profile_onboarding") == ("profile_onboarding", True), "0.51 upgrade intent defers to rules")
    ok &= check(T.decide({**base, "upgrade_intent": 0.8}, 2.5, "profile_onboarding") == ("free_to_paid", False),
                "clear signal keeps Jev label")
    ok &= check(T.decide(base, 2.5, "lead_engagement") == ("free_to_paid", True), "rules label outside the nearby set is ignored")

    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
