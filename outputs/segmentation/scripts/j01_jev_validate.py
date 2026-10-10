"""Jev vs rules on the September holdout.

Sample sellers that got a September bot call, stratified by their rule label (e02 holdout labels,
built from pre-September data). For each, build a state from pre-September data only, ask Jev
five signal Nouls plus one direct Choice in one request, then compare both Jev designs with the
rules on the first September call's outcome.

Usage:
  python -I j01_jev_validate.py build [--per-cat 350]   # write work/j01_states.jsonl
  python -I j01_jev_validate.py run [--limit N] [--concurrency 8]   # call Jev, append work/j01_answers.jsonl
  python -I j01_jev_validate.py eval                     # write J_jev_validation.md
"""
import argparse
import asyncio
import json
import math
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

SEG = Path(__file__).resolve().parent.parent
CACHE = SEG.parent / "cache"
WORK = SEG / "work"
ENV = SEG.parent.parent / ".env"
CUT = pd.Timestamp("2026-09-01")
STATES = WORK / "j01_states.jsonl"
ANSWERS = WORK / "j01_answers.jsonl"
CATS = ["warm_followup", "lead_engagement", "free_to_paid", "reactivation", "profile_onboarding"]

# --- questions -------------------------------------------------------------------------------
NOULS = {
    "pending_commitment": (
        "The seller has an open commitment with IndiaMART from a recent call: on one of the last calls "
        "(roughly within the last 60 days) they agreed to a meeting or demo, or asked to be called back at a later time."),
    "ignores_leads": (
        "The seller receives buyer enquiries or phone enquiries (PNS) through IndiaMART but mostly does not reply to "
        "or answer them, or has said the leads they get are fake, irrelevant or useless."),
    "upgrade_intent": (
        "The seller has shown interest in paying for IndiaMART services: they explored or asked about paid plans or "
        "packages, tried to buy buy-leads or buyer contacts, or asked about prices of IndiaMART services."),
    "inactive_business": (
        "The seller's business looks inactive on IndiaMART or closed: no recent activity, no enquiries or replies and "
        "no catalog edits for months, or the seller said the business has stopped, closed or they no longer sell."),
    "catalog_needs_work": (
        "The seller's IndiaMART profile or catalog is incomplete or weak: few products, a low catalog quality score, "
        "missing business details, wrong products listed, or the seller is newly registered and still setting up."),
}
CHOICE_CRITERIA = {
    "warm_followup": "Has a recent open commitment (agreed to a meeting or demo, or asked for a callback); the call should confirm and lock a slot.",
    "lead_engagement": "Gets buyer enquiries or phone enquiries but mostly does not reply or answer them, or distrusts lead quality; the call should get them using their leads.",
    "free_to_paid": "Shows interest in paid IndiaMART services (explored plans, tried to buy buy-leads, asked prices); the call should offer a free meeting where an executive explains plans.",
    "reactivation": "Inactive on IndiaMART or business possibly closed; the call should check whether they are still in business.",
    "profile_onboarding": "Profile or catalog is incomplete or weak, or newly registered; the call should offer free help to complete the catalog.",
    "discovery": "None of the above is clearly supported by the data; the call should ask a few questions to find out what the seller needs.",
}
CHOICE_INSTR = "Which call purpose best fits this IndiaMART seller for the next outbound call, given their profile, engagement and call history?"


def _num(x):
    if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NA:
        return None
    return float(x) if isinstance(x, (float, np.floating)) else int(x) if isinstance(x, (int, np.integer)) else x


def _txt(x, n):
    return x[:n] if isinstance(x, str) else ""


def _pct(x):
    x = _num(x)
    return None if x is None else f"{round(100 * x)}%"


