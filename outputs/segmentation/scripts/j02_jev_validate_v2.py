"""Second Jev run on the same 2,100 holdout sellers as j01, with the fixes from the first run.

Changes vs j01:
  1. Missing fields are sent as "unknown" with a note that unknown is not zero, plus typical-seller
     medians so Jev can judge whether a number is low.
  2. Sellers with no engagement data, no catalog data and no past calls go to discovery in code;
     Jev's answer is not used for them.
  3. inactive_business needs recorded zero activity or a stated closure (criteria spell out that
     unknown data is not inactivity).
  4. catalog_needs_work is a Score with four concrete levels instead of a Noul.

Usage:
  python -I j02_jev_validate_v2.py run [--concurrency 8]
  python -I j02_jev_validate_v2.py eval
"""
import argparse
import asyncio
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("j01", HERE / "j01_jev_validate.py")
j01 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(j01)

SEG, WORK, CACHE, CUT = j01.SEG, j01.WORK, j01.CACHE, j01.CUT
ANSWERS = WORK / "j02_answers.jsonl"

NOULS = {
    "pending_commitment": j01.NOULS["pending_commitment"],
    "ignores_leads": j01.NOULS["ignores_leads"],
    "upgrade_intent": j01.NOULS["upgrade_intent"],
    "inactive_business": {
        "instructions": "The seller's business has gone quiet or closed.",
        "criteria": {
            "true": ("The recorded data shows zero activity, zero buyer enquiries and zero catalog edits over the last "
                     "90 days, or the seller said on a call that the business has closed, stopped or no longer sells."),
            "false": ("The data shows recent activity, enquiries, replies or catalog edits, or the activity data is "
                      "unknown. Unknown or missing data is not evidence that the business is inactive."),
        },
    },
}
CATALOG_LEVELS = [
    "The catalog is well built: plenty of products listed, a quality score well above the typical seller, and recent edits.",
    "The catalog is usable but basic: around the typical number of products and a typical quality score.",
    "The catalog is thin: only a handful of products, a quality score well below the typical seller, or business details missing.",
    "Almost nothing is set up: the seller is newly registered or has one or two products and no real catalog yet.",
]
CATALOG_INSTR = ("How much work does this seller's IndiaMART catalog need? Compare the products listed and the "
                 "catalog quality score with the typical seller values given. If catalog data is unknown, judge "
                 "only from any call history and profile details.")
CHOICE_INSTR = {
    "question": j01.CHOICE_INSTR,
    "note": "Fields marked unknown were not available for this seller. Unknown is not zero and is not evidence of inactivity.",
}


