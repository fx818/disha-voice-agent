"""C4: objection library, bot-response patterns after objections, seller-question FAQ + answer adequacy, live cues.
Objections evaluator calls have no transcripts, so response-after-objection is measured two ways:
 (a) topics evaluator timeline: next topic after an objection topic (T19/T21/T22/...)
 (b) transcripts: seller objection turn detected by Hinglish cues -> next bot turn classified into a response pattern.
Writes work/c4_*.csv"""
import gc, json, os, re, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.dirname(BASE)
CACHE = os.path.join(OUT, "cache")
WORK = os.path.join(BASE, "work")
THEMES = ["pricing", "free_payment", "profile", "leads", "not_using", "callback", "exec", "wrong_ivr", "identity", "bot_doubt"]
I = re.I

calls = pd.read_parquet(os.path.join(WORK, "c2_calls_full.parquet"),
                        columns=["attempt_id", "meeting_fixed", "lead_call_duration", "disposition_label", "call_attempt_count"] + ["th_" + t for t in THEMES])
calls["meeting_fixed"] = calls.meeting_fixed.fillna(0).astype(int)
calls = calls.set_index("attempt_id")

# ================= 1. objection library =================
ob = pd.read_parquet(os.path.join(WORK, "ev_objections.parquet"))
obc = pd.read_parquet(os.path.join(WORK, "ev_objections_calls.parquet"))
ob = ob.join(calls, on="attempt_id")
n_calls = len(obc)
lib = ob.groupby("obj_cat").agg(n=("attempt_id", "nunique"), meeting=("meeting_fixed", "mean"),
                                early_drop=("lead_call_duration", lambda x: (x < 10).mean()),
                                median_sec=("lead_call_duration", "median")).sort_values("n", ascending=False)
lib["share_of_obj_calls"] = lib.n / n_calls
base_obj_meeting = obc.join(calls, on="attempt_id").meeting_fixed.mean()
lib["base_meeting_objection_sample"] = base_obj_meeting
# reasons: frequent keyword buckets inside reasons text
RB = {"busy_at_work/customers": r"busy|customer|workload|rush|occupied", "travelling/out_of_town": r"travel|out of (town|station|city)|outside|driving",
      "health/family/festival": r"hospital|ill|sick|health|family|wedding|festival|death|funeral|puja|diwali|navratri",
      "asked_for_callback_time": r"call ?back|later|another time|free", "no_need/no_requirement": r"no need|not need|no requirement|does not require|not required",
      "cost/paid_not_wanted": r"paid|cost|price|expensive|budget|money|afford|free", "already_met/in_touch_exec": r"already (met|had|been|in touch|spoken|discussed|visited|has)|met (with )?(an|the|a) (indiamart|sales|local|field)|in touch with|previous(ly)? (met|visit|meeting)|visited (by|him|her|them)",
      "bad_experience/no_leads": r"experience|no (leads|business|enquir)|not (getting|beneficial)|fake|irrelevant", "business_closed/not_seller": r"closed|shut|not a seller|buyer|not doing|stopped",
      "wrong_person/number": r"wrong|not the (owner|right)|different (person|company)", "trust/privacy/AI": r"trust|fraud|scam|privacy|ai\b|bot|robot|recorded|human",
      "disconnect/no_audio": r"disconnect|audio|hear|network|abrupt|silence|no response"}
rrows = []
for cat, g in ob.groupby("obj_cat"):
    for k, rx in RB.items():
        m = g.reasons.str.contains(rx, flags=I, regex=True)
        if m.sum() >= 5:
            rrows.append({"obj_cat": cat, "reason_bucket": k, "n": int(m.sum()), "share": m.mean(), "meeting": g.loc[m, "meeting_fixed"].mean()})