# --- build -----------------------------------------------------------------------------------
def make_state(p, f, h, obj, qs, bucket_map, ref_time):
    """Jev state for one seller. p: sellers row or None, f: B_seller_segments row, h: answered calls before
    ref_time (sorted oldest first), obj/qs: that seller's objection and question rows."""
    state = {
        "seller_profile": None if p is None else {
            "state": _num(p.seller_state), "business_type": _num(p.business_type), "annual_turnover": _num(p.annual_turnover),
            "nature_of_business": _num(p.nature_of_business),
            "gst_registration_year": _num(p.gst_registration_year),
            "main_category": _num(p.top_category_1), "category_group": _num(p.top_category_group),
            "number_of_categories": _num(p.num_categories)},
        "catalog": {
            "has_catalog_data": bool(f.has_catalog),
            "products_listed": _num(f.eng_product_count),
            "catalog_quality_score_out_of_100": _num(f.eng_cqs),
            "products_edited_last_90_days": _num(f.eng_products_modified_90d),
            "products_edited_last_year": _num(f.eng_products_modified_1yr),
            "profile_fields_missing": _num(f.n_missing_profile)},
        "buyer_demand_and_response": {
            "has_engagement_data": bool(f.has_eng),
            "activity_events_last_30_days": _num(f.eng_activity_30d),
            "buyer_enquiries_received_last_90_days": _num(f.eng_enq_received_90d),
            "buyer_enquiries_received_last_year": _num(f.eng_enq_received_1yr),
            "share_of_enquiries_replied_last_year": _pct(f.reply_ratio_1yr),
            "phone_enquiries_received_last_90_days": _num(f.eng_pns_received_90d),
            "phone_enquiries_received_last_year": _num(f.eng_pns_received_1yr),
            "share_of_phone_enquiries_answered_last_year": _pct(f.pns_answer_ratio_1yr),
            "pickup_rate_of_indiamart_calls_last_90_days": None if _num(f.eng_pickup_ratio_90d) is None else f"{round(f.eng_pickup_ratio_90d)}%"},
    }
    if len(h):
        last = h.iloc[-1]
        trig = []
        for code in h.redis_bucket.iloc[::-1]:
            m = bucket_map.get(code, {}).get("meaning")
            if m and m not in trig:
                trig.append(m)
        state["indiamart_call_history"] = {
            "answered_calls": int(len(h)),
            "days_since_last_call": int((ref_time - last.call_start_time).days),
            "last_call_outcome": last.disposition_label,
            "outcome_counts": h.disposition_label.value_counts().to_dict(),
            "why_indiamart_called_most_recent_first": trig[:3],
            "recent_call_summaries_newest_first": [
                {"days_ago": int((ref_time - r.call_start_time).days), "outcome": r.disposition_label,
                 "summary": _txt(r.lead_call_summary, 350)}
                for r in h.iloc[::-1].head(3).itertuples()],
            "objections_raised": [f"{r.obj_cat}: {_txt(r.reasons, 200)}" for r in obj.head(4).itertuples()],
            "questions_seller_asked": [f"{r.q_cat}: {_txt(r.que_ctx, 160)}" for r in qs.drop_duplicates("que").head(4).itertuples()],
        }
    else:
        state["indiamart_call_history"] = {"answered_calls": 0}
    return state


def build(per_cat: int, seed: int = 7):
    lab = pd.read_parquet(WORK / "e02_holdout_labels.parquet")
    sample = lab.groupby("rule_use_case").sample(n=per_cat, random_state=seed)
    ids = set(sample.fk_glusr_usr_id)

    sel = pd.read_parquet(CACHE / "sellers.parquet", columns=[
        "fk_glusr_usr_id", "seller_state", "business_type", "annual_turnover", "nature_of_business",
        "gst_registration_year", "top_category_1", "top_category_group", "num_categories"]).set_index("fk_glusr_usr_id")
    b = pd.read_parquet(SEG / "B_seller_segments.parquet").set_index("fk_glusr_usr_id")
    bucket_map = json.loads((SEG / "A_bucket_map.json").read_text())

    calls = pd.read_parquet(CACHE / "bot_calls.parquet", columns=[
        "attempt_id", "fk_glusr_usr_id", "redis_bucket", "call_start_time", "disposition_label",
        "lead_call_duration", "lead_call_summary"])
    calls = calls[calls.fk_glusr_usr_id.isin(ids)]
    pre = calls[calls.call_start_time < CUT].sort_values("call_start_time")
    pre_ids = set(pre.attempt_id)
    obj = pd.read_parquet(WORK / "ev_objections.parquet")
    obj = obj[obj.attempt_id.isin(pre_ids)].merge(pre[["attempt_id", "fk_glusr_usr_id"]], on="attempt_id")
    qs = pd.read_parquet(WORK / "ev_questions.parquet")
    qs = qs[qs.attempt_id.isin(pre_ids)].merge(pre[["attempt_id", "fk_glusr_usr_id"]], on="attempt_id")

    WORK.mkdir(exist_ok=True)
    with STATES.open("w") as fh:
        for _, row in sample.iterrows():
            sid = int(row.fk_glusr_usr_id)
            p = sel.loc[sid] if sid in sel.index else None
            state = make_state(p, b.loc[sid], pre[pre.fk_glusr_usr_id == sid], obj[obj.fk_glusr_usr_id == sid],
                               qs[qs.fk_glusr_usr_id == sid], bucket_map, CUT)
            fh.write(json.dumps({"seller_id": sid, "rule_use_case": row.rule_use_case, "state": state},
                                ensure_ascii=False, default=str, allow_nan=False) + "\n")
    print(f"wrote {len(sample)} states -> {STATES}")


# --- run -------------------------------------------------------------------------------------
def _load_env():
    if "TYPESAFE_API_KEY" not in os.environ and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith("TYPESAFE_API_KEY="):
                os.environ["TYPESAFE_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")


