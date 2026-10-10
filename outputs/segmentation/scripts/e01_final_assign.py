"""Final use-case assignment: contact gate (D) + campaign trigger (A) + seller profile (B) + past call themes (C).

Writes outputs/segmentation/seller_use_case.parquet and .csv (one row per seller) and prints validation tables.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEG = Path(__file__).resolve().parent.parent
CACHE = SEG.parent / "cache"

# Trigger groups from A_bucket_map.json (codex decoding); confidence noted in the report.
TRIGGER_GROUP = {
    "PIM": "monetise", "PAM": "monetise", "OLP": "monetise", "PANF": "monetise", "PNCHF": "monetise",
    "PUA": "monetise_soft",            # viewed / checked BuyLeads (medium confidence)
    "SCHD": "warm", "OLPR": "warm",
    "NUR": "onboard", "PUT": "profile",
    "PNSM": "leads", "PNSR": "leads", "ENQR": "leads",
}

b = pd.read_parquet(SEG / "B_seller_segments.parquet")
d = pd.read_parquet(SEG / "D_seller_flags.parquet",
                    columns=["fk_glusr_usr_id", "contact_policy", "reason", "cool_off_days", "open_ticket"])
a = pd.read_parquet(SEG / "A_seller_paid_status.parquet")

calls = pd.read_parquet(CACHE / "bot_calls.parquet",
                        columns=["attempt_id", "fk_glusr_usr_id", "redis_bucket", "call_start_time",
                                 "disposition_label", "meeting_fixed", "lead_call_duration"])
calls = calls.sort_values("call_start_time")
last = calls.groupby("fk_glusr_usr_id").tail(1).set_index("fk_glusr_usr_id")
trig = calls.assign(g=calls.redis_bucket.map(TRIGGER_GROUP).fillna("generic"))
any_grp = pd.crosstab(trig.fk_glusr_usr_id, trig.g).gt(0)

th = pd.read_parquet(SEG / "C_call_themes.parquet",
                     columns=["fk_glusr_usr_id", "th_pricing", "th_free_payment", "th_profile",
                              "th_leads", "th_not_using"])
th = th.groupby("fk_glusr_usr_id").max()

s = b.merge(d, on="fk_glusr_usr_id", how="left").merge(a, on="fk_glusr_usr_id", how="left")
s = s.set_index("fk_glusr_usr_id")
s["last_bucket"] = last.redis_bucket.reindex(s.index)
s["last_trigger"] = s.last_bucket.map(TRIGGER_GROUP).fillna("generic").where(s.last_bucket.notna(), "none")
for g in ["monetise", "monetise_soft", "warm", "onboard", "profile", "leads"]:
    s[f"ever_{g}"] = any_grp[g].reindex(s.index).fillna(False).astype(bool) if g in any_grp else False
for c in th.columns:
    s[f"past_{c}"] = th[c].reindex(s.index).fillna(0).astype(bool)

# --- signals per category (each a bool series, plus why) ---------------------------------
sig = {
    "warm_followup": s.f_warm | s.last_trigger.eq("warm"),
    "lead_engagement": s.f_lead_nonconsumption | s.last_trigger.eq("leads"),
    "free_to_paid": s.f_free_to_paid | s.last_trigger.eq("monetise")
                    | (s.last_trigger.eq("monetise_soft") & (s.past_th_pricing | s.past_th_free_payment)),
    "reactivation": s.f_dormant | s.past_th_not_using,
    "profile_onboarding": s.f_profile_enrichment | s.f_low_demand_active
                          | s.last_trigger.isin(["onboard", "profile"]) | s.past_th_profile,
}
# Priority: commitments first; then fix lead consumption before selling more leads;
# then monetise intent; dormant before catalog work (no point polishing a closed shop).
ORDER = ["warm_followup", "lead_engagement", "free_to_paid", "reactivation", "profile_onboarding"]
s["use_case"] = "discovery"
for cat in reversed(ORDER):
    s.loc[sig[cat], "use_case"] = cat
# PUA-only sellers with no other signal: soft monetise (viewed BuyLeads) -> free_to_paid, lower confidence
soft = s.use_case.eq("discovery") & s.last_trigger.eq("monetise_soft")
s.loc[soft, "use_case"] = "free_to_paid"

n_sig = pd.DataFrame(sig).sum(axis=1)
src_profile = {"warm_followup": s.f_warm, "lead_engagement": s.f_lead_nonconsumption,
               "free_to_paid": s.f_free_to_paid, "reactivation": s.f_dormant,
               "profile_onboarding": s.f_profile_enrichment | s.f_low_demand_active}
s["use_case_confidence"] = "low"
for cat, prof in src_profile.items():
    m = s.use_case.eq(cat)
    trig_agrees = {
        "warm_followup": s.last_trigger.eq("warm") | s.last_bot_disposition.isin(["Meeting Fixed", "Call Later / Busy"]),
        "lead_engagement": s.last_trigger.eq("leads") | s.past_th_leads,
        "free_to_paid": s.last_trigger.eq("monetise") | s.past_th_pricing | s.past_th_free_payment,
        "reactivation": s.past_th_not_using | s.f_dormant,
        "profile_onboarding": s.last_trigger.isin(["onboard", "profile"]) | s.past_th_profile,
    }[cat]
    s.loc[m & (prof | trig_agrees), "use_case_confidence"] = "medium"
    s.loc[m & prof & trig_agrees, "use_case_confidence"] = "high"
s.loc[soft, "use_case_confidence"] = "low"

s["secondary_use_cases"] = [",".join(c for c in ORDER if sig[c].iat[i] and c != u)
                            for i, u in enumerate(s.use_case)]
s["new_business"] = s.new_business_gst.fillna(False).astype(bool)
s["thin_catalog"] = s.f_profile_enrichment
s["contact_policy"] = s.contact_policy.fillna("OK_TO_CALL")
s["route"] = np.where(s.contact_policy.eq("OK_TO_CALL"), "bot:" + s.use_case,
                      s.contact_policy.str.lower())

keep = ["route", "contact_policy", "reason", "cool_off_days", "use_case", "use_case_confidence",
        "secondary_use_cases", "last_bucket", "last_trigger", "new_business", "thin_catalog",
        "paid_status", "data_tier", "eng_cqs", "eng_product_count", "reply_ratio_1yr",
        "pns_answer_ratio_1yr", "days_since_last_bot_call", "last_bot_disposition"]
out = s[keep].reset_index()
out.to_parquet(SEG / "seller_use_case.parquet", index=False)
out.to_csv(SEG / "seller_use_case.csv", index=False)

# --- validation -----------------------------------------------------------------------
print("rows", len(out))
print(pd.crosstab(out.use_case, out.contact_policy, margins=True))
print(pd.crosstab(out.use_case, out.use_case_confidence, normalize="index").round(2))
print("signals per seller", n_sig.value_counts().sort_index().to_dict())

# Out-of-time check: label from calls before Sep, score September calls.
# Uses B flags (snapshot) + trigger of the September call itself (known at dial time).
sep = calls[calls.call_start_time >= "2026-09-01"].copy()
sep["trigger"] = sep.redis_bucket.map(TRIGGER_GROUP).fillna("generic")
sep = sep.merge(out[["fk_glusr_usr_id", "use_case"]], on="fk_glusr_usr_id")
sep["early_drop"] = sep.lead_call_duration < 10
sep["ni"] = sep.disposition_label.eq("Not Interested")
v = sep.groupby("use_case").agg(calls=("attempt_id", "size"), meeting=("meeting_fixed", "mean"),
                                not_interested=("ni", "mean"), early_drop=("early_drop", "mean"),
                                median_sec=("lead_call_duration", "median"))
v.loc["ALL"] = [len(sep), sep.meeting_fixed.mean(), sep.ni.mean(), sep.early_drop.mean(),
                sep.lead_call_duration.median()]
print("September outcomes by assigned use case (assignment uses data incl. Sep — descriptive, not a holdout):")
print(v.round(3))
summary = {"sizes": out.use_case.value_counts().to_dict(),
           "routes": out.route.value_counts().to_dict(),
           "confidence": out.use_case_confidence.value_counts().to_dict(),
           "sep_outcomes": v.round(4).reset_index().to_dict(orient="records")}
(SEG / "work" / "e01_summary.json").write_text(json.dumps(summary, indent=1, default=str))
