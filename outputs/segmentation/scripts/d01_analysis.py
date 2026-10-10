"""D01: exec-call overlay, suppression signals, contact fatigue, best time. Writes tables to work/d/*.csv (memory-light)."""
import gc, os
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.dirname(BASE), "cache")
WORK = os.path.join(BASE, "work"); OUT = os.path.join(WORK, "d")
os.makedirs(OUT, exist_ok=True)
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)

def save(df, name):
    df.to_csv(os.path.join(OUT, name + ".csv")); print("\n##", name); print(df.to_string())

def outc(g):
    return pd.Series({"n": len(g), "sellers": g.fk.nunique(), "meeting": g.mtg.mean(), "not_int": g.ni.mean(),
                      "early_drop": g.early.mean(), "med_dur": g.dur.median()})

# ---------- bot calls ----------
b = pd.read_parquet(os.path.join(CACHE, "bot_calls.parquet"),
    columns=["attempt_id", "fk_glusr_usr_id", "call_attempt_count", "call_start_time", "lead_call_duration", "disposition_label", "meeting_fixed"])
b = b.rename(columns={"fk_glusr_usr_id": "fk", "call_start_time": "t", "lead_call_duration": "dur", "call_attempt_count": "att"})
print("attempt_id unique:", b.attempt_id.is_unique, len(b))
b["mtg"] = b.meeting_fixed.astype("int8"); b["ni"] = (b.disposition_label == "Not Interested").astype("int8")
b["early"] = (b.dur < 10).astype("int8"); b = b.drop(columns=["meeting_fixed"])
b = b.sort_values(["fk", "t"]).reset_index(drop=True)
base = outc(b); save(base.to_frame("all_calls"), "d00_baseline")

# ---------- 1. exec calls ----------
e = pd.read_parquet(os.path.join(CACHE, "exec_calls.parquet"),
    columns=["fk_glusr_usr_id", "module", "status", "call_start_time", "call_duration", "call_duration_customer"])
e = e.rename(columns={"fk_glusr_usr_id": "fk"}); e["t"] = pd.to_datetime(e.call_start_time); e = e.drop(columns="call_start_time")
e = e[(e.t >= "2026-08-01") & (e.t < "2026-10-01")]
e["ans"] = (e.status == "Answered").astype("int8")
bot_sellers = set(b.fk.unique())
mod = e.groupby("module").apply(lambda g: pd.Series({"calls": len(g), "sellers": g.fk.nunique(), "answer_rate": g.ans.mean(),
    "med_cust_sec_answered": g.loc[g.ans == 1, "call_duration_customer"].median(),
    "calls_per_seller": len(g) / g.fk.nunique(), "pct_sellers_in_bot_data": np.mean([x in bot_sellers for x in g.fk.unique()])}))
save(mod.sort_values("calls", ascending=False), "d01_exec_modules")
print("exec months:", e.t.dt.to_period("M").value_counts().to_dict(), "status:", e.status.value_counts().to_dict())
print("hours exec:", e.t.dt.hour.value_counts().sort_index().to_dict())
COMPL = ["CustTkt", "ServiceOVP", "OnlineFeedback"]
# overlap between modules at seller level
sm = e.groupby(["fk", "module"]).size().unstack(fill_value=0) > 0
save(sm.astype(int).T.dot(sm.astype(int)), "d01b_module_seller_overlap")

# ---------- 2. bot vs exec timing ----------
ba = b[b.t >= "2026-08-01"].copy()
ex = e[["fk", "t", "module", "ans"]].sort_values("t").rename(columns={"t": "te"})
ba = ba.sort_values("t")
prev = pd.merge_asof(ba[["attempt_id", "t", "fk"]], ex, left_on="t", right_on="te", by="fk", direction="backward")
nxt = pd.merge_asof(ba[["attempt_id", "t", "fk"]], ex, left_on="t", right_on="te", by="fk", direction="forward")
ba["d_prev"] = (ba.t - prev.te.values).dt.total_seconds().values / 86400
ba["d_next"] = (nxt.te.values - ba.t).dt.total_seconds().values / 86400
ba["prev_mod"] = prev.module.values; ba["next_mod"] = nxt.module.values
ex_sellers = set(e.fk.unique()); compl_sellers = set(e.loc[e.module.isin(COMPL), "fk"])
def grp(r):
    if r.fk not in ex_sellers: return "C_no_exec_contact_aug_sep"
    if r.d_prev <= 7: return "A1_exec_in_prior_7d"
    if r.d_next <= 7: return "A2_exec_in_next_7d"
    return "B_exec_aug_sep_but_>7d_away"
