"""C1: stream evaluator.parquet one eval_agent at a time -> compact per-call tables in outputs/segmentation/work/.
Memory-safe: pyarrow filters on eval_agent, only agent_output + ids, frames deleted after each agent."""
import gc, json, os
import pandas as pd
import pyarrow.parquet as pq

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # outputs/segmentation
CACHE = os.path.join(os.path.dirname(BASE), "cache")
WORK = os.path.join(BASE, "work")
os.makedirs(WORK, exist_ok=True)
EV = os.path.join(CACHE, "evaluator.parquet")


def load(agent):
    t = pq.read_table(EV, columns=["attempt_id", "agent_output"], filters=[("eval_agent", "==", agent)])
    ids = t["attempt_id"].to_pylist()
    outs = t["agent_output"].to_pylist()
    del t
    gc.collect()
    for a, s in zip(ids, outs):
        try:
            yield a, json.loads(s)
        except Exception:
            continue


def save(rows, name, cols):
    pd.DataFrame(rows, columns=cols).to_parquet(os.path.join(WORK, name + ".parquet"), index=False)
    print(name, len(rows))


# disposition
rows = [(a, d.get("disposition"), d.get("sub_disposition")) for a, d in load("disposition")]
save(rows, "ev_disposition", ["attempt_id", "ev_disp", "ev_subdisp"]); del rows; gc.collect()

# ivr
rows = [(a, d.get("category")) for a, d in load("ivr")]
save(rows, "ev_ivr", ["attempt_id", "ivr_cat"]); del rows; gc.collect()

# se_contact
rows = [(a, d.get("category"), (d.get("seller_exact_quote") or "")[:200]) for a, d in load("se_contact")]
save(rows, "ev_se_contact", ["attempt_id", "se_cat", "se_quote"]); del rows; gc.collect()

# seller_questions (exploded, one row per question x category)
rows = []
called = []
for a, d in load("seller_questions"):
    called.append(a)
    for i, q in enumerate(d.get("questions") or []):
        cats = q.get("category") or []
        if isinstance(cats, str):
            cats = [cats]
        for c in cats:
            rows.append((a, i, c, (q.get("que_dialogue") or "")[:300], (q.get("ans_dialogue") or "")[:400],
                         (q.get("que_context") or "")[:300], (q.get("ans_context") or "")[:300]))
save(rows, "ev_questions", ["attempt_id", "q_idx", "q_cat", "que", "ans", "que_ctx", "ans_ctx"])
save([(a,) for a in called], "ev_questions_calls", ["attempt_id"]); del rows, called; gc.collect()

# topics (exploded)
rows = []
for a, d in load("topics"):
    for t in d.get("discussion_timeline") or []:
        ev = t.get("evidence") or []
        rows.append((a, t.get("sequence_number"), t.get("topic_id") or ("OTHER:" + str(t.get("topic_name"))),
                     (t.get("subtopic") or "")[:150], " | ".join(ev)[:400]))
save(rows, "ev_topics", ["attempt_id", "seq", "topic_id", "subtopic", "evidence"]); del rows; gc.collect()

# objections (exploded)
rows = []
called = []
for a, d in load("objections"):
    called.append((a, bool(d.get("meeting_fixed"))))
    for o in d.get("objection_analysis") or []:
        rows.append((a, o.get("category"), " || ".join(o.get("reasons") or [])[:600],
                     " || ".join(o.get("evidence_quotes") or [])[:600]))
save(rows, "ev_objections", ["attempt_id", "obj_cat", "reasons", "quotes"])
save(called, "ev_objections_calls", ["attempt_id", "obj_meeting_fixed"]); del rows, called; gc.collect()

# latency_repetition (compact)
rows = []
for a, d in load("latency_repetition"):
    lat = d.get("latency") or {}
    rows.append((a, bool(d.get("is_loopy")), lat.get("p50_sec"), lat.get("seller_had_to_repeat_count"),
                 lat.get("overlap_count"), d.get("n_turns")))
save(rows, "ev_latency", ["attempt_id", "is_loopy", "lat_p50", "seller_repeat", "overlaps", "n_turns"]); del rows; gc.collect()
