"""C2: tag every answered bot call with seller-side conversation themes.
Sources: seller-attributed sentences of lead_call_summary, seller turns (call_turns), and compact evaluator tables (work/ev_*.parquet).
Bot-pitch flags (what the bot opened with) are tagged separately from the agent sentences / first bot pitch turn.
Writes outputs/segmentation/C_call_themes.parquet and work/c2_*.csv tables."""
import gc, os, re, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.dirname(BASE), "cache")
WORK = os.path.join(BASE, "work")
I = re.I

THEMES = ["pricing", "free_payment", "profile", "leads", "not_using", "callback", "exec", "wrong_ivr", "identity"]

# ---------- regexes on seller-attributed summary sentences (English) ----------
SUM = {
    "pricing": r"\b(price|pricing|cost|costs|charges?|fees?|packages?|subscription|premium|how much|expensive|budget|afford|money|invest(ment)?|(paid|free|indiamart|the|a|any|their|his) plans?|paid (service|services|package|membership|version|option|listing))\b",
    "free_payment": r"(\bfree (plan|listing|service|services|version|account|membership|member|user|option|trial|seller)\b|\busing (the )?free\b|payment (attempt|for|failed|issue|of)|pa(y|id|ying) (for|to get) (the )?(buyer|contact|lead|enquir)|buyer contacts?|buy(ing)? (leads|contacts|buyleads?)|buy ?leads?|credits?\b|\bfree of cost)",
    "profile": r"\b(profile|catalog|catalogue|photos?|images?|pictures?|product (list|lists|details|listing|listings|information|info|description)|listings?|update (his|her|their|the|my) (products?|details|profile|catalog)|wrong products?|gst|website)\b",
    "leads": r"((not|no|never|n't|hardly|rarely) (been )?(getting|get|gets|receiving|receive|received|got|generating|generated) (any |many |much |enough |good |relevant |genuine )?(leads|enquir\w*|inquir\w*|business|orders|buyers|response|results?|calls|benefit)|(fake|irrelevant|useless|poor|bad|low|wrong|junk|spam|unqualified|non-serious|non serious|quality of( the)?|few|less|fewer) (leads|enquir\w*|inquir\w*|buyers)|(enquiries|inquiries|leads from indiamart|indiamart leads|indiamart enquiries) (are|were|do not|don't|did not) (not|fake|irrelevant|useless|poor|convert|work)|\bno (orders|benefit|results?|leads) (from|through|via|on)\b|no business (from|through|via|on) indiamart|(indiamart|it|the service|the platform|paid services?) (was|is|were|are) not (useful|beneficial|worth|profitable|helpful)|not (beneficial|worth it|profitable)|waste of (money|time)|(bad|poor|negative|unsatisfactory) (past )?experience|dissatisf|did(n't| not) (benefit|get (any )?(leads|enquir\w*|business|orders|results?))|leads? quality|quality (of )?(leads|enquir\w*)|(do not|don't|not) convert)",
    "not_using": r"(not using indiamart|(no longer|stopped|not) (using|use|uses|active on|on) indiamart|no longer (use|using|on|work|in|operat|doing|deal)|stopped (using|the business|business|working|operations)|(business|shop|store|company|factory|unit|firm|work) (is |was |has been |had been |remains |is currently |is temporarily )?(closed|shut|band|not running|not operational|inactive)|closed (the|his|their|down)|shut down|(left|quit|changed|switched) (the |his |their )?(business|line|work|field)|not (active|operational|running|doing (any )?business|currently operating)|\binactive\b|retired|deactivat|delete (my|the|his|their) (account|profile|listing)|remov(e|al of) (my|the|his|their) (listing|profile|number|account)|not (in|doing) (this|that|the) business|does(n't| not) (deal|do|sell|manufacture)|not a seller|(is|am|was) (a|only a|just a) (buyer|customer)|only (a )?buyer|not (selling|dealing)|no longer in)",
    "callback": r"(\bbusy\b|call (him |her |them )?(back|later|again)|callback|\blater\b|driving|travell?ing|out of (town|station|city|office)|in a meeting|not available|another time|no time|not (have|having) (the )?time|not free|occupied|unavailable|currently away|at the hospital|attending)",
    "exec": r"(already (met|had|meeting|in touch|in contact|spoken|talked|working|have|has|connected|dealing|associated|taken|a (paid|premium) (member|customer|user)|discussed|been (contacted|visited|in touch))|(executive|representative|expert|salesperson|sales person|sales executive|team|manager|relationship manager|rm) (already|has already|had already|visited|came|met)|met (with )?(the|an|a|indiamart|their|his) (executive|representative|expert|sales|team|person)|in touch with (an|the|indiamart|their|his|a)|existing (customer|member|executive|contact|relationship)|\bnsd\b|own executive|meeting (had|has) already|previous(ly)? (met|meeting|visit))",
    "wrong_ivr": r"(wrong number|wrong person|not the (right|correct|owner|concerned|relevant)|(is not|isn't|not) (the )?(owner|decision|right person|concerned person|person)|no such (company|business|person)|does not belong|\bivr\b|voicemail|voice mail|automated (message|system|response|voice|reply)|answering machine|recorded message|truecaller|not reachable|call (forwarding|forwarded)|press \d|personal number|number (belongs|is of|is not)|different (person|company|business) name)",
    "identity": r"(who (is|was) (calling|this|speaking|on the)|asked (who|for the (agent|caller)'?s? (name|identity)|where (she|the agent) (was|is) calling from|about (the agent's|her|the caller's) identity)|questioned (the agent's |her )?identity|identity of the (agent|caller)|fraud|scam|fake call|\btrust\b|genuine|how did (you|she|the agent|indiamart) get (my|his|their) number|suspicious|skeptic\w* (about|whether|if)|doubt\w* (about |whether |if )?(the agent|she|the caller|it was|the call))",
}
# ---------- regexes on seller turns (Hinglish / Devanagari / English) ----------
TURN = {
    "pricing": r"(kitn[ae] ka|kitna (paisa|charge|lagega|hai|padega|hoga)|kitne (paise|rupay|ka)|\bprice|charges?\b|package|\bplan\b|\bfees?\b|paisa|paise|rupa?y|mehe?nga|mahnga|budget|\bpaid\b|premium|subscription|पैकेज|प्लान|कितना|पैसे|पेमेंट|प्राइस|चार्ज)",
    "free_payment": r"(\bfree\b(?! (nahi|nhi|hoon|hu|ho|hai|time|ho ?kar|hoke|rehta|rahunga))|free (mein|me|wala|vala)\b|muft|buy ?lead|contact (khareed|kharid|lena|liya)|payment (kiya|ki|fail|nahi|nhi|kar)|pay kiya|credit|फ्री)",
    "profile": r"(profile|catalog|catlog|photo|foto|image|product (add|update|daal|dal|list)|listing|website|\bgst\b|प्रोफाइल|कैटलॉग|फोटो)",
    "leads": r"((lead|enquiry|inquiry|enquiri|inquiri|order|buyer|business)s? (nahi|nhi|nahin) (aa|mil|aat|aay|aati|aate|milt|aaya|aayi|hai|ho)|koi (lead|enquiry|inquiry|order|business|fayda|faayda|benefit|response)|\bfake\b|faltu (lead|enquiry|inquiry|call|buyer)|bekar|bekaar|kaam k[ae] nahi|fayda nahi|faayda nahi|fayda (kya|kuch)|faayda (kya|kuch)|response nahi|genuine nahi|फायदा|लीड नहीं|इंक्वायरी नहीं)",
    "not_using": r"(\b(band|bandh) (hai|ho gaya|ho gya|kar diya|kar di|kar rakha|hai abhi)|kaam band|dukaan band|dukan band|business band|chhod (diya|di|chuke)|chod (diya|di)|use (nahi|nhi|nahin) kar|indiamart (nahi|nhi) (chala|use|chalate)|account (band|delete|hata|deactivate)|delete kar|hata do|hata dijiye|nahi chalate|ab (nahi|nhi) karte|kaam nahi kar rahe|बंद)",
    "callback": r"(\bbusy\b|abhi time nahi|time nahi hai|baad (mein|me)\b|call back|callback|\bdriv|gaadi chala|meeting (mein|me) (hoon|hu)|bahar (hoon|hu)|abhi nahi|\blater\b|call later|free nahi|kal (call|baat|phone)|thodi der|व्यस्त|बिजी|बाद में)",
    "exec": r"(meeting ho (gayi|gai|chuki|gaya|chuka)|mil (chuke|chuka|liya|liye|gaye|lie)|aa(ye)? (chuke|gaye) (the|hain)|aaye the|executive|(baat|meeting) ho (chuki|gayi|gai)|pehle (hi|se) (baat|meeting|mil)|already (met|meeting|baat|ho|mil|aa|le|li|liya|connected|in touch)|एग्जीक्यूटिव|मीटिंग हो)",
    "wrong_ivr": r"(wrong number|galat number|rong number|voicemail|truecaller|\bpress\b|dabaye|abhi vyast|subscriber|forward|personal number|yeh number (nahi|nhi|kisi)|aap jis number|the number you|please hold|kripya)",
    "identity": r"(\bai\b|robot|\bbot\b|computer|machine|recorded|recording|insaan|real (person|insaan)|kaun bol|aap kaun|kahan se bol|kaha se bol|kis company|kaun si company|fraud|froud|number kahan se|number kaha se|कौन बोल|कहां से)",
}
# summary-side bot doubt must be phrased as a doubt: arrowhead summaries call the agent "the bot" ("Seller asked the bot ...")
BOT_DOUBT_SUM = r"((if|whether|is|was) (it|she|the agent|the caller|this|the call|he was talking|they were talking|speaking)( was| is| were)? (to )?(a |an )?(bot|robot|ai|a\.i\.|machine|computer|recorded|automated|human|real)|talking to (a |an )?(bot|robot|ai|machine|computer|human|real person)|real person|\bhuman\b|recorded (call|message|voice)|computer(-generated| call| voice)|\b(an|the) ai\b|artificial)"
BOT_DOUBT = re.compile(r"(\b(ai|a\.i\.|bot|robot|machine|recorded|computer)\b|real person|human|insaan|real insaan)", I)