ba["exgrp"] = [grp(r) for r in ba.itertuples()]
save(ba.groupby("exgrp").apply(outc), "d02_bot_vs_exec_window")
# finer prior-gap
ba["prev_bin"] = pd.cut(ba.d_prev, [-0.01, 1, 3, 7, 14, 30, 61], labels=["<=1d", "1-3d", "3-7d", "7-14d", "14-30d", "30-61d"])
save(ba.groupby("prev_bin", observed=True).apply(outc), "d02b_days_since_exec_call")
w7 = ba[ba.d_prev <= 7]
save(w7.groupby("prev_mod").apply(outc), "d02c_prior7d_by_module")
ba["compl_seller"] = ba.fk.isin(compl_sellers)
save(ba.groupby("compl_seller").apply(outc), "d02d_complaint_module_sellers")
del prev, nxt; gc.collect()

# ---------- 3. event signals -> subsequent calls ----------
dp = pd.read_parquet(os.path.join(WORK, "ev_disposition.parquet"))
iv = pd.read_parquet(os.path.join(WORK, "ev_ivr.parquet"))
se = pd.read_parquet(os.path.join(WORK, "ev_se_contact.parquet"), columns=["attempt_id", "se_cat"])
q = pd.read_parquet(os.path.join(WORK, "ev_questions.parquet"), columns=["attempt_id", "q_cat"])
ev = b[["attempt_id", "fk", "t"]]
sig = {}
x = ev.merge(dp, on="attempt_id")
for v in ["wrong_number", "do_not_call", "not_interested", "already_in_touch_with_im", "alternate_number_or_not_dm", "callback_requested", "budget_issue_denial", "meeting_fixed", "online_meeting_fixed"]:
    sig["disp=" + v] = x[x.ev_disp == v]
for v in ["business_closed", "bad_past_experience", "voicemail", "already_met_exec", "in_touch_with_exec", "no_response", "using_competitor", "flat_refusal_or_no_requirement"]:
    sig["sub=" + v] = x[x.ev_subdisp == v]
sig["ANY_disposition_eval(baseline)"] = x
y = ev.merge(iv, on="attempt_id")
for v in y.ivr_cat.unique(): sig["ivr=" + v] = y[y.ivr_cat == v]
z = ev.merge(se, on="attempt_id")
for v in z.se_cat.unique(): sig["se=" + v] = z[z.se_cat == v]
qq = ev.merge(q[q.q_cat.astype(str).str.contains("Bot", case=False)].drop_duplicates("attempt_id"), on="attempt_id")
sig["q=AI_bot_confirmation"] = qq
# NI-count signals from bot_calls itself
b["ni_cum"] = b.groupby("fk").ni.cumsum(); b["mtg_cum"] = b.groupby("fk").mtg.cumsum()
for k in [1, 2, 3]:
    sig[f"NI_count_reached_{k}_no_meeting"] = b[(b.ni_cum == k) & (b.ni == 1) & (b.mtg_cum == 0)]
