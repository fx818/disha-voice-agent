"""Export complete persona specs for sample sellers: the generator's spec plus what Disha's OnStart adds on top
(call purpose from Jev, purpose-adjusted delivery, nudge budget, call plan, opening line, fixes from the fix loop).

Uses the running Disha Console's preview (the same OnStart code as on Samvaad, live Jev).

Usage: .venv/bin/python -I tools/export_specs.py [seller_id ...]
Writes outputs/personas/<id>.json and outputs/PERSONA_SPECS.md (real seller data, kept out of git), and an anonymised
copy for the repo in samples/personas/ (company names become "Seller A", "Seller B", ...; seller ids are removed).
"""
import importlib.util
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
OUT = ROOT / "outputs"
CONSOLE = "http://localhost:7862"

_spec = importlib.util.spec_from_file_location("disha_tools", ROOT / "samvaad" / "code_tool" / "disha_tools.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

# Fields generator.generate.features() reads from a seller row (outputs/cache/seller_table.parquet).
INPUT_FIELDS = [
    ("company", "company name (from past call openings and summaries)"),
    ("seller_state, seller_city, seller_locality", "where the seller is; state sets language and region"),
    ("annual_turnover, business_type, nature_of_business", "size and kind of business"),
    ("top_category_1..3, top_category_group", "what they sell"),
    ("gst_registration_year", "how new the business is"),
    ("eng_pickup_ratio_1yr, eng_enq_received_90d, eng_enq_replies_90d", "engagement with IndiaMART and buyers"),
    ("eng_cqs, eng_product_count", "catalog quality score and products listed"),
    ("bot_answered, bot_attempts, avg_answered_call_sec", "past VANI bot calls"),
    ("calls_meeting_fixed, calls_not_interested, calls_call_later", "past call outcomes"),
    ("ctx_early_calls, ctx_last_bucket", "derived from the call log: hang-ups under 10 s, last call trigger"),
    ("past_dispositions_detailed, past_objections, past_questions_asked", "evaluator outputs from past calls"),
    ("asked_if_talking_to_bot, showed_frustration, already_in_touch_with_executive, do_not_call_requested",
     "flags from past calls"),
]


def preview(sid: int, learned: bool = False) -> dict:
    """Clean persona from the seller data (learned=False), or with this seller's fix-loop changes applied."""
    req = urllib.request.Request(f"{CONSOLE}/api/preview/{sid}", data=json.dumps({"use_learned": learned}).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def note(notes: str, prefix: str) -> str:
    m = re.search(rf"^{re.escape(prefix)}(.*)$", notes, re.M)
    return m.group(1).strip() if m else ""


def build(sid: int) -> dict:
    v = preview(sid)
    av = v["variables"]
    lv = preview(sid, learned=True)
    learned = {k: (v_now, lv_val) for k, v_now, lv_val in (
        ("start language", v.get("language"), lv.get("language")), ("pace", v.get("pace"), lv.get("pace")),
        ("call purpose", av.get("use_case"), lv["variables"].get("use_case")),
        ("nudge budget", av.get("nudge_budget"), lv["variables"].get("nudge_budget"))) if v_now != lv_val}
    lnotes = lv["variables"].get("persona_notes") or ""
    m = re.search(r"^Learned from earlier calls.*?(?=^\S|\Z)", lnotes, re.M | re.S)
    spec = av["persona_spec"] if isinstance(av["persona_spec"], dict) else json.loads(av["persona_spec"] or "{}")
    spec = spec.get("spec", spec)
    prof = json.loads(v["sent_to_samvaad"]["agent_variables"]["seller_profile"])
    notes = av.get("persona_notes") or ""
    return {
        "seller_id": str(sid),
        "seller": spec.get("seller_snapshot"),
        "contact_policy": prof.get("rules", {}).get("contact_policy"),
        "call_purpose": {"use_case": av.get("use_case"), "confidence": av.get("use_case_confidence"),
                         "reason": av.get("use_case_reason")},
        "delivery_profile": spec.get("delivery_profile"),
        "voice": {**(spec.get("voice") or {}), "final_pace": v.get("pace"),
                  "note": "the platform voice is fixed (female); only pace changes per seller"},
        "final_delivery": {"style": av.get("persona_style"), "pace": v.get("pace"), "reason": note(notes, "Delivery: ")},
        "language": spec.get("language"),
        "start_language": v.get("language"),
        "tone": spec.get("tone"),
        "opening_line": v.get("opening"),
        "conversation_plan": {
            "opening_approach": (spec.get("plan") or {}).get("opening"),
            "call_plan": T.call_plan_text(av.get("use_case")),
            "personalisation": (spec.get("plan") or {}).get("personalisation"),
            "objection_playbook": (spec.get("plan") or {}).get("objection_playbook"),
            "escalation_rules": (spec.get("plan") or {}).get("escalation_rules"),
            "target_call_sec": (spec.get("plan") or {}).get("target_call_sec"),
        },
        "nudge_budget": {"value": av.get("nudge_budget"), "reason": note(notes, "Nudge budget: ")},
        "fix_loop": {"changes_next_call": {k: {"from": a, "to": b} for k, (a, b) in learned.items()},
                     "learned_notes": m.group(0).strip() if m else ""},
        "evidence_refs": spec.get("evidence_refs"),
        "guardrails": spec.get("guardrails"),
    }


def md(s: dict) -> str:
    sn = s["seller"] or {}
    h = sn.get("history") or {}
    L = [f"## {sn.get('company') or s['seller_id']} · {sn.get('city')}, {sn.get('state')} (seller {s['seller_id']})", "",
         f"**Seller file (input):** {sn.get('nature')}, turnover {sn.get('turnover') or 'unknown'}, sells "
         f"{', '.join(sn.get('top_categories') or []) or 'unknown'}. Past bot calls: {h.get('bot_answered')} answered, "
         f"{h.get('meetings')} meeting(s), {h.get('not_interested')} not interested, {h.get('call_later')} call later, "
         f"{h.get('early_drops')} hung up within 10 s; flags: {', '.join(h.get('flags') or []) or 'none'}. "
         f"Contact policy: {s['contact_policy']}.", "",
         "| Choice | Value | Reason | Confidence |", "|---|---|---|---|"]
    cp = s["call_purpose"]
    L.append(f"| Call purpose (Jev + rules) | {cp['use_case']} | {cp['reason']} | {cp['confidence']} |")
    dp = s["delivery_profile"] or {}
    L.append(f"| Persona profile | {dp.get('label')} | chosen from the seller's history and size | |")
    vo = s["voice"]
    L.append(f"| Voice | {vo.get('gender')} (platform voice), pace {vo.get('final_pace')} | {vo.get('reason')} "
             f"Final: {s['final_delivery']['reason']} | {vo.get('confidence')} |")
    la = s["language"] or {}
    L.append(f"| Language | starts in {s['start_language']}, {round((la.get('english_mix') or 0) * 100)}% English words, "
             f"{la.get('formality')} register, ready for {', '.join(la.get('switch_ready') or [])} | {la.get('reason')} | "
             f"{la.get('confidence')} |")
    to = s["tone"] or {}
    L.append(f"| Tone | warmth {to.get('warmth')}, empathy {to.get('empathy')}, energy {to.get('energy')} | "
             f"{to.get('reason')} | {to.get('confidence')} |")
    op = s["conversation_plan"]["opening_approach"] or {}
    L.append(f"| Opening | “{s['opening_line']}” | {op.get('approach')} {op.get('reason') or ''} | {op.get('confidence')} |")
    nb = s["nudge_budget"]
    L.append(f"| Nudge budget | {nb['value']} | {nb['reason']} | |")
    L += ["", "**Conversation plan**", "", "```", s["conversation_plan"]["call_plan"] or "(none)", "```", ""]
    obj = s["conversation_plan"]["objection_playbook"] or []
    if obj:
        L += ["**Objection playbook**", ""]
        L += [f"- *{o.get('objection')}*: {o.get('approach')} ({o.get('evidence') or 'no evidence id'})" for o in obj]
        L.append("")
    esc = s["conversation_plan"]["escalation_rules"] or []
    if esc:
        L += ["**Escalation rules**", ""]
        L += [f"- *{e.get('trigger')}*: {e.get('action')}" for e in esc]
        L.append("")
    fl = s["fix_loop"]
    ch = "; ".join(f"{k}: {d['from']} → {d['to']}" for k, d in fl["changes_next_call"].items())
    L += [f"**Fix loop (from earlier test calls with this seller):** "
          + (f"next call would change {ch}." if ch else "no change to the next call.")
          + (f" {fl['learned_notes'].splitlines()[0]}" if fl["learned_notes"] else ""), "",
          f"**Evidence items:** {', '.join(s['evidence_refs'] or [])} (docs/evidence_report.md)", ""]
    return "\n".join(L)


SAMPLES = ROOT / "samples" / "personas"


def anonymise(specs: list) -> tuple[list, list]:
    """Replace each seller's company name and id with a neutral label everywhere in its spec."""
    out, labels = [], []
    for i, s in enumerate(specs):
        letter = chr(ord("A") + i)
        sn = s.get("seller") or {}
        cats = ", ".join((sn.get("top_categories") or [])[:2]) or "seller"
        label = f"Seller {letter}"
        text = json.dumps(s, ensure_ascii=False, default=str)
        for name in {sn.get("company"), (sn.get("company") or "").upper()} - {None, ""}:
            text = text.replace(json.dumps(name)[1:-1], label)
        text = text.replace(s["seller_id"], f"sample-{letter.lower()}")
        a = json.loads(text)
        a["seller_id"] = f"sample-{letter.lower()}"
        out.append(a)
        labels.append((label, f"sample-{letter.lower()}", cats, a["call_purpose"]["use_case"]))
    return out, labels


def main():
    ids = [int(x) for x in sys.argv[1:]] or [int(x) for x in os.getenv("DISHA_SPEC_SELLERS", "").split(",") if x.strip()]
    if not ids:
        sys.exit("give seller ids, or set DISHA_SPEC_SELLERS in .env")
    (OUT / "personas").mkdir(parents=True, exist_ok=True)
    specs = []
    for sid in ids:
        s = build(sid)
        (OUT / "personas" / f"{sid}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False, default=str))
        specs.append(s)
        print(f"{sid}: {s['call_purpose']['use_case']} · {(s['delivery_profile'] or {}).get('id')} · "
              f"{s['start_language']} · pace {s['voice']['final_pace']}")
    head = ["# Disha persona specs: sample sellers", "",
            "One spec per seller, built by the same code that runs on Samvaad before Disha's first word: the persona "
            "generator (generator/generate.py) plus the call purpose from Jev, the purpose-adjusted delivery, the nudge "
            "budget, the call plan and any fixes from the fix loop. Every choice carries its reason and confidence; "
            "evidence ids refer to docs/evidence_report.md. Voice gender, pace and tone levels are informed guesses "
            "(no past call varied them) and are marked low confidence; live switching corrects them during the call.", "",
            "## Input: what generate.py reads", "",
            "`generate_persona(row)` takes one flat seller row (a dict). `--seller-id N` builds it from the PS07 data "
            "(`seller_row()` in generator/generate.py). Fields read:", "",
            "| Field(s) | Used for |", "|---|---|"]
    head += [f"| `{a}` | {b} |" for a, b in INPUT_FIELDS]
    head += ["", "Missing fields are allowed: the affected choices fall back to defaults and are marked low confidence.", ""]
    (OUT / "PERSONA_SPECS.md").write_text("\n".join(head + [md(s) for s in specs]))
    print(f"wrote {OUT / 'PERSONA_SPECS.md'} and {len(specs)} JSON specs in {OUT / 'personas'}")
    anon, labels = anonymise(specs)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for a in anon:
        (SAMPLES / f"{a['seller_id']}.json").write_text(json.dumps(a, indent=1, ensure_ascii=False, default=str))
    idx = ["", "## Sellers in this set", "", "| Seller | Sells | Call purpose | JSON |", "|---|---|---|---|"]
    idx += [f"| {l} | {c} | {u} | [{f}.json]({f}.json) |" for l, f, c, u in labels]
    note = ["", "Company names and seller ids are replaced (Seller A, B, ...); everything else is exactly what Disha "
            "builds for that seller.", ""]
    (SAMPLES / "PERSONA_SPECS.md").write_text("\n".join(head[:2] + note + idx + [""] + head[2:] + [md(a) for a in anon]))
    print(f"wrote the anonymised copy in {SAMPLES}")


if __name__ == "__main__":
    main()