PITCH = {
    "pitch_paid": r"(paid (package|service|services|plan|membership)|premium|subscription|package)",
    "pitch_profile": r"(profile|catalog|catalogue|visibility)",
    "pitch_enquiry": r"(buyer enquir|enquiries in|enquiry|inquir|buyer demand|demand in)",
    "pitch_payment_attempt": r"(payment attempt|attempted (a )?payment|tried to (pay|purchase|buy)|buyer contacts)",
    "pitch_free_plan": r"(free plan|free listing|free service|free member)",
}

# ---------- evaluator-derived tags ----------
TOPIC_MAP = {
    "pricing": {"T26_SELLER_ENQUIRED_FOR_PAID_PACKAGE", "T22_OBJECTION_NO_NEED_PAID_SERVICES"},
    "profile": {"T05_WRONG_PRODUCTS_DIFFERENT_BUSINESS"},
    "leads": {"T30_SELLER_POOR_EXPERIENCE"},
    "callback": {"T21_OBJECTION_BUSY_CALL_LATER", "T23_CALL_DATE_TIME_REQUEST"},
    "wrong_ivr": {"T04_WRONG_NUMBER", "T31_NOT_RIGHT_CONTACT_PERSON"},
    "identity": {"T20_OBJECTION_SELLER_IDENTIFIED_AI"},
}
Q_MAP = {"pricing": {"Pricing Payment"}, "leads": {"Enquiry Lead"}, "callback": {"Callback Contact"},
         "identity": {"Identity Confirmation", "AI Bot Confirmation"}, "profile": set()}
