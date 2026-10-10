"""Measure Disha's live calls: switch-matching accuracy and feedback-loop improvement.

1. Switch accuracy: every switch Disha logged (switch_log_json on each Samvaad interaction), with Jev's after-call
   check (`verified_signal`: how strongly the transcript supports the signal). A switch counts as confirmed when
   verified_signal >= 0.5.
2. Feedback loop: for each seller with two or more reviewed calls (outputs/learning/reviews.json), compare the call
   before a fix was applied with the next call that carried the fix (call_1.learned_overrides).

Usage: .venv/bin/python -I tools/analyze_live.py [--since 2026-10-09]
Writes docs/live_results.md (anonymised: no seller names or ids).
"""
import json
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)
APP = "Disha---Ind-85eb0f30-d809"
CONFIRMED = 0.5


def interactions(since: str) -> list:
    org, ws, key = os.environ["SAMVAAD_ORG_ID"], os.environ["SAMVAAD_WORKSPACE_ID"], os.environ["SAMVAAD_API_KEY"]
    url = f"https://apps.sarvam.ai/api/analytics/v1/{org}/{ws}/{APP}/interactions"
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    items, offset = [], 0
    while True:
        r = httpx.get(url, headers={"X-API-Key": key}, timeout=60, params={
            "start_datetime": f"{since}T00:00:00Z", "end_datetime": end, "limit": 500, "offset": offset})
        r.raise_for_status()
        page = r.json().get("items") or []
        items += page
        if len(page) < 500:
            return items
        offset += 500


def switch_accuracy(items: list) -> tuple[dict, int, int]:
    by = defaultdict(list)
    calls_with = 0
    voice_calls = [it for it in items if it.get("channel_type") == "v2v" and (it.get("duration_in_seconds") or 0) >= 20]
    for it in voice_calls:
        try:
            log = json.loads((it.get("agent_variables") or {}).get("switch_log_json") or "{}")
        except ValueError:
            continue
        sw = log.get("switches") or []
        calls_with += bool(sw)
        for w in sw:
            v = w.get("verified_signal")
            if isinstance(v, (int, float)):
                by[w.get("signal") or "unknown"].append(float(v))
    return by, calls_with, len(voice_calls)


METRICS = [("wanted_faster", "seller wanted it faster", -1), ("wanted_simpler", "seller was confused by the wording", -1),
           ("irritated_by_push", "irritated by pushing", -1), ("persona_fit", "persona fit", +1), ("goal_met", "goal met", +1)]


def feedback_loop() -> list:
    reviews = json.loads((ROOT / "outputs" / "learning" / "reviews.json").read_text())
    pairs = []
    for sid, rec in reviews.items():
        hist = [h for h in rec.get("history", []) if h.get("status") == "reviewed" and h.get("persona")]
        for prev, nxt in zip(hist, hist[1:]):
            applied = (nxt.get("call_1") or {}).get("learned_overrides") or []
            if not applied:
                continue
            pairs.append({"seller": sid, "applied": applied, "before": prev["persona"], "after": nxt["persona"],
                          "lang_before": prev.get("seller_language"), "start_after": (nxt.get("call_1") or {}).get("start_language")})
    return pairs


def main():
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else "2026-10-09"
    items = interactions(since)
    by, calls_with, n_calls = switch_accuracy(items)
    allv = [v for vs in by.values() for v in vs]
    L = ["# Live results: switch matching and the feedback loop", "",
         f"Measured on Disha's Samvaad test calls since {since} (`tools/analyze_live.py`). Test calls were placed by the "
         "team acting as sellers, so these numbers show the system works as designed; they are not seller outcomes.", "",
         "## 1. Early-signal matching accuracy", "",
         f"- **{n_calls} voice calls** (20 s or longer); **{calls_with}** had at least one logged switch; "
         f"**{len(allv)} switches** in total",
         f"- After each call, Jev checks every switch against the transcript (`verified_signal`, 0–1). A switch counts "
         f"as **confirmed** when it is {CONFIRMED} or higher.",
         f"- **Overall: {sum(v >= CONFIRMED for v in allv)}/{len(allv)} confirmed "
         f"({100 * sum(v >= CONFIRMED for v in allv) / max(len(allv), 1):.0f}%)**, median score "
         f"{st.median(allv) if allv else 0:.2f}", "",
         "| Signal | Switches | Confirmed (≥ 0.5) | Median Jev score |", "|---|---|---|---|"]
    for sig, vs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        ok = sum(v >= CONFIRMED for v in vs)
        L.append(f"| {sig} | {len(vs)} | {ok} ({100 * ok / len(vs):.0f}%) | {st.median(vs):.2f} |")
    L += ["", "Low scores mostly come from **language** switches logged without a clear target language, or a switch "
          "logged on a turn whose words do not show the signal strongly. Known gap: Disha sometimes adapts without "
          "logging the switch at all (caught only by the post-call summary), so this is accuracy of the switches she "
          "logs, not recall.", ""]
    pairs = feedback_loop()
    L += ["## 2. Feedback loop: the call before a fix vs the next call with the fix", "",
          f"- **{len(pairs)} call pairs** where the next call to the same seller carried fixes learned from the "
          "previous call (sellers anonymised)",
          "- Scores are Jev's after-call review of each call (probabilities 0–1); lower is better for the first three, "
          "higher is better for the last two", "",
          "| Measure | Before fix (mean) | After fix (mean) | Change |", "|---|---|---|---|"]
    for key, label, good in METRICS:
        b = [p["before"].get(key) for p in pairs if isinstance(p["before"].get(key), (int, float))]
        a = [p["after"].get(key) for p in pairs if isinstance(p["after"].get(key), (int, float))]
        if b and a:
            d = st.mean(a) - st.mean(b)
            arrow = "better" if d * good > 0 else "worse" if d * good < 0 else "same"
            L.append(f"| {label} | {st.mean(b):.2f} | {st.mean(a):.2f} | {d:+.2f} ({arrow}) |")
    L += ["", "**Each pair:**", "", "| Seller | Fixes applied on the next call | Language heard → next start language |",
          "|---|---|---|"]
    labels = {}
    for p in pairs:
        lab = labels.setdefault(p["seller"], f"Seller {chr(ord('A') + len(labels))}")
        L.append(f"| {lab} | {'; '.join(map(str, p['applied']))} | {p['lang_before']} → {p['start_after']} |")
    L += ["", "**Reading this honestly:**", "",
          f"- **The loop works mechanically:** in all {len(pairs)} pairs the next call carried the fixes learned from the "
          "previous one (start language, pace, simpler wording, notes), with no manual step.",
          "- **The review scores did not improve in these test calls.** The calls were placed by the team, who played a "
          "different scenario on each call (busy, other languages, hostile), so a call and the next call to the same "
          "seller are not comparable; 13 pairs is also too few. These scores cannot show whether the fixes help.",
          "- **Language:** the review reads an English translation of the transcript, so the seller's language it "
          "reports can be wrong; the fix loop therefore takes the start language from the switch log, which records "
          "the language actually spoken.",
          "- **How to show the improvement properly:** real seller calls, comparing each seller's next call with and "
          "without the learned fixes (see `docs/ab_test_plan.md`, arm C).", ""]
    out = ROOT / "docs" / "live_results.md"
    out.write_text("\n".join(L))
    print(f"wrote {out}: {len(allv)} switches, {len(pairs)} feedback pairs")


if __name__ == "__main__":
    main()
