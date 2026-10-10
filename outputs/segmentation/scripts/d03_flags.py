"""D03: build D_seller_flags.parquet (contact policy per seller) from work/d/seller_flags_raw.parquet + bot/exec calls."""
import os, numpy as np, pandas as pd
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); CACHE = os.path.join(os.path.dirname(BASE), "cache"); OUT = os.path.join(BASE, "work", "d")
END = pd.Timestamp("2026-10-01")
s = pd.read_parquet(os.path.join(OUT, "seller_flags_raw.parquet"))
dp = pd.read_parquet(os.path.join(BASE, "work", "ev_disposition.parquet"))
b = pd.read_parquet(os.path.join(CACHE, "bot_calls.parquet"), columns=["attempt_id", "fk_glusr_usr_id", "call_start_time", "meeting_fixed"]).rename(columns={"fk_glusr_usr_id": "fk", "call_start_time": "t"})
x = b.merge(dp, on="attempt_id").sort_values("t")
last = x.groupby("fk").agg(last_disp=("ev_disp", "last"), last_sub=("ev_subdisp", "last"))
everbad = x[x.ev_subdisp == "bad_past_experience"].fk.unique(); everbudget = x[x.ev_disp == "budget_issue_denial"].fk.unique()
lastbot = b.groupby("fk").t.max().rename("last_bot_call")
r30 = b[b.t >= END - pd.Timedelta(days=30)].groupby("fk").agg(n30=("t", "size"), m30=("meeting_fixed", "sum"))
e = pd.read_parquet(os.path.join(CACHE, "exec_calls.parquet"), columns=["fk_glusr_usr_id", "module", "call_start_time"]).rename(columns={"fk_glusr_usr_id": "fk"})
e["te"] = pd.to_datetime(e.call_start_time)
laste = e.groupby("fk").te.max().rename("last_exec_call")
lastc = e[e.module.isin(["CustTkt", "ServiceOVP", "OnlineFeedback"])].groupby("fk").te.max().rename("last_complaint_call")
s = s.join(last, on="fk").join(lastbot, on="fk").join(r30, on="fk").join(laste, on="fk").join(lastc, on="fk")
s["bad_exp"] = s.fk.isin(everbad); s["budget_last"] = s.last_disp == "budget_issue_denial"
s["dnc_any"] = s.F_dnc | (s.last_disp == "do_not_call") | s.fk.isin(x[x.ev_disp == "do_not_call"].fk.unique())
s["fatigue30"] = (s.n30.fillna(0) >= 4) & (s.m30.fillna(0) == 0)
s["exec_recent7"] = s.last_exec_call >= END - pd.Timedelta(days=7)
ni = s.calls_not_interested.fillna(0); m0 = s.calls_meeting_fixed.fillna(0) == 0
rules = [  # (policy, reason, cool_off_days, mask) in priority order
    ("SUPPRESS", "do_not_call_requested", None, s.dnc_any),
    ("SUPPRESS", "wrong_number_last_call", None, s.F_wrong_num_last),
    ("SUPPRESS", "business_closed", None, s.F_closed),
    ("ROUTE_TO_HUMAN", "complaint_or_service_contact", None, s.F_open_ticket),
    ("ROUTE_TO_HUMAN", "showed_frustration", None, s.F_frustr),
    ("ROUTE_TO_HUMAN", "bad_past_experience", None, s.bad_exp),
    ("ROUTE_TO_HUMAN", "already_in_touch_with_executive", None, s.F_exec_touch),
    ("COOL_OFF_N_DAYS", "not_interested_3plus_no_meeting", 90, (ni >= 3) & m0),
    ("COOL_OFF_N_DAYS", "not_interested_2_no_meeting", 30, (ni == 2) & m0),
    ("COOL_OFF_N_DAYS", "4plus_answered_calls_30d_no_meeting", 30, s.fatigue30),
    ("COOL_OFF_N_DAYS", "budget_denial_last_call", 30, s.budget_last),
    ("COOL_OFF_N_DAYS", "ivr_or_silence_only", 14, s.F_ivr_only),
    ("COOL_OFF_N_DAYS", "exec_call_in_last_7d", 7, s.exec_recent7),
]
s["contact_policy"] = "OK_TO_CALL"; s["reason"] = ""; s["cool_off_days"] = np.nan; s["all_reasons"] = ""
for pol, rs, cd, m in reversed(rules):  # reversed so highest priority wins
    m = m.fillna(False).astype(bool)
    s.loc[m, "contact_policy"] = pol; s.loc[m, "reason"] = rs; s.loc[m, "cool_off_days"] = cd
for pol, rs, cd, m in rules:
    m = m.fillna(False).astype(bool); s.loc[m, "all_reasons"] = s.loc[m, "all_reasons"] + rs + ";"
s["all_reasons"] = s.all_reasons.str.rstrip(";")
s.loc[s.contact_policy == "OK_TO_CALL", "reason"] = "no_suppression_signal"
s.loc[(s.contact_policy == "OK_TO_CALL") & s.F_botq, "reason"] = "ok_disclose_ai_if_asked"
out = s.rename(columns={"fk": "fk_glusr_usr_id", "F_exec_aug_sep": "exec_contact_aug_sep", "F_open_ticket": "open_ticket"})[
    ["fk_glusr_usr_id", "contact_policy", "reason", "cool_off_days", "exec_contact_aug_sep", "open_ticket", "all_reasons", "last_bot_call", "last_exec_call", "last_complaint_call"]]
out["cool_off_days"] = out.cool_off_days.astype("Int16")
out.to_parquet(os.path.join(BASE, "D_seller_flags.parquet"), index=False)
print(len(out)); print(out.contact_policy.value_counts()); print(out.groupby(["contact_policy", "reason"]).size())
print("multi-reason sellers:", (out.all_reasons.str.count(";") >= 1).sum())
# outcomes of all bot calls by assigned policy (descriptive; in-sample)
bb = pd.read_parquet(os.path.join(CACHE, "bot_calls.parquet"), columns=["fk_glusr_usr_id", "meeting_fixed", "lead_call_duration"]).merge(out[["fk_glusr_usr_id", "contact_policy", "reason"]], on="fk_glusr_usr_id")
bb["early"] = bb.lead_call_duration < 10
print(bb.groupby("reason").agg(n=("meeting_fixed", "size"), meeting=("meeting_fixed", "mean"), early=("early", "mean")).round(4))
