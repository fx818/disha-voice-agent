"""Export paste-ready `seller_profile` JSON for demo sellers (the Disha code tool's only input).

Each profile has three parts:
  gen: the flat seller row the persona generator reads (generator.generate.seller_row, trimmed to the fields it uses)
  jev: the Jev state (same builder as the holdout validation, full history up to the end of the data)
  rules: the rule-based use case and contact gate from outputs/segmentation/seller_use_case.parquet (cross-check)

Usage:
  .venv/bin/python -I tools/export_profiles.py               # pick 4–5 contrasting demo sellers
  .venv/bin/python -I tools/export_profiles.py --ids 1 2 3     # explicit sellers
Writes outputs/demo_profiles.json, outputs/demo_profiles.md and outputs/demo_set.md.
Use --offline-preview only for explicitly unverified candidates when Jev is inaccessible.
"""
import argparse
import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data_prep.load import product_gaps  # noqa: E402
from generator.generate import seller_row, generate_persona, features, delivery_profile, choose_language, seller_table  # noqa: E402

SEG = ROOT / "outputs" / "segmentation"
CACHE = ROOT / "outputs" / "cache"
REF_TIME = pd.Timestamp("2026-10-01")  # day after the last call in the data
_spec = importlib.util.spec_from_file_location("j01", SEG / "scripts" / "j01_jev_validate.py")
j01 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(j01)

# Fields generator.generate.features() and persona_to_samvaad read.
GEN_FIELDS = [
    "fk_glusr_usr_id", "company", "seller_state", "seller_city", "seller_locality", "annual_turnover", "business_type",
    "nature_of_business", "top_category_1", "top_category_2", "top_category_3", "top_category_group",
    "gst_registration_year", "eng_pickup_ratio_1yr", "eng_enq_received_90d", "eng_enq_replies_90d", "eng_cqs",
    "eng_product_count", "bot_answered", "bot_attempts", "avg_answered_call_sec", "calls_meeting_fixed",
    "calls_not_interested", "calls_call_later", "ctx_early_calls", "ctx_last_bucket", "past_dispositions_detailed",
    "past_objections", "past_questions_asked", "asked_if_talking_to_bot", "showed_frustration",
    "already_in_touch_with_executive", "do_not_call_requested",
]
SECOND_LANGUAGE_STATES = ["Tamil Nadu", "Karnataka", "Kerala", "Andhra Pradesh"]


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item"):  # numpy scalar
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


DEMO_SLOTS = [
    ("upgrade", ["free_to_paid"], ["brisk", "warm_engaged"], ["hi-IN"]),
    ("reactivation", ["reactivation"], ["consultative", "repair"], ["hi-IN"]),
    ("onboarding", ["profile_onboarding"], ["friendly_default", "warm_engaged"], ["hi-IN"]),
    ("second language", ["lead_engagement", "warm_followup", "profile_onboarding", "free_to_paid", "reactivation"],
     [], ["ta-IN", "en-IN"]),
    ("repair", ["lead_engagement", "warm_followup"], ["repair"], ["hi-IN", "ta-IN", "en-IN"]),
]


