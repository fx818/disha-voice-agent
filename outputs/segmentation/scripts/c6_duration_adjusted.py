"""C6: duration-adjusted meeting/NI rates per theme (themes are only detectable in longer calls -> survivorship).
Expected rate = overall rate within the same duration bin, weighted by the theme's duration mix. Writes work/c6_duration_adjusted.csv"""
import os
import numpy as np
import pandas as pd
WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work")
THEMES = ["pricing", "free_payment", "profile", "leads", "not_using", "callback", "exec", "wrong_ivr", "identity", "bot_doubt"]
df = pd.read_parquet(os.path.join(WORK, "c2_calls_full.parquet"), columns=["lead_call_duration", "meeting_fixed", "disposition_label", "call_attempt_count"] + ["th_" + t for t in THEMES])
df["meeting_fixed"] = df.meeting_fixed.fillna(0)
df["ni"] = (df.disposition_label == "Not Interested").astype(float)
df["bin"] = pd.cut(df.lead_call_duration, [-1, 10, 20, 30, 45, 60, 90, 120, 180, 300, 1e6])
rate = df.groupby("bin")[["meeting_fixed", "ni"]].mean()
rows = []
for th in THEMES:
    g = df[df["th_" + th]]
    w = g.bin.value_counts(normalize=True)
    exp_m = (w * rate.meeting_fixed.reindex(w.index)).sum(); exp_ni = (w * rate.ni.reindex(w.index)).sum()
    fa = g[g.call_attempt_count == 1]
    rows.append({"theme": th, "n": len(g), "meeting": g.meeting_fixed.mean(), "expected_meeting_same_duration": exp_m,
                 "lift_meeting": g.meeting_fixed.mean() / exp_m, "not_int": g.ni.mean(), "expected_ni_same_duration": exp_ni,
                 "n_first_attempt": len(fa), "meeting_first_attempt": fa.meeting_fixed.mean()})
out = pd.DataFrame(rows); out.to_csv(os.path.join(WORK, "c6_duration_adjusted.csv"), index=False)
print(out.round(3).to_string()); print(rate.round(3))