def _unknownify(x):
    if isinstance(x, dict):
        return {k: _unknownify(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_unknownify(v) for v in x]
    return "unknown" if x is None else x


def reference_medians():
    b = pd.read_parquet(SEG / "B_seller_segments.parquet",
                        columns=["has_catalog", "has_eng", "eng_cqs", "eng_product_count", "eng_enq_received_1yr"])
    c, e = b[b.has_catalog], b[b.has_eng]
    return {"typical_seller_products_listed": float(c.eng_product_count.median()),
            "typical_seller_catalog_quality_score_out_of_100": float(c.eng_cqs.median()),
            "typical_seller_buyer_enquiries_last_year": float(e.eng_enq_received_1yr.median())}


def no_data(state):
    return (not state["catalog"]["has_catalog_data"] and not state["buyer_demand_and_response"]["has_engagement_data"]
            and state["indiamart_call_history"]["answered_calls"] == 0)


async def run(concurrency: int):
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, NoulCriteria, RetryPolicy, Score
    j01._load_env()
    ref = reference_medians()
    done = {json.loads(l)["seller_id"] for l in ANSWERS.open()} if ANSWERS.exists() else set()
    rows = [json.loads(l) for l in j01.STATES.open()]
    rows = [r for r in rows if r["seller_id"] not in done]
    qs = {}
    for k, v in NOULS.items():
        qs[k] = Noul(instructions=v["instructions"], criteria=NoulCriteria(**v["criteria"])) if isinstance(v, dict) else Noul(instructions=v)
    qs["catalog_need"] = Score(instructions=CATALOG_INSTR, criteria=CATALOG_LEVELS)
    qs["use_case"] = Choice(instructions=CHOICE_INSTR, criteria=j01.CHOICE_CRITERIA)
    sem = asyncio.Semaphore(concurrency)
    t0, n_ok, n_err = time.time(), 0, 0
    async with AsyncTypeSafeClient(retry=RetryPolicy(max_retries=4, timeout=30.0)) as client:
        async def one(r):
            nonlocal n_ok, n_err
            state = _unknownify(r["state"])
            state["reference_typical_seller"] = ref
            async with sem:
                t = time.time()
                try:
                    resp = await client.system_one(state=state, questions=qs)
                except Exception as e:
                    n_err += 1
                    rec = {"seller_id": r["seller_id"], "error": f"{type(e).__name__}: {e}"[:300]}
                else:
                    n_ok += 1
                    a = resp.answers
                    rec = {"seller_id": r["seller_id"], "model": resp.model, "latency_s": round(time.time() - t, 3),
                           "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                           **{k: a[k].noul for k in NOULS},
                           "catalog_need": a["catalog_need"].score, "catalog_need_conf": a["catalog_need"].confidence,
                           "choice": a["use_case"].choice, "choice_confidence": a["use_case"].confidence,
                           "choice_probs": a["use_case"].probabilities}
                with ANSWERS.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
        await asyncio.gather(*(one(r) for r in rows))
    print(f"ok={n_ok} err={n_err} in {time.time() - t0:.1f}s")


def label_v2(r, catalog_thr=1.5, thr=0.5):
    if r["no_data"]:
        return "discovery"
    for cat, q in [("warm_followup", "pending_commitment"), ("lead_engagement", "ignores_leads"),
                   ("free_to_paid", "upgrade_intent"), ("reactivation", "inactive_business")]:
        if r[q] >= thr:
            return cat
    return "profile_onboarding" if r["catalog_need"] >= catalog_thr else "discovery"


def evaluate():
    st = pd.DataFrame([json.loads(l) for l in j01.STATES.open()])
    st["no_data"] = st.state.map(no_data)
    a2 = pd.DataFrame([json.loads(l) for l in ANSWERS.open()]).drop_duplicates("seller_id", keep="last")
    n_err = int(a2["error"].notna().sum()) if "error" in a2 else 0
    a2 = a2[a2["error"].isna()] if "error" in a2 else a2
    v1 = pd.read_parquet(WORK / "j01_eval.parquet")[["seller_id", "jev_noul", "jev_choice"]].rename(
        columns={"jev_noul": "jev_v1_signals", "jev_choice": "jev_v1_choice"})
    d = st.merge(a2, on="seller_id").merge(v1, on="seller_id")
    d["jev_v2_signals"] = d.apply(label_v2, axis=1)
    d["jev_v2_choice"] = np.where(d.no_data, "discovery", d.choice)

    calls = pd.read_parquet(CACHE / "bot_calls.parquet", columns=[
        "fk_glusr_usr_id", "call_start_time", "disposition_label", "meeting_fixed", "lead_call_duration"])
    sep = calls[(calls.call_start_time >= CUT) & calls.fk_glusr_usr_id.isin(d.seller_id)].sort_values("call_start_time")
    first = sep.groupby("fk_glusr_usr_id").head(1).set_index("fk_glusr_usr_id")
    d = d.join(first[["meeting_fixed", "disposition_label", "lead_call_duration"]], on="seller_id")
    d["early_drop"] = d.lead_call_duration < 10
    d["ni"] = d.disposition_label.eq("Not Interested")
    d["outcome"] = np.where(d.early_drop, "early_drop", d.disposition_label)

    methods = ["rule_use_case", "jev_v1_signals", "jev_v1_choice", "jev_v2_signals", "jev_v2_choice"]
    out = ["# Jev vs rules: second run (tuned questions)\n",
           f"Same {len(st)} holdout sellers as run 1 · answered: {len(d)} · errors: {n_err} · model {d.model.iloc[0]} · "
           f"median latency {d.latency_s.median():.2f}s · mean tokens in/out {d.input_tokens.mean():.0f}/{d.output_tokens.mean():.0f}  ",
           f"Sellers with no engagement, catalog or call data (sent to discovery in code): {int(d.no_data.sum())}\n",
           "## Separation of September outcomes\n",
           "| Method | Cramér's V | 95% CI | V minus rules (95% CI) | Meeting spread | Discovery share |",
           "|---|---|---|---|---|---|"]
    rng = np.random.default_rng(0)
    idx = np.arange(len(d))
    boots = {m: [] for m in methods}
    for _ in range(1000):
        s = d.iloc[rng.choice(idx, len(idx))]
        for m in methods:
            boots[m].append(j01.cramers_v(s[m], s.outcome))
    base = np.array(boots["rule_use_case"])
    for m in methods:
        g = d.groupby(m).meeting_fixed.agg(["mean", "size"])
        g = g[g["size"] >= 40]
        lo, hi = np.percentile(boots[m], [2.5, 97.5])
        dv = np.array(boots[m]) - base
        diff = "—" if m == "rule_use_case" else f"{dv.mean():+.3f} ({np.percentile(dv, 2.5):+.3f} to {np.percentile(dv, 97.5):+.3f})"
        out.append(f"| {m} | {j01.cramers_v(d[m], d.outcome):.3f} | {lo:.3f}–{hi:.3f} | {diff} | "
                   f"{100 * (g['mean'].max() - g['mean'].min()):.1f} pts | {100 * (d[m] == 'discovery').mean():.1f}% |")

    out.append("\n## Outcomes per category (run 2)\n")
    for m in ["rule_use_case", "jev_v2_signals", "jev_v2_choice"]:
        t = d.groupby(m).agg(sellers=("seller_id", "size"), meeting=("meeting_fixed", "mean"),
                             not_interested=("ni", "mean"), early_drop=("early_drop", "mean"),
                             median_sec=("lead_call_duration", "median"))
        t[["meeting", "not_interested", "early_drop"]] = (t[["meeting", "not_interested", "early_drop"]] * 100).round(1)
        out.append(f"### {m}\n\n" + t.to_markdown() + "\n")

    out.append("## Agreement with rules\n")
    for m in methods[1:]:
        out.append(f"- {m}: {100 * (d.rule_use_case == d[m]).mean():.1f}% exact, Cohen's κ {j01.cohen_kappa(d.rule_use_case, d[m]):.2f}")
    out.append("\nRows = rules, columns = Jev run 2 (signals):\n\n" + pd.crosstab(d.rule_use_case, d.jev_v2_signals).to_markdown() + "\n")

    out.append("## Did the fixes work?\n")
    nd = d[d.no_data]
    out.append(f"- No-data sellers: {len(nd)}; their meeting rate {100 * nd.meeting_fixed.mean():.1f}%. "
               f"Run 1 sent {int((nd.jev_v1_signals == 'reactivation').sum())} of them to reactivation.")
    has = d[~d.no_data]
    out.append(f"- inactive_business ≥ 0.5 among sellers with data: run 2 {100 * (has.inactive_business >= .5).mean():.0f}%")
    cn = d.groupby("rule_use_case").catalog_need.mean().round(2).to_dict()
    out.append(f"- catalog_need score (0 well built … 3 almost nothing) mean by rule category: {cn}")
    out.append(f"- share with catalog_need ≥ 1.5: {100 * (d.catalog_need >= 1.5).mean():.0f}%")
    out.append(f"- Direct choice confidence: median {d.choice_confidence.median():.2f}, share ≥ 0.6 {100 * (d.choice_confidence >= .6).mean():.0f}%")

    (SEG / "J2_jev_validation_v2.md").write_text("\n".join(out))
    d.drop(columns=["state"]).to_parquet(WORK / "j02_eval.parquet", index=False)
    print("\n".join(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["run", "eval"])
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    asyncio.run(run(a.concurrency)) if a.step == "run" else evaluate()