sig["any_bot_call(baseline_repeat)"] = b.drop_duplicates("fk")
rows = []
tfirst_all = {}
for name, s in sig.items():
    f = s.groupby("fk").t.min().rename("t0")
    tfirst_all[name] = f
    sub = b.merge(f, left_on="fk", right_index=True)
    sub = sub[sub.t > sub.t0]
    gap = (sub.groupby("fk").t.min() - f.reindex(sub.fk.unique())).dt.total_seconds() / 86400
    r = outc(sub) if len(sub) else pd.Series({"n": 0})
    r["flag_sellers"] = len(f); r["sellers_called_again"] = sub.fk.nunique(); r["pct_called_again"] = sub.fk.nunique() / len(f)
    r["med_gap_days_to_next"] = gap.median() if len(gap) else np.nan
    # meeting rate among subsequent calls >=14 days later
    lt = sub[(sub.t - sub.t0).dt.total_seconds() / 86400 >= 14]
    r["n_14d+"] = len(lt); r["meeting_14d+"] = lt.mtg.mean() if len(lt) else np.nan
    st = sub[(sub.t - sub.t0).dt.total_seconds() / 86400 < 7]
    r["n_<7d"] = len(st); r["meeting_<7d"] = st.mtg.mean() if len(st) else np.nan
    r["sellers_ever_meeting_after"] = sub.groupby("fk").mtg.max().mean() if len(sub) else np.nan
    rows.append(r.rename(name))
save(pd.DataFrame(rows), "d03_signal_subsequent_outcomes")
# same-call outcome for ivr categories
yy = y.merge(b[["attempt_id", "mtg", "early", "dur"]], on="attempt_id")
save(yy.groupby("ivr_cat").agg(n=("mtg", "size"), meeting=("mtg", "mean"), early=("early", "mean"), med_dur=("dur", "median")), "d03b_ivr_same_call")

# ---------- seller-level flags ----------
s = pd.read_parquet(os.path.join(CACHE, "sellers.parquet"), columns=["fk_glusr_usr_id", "do_not_call_requested", "already_in_touch_with_executive",
    "showed_frustration", "asked_if_talking_to_bot", "calls_not_interested", "calls_meeting_fixed", "nature_of_business", "bot_answered"])
s = s.rename(columns={"fk_glusr_usr_id": "fk"})
s["F_dnc"] = s.do_not_call_requested == 1; s["F_exec_touch"] = s.already_in_touch_with_executive == 1
s["F_frustr"] = s.showed_frustration == 1; s["F_botq"] = s.asked_if_talking_to_bot == 1
s["F_ni2_0m"] = (s.calls_not_interested >= 2) & (s.calls_meeting_fixed.fillna(0) == 0)
lastd = x.sort_values("t").groupby("fk").ev_disp.last()
everd = x.groupby("fk").ev_disp.agg(set)
s["F_wrong_num"] = s.fk.map(everd).map(lambda v: isinstance(v, set) and "wrong_number" in v)
s["F_wrong_num_last"] = s.fk.map(lastd) == "wrong_number"
evers = x.groupby("fk").ev_subdisp.agg(set)
s["F_closed"] = s.fk.map(evers).map(lambda v: isinstance(v, set) and "business_closed" in v)
s["F_ivr_only"] = s.fk.isin(set(y.loc[y.ivr_cat != "human_answered_and_talked", "fk"])) & ~s.fk.isin(set(y.loc[y.ivr_cat == "human_answered_and_talked", "fk"]))
s["F_exec_aug_sep"] = s.fk.isin(ex_sellers); s["F_open_ticket"] = s.fk.isin(compl_sellers)
F = [c for c in s.columns if c.startswith("F_")]
fm = s[F].astype(int)
save(fm.T.dot(fm), "d04_flag_overlap_matrix")
# outcomes of ALL bot calls for flagged sellers (seller-level flags are not time-stamped)
bb = b.merge(s[["fk"] + F], on="fk", how="left")
rows = [outc(bb[bb[c] == True]).rename(c) for c in F]
rows.append(outc(bb).rename("ALL"))
save(pd.DataFrame(rows), "d04b_flag_all_call_outcomes")
s[["fk"] + F + ["calls_not_interested", "calls_meeting_fixed"]].to_parquet(os.path.join(OUT, "seller_flags_raw.parquet"), index=False)
lastt = b.groupby("fk").t.max(); lastt.rename("last_bot_call").to_frame().to_parquet(os.path.join(OUT, "last_bot_call.parquet"))
del bb, x, y, z, dp, iv, se, q, qq; gc.collect()