pd.DataFrame(rrows).to_csv(os.path.join(WORK, "c4_obj_reasons.csv"), index=False)
# representative short quotes (<=90 chars, no digits runs that look like phones)
rng = np.random.default_rng(7)
qrows = []
for cat, g in ob.groupby("obj_cat"):
    qs = [q.strip() for s in g.quotes.dropna() for q in s.split("||")]
    qs = [q for q in qs if 18 <= len(q) <= 90 and not re.search(r"\d{6,}", q) and not re.fullmatch(r"(hello\W*)+", q, I)
          and not re.search(r"indiamart se|kya aap .* se (bol|baat)|nikaal pa|main aapko|call kar lungi|bol rahi hoon|meeting sales executive|business karte hain|madarchod|bhench|chutiya|\*", q, I)]
    pick = list(rng.choice(qs, size=min(8, len(qs)), replace=False)) if qs else []
    rs = g.reasons.dropna().tolist()
    rpick = list(rng.choice(rs, size=min(2, len(rs)), replace=False)) if rs else []
    qrows.append({"obj_cat": cat, "quotes": " ## ".join(pick), "reasons": " ## ".join(r.split("||")[0][:160] for r in rpick)})
pd.DataFrame(qrows).to_csv(os.path.join(WORK, "c4_obj_quotes.csv"), index=False)
# objection mix inside each theme (objection calls only)
mix = []
for th in THEMES:
    g = ob[ob["th_" + th] == True]
    if g.attempt_id.nunique() >= 30:
        vc = g.groupby("obj_cat").attempt_id.nunique() / g.attempt_id.nunique()
        for k, v in vc.items():
            mix.append({"theme": th, "obj_cat": k, "share": v, "n_theme_obj_calls": g.attempt_id.nunique(),
                        "meeting": g[g.obj_cat == k].meeting_fixed.mean()})
pd.DataFrame(mix).to_csv(os.path.join(WORK, "c4_obj_by_theme.csv"), index=False)
lib.to_csv(os.path.join(WORK, "c4_obj_library.csv"))
print(lib.round(3).to_string())
del ob; gc.collect()

# ================= 2a. topics timeline: what bot did after an objection topic =================
tp = pd.read_parquet(os.path.join(WORK, "ev_topics.parquet")).sort_values(["attempt_id", "seq"])
OBJ_T = {"T19_OBJECTION_NOT_INTERESTED", "T21_OBJECTION_BUSY_CALL_LATER", "T22_OBJECTION_NO_NEED_PAID_SERVICES", "T17_COMPETITOR_REFERENCE",
         "T20_OBJECTION_SELLER_IDENTIFIED_AI", "T30_SELLER_POOR_EXPERIENCE", "T31_NOT_RIGHT_CONTACT_PERSON", "T04_WRONG_NUMBER",
         "T05_WRONG_PRODUCTS_DIFFERENT_BUSINESS", "T32_NETWORK_ISSUES", "T13_SELLER_ACTIVE_ON_INDIAMART"}
tp["next_topic"] = tp.groupby("attempt_id").topic_id.shift(-1).fillna("END_OF_CALL")
tp["next_evidence"] = tp.groupby("attempt_id").evidence.shift(-1).fillna("")
t_obj = tp[tp.topic_id.isin(OBJ_T)].groupby(["attempt_id", "topic_id"]).head(1).join(calls[["meeting_fixed"]], on="attempt_id")
t_obj["next_topic"] = t_obj.next_topic.str.replace(r"^OTHER:.*", "OTHER(free-text topic)", regex=True)
resp = t_obj.groupby(["topic_id", "next_topic"]).agg(n=("attempt_id", "size"), meeting=("meeting_fixed", "mean")).reset_index()
tot = t_obj.groupby("topic_id").agg(N=("attempt_id", "size"), meeting_all=("meeting_fixed", "mean"))
resp = resp.join(tot, on="topic_id"); resp = resp[resp.n >= 15].sort_values(["topic_id", "n"], ascending=[True, False])
resp.to_csv(os.path.join(WORK, "c4_topic_next_after_objection.csv"), index=False)
print(resp.round(3).to_string())
# example bot evidence for best next topics
ex = t_obj[t_obj.next_evidence.str.len() > 10].groupby(["topic_id", "next_topic"]).next_evidence.apply(lambda x: " ## ".join(x.head(2).str[:140]))
ex.to_csv(os.path.join(WORK, "c4_topic_next_examples.csv"))
del tp, t_obj; gc.collect()

