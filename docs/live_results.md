# Live results: switch matching and the feedback loop

Measured on Disha's Samvaad test calls since 2026-10-09 (`tools/analyze_live.py`). Test calls were placed by the team acting as sellers, so these numbers show the system works as designed; they are not seller outcomes.

## 1. Early-signal matching accuracy

- **53 voice calls** (20 s or longer); **25** had at least one logged switch; **30 switches** in total
- After each call, Jev checks every switch against the transcript (`verified_signal`, 0–1). A switch counts as **confirmed** when it is 0.5 or higher.
- **Overall: 27/30 confirmed (90%)**, median score 0.79

| Signal | Switches | Confirmed (≥ 0.5) | Median Jev score |
|---|---|---|---|
| rush | 11 | 11 (100%) | 0.86 |
| language | 10 | 7 (70%) | 0.57 |
| confusion | 4 | 4 (100%) | 0.79 |
| interest | 4 | 4 (100%) | 0.81 |
| frustration | 1 | 1 (100%) | 0.87 |

Low scores mostly come from **language** switches logged without a clear target language, or a switch logged on a turn whose words do not show the signal strongly. Known gap: Disha sometimes adapts without logging the switch at all (caught only by the post-call summary), so this is accuracy of the switches she logs, not recall.

## 2. Feedback loop: the call before a fix vs the next call with the fix

- **13 call pairs** where the next call to the same seller carried fixes learned from the previous call (sellers anonymised)
- Scores are Jev's after-call review of each call (probabilities 0–1); lower is better for the first three, higher is better for the last two

| Measure | Before fix (mean) | After fix (mean) | Change |
|---|---|---|---|
| seller wanted it faster | 0.45 | 0.53 | +0.08 (worse) |
| seller was confused by the wording | 0.63 | 0.63 | -0.00 (better) |
| irritated by pushing | 0.25 | 0.34 | +0.09 (worse) |
| persona fit | 0.61 | 0.51 | -0.10 (worse) |
| goal met | 0.72 | 0.55 | -0.17 (worse) |

**Each pair:**

| Seller | Fixes applied on the next call | Language heard → next start language |
|---|---|---|
| Seller A | start language English -> Hindi; pace 1.1 -> 1.2; simpler wording | Hindi → Hindi |
| Seller B | simpler wording | Hindi → Hindi |
| Seller B | simpler wording | English → Hindi |
| Seller C | pace 1.4 -> 1.6; simpler wording | Hindi → Hindi |
| Seller C | pace 1.4 -> 1.6; simpler wording | English → Hindi |
| Seller D | pace 1.15 -> 1.35; simpler wording | Hindi → Hindi |
| Seller E | pace 1.1 -> 1.0; simpler wording | Hindi → Tamil |
| Seller E | start language Tamil -> Hindi; simpler wording; note: Last time the opening did not land: confirm the business first, then give the reason for the call in one plain line. | Hindi → Hindi |
| Seller E | start language Tamil -> Hindi; simpler wording; note: Last time the opening did not land: confirm the business first, then give the reason for the call in one plain line. | English → Hindi |
| Seller E | start language Tamil -> Hindi; simpler wording; note: Last time the opening did not land: confirm the business first, then give the reason for the call in one plain line. | English → Hindi |
| Seller E | start language Tamil -> Hindi; pace 1.1 -> 1.2; simpler wording; note: Last time the opening did not land: confirm the business first, then give the reason for the call in one plain line. | English → Hindi |
| Seller E | start language Tamil -> Hindi; pace 1.1 -> 1.2; simpler wording; note: Last time the opening did not land: confirm the business first, then give the reason for the call in one plain line. | Hindi → Hindi |
| Seller F | simpler wording | Hindi → Hindi |

**Reading this honestly:**

- **The loop works mechanically:** in all 13 pairs the next call carried the fixes learned from the previous one (start language, pace, simpler wording, notes), with no manual step.
- **The review scores did not improve in these test calls.** The calls were placed by the team, who played a different scenario on each call (busy, other languages, hostile), so a call and the next call to the same seller are not comparable; 13 pairs is also too few. These scores cannot show whether the fixes help.
- **Language:** the review reads an English translation of the transcript, so the seller's language it reports can be wrong; the fix loop therefore takes the start language from the switch log, which records the language actually spoken.
- **How to show the improvement properly:** real seller calls, comparing each seller's next call with and without the learned fixes (see `docs/ab_test_plan.md`, arm C).
