"""Evidence analysis: which seller traits and bot behaviours go with which call outcomes.

Writes outputs/evidence.json, outputs/evidence_report.md and outputs/live_thresholds.json.
Run: python -m data_prep.evidence
"""
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from data_prep import lexicon as X
from data_prep import load as L

OUT = Path(__file__).resolve().parent.parent / "outputs"

REGION = {
    "Delhi": "NCR_Punjab", "Haryana": "NCR_Punjab", "Punjab": "NCR_Punjab", "Chandigarh": "NCR_Punjab",
    "Uttar Pradesh": "Hindi_belt", "Bihar": "Hindi_belt", "Madhya Pradesh": "Hindi_belt",
    "Rajasthan": "Hindi_belt", "Jharkhand": "Hindi_belt", "Chhattisgarh": "Hindi_belt",
    "Uttarakhand": "Hindi_belt", "Himachal Pradesh": "Hindi_belt", "Jammu & Kashmir": "Hindi_belt",
    "Gujarat": "West", "Maharashtra": "West", "Goa": "West", "Dadra & Nagar Haveli": "West",
    "Daman & Diu": "West",
    "Tamil Nadu": "South", "Karnataka": "South", "Kerala": "South", "Andhra Pradesh": "South",
    "Telangana": "South", "Puducherry": "South", "Pondicherry": "South",
    "West Bengal": "East", "Odisha": "East", "Assam": "East", "Meghalaya": "East", "Tripura": "East",
    "Manipur": "East", "Nagaland": "East", "Sikkim": "East", "Arunachal Pradesh": "East",
    "Mizoram": "East",
}
TURNOVER_BAND = {"0 - 40 L": "micro", "40 L - 1.5 Cr": "small", "1.5 - 5 Cr": "mid", "5 - 25 Cr": "large",
                 "25 - 100 Cr": "large", "100 - 500 Cr": "large", "500 Cr & above": "large"}


def region_of(state):
    return REGION.get(state, "Other") if isinstance(state, str) else "Unknown"


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def two_prop_z(k1, n1, k2, n2):
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0
    return ((k1 / n1 - k2 / n2) / se) if se else 0.0


def strength(n, z=None, lift=None):
    """Heuristic evidence strength from sample size and significance."""
    if z is not None:
        if abs(z) >= 3 and n >= 1000:
            return "strong"
        if abs(z) >= 2:
            return "moderate"
        return "weak"
    if n >= 5000 and lift is not None and abs(lift) >= 0.15:
        return "strong"
    if n >= 500:
        return "moderate"
    return "weak"


class Ev:
    def __init__(self):
        self.items = []
        self.sections = []

    def add(self, key, claim, metric, segment, n, value, baseline=None, strength="moderate", note="",
            implication=""):
        eid = f"E{len(self.items) + 1}"
        self.items.append(dict(id=eid, key=key, claim=claim, metric=metric, segment=segment, n=int(n),
                               value=_r(value), baseline=_r(baseline), strength=strength, note=note,
                               implication=implication))
        return eid

    def section(self, title, md):
        self.sections.append((title, md))


def _r(v):
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(v) else round(float(v), 4)
    if isinstance(v, dict):
        return {k: _r(x) for k, x in v.items()}
    if isinstance(v, (np.integer,)):
        return int(v)
    return v


def outcome_table(df, col, min_n=500):
    t = df.groupby(col, observed=True).agg(
        n=("meeting_fixed", "size"), meeting=("meeting_fixed", "mean"), not_int=("ni", "mean"),
        call_later=("cl", "mean"), early_drop=("early", "mean"), median_sec=("lead_call_duration", "median"))
    return t[t.n >= min_n].sort_values("meeting", ascending=False)


def md_table(t, pct=("meeting", "not_int", "call_later", "early_drop")):
    t = t.copy()
    for c in pct:
        if c in t:
            t[c] = (t[c] * 100).round(1).astype(str) + "%"
    return t.to_markdown()


# --------------------------------------------------------------------------------------------
def build_calls():
    s = L.sellers()
    c = L.bot_calls().sort_values(["fk_glusr_usr_id", "call_start_time"])
    c["early"] = c.lead_call_duration < 10
    c["ni"] = c.disposition_label.eq("Not Interested")
    c["cl"] = c.disposition_label.eq("Call Later / Busy")
    g = c.groupby("fk_glusr_usr_id")
    c["prior_calls"] = g.cumcount()
    c["prior_call_later"] = g.cl.cumsum() - c.cl
    c["prior_early"] = g.early.cumsum() - c.early
    c["prior_ni"] = g.ni.cumsum() - c.ni
    c["hour"] = c.call_start_time.dt.hour
    df = c.merge(s, on="fk_glusr_usr_id", how="left")
    df["region"] = df.seller_state.map(region_of)
    df["turnover_band"] = df.annual_turnover.map(TURNOVER_BAND).fillna("unknown")
    df["engagement"] = pd.cut(df.eng_pickup_ratio_1yr, [-1, 0, 20, 50, 101],
                              labels=["never_picks", "low", "medium", "high"]).astype(str)
    df.loc[df.eng_pickup_ratio_1yr.isna(), "engagement"] = "unknown"
    return df


