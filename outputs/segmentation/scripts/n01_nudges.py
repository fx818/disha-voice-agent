"""How many nudges pay off? Per call with a turn transcript: seller refusals, bot nudges after a refusal (persuasion
instead of a close), and what each nudge led to: a booked meeting with no further refusal, or irritation.

  .venv/bin/python -I outputs/segmentation/scripts/n01_nudges.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
C, S = ROOT / "outputs" / "cache", ROOT / "outputs" / "segmentation"

REFUSE = re.compile(
    r"interest(ed)? nahi|not interested|nahi+n? chahiye|nahi chaiye|zaru?o?rat nahi|zarurat nahi|need nahi|no need|"
    r"don'?t need|nahi karna|nahi lena|nahi le ?na|koi zaru?o?rat|mana kar|mat karo|band karo|nahi chahie|"
    r"नहीं चाहिए|नहीं चाहिये|इंटरेस्ट नहीं|interest नहीं|ज़रूरत नहीं|जरूरत नहीं|नहीं करना|नहीं लेना|मत करो|कोई ज़रूरत|कोई जरूरत", re.I)
IRRITATED = re.compile(
    r"bola na|kaha na|bol diya|bol to diya|baar baar|bar bar|pareshan|disturb|dimag|faltu|bakwas|samajh nahi aata kya|"
    r"बोला ना|कहा ना|बोल दिया|बार बार|बार-बार|परेशान|डिस्टर्ब|दिमाग|फालतू|बकवास", re.I)
CLOSE = re.compile(r"dhanya?wa?a?d|shukriya|thank|धन्यवाद|शुक्रिया|have a (good|nice)|accha din|अच्छा दिन|alvida", re.I)


def per_call(g):
    g = g.sort_values("turn_no")
    sp, tx = g.speaker.tolist(), g.text.fillna("").astype(str).tolist()
    refusals, nudges, events = 0, 0, []  # events: (k, worked_later?, irritated_next?)
    i = 0
    while i < len(sp):
        if sp[i] == "seller" and REFUSE.search(tx[i]):
            refusals += 1
            j = i + 1
            while j < len(sp) and sp[j] != "bot":
                j += 1
            if j < len(sp) and not CLOSE.search(tx[j]):  # bot kept persuading: a nudge
                nudges += 1
                k = j + 1
                while k < len(sp) and sp[k] != "seller":
                    k += 1
                nxt = tx[k] if k < len(sp) else ""
                later = " ".join(t for s, t in zip(sp[j + 1:], tx[j + 1:]) if s == "seller")
                events.append((nudges, bool(REFUSE.search(later)), bool(IRRITATED.search(nxt)), k >= len(sp)))
            i = j
        else:
            i += 1
    return refusals, nudges, events


def main():
    t = pd.read_parquet(C / "call_turns.parquet", columns=["attempt_id", "turn_no", "speaker", "text"])
    calls = pd.read_parquet(C / "bot_calls.parquet", columns=["attempt_id", "fk_glusr_usr_id", "meeting_fixed",
                                                               "disposition_label", "lead_call_duration"])
    uc = pd.read_parquet(S / "seller_use_case.parquet", columns=["fk_glusr_usr_id", "use_case", "contact_policy"])
    st = pd.read_parquet(C / "seller_table.parquet", columns=["fk_glusr_usr_id", "calls_not_interested",
                                                                "showed_frustration"])
    rows = []
    for aid, g in t.groupby("attempt_id", sort=False):
        r, n, ev = per_call(g)
        rows.append((aid, r, n, ev))
    d = pd.DataFrame(rows, columns=["attempt_id", "refusals", "nudges", "events"]).merge(calls, on="attempt_id")
    d = d.merge(uc, on="fk_glusr_usr_id", how="left").merge(st, on="fk_glusr_usr_id", how="left")
    d["meeting"] = d.meeting_fixed.fillna(False).astype(bool)
    d["history"] = np.where(d.showed_frustration.fillna(0) > 0, "frustrated before",
                   np.where(d.calls_not_interested.fillna(0) >= 2, "declined 2+ times before", "no refusal history"))
    print(f"calls with transcripts: {len(d):,}  with a seller refusal: {(d.refusals > 0).sum():,} "
          f"({(d.refusals > 0).mean():.1%})  meeting rate overall {d.meeting.mean():.1%}, "
          f"after any refusal {d[d.refusals > 0].meeting.mean():.1%}")

    def nudge_table(sub, label):
        out = []
        for k in (1, 2, 3):
            evs = [e for es in sub.events for e in es if e[0] == k]
            mt = [m for es, m in zip(sub.events, sub.meeting) for e in es if e[0] == k]
            if not evs:
                continue
            n = len(evs)
            worked = sum(1 for e, m in zip(evs, mt) if m and not e[1])  # booked, no refusal after this nudge
            irr = sum(e[2] for e in evs)
            hang = sum(e[3] for e in evs)
            out.append(dict(group=label, nudge=k, n=n, booked_after=worked / n, irritated=irr / n, hung_up=hang / n))
        return out

    res = nudge_table(d[d.refusals > 0], "ALL")
    for g, sub in d[d.refusals > 0].groupby("use_case"):
        res += nudge_table(sub, f"purpose: {g}")
    for g, sub in d[d.refusals > 0].groupby("history"):
        res += nudge_table(sub, f"history: {g}")
    for g, sub in d[d.refusals > 0].groupby("contact_policy"):
        res += nudge_table(sub, f"policy: {g}")
    r = pd.DataFrame(res)
    pd.set_option("display.width", 200)
    print(r.to_string(index=False, formatters={c: "{:.1%}".format for c in ("booked_after", "irritated", "hung_up")}))
    # how many nudges did the bot actually use, and the meeting rate by that count
    d2 = d[d.refusals > 0].copy()
    d2["nudge_bucket"] = d2.nudges.clip(upper=3).astype(str).replace({"3": "3+"})
    print("\nmeeting rate by nudges used (calls with a refusal):")
    print(d2.groupby("nudge_bucket").agg(calls=("meeting", "size"), meeting=("meeting", "mean"),
                                         avg_sec=("lead_call_duration", "mean")).to_string(
        formatters={"meeting": "{:.1%}".format, "avg_sec": "{:.0f}".format}))
    r.to_csv(S / "N01_nudges.csv", index=False)


if __name__ == "__main__":
    main()
