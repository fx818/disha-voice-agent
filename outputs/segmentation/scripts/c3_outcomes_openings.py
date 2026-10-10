"""C3: outcomes per theme vs baseline, theme x bucket / pitch, bot version + opening-hook comparisons.
Reads work/c2_calls_full.parquet (+ call_turns for opening hooks). Writes work/c3_*.csv"""
import gc, os, re, warnings
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.dirname(BASE), "cache")
WORK = os.path.join(BASE, "work")
THEMES = ["pricing", "free_payment", "profile", "leads", "not_using", "callback", "exec", "wrong_ivr", "identity", "bot_doubt"]
PITCH = ["pitch_paid", "pitch_profile", "pitch_enquiry", "pitch_payment_attempt", "pitch_free_plan"]


def z2(p1, n1, p0, n0):
    p = (p1 * n1 + p0 * n0) / (n1 + n0)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n0)) if 0 < p < 1 else np.nan
    return (p1 - p0) / se if se else np.nan


def strength(n, z):
    if n >= 1000 and abs(z) >= 3:
        return "strong"
    if abs(z) >= 2 or n >= 500:
        return "moderate"
    return "weak"


def outc(g):
    return pd.Series({"n": len(g), "meeting": g.meeting_fixed.mean(), "not_int": (g.disposition_label == "Not Interested").mean(),
                      "call_later": (g.disposition_label == "Call Later / Busy").mean(),
                      "early_drop": (g.lead_call_duration < 10).mean(), "median_sec": g.lead_call_duration.median()})


df = pd.read_parquet(os.path.join(WORK, "c2_calls_full.parquet"))
df["meeting_fixed"] = df.meeting_fixed.fillna(0).astype(int)
df["engaged"] = df.lead_call_duration >= 10
bt = pq.read_table(os.path.join(CACHE, "bot_calls.parquet"), columns=["attempt_id", "call_start_time"]).to_pandas()
df = df.merge(bt, on="attempt_id", how="left"); del bt
base = outc(df); base_e = outc(df[df.engaged])
print("baseline", base.to_dict(), "\nengaged", base_e.to_dict())

rows = []
for th in THEMES:
    m = df["th_" + th]
    g = df[m]; o = outc(g)
    ge = g[g.engaged]; oe = outc(ge)
    rest_e = df[df.engaged & ~m]
    z = z2(oe.meeting, oe.n, rest_e.meeting_fixed.mean(), len(rest_e))
    rows.append({"theme": th, "n": int(o.n), "share": o.n / len(df), "meeting": o.meeting, "not_int": o.not_int,
                 "call_later": o.call_later, "early_drop": o.early_drop, "median_sec": o.median_sec,
                 "n_engaged": int(oe.n), "meeting_engaged": oe.meeting, "not_int_engaged": oe.not_int,
                 "meeting_engaged_rest": rest_e.meeting_fixed.mean(), "z_engaged": z,
                 "first_attempt_share": (g.call_attempt_count == 1).mean(), "strength": strength(oe.n, z)})
out = pd.DataFrame(rows)
out.loc[len(out)] = {"theme": "BASELINE(all)", "n": int(base.n), "share": 1, "meeting": base.meeting, "not_int": base.not_int,
                     "call_later": base.call_later, "early_drop": base.early_drop, "median_sec": base.median_sec,
                     "n_engaged": int(base_e.n), "meeting_engaged": base_e.meeting, "not_int_engaged": base_e.not_int,
                     "first_attempt_share": (df.call_attempt_count == 1).mean()}
nt = df[["th_" + t for t in THEMES[:-1]]].sum(axis=1)
g0 = df[nt == 0]; o0 = outc(g0)
out.loc[len(out)] = {"theme": "no_theme", "n": int(o0.n), "share": o0.n / len(df), "meeting": o0.meeting, "not_int": o0.not_int,
                     "call_later": o0.call_later, "early_drop": o0.early_drop, "median_sec": o0.median_sec}
out.to_csv(os.path.join(WORK, "c3_theme_outcomes.csv"), index=False)
print(out.round(3).to_string())

# co-occurrence
co = pd.DataFrame({a: [(df["th_" + a] & df["th_" + b]).sum() / max(df["th_" + a].sum(), 1) for b in THEMES] for a in THEMES}, index=THEMES).T
co.to_csv(os.path.join(WORK, "c3_cooccur.csv"))

