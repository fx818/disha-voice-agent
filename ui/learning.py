"""The fix loop's memory: call reviews per seller, the fixes they produce for that seller's next call, and rules
suggested across calls (applied only after a person approves them).

Files (outputs/learning/):
  reviews.json   {seller_id: {"state", "rules_use_case", "history": [review...], "overrides": {...}}}
  rules.json     {rule_id: {"status": "approved" | "dismissed", ...}}

Step 2 (per seller, automatic): fixes marked auto in a review become the `overrides` block of that seller's next
seller_profile; OnStart applies them. Step 3 (across sellers, approved): insights() groups reviews into suggested
rules; an approved rule adds its overrides to every matching seller's profile. A seller's own fixes win over rules.
The contact policy is never overridden.
"""
import hashlib
import re
import json
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "outputs" / "learning"
REVIEWS, RULES = DIR / "reviews.json", DIR / "rules.json"
LANG_CODE = {"Hindi": "hi-IN", "English": "en-IN", "Tamil": "ta-IN", "Bengali": "bn-IN", "Gujarati": "gu-IN",
             "Kannada": "kn-IN", "Malayalam": "ml-IN", "Marathi": "mr-IN", "Odia": "od-IN", "Punjabi": "pa-IN",
             "Telugu": "te-IN"}
MIN_CALLS = 2        # a suggested rule needs at least this many reviewed calls behind it
MIN_RATE = 0.5       # ... and this share of them pointing the same way
MIN_SELLERS = 2      # ... from at least this many different sellers (one seller's calls are not a pattern)
_lock = threading.Lock()


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _write(p: Path, d: dict):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    tmp.replace(p)


def _short(iid: str) -> str:
    """A readable call label: the call's start time (ids share a session prefix, so the prefix is not unique)."""
    m = re.search(r"(\d{2}:\d{2}):\d{2}", iid or "")
    day = (iid or "")[6:8]
    return f"{day}/{m.group(1)}" if m and day else (iid or "?")[-8:]


# ---- step 2: per-seller fixes -----------------------------------------------------------------------------

def _overrides(history: list) -> dict:
    """Active overrides from the auto fixes of all reviews, oldest first so the latest call wins."""
    ov, why, pace, notes = {}, [], 0.0, []
    for r in history:
        for f in r.get("fixes") or []:
            if not f.get("auto"):
                continue
            k, v = f.get("kind"), f.get("value")
            if k == "use_case":
                ov["use_case"] = v
            elif k == "start_language":
                ov["start_language"] = v
            elif k == "pace_delta":
                pace = max(-0.2, min(0.2, pace + float(v)))
            elif k == "simpler":
                ov["simpler"] = True
            elif k == "nudge_budget":
                ov["nudge_budget"] = min(int(v), ov.get("nudge_budget", 2))  # only ever lowered
            elif k == "note" and v not in notes:
                notes.append(v)
            else:
                continue
            why.append(f"call {_short(r.get('interaction_id'))}: {f.get('why')}")
    if pace:
        ov["pace_delta"] = round(pace, 2)
    if notes:
        ov["notes"] = notes[-3:]
    if ov:
        ov["why"] = "; ".join(list(dict.fromkeys(why))[-2:])[:200]  # the two latest reasons
    return ov


def record(seller: dict, interaction_id: str, review: dict) -> dict:
    """Store a review for this seller (once per call) and return the seller's active overrides."""
    sid = str(seller["seller_id"])
    if not isinstance(review, dict) or review.get("status") != "reviewed":
        return learned(sid)
    prof = json.loads(seller.get("profile") or "{}")
    with _lock:
        d = _read(REVIEWS)
        s = d.setdefault(sid, {"history": []})
        s.update(company=seller.get("company"), state=(prof.get("gen") or {}).get("seller_state"),
                 rules_use_case=(prof.get("rules") or {}).get("use_case"))
        s["history"] = [r for r in s["history"] if r.get("interaction_id") != interaction_id]
        s["history"].append({**review, "interaction_id": interaction_id, "at": time.strftime("%Y-%m-%d %H:%M")})
        s["overrides"] = _overrides(s["history"])
        _write(REVIEWS, d)
    return s["overrides"]


def learned(sid: str) -> dict:
    return (_read(REVIEWS).get(str(sid)) or {}).get("overrides") or {}


def clear(sid: str):
    with _lock:
        d = _read(REVIEWS)
        if str(sid) in d:
            d[str(sid)]["overrides"] = {}
            d[str(sid)]["cleared_at"] = time.strftime("%Y-%m-%d %H:%M")
            _write(REVIEWS, d)


def history(sid: str) -> list:
    return (_read(REVIEWS).get(str(sid)) or {}).get("history") or []


def reviewed_ids() -> set:
    return {r.get("interaction_id") for s in _read(REVIEWS).values() for r in s.get("history") or []}


# ---- step 3: rules suggested across calls -----------------------------------------------------------------