async def run(limit: int | None, concurrency: int):
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, RetryPolicy
    _load_env()
    done = set()
    if ANSWERS.exists():
        done = {json.loads(l)["seller_id"] for l in ANSWERS.open()}
    rows = [json.loads(l) for l in STATES.open()]
    rows = [r for r in rows if r["seller_id"] not in done][: limit or None]
    questions = {k: Noul(instructions=v) for k, v in NOULS.items()}
    questions["use_case"] = Choice(instructions=CHOICE_INSTR, criteria=CHOICE_CRITERIA)
    sem = asyncio.Semaphore(concurrency)
    t0, n_ok, n_err = time.time(), 0, 0
    async with AsyncTypeSafeClient(retry=RetryPolicy(max_retries=4, timeout=30.0)) as client:
        async def one(r):
            nonlocal n_ok, n_err
            async with sem:
                t = time.time()
                try:
                    resp = await client.system_one(state=r["state"], questions=questions)
                except Exception as e:  # keep going; record the failure
                    n_err += 1
                    rec = {"seller_id": r["seller_id"], "error": f"{type(e).__name__}: {e}"[:300]}
                else:
                    n_ok += 1
                    a = resp.answers
                    rec = {"seller_id": r["seller_id"], "model": resp.model,
                           "latency_s": round(time.time() - t, 3),
                           "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                           **{k: a[k].noul for k in NOULS},
                           "choice": a["use_case"].choice, "choice_confidence": a["use_case"].confidence,
                           "choice_probs": a["use_case"].probabilities}
                with ANSWERS.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
        await asyncio.gather(*(one(r) for r in rows))
    print(f"ok={n_ok} err={n_err} in {time.time() - t0:.1f}s")


# --- eval ------------------------------------------------------------------------------------
def jev_noul_label(r, thr=0.5):
    order = [("warm_followup", "pending_commitment"), ("lead_engagement", "ignores_leads"),
             ("free_to_paid", "upgrade_intent"), ("reactivation", "inactive_business"),
             ("profile_onboarding", "catalog_needs_work")]
    for cat, q in order:
        if r[q] >= thr:
            return cat
    return "discovery"


def cramers_v(x, y):
    t = pd.crosstab(np.asarray(x), np.asarray(y)).values.astype(float)
    n = t.sum()
    e = np.outer(t.sum(1), t.sum(0)) / n
    chi2 = ((t - e) ** 2 / np.where(e == 0, 1, e)).sum()
    k = min(t.shape) - 1
    return math.sqrt(chi2 / (n * k)) if k > 0 else 0.0


def cohen_kappa(a, b):
    labels = sorted(set(a) | set(b))
    t = pd.crosstab(pd.Categorical(a, labels), pd.Categorical(b, labels), dropna=False).values.astype(float)
    n = t.sum()
    po = np.trace(t) / n
    pe = (t.sum(0) * t.sum(1)).sum() / n ** 2
    return (po - pe) / (1 - pe)