OBJ_MAP = {"callback": {"Seller Unavailability & Scheduling Constraints", "Callback / Deferred Engagement (Neutral)"},
           "exec": {"Existing Engagement / Past Experience"}, "wrong_ivr": {"Wrong Contact / Business Not Applicable"},
           "profile": {"Product / Service / Business Mismatch"}, "identity": {"Information / Trust / Privacy Concerns"}}
SUBD_MAP = {"exec": {"already_met_exec", "in_touch_with_exec"}, "not_using": {"business_closed"},
            "leads": {"bad_past_experience"}, "wrong_ivr": {"voicemail"}}
DISP_MAP = {"wrong_ivr": {"wrong_number", "alternate_number_or_not_dm"}, "pricing": {"budget_issue_denial"}}

SELLER_START = re.compile(r"^\W*(the lead|lead|seller|the seller|he|they|the owner|the recipient|the person|the user|the customer)\b", I)
SELLER_VERB = re.compile(r"\b(the lead|the seller|seller|he|they)\s+(\w+ly\s+)?(stated|said|mentioned|asked|requested|expressed|informed|explained|indicated|replied|responded|declined|agreed|confirmed|inquired|enquired|noted|clarified|refused|complained|told|wanted|questioned|shared|revealed|claimed|insisted|denied)\b", I)
SELLER_CLAUSE = re.compile(r"(,|;|\bbut|\band|\bwhile|\bhowever|\bto which|\bwhereupon)\s+(then\s+)?(the lead|the seller|he|they)\s+(\w+ly\s+)?(stated|said|mentioned|asked|requested|expressed|informed|explained|indicated|replied|responded|declined|agreed|confirmed|inquired|enquired|noted|clarified|refused|complained|told|questioned|shared|revealed|claimed|insisted|denied|interrupted)\b", I)
AGENT_START = re.compile(r"^\W*(the agent|agent|she|the bot|the executive|the caller|the ai)\b", I)
SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_summary(s):
    if not isinstance(s, str) or not s:
        return "", ""
    sel, ag = [], []
    for sent in SPLIT.split(s):
        if AGENT_START.search(sent):
            m = SELLER_CLAUSE.search(sent)  # 'The agent asked X, but the lead stated Y' -> keep Y as seller evidence
            if m:
                ag.append(sent[:m.start()]); sel.append(sent[m.start():])
            else:
                ag.append(sent)
        elif SELLER_START.search(sent) or SELLER_VERB.search(sent):
            sel.append(sent)
        else:
            ag.append(sent)  # neutral sentences ('The call ended...') - not seller evidence
    return " ".join(sel), " ".join(ag)


