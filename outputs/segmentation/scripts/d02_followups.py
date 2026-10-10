"""D02: follow-ups - first-call time controls, exec calls after bot meetings, module seller profile."""
import os, numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); CACHE = os.path.join(os.path.dirname(BASE), "cache")
b = pd.read_parquet(os.path.join(CACHE, "bot_calls.parquet"), columns=["fk_glusr_usr_id", "call_start_time", "lead_call_duration", "meeting_fixed", "redis_bucket"]).rename(columns={"fk_glusr_usr_id": "fk", "call_start_time": "t"})
b = b.sort_values(["fk", "t"]); b["seq"] = b.groupby("fk").cumcount() + 1; b["early"] = b.lead_call_duration < 10
f = b[b.seq == 1].copy(); f["wd"] = f.t.dt.day_name().str[:3]; f["hour"] = f.t.dt.hour
print(f.groupby("wd").agg(n=("meeting_fixed", "size"), mtg=("meeting_fixed", "mean"), early=("early", "mean")))
s = pd.read_parquet(os.path.join(CACHE, "sellers.parquet"), columns=["fk_glusr_usr_id", "nature_of_business"]).rename(columns={"fk_glusr_usr_id": "fk"})
f = f.merge(s, on="fk", how="left"); f["nob"] = f.nature_of_business.fillna("NA").replace({"Retailer": "Trader - Retailer", "Wholesaler/Distributor": "Trader - Wholesaler/Distributor", "Unknown": "NA"})
f["hband"] = pd.cut(f.hour, [8, 10, 12, 14, 16, 18, 21], labels=["09-10", "11-12", "13-14", "15-16", "17-18", "19-20"])
print("FIRST CALL meeting hband x nob"); print(f.pivot_table(index="hband", columns="nob", values="meeting_fixed", aggfunc="mean", observed=True).round(4))
print(f.pivot_table(index="hband", columns="nob", values="early", aggfunc="mean", observed=True).round(4))
print(f.pivot_table(index="hband", columns="nob", values="early", aggfunc="size", observed=True))
print(f.pivot_table(index="wd", columns="nob", values="meeting_fixed", aggfunc="mean", observed=True).round(4))
# month mix by weekday (weekend effect could be calendar/version)
print(f.groupby([f.t.dt.to_period("M"), "wd"]).meeting_fixed.mean().unstack().round(3))
# exec after bot meeting
e = pd.read_parquet(os.path.join(CACHE, "exec_calls.parquet"), columns=["fk_glusr_usr_id", "module", "call_start_time"]).rename(columns={"fk_glusr_usr_id": "fk"})
e["te"] = pd.to_datetime(e.call_start_time); e = e.sort_values("te")
ba = b[b.t >= "2026-08-01"].sort_values("t")
nx = pd.merge_asof(ba[["t", "fk", "meeting_fixed"]], e[["fk", "te", "module"]], left_on="t", right_on="te", by="fk", direction="forward")
nx["within7"] = (nx.te - nx.t).dt.total_seconds() / 86400 <= 7
print("P(exec call within next 7d | bot call outcome)"); print(nx.groupby("meeting_fixed").within7.agg(["mean", "size"]))
print(nx[nx.within7].groupby(["meeting_fixed", "module"]).size().unstack(0))
# bucket mix of exec module sellers
bb = b.drop_duplicates("fk", keep="last")[["fk", "redis_bucket"]]
em = e.drop_duplicates(["fk", "module"]).merge(bb, on="fk")
print(em.groupby("module").redis_bucket.value_counts(normalize=True).unstack().round(2)[["PIM", "PUA", "UA", "PAM", "OLP"]])
print("all", bb.redis_bucket.value_counts(normalize=True).round(2).head(5).to_dict())
