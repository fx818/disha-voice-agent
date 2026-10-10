# A/B test plan: Disha vs the current VANI bot

All past-call evidence is correlational. This plan measures the real lift of Disha's personas, live switching and
feedback loop against the current bot.

## Arms

| Arm | What sellers get | Answers |
|---|---|---|
| **A: baseline** | current VANI bot, one style for everyone | the reference |
| **B: Disha** | persona per seller + Jev call purpose + live switching, **fix loop off** | does the persona and switching lift outcomes? |
| **C: Disha + fix loop** | as B, plus learned fixes on repeat calls | does the feedback loop add on top? |

## Assignment

- **Unit:** the seller (GLID), not the call, so a seller always hears the same arm and repeat calls stay clean
- **How:** `hash(GLID) mod 100`: 0–39 → A, 40–69 → B, 70–99 → C (A larger as the safe default)
- **Who:** sellers that pass the contact gate (OK_TO_CALL or COOL_OFF); SUPPRESS and ROUTE_TO_HUMAN sellers are never
  called in any arm
- **Same everything else:** same call lists, triggers, calling hours and attempt limits in every arm; only the agent
  differs
- **Check balance** before reading results: state, turnover, call purpose and past outcomes per arm

## Metrics

| Type | Metric | Why |
|---|---|---|
| **Primary** | meeting rate per answered call | the business goal |
| Secondary | meetings per seller within 30 days | counts repeat calls and the fix loop (arm C vs B) |
| Secondary | meeting rate per call purpose and per persona | where the lift comes from |
| Secondary | switch confirmation rate (Jev ≥ 0.5) | live matching accuracy (today 90% on test calls, `live_results.md`) |
| **Guardrail** | early hang-up (< 10 s), not interested, do-not-call requests, complaints | must not get worse |
| Guardrail | call length, attempts per meeting | cost |

## Sample size

Two-sided, α = 0.05, power 80%, per arm (answered calls):

| Baseline | Lift to detect | Calls per arm |
|---|---|---|
| 11.5% (all answered calls) | +20% (→ 13.8%) | 3,278 |
| 11.5% | +15% (→ 13.2%) | 5,715 |
| 11.5% | +10% (→ 12.7%) | 12,601 |
| 17.4% (first answered call) | +15% (→ 20.0%) | 3,503 |

- VANI answered about **1,470 calls a day** in the data (269,455 over April–September)
- At a 40/30/30 split, **+15% on all answered calls needs about 2 weeks** (5,715 calls in the smallest arm at ~440 a day)
- Calls from the same seller are correlated: analyse with seller-level bootstrap (or cluster-robust errors), which
  can add a few days

## Running it on Samvaad

- **Arms B and C:** Disha's committed version; arm B passes `seller_profile` without the `overrides` block (fix loop
  off), arm C with it
- **Arm A:** the current VANI bot unchanged
- **Logging:** every call records arm, GLID, call purpose, persona, `disposition`, `switch_log_json`, `call_review`
- **Freeze:** no prompt or code changes during the test; changes wait for the next round

## Decision rules

- **Primary read** after the planned sample: B vs A and C vs A on meeting rate (two-proportion test, seller-level
  bootstrap CI)
- **Ship Disha** if the meeting-rate lift is positive with the CI above 0 and no guardrail gets worse by more than
  1 percentage point
- **Stop early** only for harm: do-not-call requests or complaints in B or C clearly above A (checked daily)
- **Fix loop:** keep it if C beats B on meetings per seller within 30 days

## What this proves for the success metrics

| Success metric | Measured by |
|---|---|
| Outcome lift vs baseline | B and C vs A, meeting rate |
| Visible improvement from the feedback loop | C vs B on repeat calls |
| Accuracy of early-signal matching | switch confirmation rate across real calls |
| Distinctness of segments | meeting rate per persona and purpose inside B and C |