# ================= 2b + 4. transcripts: objection cues, live cues, next bot response =================
ct = pd.read_parquet(os.path.join(CACHE, "call_turns.parquet"), columns=["attempt_id", "turn_no", "speaker", "text", "start_sec", "end_sec"])
ct = ct[ct.speaker.isin(["bot", "seller"])].sort_values(["attempt_id", "turn_no"]).reset_index(drop=True)
ct["text"] = ct.text.fillna("")
ct["pos"] = ct.groupby("attempt_id").cumcount()
ct["n_pos"] = ct.groupby("attempt_id").pos.transform("max")
# next bot turn text for each seller turn, and whether the seller spoke again after that bot turn
nxt_bot = ct[ct.speaker == "bot"][["attempt_id", "pos", "text"]].rename(columns={"pos": "bpos", "text": "bot_next"})
sel = ct[ct.speaker == "seller"].copy()
sel = pd.merge_asof(sel.sort_values("pos").assign(pp=lambda d: d.pos + 1), nxt_bot.sort_values("bpos").assign(pp=lambda d: d.bpos),
                    on="pp", by="attempt_id", direction="forward").sort_values(["attempt_id", "pos"])
last_seller_pos = ct[ct.speaker == "seller"].groupby("attempt_id").pos.max()
sel["seller_spoke_after_bot_reply"] = sel.bpos.notna() & (sel.bpos < sel.attempt_id.map(last_seller_pos))
sel["ends_within_2"] = (sel.n_pos - sel.pos) <= 2
sel = sel.join(calls, on="attempt_id")
sel = sel[sel.meeting_fixed.notna()]
print("seller turns", len(sel), "calls", sel.attempt_id.nunique())

LT = json.load(open(os.path.join(OUT, "live_thresholds.json")))
CUES = {k: "|".join(LT[k]["keywords"]) for k in ["rush", "frustration", "confusion", "interest", "bot_question"]}
# objection cues (seller side, Hinglish)
OBJ_CUES = {
    "not_interested": r"interest(ed)? nahi|not interested|nahi chahiye|nahi karna|zarurat nahi|zaroorat nahi|requirement nahi|need nahi|koi zarurat|मत|नहीं चाहिए",
    "busy_later": CUES["rush"],
    "no_need_paid/cost": r"paid nahi|paisa nahi|paise nahi|budget nahi|mehe?nga|expensive|free (mein|me|wala)|paid (wala|service) nahi|kitna (paisa|charge)|charge",
    "already_met_exec": r"meeting ho (gayi|gai|chuki)|mil (chuke|liya)|aa(ye)? (chuke|gaye) the|already|pehle (hi|se) (baat|meeting)|executive (se|ke) (baat|saath)",
    "no_leads/bad_exp": r"(lead|enquiry|inquiry|order|business)s? (nahi|nhi) (aa|mil|aat|aay)|koi (fayda|faayda|benefit|lead|enquiry)|fake|faltu|bekar|bekaar|fayda nahi|faayda nahi",
    "business_closed/not_using": r"band (hai|ho gaya|kar diya)|kaam band|dukaan band|chhod (diya|di)|use nahi kar|nahi chalate",
    "wrong_person": r"wrong number|galat number|main (nahi|nahin) hoon|woh (nahi|nahin) hai|(owner|malik|sir|boss) (nahi|bahar)|unse baat",
    "identity/trust": r"kaun bol|aap kaun|kahan se|kis company|fraud|number kahan se|\bai\b|robot|\bbot\b|computer|recorded|insaan",
}
# bot response patterns (next bot turn)
RESP = [
    ("exit_close", r"dhanyavaad|dhanyawad|thank you|aapka din shubh|shubh din|अपना समय देने"),
    ("callback_time_ask", r"(kab|kis time|kitne baje|kaun sa time|kis samay).{0,40}(call|baat|phone|free)|call (back|kar lu|karungi|kar lungi)|baad mein (call|baat)|callback"),
    ("ack_existing_exec", r"(executive|unhi|unse).{0,60}(follow|aage|naye|nayi|update|dobara|phir se)|pehle (mil|baat)"),
    ("free_no_charge_reframe", r"free|koi charge nahi|bina (kisi )?charge|muft|nishulk|koi paisa nahi|charge nahi"),
    ("price_answer", r"\d[\d,]*\s*(rupa?y|rs|₹|hazaar|hazar)|rupaye|rupay"),
    ("online_or_phone_option", r"online|video|zoom|google meet|phone par|phone pe|whatsapp"),
    ("enquiry_value_hook", r"enquir|inquir|buyer|lead|grahak|demand|इंक्वायरी"),
    ("short_meeting_time_ask", r"(15|pandrah|10|das|20|bees) (se|-) ?(20|bees|15|minute)|chhoti si meeting|kal .{0,30}(time|baje|samay)|kis din|kaunsa din"),
    ("empathy_ack", r"samajh (sakti|rahi|sakta|gayi)|koi baat nahi|bilkul|maafi|sorry|kshama"),
    ("identity_answer", r"indiamart se|payal|ai assistant|virtual|main (ek )?(insaan|human)|bot nahi|robot nahi"),
]
def resp_type(t):
    if not t:
        return "NO_BOT_REPLY(call ended)"
    hits = [n for n, rx in RESP if re.search(rx, t, I)]
    return "+".join(hits[:2]) if hits else "other"
