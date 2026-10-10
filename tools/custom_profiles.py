"""Pick test sellers that exercise different parts of Disha, preview what Disha will do for each, and write
paste-ready seller_profile JSON to outputs/custom_profiles.md (the demo set in outputs/demo_profiles.* is untouched).

  .venv/bin/python -I tools/custom_profiles.py                 # auto-pick one seller per test slot
  .venv/bin/python -I tools/custom_profiles.py --ids 123 456   # specific sellers

Each preview runs the uploaded code tool's OnStart locally (live Jev, same as on Samvaad).
"""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "outputs" / "cache"
SEG = ROOT / "outputs" / "segmentation"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EXP = _load("export_profiles", ROOT / "tools" / "export_profiles.py")
TEST = _load("test_disha_tools", ROOT / "samvaad" / "code_tool" / "test_disha_tools.py")

# (slot, what it tests, filter on the merged seller table)
SLOTS = [
    ("english_start", "Opens in English (South India, few transcripts): second language from the first word",
     lambda d: d.seller_state.isin(["Karnataka", "Kerala", "Andhra Pradesh"]) & d.ok),
    ("lead_engagement", "Gets enquiries but rarely replies: calm business-coach purpose, slower pace",
     lambda d: (d.use_case == "lead_engagement") & d.ok),
    ("ai_disclosure", "Asked 'are you a bot?' before: opening discloses AI identity up front",
     lambda d: (d.asked_if_talking_to_bot == 1) & d.ok),
    ("large_formal", "Larger company (5 Cr+): consultative, formal register, more English",
     lambda d: d.annual_turnover.isin(["5 - 25 Cr", "25 - 100 Cr", "100 - 500 Cr"]) & d.ok),
    ("repair_cool_off", "Refused twice before (COOL_OFF): calm repair persona, one soft ask only",
     lambda d: (d.contact_policy == "COOL_OFF_N_DAYS") & (d.calls_not_interested >= 2) & (d.calls_meeting_fixed == 0)
     & d.company.notna()),
    ("do_not_call", "Asked not to be called (SUPPRESS): must NOT pitch, apologise and close",
     lambda d: (d.contact_policy == "SUPPRESS") & (d.do_not_call_requested == 1) & d.company.notna()),
    ("discovery", "Too little engagement / catalog data for a clear purpose: short qualifying questions first",
     lambda d: (d.use_case == "discovery") & d.ok),
]


def candidates():
    t = pd.read_parquet(CACHE / "seller_table.parquet", columns=[
        "fk_glusr_usr_id", "company", "seller_state", "annual_turnover", "bot_answered", "calls_not_interested",
        "calls_meeting_fixed", "asked_if_talking_to_bot", "do_not_call_requested"])
    u = pd.read_parquet(SEG / "seller_use_case.parquet", columns=["fk_glusr_usr_id", "use_case", "contact_policy"])
    d = t.merge(u, on="fk_glusr_usr_id")
    calls = pd.read_parquet(CACHE / "bot_calls.parquet", columns=["fk_glusr_usr_id", "lead_call_duration", "lead_call_summary"])
    talked = set(calls.loc[calls.lead_call_duration >= 30, "fk_glusr_usr_id"])
    wrong = set(calls.loc[calls.lead_call_summary.fillna("").str.contains("wrong number", case=False), "fk_glusr_usr_id"])
    d["talked"] = d.fk_glusr_usr_id.isin(talked) & ~d.fk_glusr_usr_id.isin(wrong)
    d["ok"] = (d.contact_policy == "OK_TO_CALL") & d.talked & d.company.notna()
    return d


async def preview(profile_text):
    ctx, dt = await TEST.on_start(profile_text)
    av = ctx.agent_variables
    spec = json.loads(av.get("persona_spec") or "{}")
    applied = spec.get("applied", {})
    return {"use_case": av.get("use_case"), "confidence": av.get("use_case_confidence"),
            "reason": av.get("use_case_reason"), "style": av.get("persona_style"), "history": av.get("seller_history"),
            "pace": applied.get("pace"), "language": applied.get("start_language"),
            "profile": ((spec.get("spec") or {}).get("delivery_profile") or {}).get("id"),
            "opening": ctx.initial_bot_message, "contact_line": next(
                (l for l in (av.get("persona_notes") or "").splitlines() if l.startswith("Contact policy")), ""),
            "secs": round(dt, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", type=int)
    a = ap.parse_args()
    if a.ids:
        picks = [(f"custom_{i}", "custom seller", i) for i in a.ids]
    else:
        d = candidates()
        picks, used = [], set()
        for slot, why, f in SLOTS:
            pool = d[f(d) & ~d.fk_glusr_usr_id.isin(used)].sort_values("bot_answered", ascending=False)
            if len(pool):
                sid = int(pool.iloc[0].fk_glusr_usr_id)
                used.add(sid)
                picks.append((slot, why, sid))
            else:
                print(f"no candidate for {slot}")
    out = ["# Custom test sellers", "",
           "Paste the JSON into Disha's `seller_profile` variable (or ask Claude to set it as the draft default) and call.",
           "Preview = what the uploaded code tool decided locally with live Jev; on the call it re-runs and can differ "
           "slightly near thresholds.", ""]
    for slot, why, sid in picks:
        prof = EXP.build_profiles([(sid, slot)])[0]
        pv = asyncio.run(preview(prof["profile"]))
        print(f"{slot:<16} {sid:>10} {(prof['company'] or '(no name)')[:28]:<28} {prof['state'] or '':<15} -> {pv['use_case']} "
              f"({pv['confidence']}) {pv['profile']} {pv['style']} pace {pv['pace']} {pv['language']}  {prof['bytes']} B")
        out += [f"## {slot}: {prof['company']} ({sid})", "",
                f"**Tests:** {why}  ",
                f"**Seller:** {prof['company']}, {prof['city']}, {prof['state']} · contact policy "
                f"{json.loads(prof['profile'])['rules']['contact_policy']}  ",
                f"**Disha will:** {pv['use_case']} ({pv['confidence']}) · persona {pv['profile']} · style {pv['style']} · "
                f"pace {pv['pace']} · starts in {pv['language']} · history {pv['history']}  ",
                f"**Why:** {pv['reason']}  ",
                f"**Opening:** {pv['opening']}  "] + ([f"**Gate:** {pv['contact_line']}  "] if pv["contact_line"] else []) + [
                "", "```json", prof["profile"], "```", ""]
    (ROOT / "outputs" / "custom_profiles.md").write_text("\n".join(out))
    print("wrote outputs/custom_profiles.md")


if __name__ == "__main__":
    main()