def evaluate():
    st = pd.DataFrame([json.loads(l) for l in STATES.open()])
    ans = pd.DataFrame([json.loads(l) for l in ANSWERS.open()]).drop_duplicates("seller_id", keep="last")
    err = ans[ans.get("error").notna()] if "error" in ans else ans.iloc[0:0]
    ans = ans[ans.get("error").isna()] if "error" in ans else ans
    d = st.merge(ans, on="seller_id")
    d["jev_noul"] = d.apply(jev_noul_label, axis=1)
    d["jev_choice"] = d["choice"]

    calls = pd.read_parquet(CACHE / "bot_calls.parquet", columns=[
        "attempt_id", "fk_glusr_usr_id", "call_start_time", "disposition_label", "meeting_fixed", "lead_call_duration"])
    sep = calls[(calls.call_start_time >= CUT) & calls.fk_glusr_usr_id.isin(d.seller_id)].sort_values("call_start_time")
    first = sep.groupby("fk_glusr_usr_id").head(1).set_index("fk_glusr_usr_id")
    d = d.join(first[["meeting_fixed", "disposition_label", "lead_call_duration"]], on="seller_id")
    d["early_drop"] = d.lead_call_duration < 10
    d["ni"] = d.disposition_label.eq("Not Interested")
    d["outcome"] = np.where(d.early_drop, "early_drop", d.disposition_label)

    methods = ["rule_use_case", "jev_noul", "jev_choice"]
    out = [f"# Jev vs rules: September holdout\n",
           f"Sellers sampled: {len(st)} (stratified by rule label) · answered by Jev: {len(d)} · errors: {len(err)}  ",
           f"Model: {d.model.iloc[0]} · median latency {d.latency_s.median():.2f}s · mean tokens in/out "
           f"{d.input_tokens.mean():.0f}/{d.output_tokens.mean():.0f}  ",
           "Inputs: pre-September data only. Outcome: each seller's first September call.\n"]

    rng = np.random.default_rng(0)
    out.append("## Separation of September outcomes\n")
    out.append("Cramér's V between category and outcome (early drop / meeting / not interested / call later / general). "
               "Higher = categories separate outcomes more. 95% bootstrap CI.\n")
    out.append("| Method | Cramér's V | 95% CI | Meeting-rate spread (max−min, cats ≥ 40 sellers) | Discovery share |")
    out.append("|---|---|---|---|---|")
    boots = {m: [] for m in methods}
    idx = np.arange(len(d))
    for _ in range(500):
        s = d.iloc[rng.choice(idx, len(idx))]
        for m in methods:
            boots[m].append(cramers_v(s[m], s.outcome))
    for m in methods:
        g = d.groupby(m).meeting_fixed.agg(["mean", "size"])
        g = g[g["size"] >= 40]
        lo, hi = np.percentile(boots[m], [2.5, 97.5])
        out.append(f"| {m} | {cramers_v(d[m], d.outcome):.3f} | {lo:.3f}–{hi:.3f} | "
                   f"{100*(g['mean'].max()-g['mean'].min()):.1f} pts | {100*(d[m]=='discovery').mean():.1f}% |")
    diffs = {m: np.array(boots[m]) - np.array(boots["rule_use_case"]) for m in methods[1:]}
    for m, dv in diffs.items():
        out.append(f"\n{m} minus rules: mean ΔV {dv.mean():+.3f}, 95% CI {np.percentile(dv,2.5):+.3f} to {np.percentile(dv,97.5):+.3f}")

    out.append("\n## Outcomes per category\n")
    for m in methods:
        t = d.groupby(m).agg(sellers=("seller_id", "size"), meeting=("meeting_fixed", "mean"),
                             not_interested=("ni", "mean"), early_drop=("early_drop", "mean"),
                             median_sec=("lead_call_duration", "median"))
        t[["meeting", "not_interested", "early_drop"]] = (t[["meeting", "not_interested", "early_drop"]] * 100).round(1)
        out.append(f"### {m}\n\n" + t.to_markdown() + "\n")

    out.append("## Agreement\n")
    for a, b2 in [("rule_use_case", "jev_noul"), ("rule_use_case", "jev_choice"), ("jev_noul", "jev_choice")]:
        out.append(f"- {a} vs {b2}: exact agreement {100*(d[a]==d[b2]).mean():.1f}%, Cohen's κ {cohen_kappa(d[a], d[b2]):.2f}")
    out.append("\nRows = rules, columns = Jev (signal Nouls):\n\n" + pd.crosstab(d.rule_use_case, d.jev_noul).to_markdown() + "\n")
    out.append("Rows = rules, columns = Jev (direct Choice):\n\n" + pd.crosstab(d.rule_use_case, d.jev_choice).to_markdown() + "\n")

    out.append("## Jev signal probabilities\n")
    qd = d[list(NOULS)].describe(percentiles=[.1, .5, .9]).T[["mean", "10%", "50%", "90%"]].round(2)
    qd["share ≥ 0.5"] = [(d[q] >= .5).mean().round(2) for q in NOULS]
    out.append(qd.to_markdown() + "\n")
    out.append(f"Direct Choice confidence: median {d.choice_confidence.median():.2f}, "
               f"share ≥ 0.6: {100*(d.choice_confidence>=.6).mean():.0f}%\n")

    (SEG / "J_jev_validation.md").write_text("\n".join(out))
    keep = ["seller_id", "rule_use_case", "jev_noul", "jev_choice", "choice_confidence", *NOULS,
            "meeting_fixed", "disposition_label", "lead_call_duration"]
    d[keep].to_parquet(WORK / "j01_eval.parquet", index=False)
    dis = d[d.rule_use_case != d.jev_noul].sample(min(30, (d.rule_use_case != d.jev_noul).sum()), random_state=1)
    with (WORK / "j01_disagreements.jsonl").open("w") as fh:
        for r in dis.itertuples():
            fh.write(json.dumps({"seller_id": r.seller_id, "rule": r.rule_use_case, "jev_noul": r.jev_noul,
                                 "jev_choice": r.jev_choice, "nouls": {q: round(getattr(r, q), 2) for q in NOULS},
                                 "state": r.state}, ensure_ascii=False, default=str) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["build", "run", "eval"])
    ap.add_argument("--per-cat", type=int, default=350)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    if a.step == "build":
        build(a.per_cat)
    elif a.step == "run":
        asyncio.run(run(a.limit, a.concurrency))
    else:
        evaluate()
