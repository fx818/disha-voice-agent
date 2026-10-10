"""C5: seller questions detected directly in transcripts (seller_questions evaluator rows have no transcripts),
so answer adequacy = did the seller keep talking after the bot's reply / did the call end within 2 turns.
Writes work/c5_*.csv"""
import os, re, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.dirname(BASE), "cache")
WORK = os.path.join(BASE, "work")
I = re.I
THEMES = ["pricing", "free_payment", "profile", "leads", "not_using", "callback", "exec", "wrong_ivr", "identity", "bot_doubt"]

calls = pd.read_parquet(os.path.join(WORK, "c2_calls_full.parquet"),
                        columns=["attempt_id", "meeting_fixed", "lead_call_duration"] + ["th_" + t for t in THEMES]).set_index("attempt_id")
calls["meeting_fixed"] = calls.meeting_fixed.fillna(0).astype(int)
ct = pd.read_parquet(os.path.join(CACHE, "call_turns.parquet"), columns=["attempt_id", "turn_no", "speaker", "text"])
ct = ct[ct.speaker.isin(["bot", "seller"])].sort_values(["attempt_id", "turn_no"]).reset_index(drop=True)
ct["text"] = ct.text.fillna("")
ct["pos"] = ct.groupby("attempt_id").cumcount()
ct["n_pos"] = ct.groupby("attempt_id").pos.transform("max")
bots = ct[ct.speaker == "bot"][["attempt_id", "pos", "text"]].rename(columns={"pos": "bpos", "text": "bot_next"})
sel = ct[ct.speaker == "seller"].copy()
sel = pd.merge_asof(sel.assign(pp=sel.pos + 1).sort_values("pp"), bots.assign(pp=bots.bpos).sort_values("pp"),
                    on="pp", by="attempt_id", direction="forward")
last_s = ct[ct.speaker == "seller"].groupby("attempt_id").pos.max()
sel["seller_continued"] = sel.bpos.notna() & (sel.bpos < sel.attempt_id.map(last_s))
sel["ends_within_2"] = (sel.n_pos - sel.pos) <= 2
sel = sel.join(calls, on="attempt_id"); sel = sel[sel.meeting_fixed.notna()]
sel["bot_next"] = sel.bot_next.fillna("")

QCAT = [
    ("bot_identity(AI?)", r"\bai\b|robot|\bbot\b|computer|recorded|recording|machine|insaan (ho|hai)|real (person|insaan)"),
    ("pricing/cost", r"kitn[ae] (ka|ki|paisa|charge|lagega|padega|hoga|rupa?y)|\bprice|charges?\b|\bfees?\b|paisa|paise|kitne ka|package|plan kya|kitna hai"),
    ("free_or_paid?", r"free (hai|hoga|mein)|charge (lagega|hai|hoga)|paid (hai|hoga)|paisa lagega|paise lagenge"),
    ("who_is_calling", r"kaun bol|aap kaun|kahan se|kaha se|kis company|kaun si company|aapka naam|who is (this|calling)"),
    ("purpose/why", r"kis (baare|baat|liye|cheez)|kyun|kyon|kya kaam|kya baat|matlab|purpose|kis wajah|kya chahiye"),
    ("enquiry/leads", r"enquiry|inquiry|enquiries|lead|buyer|kaun se (buyer|customer)|order"),
    ("benefit/how_it_works", r"fayda|faayda|benefit|kya milega|kaise (hoga|karenge|kaam|milega)|process|kya karna"),
    ("meeting_logistics", r"kab aa|kitne baje|kahan aa|kaun aayega|address|location|kis din|kis time|online|kahan (milna|aana)"),
    ("profile/catalog", r"profile|catalog|photo|listing|product (add|update)"),
]
def qcat(t):
    if not re.search(r"\?|\b(kya|kaun|kitna|kitne|kab|kahan|kaha|kaise|kyun|kyon|what|who|how|why|when)\b", t, I):
        return None
    for n, rx in QCAT:
        if re.search(rx, t, I):
            return n
    return None