def seller_outcomes(ev, df):
    base = df.meeting_fixed.mean()
    n = len(df)
    ev.section("Baseline", f"{n:,} answered bot calls to {df.fk_glusr_usr_id.nunique():,} sellers. "
               f"Meeting fixed {base:.1%}, not interested {df.ni.mean():.1%}, call later {df.cl.mean():.1%}, "
               f"early drop (<10 s) {df.early.mean():.1%}, median duration {df.lead_call_duration.median():.0f} s.")
    ev.add("baseline", "Baseline outcome rates over all answered bot calls", "meeting_fixed_rate", "all", n,
           base, None, "strong", f"early_drop={df.early.mean():.3f}, not_interested={df.ni.mean():.3f}")

    # attempt number
    t = outcome_table(df, "call_attempt_count")
    ev.section("By call attempt number", md_table(t))
    a1 = df[df.call_attempt_count == 1]
    a4 = df[df.call_attempt_count >= 4]
    z = two_prop_z(a1.meeting_fixed.sum(), len(a1), a4.meeting_fixed.sum(), len(a4))
    ev.add("attempt_decay",
           "Meeting rate collapses and early hang-ups rise with every repeat attempt; repeat-call sellers need "
           "a shorter, different opening that acknowledges the earlier call",
           "meeting_fixed_rate", "call_attempt_count>=4 vs 1", len(a4), a4.meeting_fixed.mean(),
           a1.meeting_fixed.mean(), strength(len(a4), z),
           f"early_drop {a4.early.mean():.1%} vs {a1.early.mean():.1%}; median {a4.lead_call_duration.median():.0f}s "
           f"vs {a1.lead_call_duration.median():.0f}s; z={z:.1f}",
           "Repeat attempts: acknowledge prior call, cut opening to one line, faster pace.")

    # prior history (computed from earlier calls, so no leakage)
    rep = df[df.prior_calls >= 1]
    pc = rep[rep.prior_call_later >= 1]
    npc = rep[rep.prior_call_later == 0]
    z = two_prop_z(pc.meeting_fixed.sum(), len(pc), npc.meeting_fixed.sum(), len(npc))
    ev.add("prior_call_later",
           "Sellers who earlier said 'call later' convert better on the follow-up call than other repeat sellers",
           "meeting_fixed_rate", "repeat calls with >=1 prior call-later", len(pc), pc.meeting_fixed.mean(),
           npc.meeting_fixed.mean(), strength(len(pc), z), f"z={z:.1f}",
           "Open by referencing the callback they asked for; go straight to scheduling.")
    pe = rep[rep.prior_early >= 1]
    npe = rep[rep.prior_early == 0]
    z = two_prop_z(pe.early.sum(), len(pe), npe.early.sum(), len(npe))
    ev.add("prior_early_drop",
           "Sellers who hung up within 10 s before are much more likely to hang up early again",
           "early_drop_rate", "repeat calls with >=1 prior early drop", len(pe), pe.early.mean(), npe.early.mean(),
           strength(len(pe), z), f"meeting {pe.meeting_fixed.mean():.1%} vs {npe.meeting_fixed.mean():.1%}; z={z:.1f}",
           "Fast hangers-up: value hook in the first sentence, faster pace, skip pleasantries.")
    pn = rep[rep.prior_ni >= 1]
    z = two_prop_z(pn.meeting_fixed.sum(), len(pn), npc.meeting_fixed.sum(), len(npc))
    ev.add("prior_not_interested",
           "Sellers who previously said not interested rarely convert on later calls",
           "meeting_fixed_rate", "repeat calls with >=1 prior not-interested", len(pn), pn.meeting_fixed.mean(),
           rep.meeting_fixed.mean(), strength(len(pn), z), f"z={z:.1f}",
           "Low-pressure tone, one soft ask, then exit politely (escalation rule).")

    # region
    t = outcome_table(df, "region")
    ev.section("By region", md_table(t))
    for reg in ["NCR_Punjab", "Hindi_belt", "West", "South", "East"]:
        x = df[df.region == reg]
        rest = df[df.region != reg]
        z = two_prop_z(x.meeting_fixed.sum(), len(x), rest.meeting_fixed.sum(), len(rest))
        ev.add(f"region_{reg}", f"Outcomes for {reg} sellers", "meeting_fixed_rate", f"region={reg}", len(x),
               x.meeting_fixed.mean(), base, strength(len(x), z),
               f"not_interested {x.ni.mean():.1%}, early_drop {x.early.mean():.1%}, median {x.lead_call_duration.median():.0f}s; z={z:.1f}")
    t = outcome_table(df, "seller_state", 1500)
    ev.section("By state (n>=1500)", md_table(t))

    # turnover
    t = outcome_table(df, "turnover_band")
    ev.section("By turnover band", md_table(t))
    lg = df[df.turnover_band.isin(["mid", "large"])]
    mi = df[df.turnover_band == "micro"]
    z = two_prop_z(lg.meeting_fixed.sum(), len(lg), mi.meeting_fixed.sum(), len(mi))
    ev.add("turnover_large",
           "Larger businesses (turnover >= 1.5 Cr) agree to meetings less often and hang up faster than micro "
           "sellers", "meeting_fixed_rate", "turnover >= 1.5 Cr vs 0-40 L", len(lg), lg.meeting_fixed.mean(),
           mi.meeting_fixed.mean(), strength(len(lg), z),
           f"early_drop {lg.early.mean():.1%} vs {mi.early.mean():.1%}; z={z:.1f}",
           "Mid/large: formal register, business-outcome framing, crisp and respectful of time.")

    # nature of business
    t = outcome_table(df, "nature_of_business")
    ev.section("By nature of business", md_table(t))
    for nat, key in [("Trader - Wholesaler/Distributor", "nature_wholesaler"),
                     ("Service Provider and Others", "nature_service"),
                     ("Manufacturer", "nature_manufacturer"), ("Trader - Retailer", "nature_retailer")]:
        x = df[df.nature_of_business.isin([nat, nat.replace("Trader - ", "")])]
        rest = df[~df.index.isin(x.index)]
        z = two_prop_z(x.meeting_fixed.sum(), len(x), rest.meeting_fixed.sum(), len(rest))
        ev.add(key, f"Outcomes for {nat}", "meeting_fixed_rate", f"nature={nat}", len(x), x.meeting_fixed.mean(),
               base, strength(len(x), z),
               f"early_drop {x.early.mean():.1%}, median {x.lead_call_duration.median():.0f}s; z={z:.1f}")

    # engagement
    t = outcome_table(df, "engagement")
    ev.section("By 1-yr pickup ratio on IndiaMART calls (engagement)", md_table(t))
    hi = df[df.engagement == "high"]
    nv = df[df.engagement == "never_picks"]
    z = two_prop_z(hi.meeting_fixed.sum(), len(hi), nv.meeting_fixed.sum(), len(nv))
    ev.add("engagement_high", "Highly engaged sellers (pickup ratio > 50%) vs sellers who never pick up",
           "meeting_fixed_rate", "engagement=high vs never_picks", len(hi), hi.meeting_fixed.mean(),
           nv.meeting_fixed.mean(), strength(len(hi), z), f"z={z:.1f}")
    rep_ = df[df.eng_enq_replies_90d > 0]
    norep = df[df.eng_enq_replies_90d == 0]
    z = two_prop_z(rep_.meeting_fixed.sum(), len(rep_), norep.meeting_fixed.sum(), len(norep))
    ev.add("enquiry_responders", "Sellers who replied to buyer enquiries in last 90 days vs those who replied to none",
           "meeting_fixed_rate", "eng_enq_replies_90d>0 vs =0", len(rep_), rep_.meeting_fixed.mean(),
           norep.meeting_fixed.mean(), strength(len(rep_), z), f"z={z:.1f}",
           "Active enquiry responders: lead with their enquiry count / buyer demand hook.")

    # flags
    for flag, label in [("already_in_touch_with_executive", "already in touch with an IndiaMART executive"),
                        ("do_not_call_requested", "asked not to be called"),
                        ("showed_frustration", "showed frustration on a past call"),
                        ("asked_if_talking_to_bot", "asked whether they were talking to a bot")]:
        x = df[df[flag] == 1]
        y = df[df[flag] == 0]
        if len(x) < 30:
            continue
        z = two_prop_z(x.meeting_fixed.sum(), len(x), y.meeting_fixed.sum(), len(y))
        ev.add(f"flag_{flag}", f"Sellers flagged as having {label}", "meeting_fixed_rate", f"{flag}=1", len(x),
               x.meeting_fixed.mean(), y.meeting_fixed.mean(), strength(len(x), z),
               f"early_drop {x.early.mean():.1%} vs {y.early.mean():.1%}; median {x.lead_call_duration.median():.0f}s; "
               f"z={z:.1f}. Flag comes from the same Apr-Sep calls, so this partly describes the flagged call itself.")

    # time of day
    t = outcome_table(df, "hour")
    ev.section("By hour of day (IST)", md_table(t.sort_index()))
    h11 = df[df.hour.isin([11, 12])]
    oth = df[~df.hour.isin([11, 12])]
    z = two_prop_z(h11.meeting_fixed.sum(), len(h11), oth.meeting_fixed.sum(), len(oth))
    ev.add("hour_late_morning", "Calls at 11:00-12:59 have the worst outcomes (busiest trading hours)",
           "meeting_fixed_rate", "hour in 11-12", len(h11), h11.meeting_fixed.mean(), oth.meeting_fixed.mean(),
           strength(len(h11), z), f"early_drop {h11.early.mean():.1%} vs {oth.early.mean():.1%}; z={z:.1f}",
           "Live: in late-morning calls, start in short mode and offer a callback slot early.")

    # lead bucket
    t = outcome_table(df, "redis_bucket")
    ev.section("By hot-lead bucket (redis_bucket)", md_table(t))
    pam = df[df.redis_bucket.isin(["PAM", "NUR", "SCHD"])]
    z = two_prop_z(pam.meeting_fixed.sum(), len(pam), df.meeting_fixed.sum(), len(df))
    ev.add("bucket_warm", "Warm lead buckets (PAM, NUR, SCHD) convert better than average", "meeting_fixed_rate",
           "redis_bucket in PAM/NUR/SCHD", len(pam), pam.meeting_fixed.mean(), base, strength(len(pam), z),
           f"z={z:.1f}", "Personalise the opening with the lead reason (e.g. paid-package interest).")