# theme x redis bucket lift (share of theme calls in bucket / share of all calls in bucket)
bk = df.redis_bucket.fillna("NA")
allsh = bk.value_counts(normalize=True)
lift = {}
for th in THEMES:
    sh = bk[df["th_" + th]].value_counts(normalize=True)
    lift[th] = (sh / allsh).reindex(allsh.index[:12])
lift = pd.DataFrame(lift).T
lift.to_csv(os.path.join(WORK, "c3_theme_bucket_lift.csv"))
print(lift.round(2).to_string())
# theme rate inside each bucket
bkr = df.groupby(bk)[["th_" + t for t in THEMES]].mean()
bkr["n"] = bk.value_counts()
bkr.sort_values("n", ascending=False).head(14).to_csv(os.path.join(WORK, "c3_bucket_theme_rate.csv"))

# theme x pitch (meeting rate among engaged)
prow = []
for th in THEMES:
    for p in PITCH:
        g = df[df["th_" + th] & df[p] & df.engaged]
        if len(g) >= 50:
            prow.append({"theme": th, "pitch": p, "n": len(g), "meeting": g.meeting_fixed.mean(), "not_int": (g.disposition_label == "Not Interested").mean()})
for p in PITCH:
    g = df[df[p] & df.engaged]
    prow.append({"theme": "ALL_engaged", "pitch": p, "n": len(g), "meeting": g.meeting_fixed.mean(), "not_int": (g.disposition_label == "Not Interested").mean()})
pd.DataFrame(prow).to_csv(os.path.join(WORK, "c3_theme_pitch.csv"), index=False)

# ---------- bot versions ----------
v = df.lead_bot_version.fillna("NA")
vt = df.groupby(v).apply(outc)
vt["first_attempt"] = df.groupby(v).call_attempt_count.apply(lambda x: (x == 1).mean())
vt["period"] = df.groupby(v).call_start_time.agg(lambda x: f"{x.min():%m-%d}..{x.max():%m-%d}")
vt.to_csv(os.path.join(WORK, "c3_version_all.csv")); print(vt.round(3).to_string())
fa = df[df.call_attempt_count == 1]
vf = fa.groupby(fa.lead_bot_version.fillna("NA")).apply(outc)
vf.to_csv(os.path.join(WORK, "c3_version_first_attempt.csv"))
# matched window 28-30 Sep 14:00-21:00
cst = df.call_start_time
win = df[(cst >= "2026-09-28") & (cst < "2026-10-01") & (cst.dt.hour >= 14) & (cst.dt.hour < 21)]
vw = win.groupby(win.lead_bot_version.fillna("NA")).apply(outc)
vw.to_csv(os.path.join(WORK, "c3_version_window.csv")); print("window\n", vw.round(3).to_string())
# Sep overlap for last_met_d / arrowhead / main_vani: same weeks
sep = df[(cst >= "2026-09-01")]
vs = sep.groupby([sep.call_start_time.dt.isocalendar().week, sep.lead_bot_version.fillna("NA")]).apply(outc)
vs = vs[vs.n >= 200]
vs.to_csv(os.path.join(WORK, "c3_version_by_week_sep.csv")); print(vs.round(3).to_string())
# version within theme (engaged calls, first attempt, n>=100)
vrow = []
for th in THEMES:
    g = df[df["th_" + th] & df.engaged]
    for ver, gg in g.groupby(g.lead_bot_version.fillna("NA")):
        if len(gg) >= 100:
            vrow.append({"theme": th, "version": ver, "n": len(gg), "meeting": gg.meeting_fixed.mean(),
                         "not_int": (gg.disposition_label == "Not Interested").mean(), "median_sec": gg.lead_call_duration.median()})
pd.DataFrame(vrow).to_csv(os.path.join(WORK, "c3_version_theme.csv"), index=False)

# ---------- opening hooks from transcripts ----------
ct = pd.read_parquet(os.path.join(CACHE, "call_turns.parquet"), columns=["attempt_id", "turn_no", "speaker", "text", "start_sec", "end_sec"])
ct = ct.sort_values(["attempt_id", "turn_no"])
b = ct[ct.speaker == "bot"]
first = b.groupby("attempt_id").head(1).set_index("attempt_id")["text"].fillna("")
greet = np.where(first.str.contains(r"meri baat", case=False), "greet_kya_meri_baat_X_se",
                 np.where(first.str.contains(r"kya aap .* se bol rahe|kya aap .* se baat", case=False), "greet_kya_aap_X_se_bol_rahe",
                          np.where(first.str.strip().str.len() <= 10, "greet_hello_only", "greet_other")))