def resp_primary(t):
    if not t:
        return "NO_BOT_REPLY(call ended)"
    for n, rx in RESP:
        if re.search(rx, t, I):
            return n
    return "other"

sel["bot_next"] = sel.bot_next.fillna("")
sel["resp"] = sel.bot_next.map(resp_primary)
for k, rx in OBJ_CUES.items():
    sel["obj_" + k] = sel.text.str.contains(rx, flags=I, regex=True)
for k, rx in CUES.items():
    sel["cue_" + k] = sel.text.str.contains(rx, flags=I, regex=True)

# per-call first objection turn x bot response
orows = []
for k in OBJ_CUES:
    g = sel[sel["obj_" + k]].groupby("attempt_id").head(1)
    tot_m = g.meeting_fixed.mean()
    for r, gg in g.groupby("resp"):
        orows.append({"objection_cue": k, "bot_response": r, "n": len(gg), "share": len(gg) / len(g), "meeting": gg.meeting_fixed.mean(),
                      "seller_continued": gg.seller_spoke_after_bot_reply.mean(), "N_obj": len(g), "meeting_obj_all": tot_m})
orr = pd.DataFrame(orows); orr = orr[orr.n >= 20].sort_values(["objection_cue", "n"], ascending=[True, False])
orr.to_csv(os.path.join(WORK, "c4_obj_cue_response.csv"), index=False)
print(orr.round(3).to_string())
# example exchanges (seller objection -> bot reply) for the best/worst responses
exr = []
for k in OBJ_CUES:
    g = sel[sel["obj_" + k] & (sel.text.str.len().between(10, 110)) & (sel.bot_next.str.len().between(10, 220))].groupby("attempt_id").head(1)
    for r, gg in g.groupby("resp"):
        for mf in [1, 0]:
            x = gg[gg.meeting_fixed == mf].head(1)
            for _, row in x.iterrows():
                exr.append({"objection_cue": k, "bot_response": r, "meeting": mf, "seller": row.text, "bot": row.bot_next})
pd.DataFrame(exr).to_csv(os.path.join(WORK, "c4_obj_cue_examples.csv"), index=False)

# objection cues by theme (transcribed calls)
cr = []
for th in THEMES:
    g = sel[sel["th_" + th] == True]
    nc = g.attempt_id.nunique()
    if nc < 50:
        continue
    for k in list(OBJ_CUES) :
        cc = g[g["obj_" + k]].attempt_id.unique()
        if len(cc) >= 15:
            m = calls.loc[cc, "meeting_fixed"].mean()
            best = g[g["obj_" + k]].groupby("attempt_id").head(1).groupby("resp").meeting_fixed.agg(["size", "mean"])
            best = best[best["size"] >= 10].sort_values("mean", ascending=False)
            cr.append({"theme": th, "objection_cue": k, "calls": len(cc), "share_theme_calls": len(cc) / nc, "meeting": m,
                       "best_resp": (best.index[0] + f" ({best['mean'].iloc[0]:.0%}, n={best['size'].iloc[0]})") if len(best) else "",
                       "worst_resp": (best.index[-1] + f" ({best['mean'].iloc[-1]:.0%}, n={best['size'].iloc[-1]})") if len(best) > 1 else ""})
pd.DataFrame(cr).to_csv(os.path.join(WORK, "c4_obj_cue_by_theme.csv"), index=False)