def bot_version(ev, df):
    """Same-window comparison: the trial versions ran only on 30 Sep afternoon."""
    w = df[(df.call_start_time >= "2026-09-28") & (df.hour >= 14)]
    t = w.groupby("lead_bot_version").agg(n=("meeting_fixed", "size"), meeting=("meeting_fixed", "mean"),
                                         early_drop=("early", "mean"), not_int=("ni", "mean"),
                                         median_sec=("lead_call_duration", "median"),
                                         first_attempt=("call_attempt_count", lambda x: (x == 1).mean()))
    ev.section("Bot versions, matched window (28-30 Sep, 14:00-21:00)", md_table(t))
    ref = w[w.lead_bot_version == "main_vani"]
    for v in ["personalis", "base_vani"]:
        x = w[w.lead_bot_version == v]
        if not len(x):
            continue
        z = two_prop_z(x.meeting_fixed.sum(), len(x), ref.meeting_fixed.sum(), len(ref))
        lo, hi = wilson(x.meeting_fixed.sum(), len(x))
        # attempt-1 only to control for attempt mix
        x1, r1 = x[x.call_attempt_count == 1], ref[ref.call_attempt_count == 1]
        ev.add(f"version_{v}",
               f"'{v}' script vs main_vani in the same days and hours",
               "meeting_fixed_rate", f"lead_bot_version={v}", len(x), x.meeting_fixed.mean(),
               ref.meeting_fixed.mean(), strength(len(x), z),
               f"95% CI {lo:.1%}-{hi:.1%}; z={z:.1f}; first-attempt only: {x1.meeting_fixed.mean():.1%} (n={len(x1)}) vs "
               f"{r1.meeting_fixed.mean():.1%} (n={len(r1)}). Single-afternoon trial, not randomised.",
               "Personalised openings are directionally better; evidence is suggestive, not conclusive."
               if v == "personalis" else "")
    allv = outcome_table(df, "lead_bot_version", 50)
    ev.section("Bot versions, all time (not comparable: different periods)", md_table(allv))