greet = pd.Series(greet, index=first.index, name="greeting")
pitch = b[b.text.str.contains("IndiaMART|इंडियामार्ट", case=False, na=False)].groupby("attempt_id").head(1)
pitch_ix = pitch.set_index("attempt_id")
pt = pitch_ix["text"].fillna("")
HOOKS = [("hook_prior_conversation", r"baat hui thi|pehle baat|baat hui"),
         ("hook_payment_attempt", r"kharidne|khareedne|payment|purchase"),
         ("hook_buyleads", r"buy[ -]?leads?"),
         ("hook_paid_explore", r"paid|premium|package"),
         ("hook_city_enquiry", r"category mein|enquir|inquir|इंक्वायरी"),
         ("hook_recent_activity", r"haal hi|recent"),
         ("hook_new_account", r"account banaya"),
         ("hook_demo_booked", r"demo"),
         ("hook_profile", r"profile|catalog|catalogue")]
def hook(t):
    for name, rx in HOOKS:
        if re.search(rx, t, re.I):
            return name
    return "hook_other"
hk = pt.map(hook).rename("hook")
plen = pt.str.split().str.len().rename("pitch_words")
# did the seller speak after the pitch?
seller_after = ct[ct.speaker == "seller"][["attempt_id", "turn_no"]].merge(pitch_ix[["turn_no"]].rename(columns={"turn_no": "pt"}), left_on="attempt_id", right_index=True)
n_after = seller_after[seller_after.turn_no > seller_after.pt].groupby("attempt_id").size()
op = pd.concat([greet, hk, plen], axis=1)
op["seller_turns_after_pitch"] = n_after.reindex(op.index).fillna(0)
op = op.merge(df.set_index("attempt_id")[["meeting_fixed", "lead_call_duration", "disposition_label", "call_attempt_count", "lead_bot_version"] + ["th_" + t for t in THEMES]],
              left_index=True, right_index=True, how="inner")
op["no_reply_after_pitch"] = (op.seller_turns_after_pitch == 0) & op.hook.notna()
op.to_parquet(os.path.join(WORK, "c3_openings.parquet"))
def oo(g):
    return pd.Series({"n": len(g), "meeting": g.meeting_fixed.mean(), "early_drop": (g.lead_call_duration < 10).mean(),
                      "no_reply_after_pitch": g.no_reply_after_pitch.mean(), "not_int": (g.disposition_label == "Not Interested").mean(),
                      "median_sec": g.lead_call_duration.median(), "first_attempt": (g.call_attempt_count == 1).mean()})
hk_t = op[op.hook.notna()].groupby("hook").apply(oo).sort_values("n", ascending=False)
hk_t.to_csv(os.path.join(WORK, "c3_hooks.csv")); print(hk_t.round(3).to_string())
hk_fa = op[op.hook.notna() & (op.call_attempt_count == 1)].groupby("hook").apply(oo).sort_values("n", ascending=False)
hk_fa.to_csv(os.path.join(WORK, "c3_hooks_first_attempt.csv")); print(hk_fa.round(3).to_string())
gr_t = op.groupby("greeting").apply(oo); gr_t.to_csv(os.path.join(WORK, "c3_greetings.csv")); print(gr_t.round(3).to_string())
hv = op[op.hook.notna()].groupby(["lead_bot_version", "hook"]).apply(oo); hv = hv[hv.n >= 50]
hv.to_csv(os.path.join(WORK, "c3_hooks_by_version.csv")); print(hv.round(3).to_string())
hrow = []
for th in THEMES:
    g = op[op["th_" + th] & op.hook.notna()]
    for h, gg in g.groupby("hook"):
        if len(gg) >= 40:
            r = oo(gg).to_dict(); r.update({"theme": th, "hook": h}); hrow.append(r)
pd.DataFrame(hrow).to_csv(os.path.join(WORK, "c3_hooks_theme.csv"), index=False)
# pitch length terciles (first attempt), drop/meeting
op2 = op[op.hook.notna()].copy()
op2["len_band"] = pd.cut(op2.pitch_words, [0, 25, 40, 55, 400], labels=["<=25", "26-40", "41-55", ">55"])
op2.groupby("len_band").apply(oo).to_csv(os.path.join(WORK, "c3_pitch_len.csv"))
print(op2.groupby("len_band").apply(oo).round(3).to_string())