def main():
    bc = pq.read_table(os.path.join(CACHE, "bot_calls.parquet"),
                       columns=["attempt_id", "fk_glusr_usr_id", "redis_bucket", "lead_bot_version", "call_attempt_count",
                                "lead_call_duration", "lead_call_summary", "disposition_label", "meeting_fixed",
                                "has_turn_transcript"]).to_pandas()
    print("bot_calls", len(bc))
    sel_parts, ag_parts = zip(*(split_summary(s) for s in bc.lead_call_summary.tolist()))
    full = bc.lead_call_summary.fillna("")
    bc.drop(columns=["lead_call_summary"], inplace=True)
    sel = pd.Series(sel_parts, index=bc.index); ag = pd.Series(ag_parts, index=bc.index)
    del sel_parts, ag_parts; gc.collect()

    flags = pd.DataFrame(index=bc.index)
    src = {}
    for th in THEMES:
        flags[th + "_sum"] = sel.str.contains(SUM[th], flags=I, regex=True)
    # bot pitch flags from agent sentences (whole summary for pitch words is fine: pitch is said by the agent)
    for p, rx in PITCH.items():
        flags[p] = ag.str.contains(rx, flags=I, regex=True)
    flags["bot_doubt_sum"] = sel.str.contains(BOT_DOUBT_SUM, flags=I, regex=True)
    flags["identity_sum"] = flags["identity_sum"] | flags["bot_doubt_sum"]
    del sel, ag, full; gc.collect()

    # seller turns
    ct = pq.read_table(os.path.join(CACHE, "call_turns.parquet"), columns=["attempt_id", "speaker", "text", "turn_no"]).to_pandas()
    st = ct[ct.speaker == "seller"].groupby("attempt_id")["text"].apply(lambda x: " || ".join(x.dropna())).rename("stext")
    # first bot pitch turn (first bot turn mentioning IndiaMART) -> pitch flags when transcript exists
    bt = ct[(ct.speaker == "bot") & ct.text.str.contains("indiamart|इंडियामार्ट", case=False, na=False)].sort_values(["attempt_id", "turn_no"]).groupby("attempt_id").head(1)
    bt = bt.set_index("attempt_id")["text"]
    del ct; gc.collect()
    aid = bc.attempt_id
    stx = aid.map(st).fillna("")
    for th in THEMES:
        flags[th + "_turn"] = stx.str.contains(TURN[th], flags=I, regex=True)
    flags["bot_doubt_turn"] = stx.str.contains(BOT_DOUBT.pattern, flags=I, regex=True)
    btx = aid.map(bt).fillna("")
    for p, rx in PITCH.items():
        flags[p] = flags[p] | btx.str.contains(rx, flags=I, regex=True)
    del st, stx, bt, btx; gc.collect()

    # evaluator tags
    def tagset(df, col, mapping):
        out = {}
        for th, vals in mapping.items():
            if vals:
                out[th] = set(df.loc[df[col].isin(vals), "attempt_id"])
        return out
    tp = pd.read_parquet(os.path.join(WORK, "ev_topics.parquet"), columns=["attempt_id", "topic_id"])
    qs = pd.read_parquet(os.path.join(WORK, "ev_questions.parquet"), columns=["attempt_id", "q_cat"])
    ob = pd.read_parquet(os.path.join(WORK, "ev_objections.parquet"), columns=["attempt_id", "obj_cat"])
    dp = pd.read_parquet(os.path.join(WORK, "ev_disposition.parquet"))
    se = pd.read_parquet(os.path.join(WORK, "ev_se_contact.parquet"), columns=["attempt_id", "se_cat"])
    iv = pd.read_parquet(os.path.join(WORK, "ev_ivr.parquet"))
    ev_sets = {th: set() for th in THEMES}
    for m in [tagset(tp, "topic_id", TOPIC_MAP), tagset(qs, "q_cat", Q_MAP), tagset(ob, "obj_cat", OBJ_MAP),
              tagset(dp, "ev_subdisp", SUBD_MAP), tagset(dp, "ev_disp", DISP_MAP)]:
        for th, s in m.items():
            ev_sets[th] |= s
    ev_sets["exec"] |= set(se.loc[se.se_cat != "neither", "attempt_id"])
    ev_sets["wrong_ivr"] |= set(iv.loc[~iv.ivr_cat.isin(["human_answered_and_talked", "silence_or_background_noise"]), "attempt_id"])
    ev_sets["identity"] |= set()
    bot_q = set(qs.loc[qs.q_cat == "AI Bot Confirmation", "attempt_id"]) | set(tp.loc[tp.topic_id == "T20_OBJECTION_SELLER_IDENTIFIED_AI", "attempt_id"])
    print("ivr cats", iv.ivr_cat.value_counts().to_dict())
    for th in THEMES:
        flags[th + "_ev"] = aid.isin(ev_sets[th])
    flags["bot_doubt_ev"] = aid.isin(bot_q)
    # evaluator coverage flags
    evcov = set(tp.attempt_id) | set(pd.read_parquet(os.path.join(WORK, "ev_questions_calls.parquet")).attempt_id) | set(pd.read_parquet(os.path.join(WORK, "ev_objections_calls.parquet")).attempt_id)
    flags["has_rich_eval"] = aid.isin(evcov)
    del tp, qs, ob, dp, se, iv, ev_sets, evcov; gc.collect()

    out = bc[["attempt_id", "fk_glusr_usr_id", "redis_bucket", "lead_bot_version", "call_attempt_count",
              "lead_call_duration", "disposition_label", "meeting_fixed", "has_turn_transcript"]].copy()
    for th in THEMES:
        out["th_" + th] = flags[th + "_sum"] | flags[th + "_turn"] | flags[th + "_ev"]
    out["th_bot_doubt"] = flags["bot_doubt_sum"] | flags["bot_doubt_turn"] | flags["bot_doubt_ev"]
    for p in PITCH:
        out[p] = flags[p]
    out["has_rich_eval"] = flags["has_rich_eval"]
    out["n_themes"] = out[["th_" + t for t in THEMES]].sum(axis=1)
    # source breakdown for the report
    srcrows = []
    for th in THEMES:
        srcrows.append({"theme": th, "summary": int(flags[th + "_sum"].sum()), "turns": int(flags[th + "_turn"].sum()),
                        "evaluator": int(flags[th + "_ev"].sum()), "any": int(out["th_" + th].sum())})
    pd.DataFrame(srcrows).to_csv(os.path.join(WORK, "c2_sources.csv"), index=False)
    del flags; gc.collect()
    out.to_parquet(os.path.join(WORK, "c2_calls_full.parquet"), index=False)
    keep = ["attempt_id", "fk_glusr_usr_id"] + ["th_" + t for t in THEMES] + ["th_bot_doubt"] + list(PITCH) + ["n_themes"]
    out[keep].to_parquet(os.path.join(BASE, "C_call_themes.parquet"), index=False)
    print(pd.read_csv(os.path.join(WORK, "c2_sources.csv")))


if __name__ == "__main__":
    main()