# --------------------------------------------------------------------------------------------
def evaluator_evidence(ev, df):
    calls = df.set_index("attempt_id")
    # objections
    o = L.evaluator("objections")
    rows = []
    for aid, out in zip(o.attempt_id, o.out):
        if not isinstance(out, dict):
            continue
        for a in out.get("objection_analysis", []) or []:
            rows.append((aid, a.get("category"), bool(out.get("meeting_fixed")),
                         "; ".join((a.get("evidence_quotes") or [])[:2])))
    ob = pd.DataFrame(rows, columns=["attempt_id", "category", "mf", "quote"])
    ob = ob.merge(df[["attempt_id", "region", "turnover_band", "nature_of_business", "meeting_fixed"]],
                  on="attempt_id", how="left")
    t = ob.groupby("category").agg(n=("mf", "size"), meeting_after=("meeting_fixed", "mean")).sort_values(
        "n", ascending=False)
    ev.section("Objection categories (objections evaluator, 5.2k calls)", md_table(t, ("meeting_after",)))
    total_calls = o.attempt_id.nunique()
    for cat, r in t.head(8).iterrows():
        q = ob[ob.category == cat].quote.dropna()
        ev.add("objection_" + re.sub(r"\W+", "_", cat.lower()).strip("_")[:40],
               f"Objection '{cat}': share of objection calls and meeting rate after it", "meeting_fixed_rate",
               f"objection={cat}", r.n, r.meeting_after, None, "moderate" if r.n >= 300 else "weak",
               f"present in {r.n / total_calls:.1%} of analysed calls; sample quote: {q.iloc[0][:120] if len(q) else ''}")
    by_reg = pd.crosstab(ob.region, ob.category, normalize="index").round(3)
    ev.section("Objection mix by region (row %)", (by_reg * 100).round(1).to_markdown())
    by_to = pd.crosstab(ob.turnover_band, ob.category, normalize="index").round(3)
    ev.section("Objection mix by turnover band (row %)", (by_to * 100).round(1).to_markdown())
    objection_mix = {
        "by_region": by_reg.to_dict(orient="index"),
        "by_turnover": by_to.to_dict(orient="index"),
        "overall": (ob.category.value_counts(normalize=True)).round(4).to_dict(),
    }

    # seller question gaps: where the bot failed
    q = L.evaluator("seller_questions")
    gaps, ques = [], []
    for aid, out in zip(q.attempt_id, q.out):
        if not isinstance(out, dict):
            continue
        for g in out.get("gaps", []) or []:
            gaps.append((aid, g.get("seller_turn_type"), ",".join(g.get("gap_type") or []),
                         g.get("seller_turn_dialogue"), g.get("suggested_kb_entry")))
        for qq in out.get("questions", []) or []:
            cats = qq.get("category") or []
            for c_ in (cats if isinstance(cats, list) else [cats]):
                ques.append((aid, c_, qq.get("que_dialogue"), qq.get("ans_dialogue")))
    gp = pd.DataFrame(gaps, columns=["attempt_id", "turn_type", "gap_type", "seller", "suggested"])
    gp = gp.merge(df[["attempt_id", "meeting_fixed"]], on="attempt_id", how="left")
    gcalls = q[q.out.map(lambda o: isinstance(o, dict) and "gaps" in o)]
    with_gap = set(gp.attempt_id)
    gc = df[df.attempt_id.isin(gcalls.attempt_id)]
    g1, g0 = gc[gc.attempt_id.isin(with_gap)], gc[~gc.attempt_id.isin(with_gap)]
    z = two_prop_z(g1.meeting_fixed.sum(), len(g1), g0.meeting_fixed.sum(), len(g0))
    busy_miss = gp.seller.fillna("").str.contains(X.SIGNAL_RE["rush"]).mean()
    effect = ("meetings drop" if z <= -2 else "no measurable change in meeting rate (gaps occur in long, "
              "engaged calls too)")
    ev.add("bot_response_gap",
           f"The bot ignores or mishandles a seller turn in {len(g1) / max(len(gc), 1):.0%} of evaluated calls; "
           f"{effect}", "meeting_fixed_rate", "calls with >=1 response gap", len(g1), g1.meeting_fixed.mean(),
           g0.meeting_fixed.mean(), strength(len(g1), z) if z <= -2 else "weak",
           f"top gap turn types: {gp.turn_type.value_counts().head(3).to_dict()}; {busy_miss:.0%} of missed turns "
           f"were 'busy/later' statements; z={z:.1f}",
           "Quality rule (not outcome-backed): acknowledge the seller's exact objection before re-asking.")
    ev.section("Bot response gaps by seller turn type",
               gp.groupby("turn_type").agg(n=("attempt_id", "size"),
                                            meeting=("meeting_fixed", "mean")).sort_values("n", ascending=False)
               .head(10).to_markdown())
    qs = pd.DataFrame(ques, columns=["attempt_id", "category", "q", "a"])
    qs = qs.merge(df[["attempt_id", "meeting_fixed", "region"]], on="attempt_id", how="left")
    qt = qs.groupby("category").agg(n=("attempt_id", "size"), meeting=("meeting_fixed", "mean")).sort_values(
        "n", ascending=False).head(12)
    ev.section("Questions sellers ask (seller_questions evaluator)", md_table(qt, ("meeting",)))
    botq = qs[qs.category.astype(str).str.contains("Bot", case=False)]
    human_claim = botq.a.fillna("").str.contains(r"main .{0,20}(?:payal|insaan|human)|nahi,? main", case=False)
    ev.add("bot_identity_question",
           "Sellers do ask if they are talking to an AI; the current bot often answers by claiming to be a person",
           "share_of_questions", "question category = AI Bot Confirmation", len(botq),
           len(botq) / max(qs.attempt_id.nunique(), 1), None, "moderate",
           f"meeting rate in those calls {botq.meeting_fixed.mean():.1%}; {human_claim.mean():.0%} of answers deny "
           "being a bot (compliance risk)",
           "Guardrail: never claim to be human; give an honest, brief identity answer and continue.")

    # topics -> meeting
    tp = L.evaluator("topics")
    trow = []
    for aid, out in zip(tp.attempt_id, tp.out):
        if isinstance(out, dict):
            for x in out.get("discussion_timeline", []) or []:
                trow.append((aid, x.get("topic_id"), x.get("sequence_number")))
    tt = pd.DataFrame(trow, columns=["attempt_id", "topic", "seq"]).dropna()
    tt = tt.drop_duplicates(["attempt_id", "topic"]).merge(df[["attempt_id", "meeting_fixed"]], on="attempt_id")
    base = df[df.attempt_id.isin(tp.attempt_id)].meeting_fixed.mean()
    ttab = tt.groupby("topic").agg(n=("attempt_id", "size"), meeting=("meeting_fixed", "mean"))
    ttab = ttab[ttab.n >= 100].sort_values("meeting", ascending=False)
    ev.section(f"Topics present in call vs meeting rate (topics evaluator; base {base:.1%})",
               md_table(ttab, ("meeting",)))
    for tid in ["T11_PAYMENT_INTEREST", "T14_PROFILE_VISIBILITY_IMPROVEMENT"]:
        if tid in ttab.index:
            r = ttab.loc[tid]
            ev.add(f"topic_{tid.lower()}", f"Calls where the bot used the '{tid}' hook", "meeting_fixed_rate",
                   f"topic={tid}", r.n, r.meeting, base, "weak",
                   "Topic presence is partly a result of the call going longer (survivorship); treat as directional.")

    # existing executive contact
    se = L.evaluator("se_contact")
    se["cat"] = se.out.map(lambda o: o.get("category") if isinstance(o, dict) else None)
    se = se.merge(df[["attempt_id", "meeting_fixed"]], on="attempt_id")
    st = se.groupby("cat").agg(n=("attempt_id", "size"), meeting=("meeting_fixed", "mean"))
    ev.section("Existing executive contact (se_contact evaluator)", md_table(st, ("meeting",)))
    met = se[se.cat.astype(str).str.contains("met|touch|already", case=False) & ~se.cat.eq("neither")]
    if len(met):
        ev.add("se_contact_existing", "Sellers who say they are already in touch with / met an executive",
               "meeting_fixed_rate", "se_contact != neither", len(met), met.meeting_fixed.mean(),
               se[se.cat == "neither"].meeting_fixed.mean(), "moderate",
               "Playbook: acknowledge the existing executive, offer the visit as a follow-up on new enquiries.")

    # who ends the call
    ex = L.evaluator("execdrop")
    ex["who"] = ex.out.map(lambda o: o.get("who_ended_call") if isinstance(o, dict) else None)
    ev.section("Who ended the call (execdrop evaluator)",
               ex.who.value_counts(normalize=True).round(3).to_frame("share").to_markdown())

    # disposition sub-reasons
    d = L.evaluator("disposition")
    d["subd"] = d.out.map(lambda o: o.get("sub_disposition") if isinstance(o, dict) else None)
    ds = d.subd.value_counts(normalize=True).head(15).round(4)
    ev.section("Detailed dispositions (top 15)", ds.to_frame("share").to_markdown())
    dropped = d.subd.astype(str).str.startswith("dropped").mean()
    ev.add("drop_points", "Where calls drop: share of dispositions that are drops at a given stage",
           "share", "disposition evaluator", len(d), dropped, None, "strong",
           "; ".join(f"{k}={v:.1%}" for k, v in ds.items() if str(k).startswith(("dropped", "no_response"))),
           "The opening and the first pitch line are where most calls are lost.")
    return objection_mix