# ---- live cues ----
base_end2 = sel.ends_within_2.mean(); base_meet = sel.drop_duplicates("attempt_id").meeting_fixed.mean()
lrows = []
for k in CUES:
    g = sel[sel["cue_" + k]]
    calls_k = g.attempt_id.unique()
    lrows.append({"cue": k, "seller_turns": len(g), "calls": len(calls_k), "ends_within_2": g.ends_within_2.mean(),
                  "meeting_in_call": calls.loc[calls_k, "meeting_fixed"].mean(), "base_ends_within_2": base_end2, "base_meeting": base_meet})
# individual keyword counts per cue
kw = []
for k in CUES:
    for w in LT[k]["keywords"]:
        m = sel.text.str.contains(w, flags=I, regex=True)
        if m.sum() >= 15:
            cc = sel.loc[m, "attempt_id"].unique()
            kw.append({"cue": k, "keyword": w, "turns": int(m.sum()), "ends_within_2": sel.loc[m, "ends_within_2"].mean(),
                       "meeting_in_call": calls.loc[cc, "meeting_fixed"].mean()})
# bot reaction to rush/frustration/confusion -> outcome
react = []
for k in ["rush", "frustration", "confusion", "interest", "bot_question"]:
    g = sel[sel["cue_" + k]].groupby("attempt_id").head(1)
    for r, gg in g.groupby("resp"):
        if len(gg) >= 20:
            react.append({"cue": k, "bot_response": r, "n": len(gg), "meeting": gg.meeting_fixed.mean(), "seller_continued": gg.seller_spoke_after_bot_reply.mean()})
pd.DataFrame(react).to_csv(os.path.join(WORK, "c4_cue_reaction.csv"), index=False)

# language detection per seller turn
def lang(t):
    if re.search(r"[઀-૿]", t): return "gujarati_script"
    if re.search(r"[஀-௿]", t): return "tamil_script"
    if re.search(r"[ఀ-౿]", t): return "telugu_script"
    if re.search(r"[ಀ-೿]", t): return "kannada_script"
    if re.search(r"[ঀ-৿]", t): return "bengali_script"
    if re.search(r"[਀-੿]", t): return "gurmukhi_script"
    if re.search(r"\b(aahe|nahi aahe|kay zhala|tumhi|mala|amhi|kasa|kuthe|sangto|bola na|kaay)\b", t, I): return "marathi_roman"
    if re.search(r"\b(che|chhe|nathi|tame|tamne|shu|kem|majama|hu tamne|kai nathi|bolo ne|haa ben)\b", t, I): return "gujarati_roman"
    if re.search(r"\b(illa|enna|pesunga|sollunga|venda|irukku|theriyadu|vanakkam|seri|naan)\b", t, I): return "tamil_roman"
    if re.search(r"\b(ledu|cheppandi|emi|meeru|undi|nenu|telugu)\b", t, I): return "telugu_roman"
    if re.search(r"\b(ki bolchen|ami|apni|bolun|hobe|na na)\b", t, I) and not re.search(r"\b(hai|hoon|nahi)\b", t, I): return "bengali_roman"
    w = re.findall(r"[a-zA-Z']+", t)
    if len(w) >= 4:
        en = sum(x.lower() in EN for x in w) / len(w)
        if en >= 0.6: return "english"
    if re.search(r"[ऀ-ॿ]", t): return "hindi_devanagari"
    return "hindi_or_hinglish"
EN = set("the is are you what please not we have i am this that it to of and in for with my your can do does call me no yes okay ok sorry who speaking from will be any don't i'm we're tell about how where when why interested time busy right now later meeting send number company business our us they them there here sure thank thanks good morning sir madam ma'am hello".split())
sel["lang"] = sel.text.map(lang)
REQ = r"hindi (nahi|nhi) (aati|aata)|english (me|mein|main) (bol|baat)|speak (in )?english|marathi (me|mein|madhe|bol)|gujarati (me|mein|ma|bol)|tamil(la)? (pesunga|me|mein)|telugu (lo|me|mein)|kannada|bangla|bengali (me|mein)|in english|apni bhasha"
sel["lang_request"] = sel.text.str.contains(REQ, flags=I, regex=True)
lg = sel.groupby("lang").agg(turns=("text", "size"), calls=("attempt_id", "nunique"), ends_within_2=("ends_within_2", "mean"))
lg["meeting_in_call"] = [calls.loc[sel.loc[sel.lang == l, "attempt_id"].unique(), "meeting_fixed"].mean() for l in lg.index]
lg.to_csv(os.path.join(WORK, "c4_lang.csv"))
# call-level: any non-Hindi turn
nonhi = sel[~sel.lang.isin(["hindi_or_hinglish", "hindi_devanagari"])].attempt_id.unique()
nh = calls.loc[sel.attempt_id.unique()]
lrows.append({"cue": "language_switch(any non-Hindi seller turn)", "seller_turns": int((~sel.lang.isin(["hindi_or_hinglish", "hindi_devanagari"])).sum()),
              "calls": len(nonhi), "ends_within_2": sel[~sel.lang.isin(["hindi_or_hinglish", "hindi_devanagari"])].ends_within_2.mean(),
              "meeting_in_call": calls.loc[nonhi, "meeting_fixed"].mean(), "base_ends_within_2": base_end2, "base_meeting": base_meet})
