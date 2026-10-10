"""Holdout check: rebuild use_case from calls BEFORE 2026-09-01 only, score September calls.
B's profile flags (eng_* snapshot) are reused as-is; warm and trigger signals are rebuilt pre-cut."""
from pathlib import Path
import pandas as pd
SEG = Path(__file__).resolve().parent.parent
CACHE = SEG.parent / "cache"
CUT = pd.Timestamp("2026-09-01")
exec(open(SEG / "scripts" / "e01_final_assign.py").read().split("b = pd.read_parquet")[0])  # TRIGGER_GROUP

b = pd.read_parquet(SEG / "B_seller_segments.parquet").set_index("fk_glusr_usr_id")
calls = pd.read_parquet(CACHE / "bot_calls.parquet", columns=["attempt_id", "fk_glusr_usr_id", "redis_bucket",
        "call_start_time", "disposition_label", "meeting_fixed", "lead_call_duration"]).sort_values("call_start_time")
th = pd.read_parquet(SEG / "C_call_themes.parquet", columns=["attempt_id", "th_pricing", "th_free_payment",
        "th_profile", "th_leads", "th_not_using"])
pre, sep = calls[calls.call_start_time < CUT], calls[calls.call_start_time >= CUT]
last = pre.groupby("fk_glusr_usr_id").tail(1).set_index("fk_glusr_usr_id")
pth = pre[["attempt_id", "fk_glusr_usr_id"]].merge(th, on="attempt_id").groupby("fk_glusr_usr_id").max(numeric_only=True)

s = b.loc[b.index.isin(sep.fk_glusr_usr_id.unique())].copy()
s["last_trigger"] = last.redis_bucket.reindex(s.index).map(TRIGGER_GROUP).fillna("generic")
s.loc[~s.index.isin(last.index), "last_trigger"] = "none"
days = (CUT - last.call_start_time.reindex(s.index)).dt.days
warm_pre = last.disposition_label.reindex(s.index).isin(["Meeting Fixed", "Call Later / Busy"]) & (days <= 60)
P = lambda c: pth[c].reindex(s.index).fillna(0).astype(bool)
sig = {
    "warm_followup": warm_pre | s.last_trigger.eq("warm"),
    "lead_engagement": s.f_lead_nonconsumption | s.last_trigger.eq("leads"),
    "free_to_paid": s.f_free_to_paid | s.last_trigger.eq("monetise")
                    | (s.last_trigger.eq("monetise_soft") & (P("th_pricing") | P("th_free_payment"))),
    "reactivation": s.f_dormant | P("th_not_using"),
    "profile_onboarding": s.f_profile_enrichment | s.f_low_demand_active
                          | s.last_trigger.isin(["onboard", "profile"]) | P("th_profile"),
}
ORDER = ["warm_followup", "lead_engagement", "free_to_paid", "reactivation", "profile_onboarding"]
s["use_case"] = "discovery"
for cat in reversed(ORDER):
    s.loc[sig[cat], "use_case"] = cat
s.loc[s.use_case.eq("discovery") & s.last_trigger.eq("monetise_soft"), "use_case"] = "free_to_paid"
s["first_sep_trigger"] = sep.groupby("fk_glusr_usr_id").redis_bucket.first().reindex(s.index).map(TRIGGER_GROUP).fillna("generic")

x = sep.merge(s[["use_case"]], left_on="fk_glusr_usr_id", right_index=True)
x["early_drop"] = x.lead_call_duration < 10
x["ni"] = x.disposition_label.eq("Not Interested")
x["call_later"] = x.disposition_label.eq("Call Later / Busy")
agg = dict(sellers=("fk_glusr_usr_id", "nunique"), calls=("attempt_id", "size"), meeting=("meeting_fixed", "mean"),
           not_interested=("ni", "mean"), call_later=("call_later", "mean"), early_drop=("early_drop", "mean"),
           median_sec=("lead_call_duration", "median"))
v = x.groupby("use_case").agg(**agg)
v.loc["ALL (called before Sep)"] = x.agg(**{k: (c, f) for k, (c, f) in agg.items()}).iloc[:, 0] if False else \
    [x.fk_glusr_usr_id.nunique(), len(x), x.meeting_fixed.mean(), x.ni.mean(), x.call_later.mean(), x.early_drop.mean(), x.lead_call_duration.median()]
print("HOLDOUT: Sep calls of sellers already called before Sep, labelled from pre-Sep data only")
print(v.round(3).to_string())
first = x.groupby("fk_glusr_usr_id").head(1)
f = first.groupby("use_case").agg(**agg)
print("\nFirst September call per seller only:")
print(f.round(3).to_string())
(SEG / "work" / "e02_holdout.csv").write_text(v.round(4).to_csv())
# per-seller holdout labels, reused by j01_jev_validate.py
s[["use_case"]].rename(columns={"use_case": "rule_use_case"}).reset_index().to_parquet(SEG / "work" / "e02_holdout_labels.parquet", index=False)