# --------------------------------------------------------------------------------------------
def turn_evidence(ev, df):
    t = L.call_turns()
    t["text"] = t.text.fillna("").astype(str)
    t["words"] = t.text.map(lambda s: len(s.split()))
    t["dur"] = (t.end_sec - t.start_sec).clip(lower=0)
    sel = df[["attempt_id", "seller_state", "region", "turnover_band", "meeting_fixed", "early",
              "disposition_label", "call_attempt_count"]]
    t = t.merge(sel, on="attempt_id", how="left")
    st = t[t.speaker == "seller"].copy()
    st["lang"] = st.text.map(lambda x: X.detect_language(x)[0])
    st["en_share"] = st.text.map(X.english_share)

    # language by state
    call_lang = (st.dropna(subset=["lang"]).groupby(["attempt_id", "seller_state"]).lang
                 .agg(lambda x: x.value_counts().index[0]).reset_index())
    lang_tab = pd.crosstab(call_lang.seller_state, call_lang.lang, normalize="index")
    lang_tab["n_calls"] = call_lang.groupby("seller_state").size()
    lang_tab = lang_tab[lang_tab.n_calls >= 15].sort_values("n_calls", ascending=False)
    ev.section("Language sellers actually speak on calls, by state (share of calls; keyword-detected)",
               (lang_tab.drop(columns="n_calls") * 100).round(0).assign(n_calls=lang_tab.n_calls).to_markdown())
    lang_by_state = {s: {k: round(float(v), 3) for k, v in r.items() if k != "n_calls" and v > 0}
                     | {"n_calls": int(r.n_calls)} for s, r in lang_tab.iterrows()}
    for state in ["Tamil Nadu", "Gujarat", "Maharashtra", "West Bengal", "Karnataka", "Telangana", "Kerala",
                  "Andhra Pradesh", "Punjab", "Odisha"]:
        if state not in lang_tab.index:
            continue
        r = lang_tab.loc[state]
        hi = r.get("hi-IN", 0)
        top = r.drop("n_calls").idxmax()
        ev.add(f"lang_{state.lower().replace(' ', '_')}",
               f"{state} sellers answer the (Hindi-speaking) bot mostly in {top}", "share_of_calls",
               f"state={state}", r.n_calls, r[top], hi, "moderate" if r.n_calls >= 100 else "weak",
               f"Hindi {hi:.0%}, English {r.get('en-IN', 0):.0%}, regional detail {dict((k, round(v, 2)) for k, v in r.drop('n_calls').items() if v > 0.02)}. "
               "Bot always opened in Hindi, so Hindi share is biased upward.")
    lang_mix_rows = st.dropna(subset=["lang"])
    nonhi = lang_mix_rows[~lang_mix_rows.lang.isin(["hi-IN"])]
    calls_switch = nonhi.attempt_id.nunique()
    ev.add("lang_switch_rate", "Share of transcribed calls where the seller spoke a non-Hindi language at least once",
           "share_of_calls", "all transcribed calls", st.attempt_id.nunique(),
           calls_switch / st.attempt_id.nunique(), None, "moderate",
           "Language-switch detection is needed live even though most calls stay in Hindi.")

    # english mix by turnover and region
    em = st.dropna(subset=["en_share"]).groupby("attempt_id").agg(en=("en_share", "mean"),
                                                                 band=("turnover_band", "first"),
                                                                 region=("region", "first"))
    emt = em.groupby("band").en.agg(["mean", "size"]).round(3)
    emr = em.groupby("region").en.agg(["mean", "size"]).round(3)
    ev.section("English-word share in seller speech by turnover band", emt.to_markdown())
    ev.section("English-word share in seller speech by region", emr.to_markdown())
    english_mix = {"by_turnover": emt["mean"].to_dict(), "by_region": emr["mean"].to_dict()}
    if "large" in emt.index and "micro" in emt.index:
        lg_, mi_ = emt.loc["large", "mean"], emt.loc["micro", "mean"]
        diff = lg_ - mi_
        ev.add("english_by_turnover",
               ("Larger businesses use more English words when they speak" if diff > 0.02 else
                "English-word share barely differs by turnover band (large vs micro)"),
               "english_word_share", "turnover large vs micro", int(emt.loc["large", "size"]), lg_, mi_,
               "weak" if abs(diff) <= 0.02 else ("moderate" if emt.loc["large", "size"] >= 200 else "weak"),
               "Keyword-based estimate.",
               "Turnover alone should not drive english_mix; use region and live detection." if abs(diff) <= 0.02
               else "Raise english_mix for mid/large businesses.")
    if "South" in emr.index:
        ev.add("english_south", "Southern sellers use the most English among regions", "english_word_share",
               "region=South", int(emr.loc["South", "size"]), emr.loc["South", "mean"],
               float(em.en.mean()), "moderate" if emr.loc["South", "size"] >= 200 else "weak",
               "Keyword-based estimate.", "South: English-heavy fallback if regional language not used.")

    # speech rate (pace matching)
    sp = st[(st.dur >= 1.0) & (st.words >= 3)].copy()
    sp["wps"] = sp.words / sp.dur
    spr = sp.groupby("region").wps.agg(["median", "size"]).round(2)
    bot = t[(t.speaker == "bot") & (t.dur >= 1.0) & (t.words >= 3)]
    bot_wps = float((bot.words / bot.dur).median())
    ev.section(f"Seller speech rate (words/sec) by region; bot median {bot_wps:.2f} w/s", spr.to_markdown())
    ev.add("speech_rate", "Seller speaking rate vs the bot's rate", "words_per_sec", "seller turns",
           len(sp), float(sp.wps.median()), bot_wps, "weak",
           f"by region {spr['median'].to_dict()}. No call recorded different bot paces, so pace effects are "
           "an informed guess.", "Pace setting = informed guess; live adaptation corrects it.")

    # per-call dynamics: early hang-up vs meeting
    pc = t.groupby("attempt_id").agg(n_turns=("turn_no", "max"), mf=("meeting_fixed", "first"),
                                     early=("early", "first"), disp=("disposition_label", "first"))
    s_agg = st.groupby("attempt_id").agg(seller_words=("words", "mean"), seller_turns=("turn_no", "size"))
    pc = pc.join(s_agg)
    # bot pitch length: first bot turn mentioning IndiaMART
    pitch = t[(t.speaker == "bot") & t.text.str.contains("indiamart", case=False)].groupby("attempt_id").first()
    pitch["truncated"] = pitch.text.str.rstrip().str.endswith(("...", "…"))
    pc = pc.join(pitch[["words", "truncated"]].rename(columns={"words": "pitch_words"}))
    pc["short_call"] = pc.n_turns <= 4
    trunc = pc.truncated.mean()
    full = pc[pc.truncated == False].copy()  # noqa: E712  (pitch line was spoken in full)
    full["pitch_len"] = pd.qcut(full.pitch_words, 3, labels=["short", "medium", "long"], duplicates="drop")
    pl = full.groupby("pitch_len", observed=True).agg(n=("mf", "size"), meeting=("mf", "mean"),
                                                     ended_within_4_turns=("short_call", "mean"),
                                                     pitch_words=("pitch_words", "median"))
    ev.section(f"Length of the bot's first IndiaMART pitch line vs outcome (pitch lines spoken in full; "
               f"{trunc:.0%} of pitch lines were cut off by the seller)",
               md_table(pl, ("meeting", "ended_within_4_turns")))
    s_, l_ = full[full.pitch_len == "short"], full[full.pitch_len == "long"]
    z = two_prop_z(s_.mf.sum(), len(s_), l_.mf.sum(), len(l_))
    ev.add("pitch_truncation",
           f"Sellers cut off the bot's first pitch line in {trunc:.0%} of transcribed calls",
           "share_of_calls", "transcribed calls with a pitch line", int(pc.pitch_words.notna().sum()), trunc, None,
           "moderate", f"meeting rate when pitch cut off {pc[pc.truncated == True].mf.mean():.1%} vs "  # noqa: E712
           f"{full.mf.mean():.1%} when spoken in full",
           "Front-load the value hook (enquiries in their city) in the first 8-10 words.")
    ev.add("pitch_length",
           "Among pitch lines spoken in full, length shows " +
           ("no clear relation to meeting rate" if abs(z) < 2 else
            ("longer lines going with more meetings" if z < 0 else "shorter lines going with more meetings")),
           "meeting_fixed_rate", "full pitch line short vs long tercile", len(s_), s_.mf.mean(), l_.mf.mean(),
           "weak", f"median words {s_.pitch_words.median():.0f} vs {l_.pitch_words.median():.0f}; z={z:.1f}. "
           "Longer lines carry more content (e.g. the lead reason), so this is confounded.",
           "Pitch length itself is not evidenced; the generator keeps the hook early and adapts length live.")

    # latency / repetition evaluator
    lr = L.evaluator("latency_repetition")
    lr["p50"] = lr.out.map(lambda o: (o.get("latency") or {}).get("p50_sec") if isinstance(o, dict) else None)
    lr["repeat"] = lr.out.map(lambda o: (o.get("latency") or {}).get("seller_had_to_repeat_count", 0)
                              if isinstance(o, dict) else 0)
    lr["overlap"] = lr.out.map(lambda o: (o.get("latency") or {}).get("overlap_count", 0) if isinstance(o, dict) else 0)
    lr["loopy"] = lr.out.map(lambda o: bool(o.get("is_loopy")) if isinstance(o, dict) else False)
    lr = lr.merge(df[["attempt_id", "meeting_fixed", "early"]], on="attempt_id")
    lr["lat_band"] = pd.cut(lr.p50, [-1, 1.0, 1.5, 2.0, 3.0, 100], labels=["<=1s", "1-1.5s", "1.5-2s", "2-3s", ">3s"])
    lt = lr.groupby("lat_band", observed=True).agg(n=("attempt_id", "size"), meeting=("meeting_fixed", "mean"))
    ev.section("Bot reply latency (p50 per call) vs meeting rate", md_table(lt, ("meeting",)))
    lp = lr[lr.loopy]
    nl = lr[~lr.loopy]
    z = two_prop_z(lp.meeting_fixed.sum(), len(lp), nl.meeting_fixed.sum(), len(nl))
    ev.add("bot_loopy", "Calls where the bot repeated itself (loopy) convert worse", "meeting_fixed_rate",
           "is_loopy", len(lp), lp.meeting_fixed.mean(), nl.meeting_fixed.mean(), strength(len(lp), z),
           f"z={z:.1f}", "Never repeat the same pitch verbatim; rephrase or move on.")
    rp = lr[lr.repeat > 0]
    nr = lr[lr.repeat == 0]
    z = two_prop_z(rp.meeting_fixed.sum(), len(rp), nr.meeting_fixed.sum(), len(nr))
    ev.add("seller_repeat", "Calls where the seller had to repeat themselves", "meeting_fixed_rate",
           "seller_had_to_repeat_count>0", len(rp), rp.meeting_fixed.mean(), nr.meeting_fixed.mean(),
           strength(len(rp), z), f"z={z:.1f}. Seller repeating = confusion/not-heard signal.")

    # live signals: hazard of the call ending soon after a signal
    st = st.sort_values(["attempt_id", "turn_no"])
    st["sig"] = st.text.map(X.signals_in)
    last_turn = t.groupby("attempt_id").turn_no.max()
    st["turns_left"] = st.attempt_id.map(last_turn) - st.turn_no
    st["ends_soon"] = st.turns_left <= 2
    base_end = st.ends_soon.mean()
    base_mf = pc.mf.mean()
    sig_rows = []
    for sname in X.SIGNALS:
        m = st.sig.map(lambda s: sname in s)
        calls_with = set(st[m].attempt_id)
        mf_with = pc[pc.index.isin(calls_with)].mf.mean()
        sig_rows.append(dict(signal=sname, seller_turns=int(m.sum()), share_turns=m.mean(),
                             calls=len(calls_with), ends_within_2_turns=st[m].ends_soon.mean(),
                             meeting_in_call=mf_with))
        z = two_prop_z(st[m].ends_soon.sum(), int(m.sum()), st.ends_soon.sum(), len(st)) if m.sum() else 0
        ev.add(f"signal_{sname}", f"Live signal '{sname}': how often it appears and what follows",
               "ends_within_2_turns", f"seller turns with {sname} keywords", int(m.sum()),
               st[m].ends_soon.mean() if m.sum() else None, base_end, strength(int(m.sum()), z),
               f"meeting rate in calls with signal {mf_with:.1%} vs {base_mf:.1%}; z={z:.1f}")
    sigt = pd.DataFrame(sig_rows).set_index("signal")
    ev.section(f"Live signals in seller turns (baseline: call ends within 2 turns {base_end:.1%}, "
               f"meeting {base_mf:.1%})", sigt.round(3).to_markdown())

    # short consecutive replies as rush/disengagement
    st["short"] = st.words <= 2
    st["prev_short"] = st.groupby("attempt_id").short.shift(1, fill_value=False)
    two_short = st[st.short & st.prev_short & (st.turn_no > 3)]
    ev.add("two_short_replies", "Two consecutive 1-2 word seller replies after the opening", "ends_within_2_turns",
           "seller turns", len(two_short), two_short.ends_soon.mean(), base_end,
           strength(len(two_short), two_prop_z(two_short.ends_soon.sum(), len(two_short), st.ends_soon.sum(), len(st))),
           "Disengagement / rush proxy.")

    early_calls = pc[pc.disp.isin(["Not Interested"]) & (pc.n_turns <= 6)]
    mf_calls = pc[pc.mf == 1]
    thresholds = {
        "source": "outputs/evidence.json (signal_*, two_short_replies, bot_loopy, seller_repeat, speech_rate)",
        "bot_words_per_sec_median": round(bot_wps, 2),
        "seller_words_per_turn": {"meeting_calls_median": float(mf_calls.seller_words.median()),
                                  "quick_not_interested_median": float(early_calls.seller_words.median())},
        "bot_reply_latency_p50_sec_median": float(lr.p50.median()),
        "rush": {"keywords": X.SIGNALS["rush"], "short_reply_max_words": 2, "consecutive_short_replies": 2,
                 "after_turn": 3, "action": "pace +0.2 (max 1.4), one-sentence replies, jump to scheduling ask",
                 "evidence": ["signal_rush", "two_short_replies", "attempt_decay"]},
        "frustration": {"keywords": X.SIGNALS["frustration"], "also": "seller interrupts bot twice (barge-in)",
                        "action": "apologise once, pace -0.1, warmth high, offer callback or exit",
                        "evidence": ["signal_frustration", "prior_not_interested"]},
        "confusion": {"keywords": X.SIGNALS["confusion"], "also": "seller repeats or asks 'kaun/kya' twice",
                      "action": "pace -0.15 (min 0.8), simpler words, restate purpose in one line",
                      "evidence": ["signal_confusion", "seller_repeat"]},
        "interest": {"keywords": X.SIGNALS["interest"],
                     "action": "energy up, give the specific detail, move to time/locality confirmation",
                     "evidence": ["signal_interest"]},
        "language_switch": {"rule": "2 consecutive seller turns detected in a language other than the current "
                                    "TTS language (or STT language_code differs) -> switch language_code + voice",
                            "single_turn_if_explicit": "seller asks e.g. 'Tamil la pesunga' / 'Hindi nahi aati'",
                            "evidence": ["lang_switch_rate", "lang_tamil_nadu"]},
        "bot_question": {"keywords": X.SIGNALS["bot_question"],
                         "action": "honest identity answer (AI assistant calling for IndiaMART), then continue",
                         "evidence": ["bot_identity_question"]},
        "cooldown_turns": 2,
    }
    return lang_by_state, english_mix, thresholds