rq = sel[sel.lang_request]
lrows.append({"cue": "explicit_language_request", "seller_turns": len(rq), "calls": rq.attempt_id.nunique(), "ends_within_2": rq.ends_within_2.mean(),
              "meeting_in_call": calls.loc[rq.attempt_id.unique(), "meeting_fixed"].mean(), "base_ends_within_2": base_end2, "base_meeting": base_meet})
pd.DataFrame(lrows).to_csv(os.path.join(WORK, "c4_live_cues.csv"), index=False)
pd.DataFrame(kw).sort_values(["cue", "turns"], ascending=[True, False]).to_csv(os.path.join(WORK, "c4_cue_keywords.csv"), index=False)
pd.DataFrame(rq[["text"]].head(25)).to_csv(os.path.join(WORK, "c4_lang_request_examples.csv"), index=False)
print(pd.DataFrame(lrows).round(3).to_string()); print(lg.round(3).to_string())
# cue rates per theme
tr = []
for th in THEMES:
    g = sel[sel["th_" + th] == True]
    nc = g.attempt_id.nunique()
    if nc < 50:
        continue
    r = {"theme": th, "transcribed_calls": nc, "meeting": calls.loc[g.attempt_id.unique(), "meeting_fixed"].mean()}
    for k in CUES:
        cc = g[g["cue_" + k]].attempt_id.unique()
        r[k + "_rate"] = len(cc) / nc
        r[k + "_meeting"] = calls.loc[cc, "meeting_fixed"].mean() if len(cc) else np.nan
    cc = g[~g.lang.isin(["hindi_or_hinglish", "hindi_devanagari"])].attempt_id.unique()
    r["nonhindi_rate"] = len(cc) / nc
    tr.append(r)
pd.DataFrame(tr).to_csv(os.path.join(WORK, "c4_cues_by_theme.csv"), index=False)

# ================= 3. seller questions FAQ + adequacy =================
q = pd.read_parquet(os.path.join(WORK, "ev_questions.parquet"))
qc = pd.read_parquet(os.path.join(WORK, "ev_questions_calls.parquet"))
q = q.join(calls, on="attempt_id")
q = q[q.meeting_fixed.notna()]
# adequacy proxy via transcripts: locate answer bot turn; did seller speak after it? did call end within next turn?
bt = ct[ct.speaker == "bot"][["attempt_id", "pos", "n_pos", "text"]]
bt["key"] = bt.text.str.lower().str.replace(r"[^a-zऀ-ॿ ]", "", regex=True).str[:40]
q["key"] = q.ans.fillna("").str.lower().str.replace(r"[^a-zऀ-ॿ ]", "", regex=True).str[:40]
bt2 = bt[bt.key.str.len() >= 12].drop_duplicates(["attempt_id", "key"])
qm = q.merge(bt2[["attempt_id", "key", "pos", "n_pos"]], on=["attempt_id", "key"], how="left")
qm["matched"] = qm.pos.notna()
qm["seller_after_ans"] = np.where(qm.matched, qm.apply(lambda r: (r.pos < last_seller_pos.get(r.attempt_id, -1)) if r.matched else np.nan, axis=1), np.nan)
qm["drop_after_answer"] = np.where(qm.matched, qm.seller_after_ans == False, np.nan)
qm["no_answer"] = qm.ans.fillna("").str.len() < 3
# heuristic answer-content checks
qm["ans_has_price"] = qm.ans.fillna("").str.contains(r"\d[\d,]*\s*(rupa?y|rs|hazaar|hazar)|rupaye|rupay|₹", case=False)
qm["ans_denies_bot"] = qm.ans.fillna("").str.contains(r"(nahi|nahin|no)[, ]+(main|mai|i am|ji)|main (ek )?(insaan|human|real)|bot nahi|robot nahi|insaan hoon|human hoon|executive hoon", case=False)
qm["ans_admits_ai"] = qm.ans.fillna("").str.contains(r"\bai\b|virtual|assistant|automated|digital", case=False)
qm["ans_deflect_exec"] = qm.ans.fillna("").str.contains(r"executive", case=False)
faq = qm.groupby("q_cat").agg(n=("attempt_id", "size"), calls=("attempt_id", "nunique"), meeting=("meeting_fixed", "mean"),
                              matched=("matched", "mean"), drop_after_answer=("drop_after_answer", "mean"), no_answer=("no_answer", "mean"),
                              ans_has_price=("ans_has_price", "mean"), ans_deflect_exec=("ans_deflect_exec", "mean"),
                              ans_denies_bot=("ans_denies_bot", "mean"), ans_admits_ai=("ans_admits_ai", "mean")).sort_values("n", ascending=False)