def load_tool():
    import time
    for attempt in range(2):
        try:
            spec = importlib.util.spec_from_file_location("disha_tools", ROOT / "samvaad/code_tool/disha_tools.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except (ImportError, SyntaxError):
            if attempt:
                raise
            print("Built tool is changing; retrying import in one minute.", flush=True)
            time.sleep(60)


def candidates(use_case: str, states=None, n=None) -> list[int]:
    """Current allowed, named sellers with >=30 seconds of real history and no wrong-number summary."""
    uc = pd.read_parquet(SEG / "seller_use_case.parquet")
    sel = pd.read_parquet(CACHE / "seller_table.parquet")
    c = uc[(uc.use_case == use_case) & (uc.contact_policy == "OK_TO_CALL")].merge(sel, on="fk_glusr_usr_id")
    c = c[c.company.fillna("").str.strip().ne("")]
    if states:
        c = c[c.seller_state.isin(states)]
    calls = pd.read_parquet(CACHE / "bot_calls.parquet")
    talked = set(calls.loc[calls.lead_call_duration >= 30, "fk_glusr_usr_id"])
    wrong = set(calls.loc[calls.lead_call_summary.fillna("").str.contains(r"wrong[ -]?number", case=False), "fk_glusr_usr_id"])
    c = c[c.fk_glusr_usr_id.isin(talked - wrong)]
    ev = pd.read_parquet(SEG / "work/j02_eval.parquet")
    agreed = set(ev.loc[(ev.rule_use_case == use_case) & (ev.jev_v2_signals == use_case), "seller_id"])
    c = c.assign(agreed=c.fk_glusr_usr_id.isin(agreed)).sort_values(
        ["agreed", "bot_answered", "fk_glusr_usr_id"], ascending=[False, False, True])
    return [int(x) for x in c.fk_glusr_usr_id.head(n) if pd.notna(x)] if n else [int(x) for x in c.fk_glusr_usr_id]


def jev_result(profile_text, tool):
    import asyncio
    key = next(l.split("=", 1)[1].strip().strip("'\"") for l in (ROOT / ".env").read_text().splitlines()
               if l.startswith("TYPESAFE_API_KEY="))
    profile = json.loads(profile_text)
    if tool.no_data(profile["jev"]):
        return {"use_case": "discovery", "borderline": True, "signals": {}, "catalog_need": None}
    state = tool._unknownify(profile["jev"])
    state["reference_typical_seller"] = tool.REFERENCE
    ans = asyncio.run(tool.jev_call(key, state, tool.jev_questions()))
    signals = {k: round(float(ans[k]["noul"]), 2) for k in tool.NOULS}
    catalog = round(float(ans["catalog_need"]["score"]), 2)
    uc, borderline = tool.decide(signals, catalog, profile["rules"]["use_case"])
    return {"use_case": uc, "borderline": borderline, "signals": signals, "catalog_need": catalog}


def live_verify(profile):
    # Bound the whole worker: DNS resolution can outlive httpx's timeout during asyncio shutdown.
    import subprocess
    try:
        proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--verify-profile"],
                              input=profile, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        raise SystemExit("Live Jev verification timed out (including DNS). No verified exports written.")
    for line in proc.stdout.splitlines():
        if line.startswith("JEV_RESULT=") and proc.returncode == 0:
            return json.loads(line.split("=", 1)[1])
    raise SystemExit("Live Jev unavailable. No verified exports written; --offline-preview creates marked provisional outputs.")


def describe(prof, spec, tool):
    uc = json.loads(prof["profile"])["rules"]["use_case"]
    code = spec["language"]["language_code"]
    language = {"hi-IN": "Hindi", "ta-IN": "Tamil", "en-IN": "English"}.get(code, "Hindi")
    adjustment = getattr(tool, "USE_CASE_DELIVERY", {}).get(uc, (0,))[0]
    pace = round(min(2.0, max(0.85, spec["voice"]["pace"] + adjustment)), 2)
    prof.update(delivery_profile=spec["delivery_profile"]["id"], language_code=code,
                start_language=language, final_pace=pace)
    prof["label"] = f"{uc} · {prof['delivery_profile']} · {language} · pace {pace:.2f}"


@lru_cache(maxsize=1)
def screening_rows():
    # Avoid repeated .loc scans on the source table's non-unique index.
    rows = seller_table().drop_duplicates("fk_glusr_usr_id").to_dict("records")
    return {int(r["fk_glusr_usr_id"]): {k: _clean(v) for k, v in r.items()} for r in rows}


def pick_demo(offline=False) -> list[dict]:
    tool = load_tool()
    out = []
    for slot, cases, personas, languages in DEMO_SLOTS:
        print(f"Screening {slot}", flush=True)
        pool = []
        used_ids = {p["seller_id"] for p in out}
        used_personas = {p["delivery_profile"] for p in out}
        used_cases = {json.loads(p["profile"])["rules"]["use_case"] for p in out}
        for uc in cases:
            counts = {}
            eligible = candidates(uc, SECOND_LANGUAGE_STATES if slot == "second language" else None)
            print(f"  {uc}: {len(eligible)} eligible sellers", flush=True)
            for sid in eligible:
                if sid in used_ids:
                    continue
                row = screening_rows()[sid]
                f = features(row)
                dp = delivery_profile(f)
                if counts.get(dp, 0) >= 15:
                    continue
                language, _ = choose_language(f, dp)
                if language["language_code"] not in languages:
                    continue
                counts[dp] = counts.get(dp, 0) + 1
                match = not personas or dp in personas
                pool.append((not match, dp in used_personas, uc in used_cases, sid, row))
        pool.sort(key=lambda x: x[:3])
        # Reserve three attempts for a relaxed persona if the first twelve fail.
        strict = [x for x in pool if not x[0]]
        relaxed = [x for x in pool if x[0]]
        trials = strict[:15] if slot == "repair" else strict[:12] + (relaxed[:3] if relaxed else strict[12:15])
        for mismatch, _, _, sid, row in trials:
            spec = generate_persona(seller_row(sid))
            prof = build_profiles([(sid, "")])[0]
            if prof["bytes"] > 3500:
                print(f"  {sid}: skipped {prof['bytes']} bytes", flush=True)
                continue
            result = ({"use_case": json.loads(prof["profile"])["rules"]["use_case"],
                       "borderline": None, "signals": {}, "catalog_need": None,
                       "status": "not_verified_network_unavailable"} if offline else live_verify(prof["profile"]))
            uc = json.loads(prof["profile"])["rules"]["use_case"]
            print(f"{slot}: {sid} {spec['delivery_profile']['id']} → {result['use_case']} borderline={result['borderline']}", flush=True)
            if result["use_case"] != uc or result["borderline"]:
                continue
            describe(prof, spec, tool)
            prof["verification"] = result
            prof["relaxation"] = f"{slot}: requested {personas}; selected {prof['delivery_profile']}" if mismatch else None
            out.append(prof)
            break
        else:
            if slot == "repair":
                print("Optional repair slot omitted: no eligible repair candidate passed selection within 15 attempts.")
                continue
            raise SystemExit(f"No confirmed candidate for {slot} within 15 attempts")
    return out


def build_profiles(items: list[tuple[int, str]]) -> list[dict]:
    ids = {sid for sid, _ in items}
    sel = pd.read_parquet(CACHE / "sellers.parquet", columns=[
        "fk_glusr_usr_id", "seller_state", "business_type", "annual_turnover", "nature_of_business",
        "gst_registration_year", "top_category_1", "top_category_group", "num_categories"]).set_index("fk_glusr_usr_id")
    b = pd.read_parquet(SEG / "B_seller_segments.parquet").set_index("fk_glusr_usr_id")
    bucket_map = json.loads((SEG / "A_bucket_map.json").read_text())
    rules = pd.read_parquet(SEG / "seller_use_case.parquet",
                            columns=["fk_glusr_usr_id", "use_case", "contact_policy", "reason"]).set_index("fk_glusr_usr_id")
    calls = pd.read_parquet(CACHE / "bot_calls.parquet", columns=[
        "attempt_id", "fk_glusr_usr_id", "redis_bucket", "call_start_time", "disposition_label",
        "lead_call_duration", "lead_call_summary"])
    calls = calls[calls.fk_glusr_usr_id.isin(ids)].sort_values("call_start_time")
    obj = pd.read_parquet(SEG / "work" / "ev_objections.parquet").merge(calls[["attempt_id", "fk_glusr_usr_id"]], on="attempt_id")
    qs = pd.read_parquet(SEG / "work" / "ev_questions.parquet").merge(calls[["attempt_id", "fk_glusr_usr_id"]], on="attempt_id")
    gaps = product_gaps().set_index("fk_glusr_usr_id")

    out = []
    for sid, label in items:
        row = seller_row(sid)
        gen = {k: _clean(row.get(k)) for k in GEN_FIELDS}
        p = sel.loc[sid] if sid in sel.index else None
        jev = j01.make_state(p, b.loc[sid], calls[calls.fk_glusr_usr_id == sid],
                             obj[obj.fk_glusr_usr_id == sid], qs[qs.fk_glusr_usr_id == sid], bucket_map, REF_TIME)
        if sid in gaps.index:  # separate snapshot: its three counts are only quoted together, never mixed with products_listed
            g = gaps.loc[sid]
            jev["catalog"]["product_snapshot"] = {"products": int(g.total_product_count),
                                                  "without_image": int(g.products_without_image),
                                                  "without_price": int(g.products_without_price)}
        r = rules.loc[sid]
        profile = {"v": 1, "seller_id": sid, "gen": gen, "jev": jev,
                   "rules": {"use_case": r.use_case, "contact_policy": r.contact_policy, "gate_reason": r.reason}}
        def encode():
            return json.dumps(profile, ensure_ascii=False, separators=(",", ":"), default=str, allow_nan=False)
        text = encode()
        # Bound only narrative excerpts; preserve generator inputs and structured Jev evidence.
        history = jev.get("indiamart_call_history", {})
        excerpts = [(r, "summary") for r in history.get("recent_call_summaries_newest_first", [])]
        for key in ("objections_raised", "questions_seller_asked"):
            excerpts += [(history[key], i) for i in range(len(history.get(key, [])))]
        while len(text.encode()) > 3500:
            editable = [(container, key) for container, key in excerpts
                        if isinstance(container[key], str) and len(container[key]) > 101]
            if not editable:
                break
            container, key = max(editable, key=lambda item: len(item[0][item[1]].encode()))
            container[key] = container[key][:max(100, len(container[key]) - 40)].rstrip("…") + "…"
            text = encode()
        out.append({"seller_id": sid, "label": label, "company": gen.get("company"), "state": gen.get("seller_state"),
                    "city": gen.get("seller_city"), "bytes": len(text.encode()), "profile": text})
    return out



def demo_notes(profiles, offline=False):
    """Capture actual built OnStart output using the same SDK context as the local harness."""
    import asyncio
    harness_spec = importlib.util.spec_from_file_location("disha_demo_harness", ROOT / "samvaad/code_tool/test_disha_tools.py")
    harness = importlib.util.module_from_spec(harness_spec)
    harness_spec.loader.exec_module(harness)
    lines = ["# Disha demo set", "",
             ("**PROVISIONAL: live Jev verification was blocked by DNS/network access to api.typesafe.ai. "
              "Use cases below are current rules labels, not live-confirmed labels. Run the exporter without "
              "--offline-preview from a network-enabled environment before presenting this as a verified demo set.**"
              if offline else "Live Jev and OnStart both confirmed these sellers."), "",
             "The default selection uses the current rules label and rejects borderline/disagreeing live Jev results. "
             "Every selected seller is OK_TO_CALL, has a company name and a call lasting at least 30 seconds, "
             "and has no wrong-number summary. Profiles are capped at 3,500 UTF-8 bytes.", "",
             "Start language and pace below are checked with the built OnStart SDK harness. "
             "These are configuration checks, not audio recordings or native-language listening validation. "
             "Keep the platform speaker fixed to compare delivery. Regional language is a generator inference, "
             "not proof of the seller’s preference. Jev agreement on this selected set is not an accuracy evaluation.", "",
             "| Seller id | Company | City / state | Use case + live Jev signals | Delivery profile | Start language | Final pace | OnStart opening |",
             "|---|---|---|---|---|---|---|---|"]
    details = []
    sound = {
        "brisk": ("Lead with the purpose immediately; keep turns short and direct.", "A rush cue should shorten the next turn further; do not claim a measured mid-call TTS speed change."),
        "consultative": ("Use measured, formal questions and leave room for the seller’s answer.", "For reactivation, check whether the business is active before discussing next steps; avoid an upgrade pitch."),
        "warm_engaged": ("Use a warmer, upbeat tone and respond to the seller’s interest.", "Offer relevant detail in small pieces, then one clear next step; avoid a rapid checklist."),
        "friendly_default": ("Use clear, friendly language and explain one setup step at a time.", "On confusion, simplify the explanation and check understanding before continuing."),
        "repair": ("Acknowledge the past frustration or refusal calmly, with a minimal, low-pressure ask.", "Leave more space for the seller; accept a refusal without arguing or repeating a pitch."),
    }
    interest = {
        "free_to_paid": "How could a paid service help my business?",
        "reactivation": "My business is still active; what would you like to check?",
        "profile_onboarding": "I want to update my product details; what is the first step?",
        "lead_engagement": "How should I respond to relevant buyer enquiries?",
        "warm_followup": "Yes, let’s continue our previous discussion.",
    }
    def cell(value):
        return str(value).replace("|", r"\|").replace("\n", " ")
    for p in profiles:
        ctx, _ = asyncio.run(harness.on_start(p["profile"], secrets={} if offline else harness.SECRETS))
        av = ctx.agent_variables
        applied = json.loads(av["persona_spec"])
        signals = json.loads(av["jev_signals"])
        uc = json.loads(p["profile"])["rules"]["use_case"]
        assert signals["source"] == ("rules_fallback" if offline else "jev") and av["use_case"] == uc, f"OnStart did not confirm {p['seller_id']}"
        assert applied["spec"] == json.loads(json.dumps(generate_persona(seller_row(p["seller_id"])), default=str)), "Bundled generator drift"
        assert applied["applied"]["pace"] == p["final_pace"], "Applied pace drift"
        assert applied["applied"]["start_language"] == p["start_language"], "Applied language drift"
        assert applied["spec"]["delivery_profile"]["id"] == p["delivery_profile"]
        p["on_start"] = {"opening": ctx.initial_bot_message, "signals": signals,
                         "pace": p["final_pace"], "start_language": p["start_language"]}
        sig = ", ".join(f"{k}={v}" for k, v in signals["signals"].items())
        sig += f"; catalog_need={signals['catalog_need']}; non-borderline agreement" if not offline else "unavailable (network blocked); OnStart rules_fallback"
        lines.append("| " + " | ".join(map(cell, [p["seller_id"], p["company"], f"{p['city']} / {p['state']}",
                     f"{uc}: {sig}", p["delivery_profile"], p["start_language"], f"{p['final_pace']:.2f}", ctx.initial_bot_message])) + " |")
        a, b = sound[p["delivery_profile"]]
        details += ["", f"## {p['seller_id']} — {p['company']}", "", f"- {a}", f"- {b}", "",
                    "Suggested demo script (pause for Disha after each cue):", ""]
        if p["start_language"] == "English":
            cues = ["I have only a minute; please be brief.", "I don’t understand; explain one step at a time.",
                    "Hindi mein baat kijiye.", "Mujhe dilchaspi hai; agla step kya hai?"]
        elif p["start_language"] == "Tamil":
            cues = ["எனக்கு நேரம் குறைவு, சுருக்கமாகச் சொல்லுங்கள்.", "புரியவில்லை, ஒரு படியாக விளக்குங்கள்.",
                    "Please speak in English.", interest[uc]]
        else:
            cues = ["Jaldi boliye, mere paas ek minute hai.", "Samajh nahi aaya; ek-ek step batayiye.",
                    "Please speak in English.", interest[uc]]
        details += [f"{i}. **{kind}:** “{cue}”" for i, (kind, cue) in enumerate(zip(["Rush", "Confusion", "Language switch", "Interest"], cues), 1)]
        if p["delivery_profile"] == "repair":
            details += ["", "Optional repair cue before interest: “Last time this wasn’t helpful; please don’t pressure me.”"]
    relaxations = [p["relaxation"] for p in profiles if p.get("relaxation")]
    lines += ["", "Relaxations: " + ("; ".join(relaxations) if relaxations else "None for selected sellers.")]
    if len(profiles) == 4:
        lines += ["", "Optional repair slot omitted: no eligible, supported-language repair candidate passed selection within the candidate budget."]
    (ROOT / "outputs/demo_set.md").write_text("\n".join(lines + details) + "\n")

def write(profiles: list[dict]):
    for p in profiles:
        profile = json.loads(p["profile"])
        assert set(profile) == {"v", "seller_id", "gen", "jev", "rules"}
        assert profile["rules"]["contact_policy"] == "OK_TO_CALL"
        assert p["bytes"] == len(p["profile"].encode()) <= 3500
    (ROOT / "outputs" / "demo_profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=1))
    md = ["# Demo seller profiles", "",
          "Paste the one-line JSON into Disha's `seller_profile` variable when starting a test call.", ""]
    if any(p.get("verification", {}).get("status") == "not_verified_network_unavailable" for p in profiles):
        md += ["**PROVISIONAL: live Jev verification unavailable; these are rules-selected candidates. See demo_set.md.**", ""]
    for p in profiles:
        md += [f"## {p['seller_id']} · {p['label']}", "",
               f"{p['company']} · {p['city']}, {p['state']} · {p['bytes']:,} bytes", "",
               "```json", p["profile"], "```", ""]
    (ROOT / "outputs" / "demo_profiles.md").write_text("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", type=int)
    ap.add_argument("--offline-preview", action="store_true", help="Export explicitly unverified candidates using rules fallback")
    ap.add_argument("--verify-profile", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.verify_profile:
        try:
            result = jev_result(sys.stdin.read(), load_tool())
            print("JEV_RESULT=" + json.dumps(result), flush=True)
        except Exception as exc:
            print(f"Jev unavailable: {type(exc).__name__}", flush=True)
            raise SystemExit(1)
        return
    profiles = build_profiles([(i, "custom") for i in a.ids]) if a.ids else pick_demo(a.offline_preview)
    if a.ids:
        tool = load_tool()
        for p in profiles:
            uc = json.loads(p["profile"])["rules"]["use_case"]
            if p["seller_id"] not in candidates(uc) or p["bytes"] > 3500:
                raise SystemExit(f"Seller {p['seller_id']} fails demo eligibility/size requirements")
            describe(p, generate_persona(seller_row(p["seller_id"])), tool)
            p["verification"] = ({"status": "not_verified_network_unavailable"} if a.offline_preview
                                 else live_verify(p["profile"]))
            if not a.offline_preview and (p["verification"]["use_case"] != uc or p["verification"]["borderline"]):
                raise SystemExit(f"Seller {p['seller_id']} not confirmed by Jev")
    demo_notes(profiles, offline=a.offline_preview)
    write(profiles)
    for p in profiles:
        print(f"{p['seller_id']:>10}  {p['bytes']:>5} B  {p['label']}  ({p['company']}, {p['state']})")


if __name__ == "__main__":
    main()