# --------------------------------------------------------------------------------------------
def segment_stats(df):
    """Compact per-segment rates the generator can quote."""
    seg = {}
    for col in ["region", "turnover_band", "nature_of_business", "engagement", "call_attempt_count"]:
        t = outcome_table(df, col, 300)
        seg[col] = {str(k): {"n": int(r.n), "meeting": round(r.meeting, 4), "early_drop": round(r.early_drop, 4),
                             "median_sec": float(r.median_sec)} for k, r in t.iterrows()}
    return seg


def main():
    ev = Ev()
    df = build_calls()
    seller_outcomes(ev, df)
    bot_version(ev, df)
    objection_mix = evaluator_evidence(ev, df)
    lang_by_state, english_mix, thresholds = turn_evidence(ev, df)

    OUT.mkdir(exist_ok=True)
    payload = {
        "generated_from": "PS07 dataset, Apr-Sep 2026",
        "strength_scale": "strong: |z|>=3 and n>=1000; moderate: |z|>=2 or n>=500 descriptive; weak: otherwise",
        "not_evidenced": ["voice gender", "voice pitch / timbre", "bot pace (no call varied it)",
                          "warmth/empathy level (no labelled tone data)"],
        "items": ev.items,
        "language_by_state": lang_by_state,
        "english_mix": english_mix,
        "objection_mix": objection_mix,
        "segments": segment_stats(df),
    }
    (OUT / "evidence.json").write_text(json.dumps(payload, indent=1, default=_r, ensure_ascii=False))
    (OUT / "live_thresholds.json").write_text(json.dumps(thresholds, indent=1, ensure_ascii=False))

    md = ["# Evidence report: what has worked on past VANI calls", "",
          "Source: 269k answered bot calls (Apr-Sep 2026), 278k evaluator outputs, 139k transcript turns. "
          "All findings are correlational (no randomised persona experiment exists). Strength: "
          + payload["strength_scale"] + ".", "",
          "**Not evidenced by the data (informed guesses in the generator):** "
          + ", ".join(payload["not_evidenced"]) + ".", "", "## Evidence items", "",
          "| id | claim | segment | n | value | baseline | strength | note |", "|---|---|---|---|---|---|---|---|"]
    for i in ev.items:
        v = i["value"]
        b = i["baseline"]
        md.append(f"| {i['id']} | {i['claim']} | {i['segment']} | {i['n']:,} | "
                  f"{v if not isinstance(v, float) else f'{v:.3f}'} | "
                  f"{'' if b is None else (b if not isinstance(b, float) else f'{b:.3f}')} | {i['strength']} | "
                  f"{i['note']}{(' → ' + i['implication']) if i['implication'] else ''} |".replace("\n", " "))
    md.append("")
    for title, body in ev.sections:
        md += [f"## {title}", "", body, ""]
    (OUT / "evidence_report.md").write_text("\n".join(md))
    print(f"{len(ev.items)} evidence items written")
    for i in ev.items:
        print(i["id"], i["key"], i["n"], i["value"], i["baseline"], i["strength"], "|", i["note"][:150])


if __name__ == "__main__":
    main()