def _rid(kind: str, when: dict) -> str:
    return kind + "-" + hashlib.sha1(json.dumps([kind, when], sort_keys=True).encode()).hexdigest()[:8]


def insights() -> dict:
    d, status = _read(REVIEWS), _read(RULES)
    rows = [(sid, s, r) for sid, s in d.items() for r in s.get("history") or [] if r.get("status") == "reviewed"]
    sugg = []

    def add(kind, when, overrides, text, evidence, n, hits, sellers):
        if len(sellers) < MIN_SELLERS:
            return
        rid = _rid(kind, when)
        st = status.get(rid, {})
        sugg.append({"id": rid, "kind": kind, "when": when, "overrides": overrides, "calls": n,
                     "text": f"{text} ({len(sellers)} sellers)", "sellers": len(sellers),
                     "matching": hits, "rate": round(hits / n, 2), "evidence": evidence[:8],
                     "status": st.get("status", "suggested"), "low_evidence": n < 5 or len(sellers) < 3})

    # call purpose: where Call 1 keeps getting the purpose wrong
    by_uc = defaultdict(list)
    for sid, s, r in rows:
        by_uc[(r.get("call_1") or {}).get("use_case")].append((sid, r))
    for uc, items in by_uc.items():
        wrong = [(sid, r) for sid, r in items if r.get("agrees") is False and (r.get("hindsight_confidence") or 0) >= 0.6]
        if uc and len(items) >= MIN_CALLS and len(wrong) >= MIN_CALLS and len(wrong) / len(items) >= MIN_RATE:
            better, _ = Counter(r.get("hindsight_use_case") for _, r in wrong).most_common(1)[0]
            add("use_case", {"use_case": uc},
                {"notes": [f"Earlier calls routed to {uc} often turned out to be {better}: check early whether the "
                           f"seller needs {better} instead."]},
                f"Calls routed to {uc} fitted {better} better in {len(wrong)} of {len(items)} reviewed calls. Tell "
                f"Disha to check for {better} early in these calls.",
                [r["interaction_id"] for _, r in wrong], len(items), len(wrong), {sid for sid, _ in wrong})
    # start language by state
    by_state = defaultdict(list)
    for sid, s, r in rows:
        if s.get("state"):
            by_state[s["state"]].append((sid, r))
    for state, pairs in by_state.items():
        items = [r for _, r in pairs]
        miss_p = [(sid, r) for sid, r in pairs if r.get("seller_language") and (r.get("seller_language_confidence") or 0) >= 0.6
                  and r["seller_language"] != (r.get("call_1") or {}).get("start_language")]
        miss = [r for _, r in miss_p]
        if len(items) >= MIN_CALLS and len(miss) >= MIN_CALLS and len(miss) / len(items) >= MIN_RATE:
            lang, _ = Counter(r["seller_language"] for r in miss).most_common(1)[0]
            code = LANG_CODE.get(lang)
            add("language", {"state": state},
                {"start_language": code} if code else {"notes": [f"Sellers in {state} often prefer {lang}: offer "
                                                                 f"{lang} as soon as they use it."]},
                f"Sellers in {state} preferred {lang} over the start language in {len(miss)} of {len(items)} calls. "
                + (f"Start in {lang}." if code else f"Switch to {lang} early."),
                [r["interaction_id"] for r in miss], len(items), len(miss), {sid for sid, _ in miss_p})
    # pace and clarity by call purpose
    for key, delta, label in (("wanted_faster", 0.1, "faster"), ("wanted_slower", -0.1, "slower")):
        for uc, items in by_uc.items():
            hit_p = [(sid, r) for sid, r in items if ((r.get("persona") or {}).get(key) or 0) >= 0.6]
            hit = [r for _, r in hit_p]
            if uc and len(items) >= MIN_CALLS and len(hit) >= MIN_CALLS and len(hit) / len(items) >= MIN_RATE:
                add("pace", {"use_case": uc, "direction": label}, {"pace_delta": delta},
                    f"In {len(hit)} of {len(items)} {uc} calls the seller wanted a {label} call. Make {uc} calls "
                    f"{abs(delta):.1f} {label}.", [r["interaction_id"] for r in hit], len(items), len(hit),
                    {sid for sid, _ in hit_p})
    simpler_p = [(sid, r) for sid, _, r in rows if ((r.get("persona") or {}).get("wanted_simpler") or 0) >= 0.6]
    simpler = [r for _, r in simpler_p]
    if len(rows) >= MIN_CALLS and len(simpler) >= MIN_CALLS and len(simpler) / len(rows) >= MIN_RATE:
        add("simpler", {}, {"simpler": True},
            f"Sellers were confused by Disha's wording in {len(simpler)} of {len(rows)} reviewed calls. Use simpler "
            "words on every call.", [r["interaction_id"] for r in simpler], len(rows), len(simpler),
            {sid for sid, _ in simpler_p})
    bad_p = [(sid, r) for sid, _, r in rows if ((r.get("persona") or {}).get("opening_ok") or 1) < 0.4]
    bad_open = [r for _, r in bad_p]
    if len(rows) >= MIN_CALLS and len(bad_open) >= MIN_CALLS and len(bad_open) / len(rows) >= MIN_RATE:
        add("opening", {}, {"notes": ["Openings often do not land: confirm the business first, then give the reason "
                                      "for the call in one plain line."]},
            f"The opening did not land in {len(bad_open)} of {len(rows)} reviewed calls.",
            [r["interaction_id"] for r in bad_open], len(rows), len(bad_open), {sid for sid, _ in bad_p})

    n = len(rows)
    agree = [r for _, _, r in rows if r.get("agrees") is not None]

    def avg(k):
        v = [(r.get("persona") or {}).get(k) for _, _, r in rows]
        v = [x for x in v if isinstance(x, (int, float))]
        return round(sum(v) / len(v), 2) if v else None

    recent = sorted(rows, key=lambda x: x[2].get("at") or "", reverse=True)[:12]
    return {"summary": {"reviewed_calls": n, "sellers": len({sid for sid, _, _ in rows}),
                        "call1_right": sum(1 for r in agree if r["agrees"]), "call1_judged": len(agree),
                        "goal_met": avg("goal_met"), "persona_fit": avg("persona_fit"),
                        "sellers_with_fixes": sum(1 for s in d.values() if s.get("overrides")),
                        "nudge_judged": sum(1 for _, _, r in rows if (r.get("nudges") or {}).get("budget") is not None),
                        "nudge_over_budget": sum(1 for _, _, r in rows if (r.get("nudges") or {}).get("over_budget"))},
            "suggestions": sorted(sugg, key=lambda x: (x["status"] != "suggested", -x["rate"], -x["calls"])),
            "recent": [{"seller_id": sid, "company": s.get("company"), "interaction_id": r.get("interaction_id"),
                        "at": r.get("at"), "call1": (r.get("call_1") or {}).get("use_case"),
                        "hindsight": r.get("hindsight_use_case"), "agrees": r.get("agrees"),
                        "fixes": [f.get("kind") for f in r.get("fixes") or []], "source": r.get("source", "samvaad")}
                       for sid, s, r in recent]}