# ---------- 4. fatigue ----------
b["gap"] = b.groupby("fk").t.diff().dt.total_seconds() / 86400
b["att_b"] = b.att.clip(upper=10)
save(b.groupby("att_b").apply(outc), "d05_by_attempt")
b["seq"] = b.groupby("fk").cumcount() + 1
save(b.groupby(b.seq.clip(upper=10)).apply(outc), "d05b_by_answered_call_seq")
gb = pd.cut(b.gap, [-0.001, 0.0417, 1, 2, 3, 5, 7, 14, 30, 60, 200], labels=["<1h", "1h-1d", "1-2d", "2-3d", "3-5d", "5-7d", "7-14d", "14-30d", "30-60d", "60d+"])
b["gap_b"] = gb
save(b[b.seq > 1].groupby("gap_b", observed=True).apply(outc), "d05c_by_gap_days")
# gap controlled for previous outcome
b["prev_disp"] = b.groupby("fk").disposition_label.shift()
b["prev_early"] = b.groupby("fk").early.shift()
t = b[b.seq > 1].pivot_table(index="gap_b", columns="prev_disp", values="mtg", aggfunc="mean", observed=True)
tn = b[b.seq > 1].pivot_table(index="gap_b", columns="prev_disp", values="mtg", aggfunc="size", observed=True)
save(t.round(4), "d05d_meeting_by_gap_x_prevdisp"); save(tn, "d05d_n")
t = b[b.seq > 1].pivot_table(index="gap_b", columns="prev_disp", values="early", aggfunc="mean", observed=True)
save(t.round(4), "d05e_early_by_gap_x_prevdisp")
# seq x gap (meeting)
b["seq_b"] = b.seq.clip(upper=5)
save(b[b.seq > 1].pivot_table(index="gap_b", columns="seq_b", values="mtg", aggfunc="mean", observed=True).round(4), "d05f_meeting_gap_x_seq")
# cumulative yield: share of all meetings reached by answered call k
mt = b[b.mtg == 1].seq.clip(upper=15).value_counts().sort_index()
save(pd.DataFrame({"meetings": mt, "cum_share": mt.cumsum() / mt.sum()}), "d05g_cum_meeting_share_by_seq")
# sellers reaching seq k
save(b.groupby(b.seq.clip(upper=12)).fk.nunique().to_frame("sellers_reaching"), "d05h_sellers_by_seq")

# ---------- 5. time ----------
b["hour"] = b.t.dt.hour; b["wd"] = b.t.dt.day_name().str[:3]
save(b.groupby("hour").apply(outc), "d06_by_hour")
save(b.groupby("wd").apply(outc), "d06b_by_weekday")
fa = b[b.seq == 1]
save(fa.groupby("hour").apply(outc), "d06c_by_hour_first_call")
b = b.merge(s[["fk", "nature_of_business"]], on="fk", how="left")
b["nob"] = b.nature_of_business.fillna("NA").replace({"Retailer": "Trader - Retailer", "Wholesaler/Distributor": "Trader - Wholesaler/Distributor", "Unknown": "NA"})
b["hband"] = pd.cut(b.hour, [8, 10, 12, 14, 16, 18, 21], labels=["09-10", "11-12", "13-14", "15-16", "17-18", "19-20"])
save(b.pivot_table(index="hband", columns="nob", values="mtg", aggfunc="mean", observed=True).round(4), "d06d_meeting_hband_x_nob")
save(b.pivot_table(index="hband", columns="nob", values="early", aggfunc="mean", observed=True).round(4), "d06e_early_hband_x_nob")
save(b.pivot_table(index="hband", columns="nob", values="mtg", aggfunc="size", observed=True), "d06f_n_hband_x_nob")
save(b.pivot_table(index="wd", columns="nob", values="mtg", aggfunc="mean", observed=True).round(4), "d06g_meeting_wd_x_nob")
save(b.pivot_table(index="hour", columns="wd", values="mtg", aggfunc="mean", observed=True).round(3), "d06h_hour_x_wd_meeting")
# hour by first-call controls for attempt mix
save(fa.merge(s[["fk"]], on="fk").groupby("hour").att.mean().to_frame("mean_att"), "d06i_att_mix_hour")
print("bot month counts", b.t.dt.to_period("M").value_counts().sort_index().to_dict())