faq = faq[faq.n >= 20]
faq["base_meeting_q_calls"] = qc.join(calls, on="attempt_id").meeting_fixed.mean()
faq["base_drop_after_any_bot_turn"] = np.nan
faq.to_csv(os.path.join(WORK, "c4_faq.csv")); print(faq.round(3).to_string())
# within pricing: answered with a price vs deflected -> meeting / drop
sub = []
for cat, flag in [("Pricing Payment", "ans_has_price"), ("Pricing Payment", "ans_deflect_exec"), ("AI Bot Confirmation", "ans_denies_bot"),
                  ("AI Bot Confirmation", "ans_admits_ai"), ("Identity Confirmation", "ans_deflect_exec"), ("Enquiry Lead", "ans_has_price"),
                  ("Benefit Value", "ans_deflect_exec"), ("Service Product Info", "ans_deflect_exec"), ("Purpose Reason", "ans_deflect_exec")]:
    g = qm[qm.q_cat == cat]
    for v in [True, False]:
        gg = g[g[flag] == v]
        if len(gg) >= 10:
            sub.append({"q_cat": cat, "answer_flag": flag, "value": v, "n": len(gg), "meeting": gg.meeting_fixed.mean(),
                        "drop_after_answer": gg.drop_after_answer.mean(), "n_matched": int(gg.matched.sum())})
pd.DataFrame(sub).to_csv(os.path.join(WORK, "c4_faq_answer_types.csv"), index=False)
print(pd.DataFrame(sub).round(3).to_string())
# examples: good (meeting & seller continued) vs bad (drop after answer)
exq = []
for cat, g in qm[(qm.que.str.len().between(6, 120)) & (qm.ans.str.len().between(6, 230))].groupby("q_cat"):
    good = g[(g.meeting_fixed == 1)].head(2)
    bad = g[(g.drop_after_answer == True)].head(2)
    for lab, x in [("good", good), ("dropped_after", bad)]:
        for _, r in x.iterrows():
            exq.append({"q_cat": cat, "type": lab, "que": r.que, "ans": r.ans})
pd.DataFrame(exq).to_csv(os.path.join(WORK, "c4_faq_examples.csv"), index=False)
# FAQ by theme
fq = []
for th in THEMES:
    g = qm[qm["th_" + th] == True]
    if g.attempt_id.nunique() >= 50:
        vc = g.groupby("q_cat").attempt_id.nunique().sort_values(ascending=False).head(5)
        for k, v in vc.items():
            gg = g[g.q_cat == k]
            fq.append({"theme": th, "q_cat": k, "calls": v, "share_theme_q_calls": v / g.attempt_id.nunique(),
                       "meeting": gg.meeting_fixed.mean(), "drop_after_answer": gg.drop_after_answer.mean()})
pd.DataFrame(fq).to_csv(os.path.join(WORK, "c4_faq_by_theme.csv"), index=False)
print("done")