def set_status(rid: str, status: str):
    with _lock:
        rules = _read(RULES)
        if status == "reset":
            rules.pop(rid, None)
        else:
            sug = next((s for s in insights()["suggestions"] if s["id"] == rid), None)
            if sug is None and rid not in rules:
                raise KeyError(rid)
            rules[rid] = {**(sug or rules.get(rid, {})), "status": status, "decided_at": time.strftime("%Y-%m-%d %H:%M")}
        _write(RULES, rules)


def approved_for(prof: dict) -> tuple[dict, list]:
    """Overrides from approved rules that match this seller, and the rule texts that matched."""
    gen, rules_uc = prof.get("gen") or {}, (prof.get("rules") or {}).get("use_case")
    ov, used = {}, []
    for r in _read(RULES).values():
        if r.get("status") != "approved":
            continue
        w = r.get("when") or {}
        if ("state" in w and w["state"] != gen.get("seller_state")) or ("use_case" in w and w["use_case"] != rules_uc):
            continue
        for k, v in (r.get("overrides") or {}).items():
            if k == "notes":
                ov["notes"] = list(dict.fromkeys((ov.get("notes") or []) + v))
            elif k == "pace_delta":
                ov[k] = round(max(-0.2, min(0.2, ov.get(k, 0) + v)), 2)
            elif k == "nudge_budget":
                ov[k] = min(int(v), ov.get(k, 2))
            else:
                ov[k] = v
        used.append(r.get("text"))
    if ov:
        ov["why"] = "approved rule: " + " | ".join(t[:80] for t in used)
    return ov, used


def profile_with_learning(prof: dict, use_learned: bool = True) -> tuple[dict, dict]:
    """The profile with an `overrides` block (approved rules, then this seller's own fixes on top)."""
    if not use_learned:
        return prof, {}
    ov, used = approved_for(prof)
    mine = learned(str(prof.get("seller_id")))
    if mine:
        notes = list(dict.fromkeys((ov.get("notes") or []) + (mine.get("notes") or [])))
        pace = round(max(-0.2, min(0.2, ov.get("pace_delta", 0) + mine.get("pace_delta", 0))), 2)
        why = "; ".join(x for x in (mine.get("why"), ov.get("why")) if x)
        nb = [x["nudge_budget"] for x in (ov, mine) if "nudge_budget" in x]
        ov = {**ov, **mine}
        if nb:
            ov["nudge_budget"] = min(nb)  # the lower budget wins
        ov.update({"notes": notes} if notes else {}, why=why[:200])
        if pace:
            ov["pace_delta"] = pace
        else:
            ov.pop("pace_delta", None)
    if not ov:
        return prof, {}
    return {**prof, "overrides": ov}, {"overrides": ov, "rules": used, "own": mine}