sel["qcat"] = sel.text.map(qcat)
q = sel[sel.qcat.notna()].copy()
# bot answer features
q["bot_has_number_price"] = q.bot_next.str.contains(r"\d[\d,]*\s*(rupa?y|rs|hazaar|hazar)|rupaye|rupay|₹|हजार|रुपये", case=False)
q["bot_says_free"] = q.bot_next.str.contains(r"free|koi charge nahi|bina charge|muft|nishulk|फ्री", case=False)
q["bot_deflects_exec"] = q.bot_next.str.contains(r"executive|एग्जीक्यूटिव", case=False)
q["bot_denies_ai"] = q.bot_next.str.contains(r"(nahi|nahin|no)[ ,]+(ji[ ,]+)?(main|mai)\b|main (ek )?(insaan|human|real)|bot nahi|robot nahi|insaan hoon|human hoon", case=False)
q["bot_admits_ai"] = q.bot_next.str.contains(r"\bai\b|virtual|assistant|automated|digital|एआई", case=False)
q["bot_names_indiamart"] = q.bot_next.str.contains(r"indiamart|इंडियामार्ट", case=False)
q["bot_city_enquiry_fact"] = q.bot_next.str.contains(r"\d+\s*(se zyada|से ज्यादा)?.{0,20}(enquir|inquir|buyer|इंक्वायरी)", case=False)
q["bot_no_reply"] = q.bot_next.str.len() == 0
q1 = q.groupby(["attempt_id", "qcat"]).head(1)
summ = q1.groupby("qcat").agg(n=("attempt_id", "size"), meeting=("meeting_fixed", "mean"), seller_continued=("seller_continued", "mean"),
                              ends_within_2=("ends_within_2", "mean"), bot_no_reply=("bot_no_reply", "mean"),
                              bot_price=("bot_has_number_price", "mean"), bot_free=("bot_says_free", "mean"), bot_exec=("bot_deflects_exec", "mean"),
                              bot_denies_ai=("bot_denies_ai", "mean"), bot_admits_ai=("bot_admits_ai", "mean")).sort_values("n", ascending=False)
summ["base_ends_within_2_all_seller_turns"] = sel.ends_within_2.mean()
summ["base_continued_all_seller_turns"] = sel.seller_continued.mean()
summ["base_meeting_transcribed"] = calls.loc[sel.attempt_id.unique(), "meeting_fixed"].mean()
summ.to_csv(os.path.join(WORK, "c5_q_summary.csv")); print(summ.round(3).to_string())
rows = []
for cat, flags in [("pricing/cost", ["bot_has_number_price", "bot_says_free", "bot_deflects_exec"]), ("free_or_paid?", ["bot_says_free", "bot_has_number_price", "bot_deflects_exec"]),
                   ("bot_identity(AI?)", ["bot_denies_ai", "bot_admits_ai", "bot_names_indiamart"]), ("who_is_calling", ["bot_names_indiamart", "bot_city_enquiry_fact"]),
                   ("purpose/why", ["bot_city_enquiry_fact", "bot_says_free", "bot_deflects_exec"]), ("enquiry/leads", ["bot_city_enquiry_fact", "bot_deflects_exec"]),
                   ("benefit/how_it_works", ["bot_city_enquiry_fact", "bot_deflects_exec", "bot_says_free"]), ("meeting_logistics", ["bot_deflects_exec", "bot_says_free"])]:
    g = q1[q1.qcat == cat]
    for f in flags:
        for v in [True, False]:
            gg = g[g[f] == v]
            if len(gg) >= 15:
                rows.append({"qcat": cat, "bot_answer": f, "value": v, "n": len(gg), "meeting": gg.meeting_fixed.mean(),
                             "seller_continued": gg.seller_continued.mean(), "ends_within_2": gg.ends_within_2.mean()})
pd.DataFrame(rows).to_csv(os.path.join(WORK, "c5_q_answer_types.csv"), index=False); print(pd.DataFrame(rows).round(3).to_string())
ex = []
for cat, g in q1[(q1.text.str.len().between(8, 110)) & (q1.bot_next.str.len().between(8, 230))].groupby("qcat"):
    for lab, x in [("continued+meeting", g[(g.meeting_fixed == 1) & g.seller_continued].head(2)), ("ended_after_reply", g[~g.seller_continued & ~g.bot_no_reply].head(2))]:
        for _, r in x.iterrows():
            ex.append({"qcat": cat, "type": lab, "seller": r.text, "bot": r.bot_next})
pd.DataFrame(ex).to_csv(os.path.join(WORK, "c5_q_examples.csv"), index=False)
# by theme
tr = []
for th in THEMES:
    g = q1[q1["th_" + th] == True]
    nc = sel[sel["th_" + th] == True].attempt_id.nunique()
    if nc < 50:
        continue
    for k, gg in g.groupby("qcat"):
        if len(gg) >= 10:
            tr.append({"theme": th, "qcat": k, "calls": len(gg), "share_theme_calls": len(gg) / nc, "meeting": gg.meeting_fixed.mean(),
                       "seller_continued": gg.seller_continued.mean()})
pd.DataFrame(tr).to_csv(os.path.join(WORK, "c5_q_by_theme.csv"), index=False)
print("done")
