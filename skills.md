# Build journey: Disha

How we built Disha, the seller-fit adaptive voice agent for IndiaMART (PS04), what we tried, what broke, and what we
learned. The README explains how the system works; this file explains how we got there.

## 1. Understanding the data

- Started from the PS07 pack: 149k seller files, 269k answered VANI bot calls (April to September 2026), 278k
  evaluator outputs, 139k transcript turns and executive calls.
- **Decoded the call triggers** (`redis_bucket` codes such as PIM, PAM, OLP, NUR) from call summaries, because the data
  has no "free vs paid seller" column. This is what made a free-to-paid purpose possible at all.
- **Turned the data into 60 evidence items** (each with sample size, baseline and strength) instead of guessing persona
  choices: fast hang-ups need a short opening, larger businesses need a formal tone, sellers answer in the state's
  language, and so on. Every persona choice now points to one of these (`docs/evidence_report.md`).
- Learned early that **everything is correlational** (no past call varied the bot's persona) and that voice gender,
  pitch, pace and tone have **no evidence at all**. We kept those as informed guesses, marked low confidence.

## 2. First agent: local and fast to iterate (v1)

- Built the **persona generator** as evidence-based rules (`generator/generate.py`): one headline persona per seller
  (Calm repair, Consultative, Brisk, Warm & engaged, Friendly default), then voice, language, tone, opening, objection
  playbook and escalation rules, each with a reason and confidence. Rules, not an LLM, so every choice is traceable.
- Ran a local Pipecat voice agent with a browser call and a live signal detector (rush, confusion, frustration,
  interest, language, bot question). Kept in `legacy/`.

## 3. Moving to Sarvam Samvaad

- First Samvaad agent: per-call variables from the persona spec, and a switch-log webhook through a tunnel.
- Hit platform limits: one state only, no model choice, no mid-call variable updates, no language-change event.
- **Code tools changed everything:** a single Python file with `OnStart` (runs before the first word), a mid-call tool
  and `OnEnd`. We bundled the whole generator into it (`tools/build_code_tool.py`), so the persona is built on Samvaad
  itself from one `seller_profile` variable.

## 4. Choosing the call purpose: rules, then Jev

- Built a contact gate (do not call, executive only, cool off, OK) and six call purposes from the data
  (`docs/segmentation_and_call_plans.md`).
- Added **Jev** (TypeSafe) to read what rules cannot: call summaries, objections, questions.
  - Run 1 agreed with the rules only 55% of the time.
  - We rewrote the questions as four yes/no signals plus a catalog score. Run 2 reached 70% agreement and matched the
    rules on outcome separation on a 2,100-seller holdout (`docs/jev_validation.md`).
- **Decision:** use both. Jev first, the rules as cross-check, and the rules decide when Jev is borderline or slow.

## 5. Getting the conversation right

- An external code review raised 24 issues; we fixed them.
- A long prompt rewrite then **made things worse**: a seller marked "do not call" was pitched four times. We went back
  to a proven prompt and made only small, targeted additions. Lesson: small injected changes beat rewrites.
- Added a **nudge budget** per purpose from 12k transcribed calls (a second nudge books half as often as the first)
  and a deterministic **call calendar**, so dates are never invented.

## 6. The Disha Console and the fix loop

- Built a local console (`ui/`): seller list, a preview that runs the real OnStart with live Jev, browser and phone
  calls, transcript, switch timeline, call output, Insights and an animated flow.
- Browser calls had heavy latency on laptop audio; moving the audio into the browser (with echo cancellation) fixed it.
- Samvaad's test-call tool dropped per-call variables, so the console sets the seller on the draft before dialling.
- Added the **fix loop**: after each call, Jev reviews it (right purpose? language? wanted faster or simpler?
  irritated?). Safe fixes go into that seller's next call; patterns across two or more sellers become rules a person
  approves. Learned the hard way that one seller is not a pattern.

## 7. Live testing: what broke and how we fixed it

| What we heard on calls | Fix |
|---|---|
| Disha asked for "the owner" after the person said it was not the company | Separate paths for employee, ex-employee (ask for the owner's number) and wrong number |
| Generic pitch that sounded like a bot | Seller brief (what they sell, catalog counts, last calls) and a natural purpose line from product data ("12 of 15 products have no photo") |
| She named products as missing photos | Only counts are known, never which products; she now says the executive will go through them |
| Reactivation calls sounded nosy and vague | A call plan per purpose: steps, expected seller replies and example lines, from the past-call evidence |
| Disha repeated the opening on every turn | The prompt inserted the 7 KB persona notes 11 times; now exactly once |
| Repeated "no" to evening or Sunday requests sounded rude | Explain a limit once, then take the request forward ("let me confirm with my manager") |
| "Arre" fillers, double thank-yous, Sunday offers | No fillers, one closing thank-you in the call's language, Sunday marked "no visits" in the calendar |
| A language switch handled but not logged | Known gap: the post-call summary records it; a post-call backfill is planned |

## 8. Delivering

- Persona specs for sample sellers with reasons and evidence (`samples/personas/`), switch logs from live calls
  (`samples/switch_logs/`), a demo video (explainer with voice-over plus two live demos), and a one-slide summary.
- Kept seller data and keys out of the repository; samples are anonymised.

## Skills and tools used

- **Data:** Python, pandas and parquet over the PS07 files; evidence statistics (z-tests, Cramér's V, holdout checks).
- **Agent design:** rule-based persona generation, prompt design for a single-state voice agent, live signal
  detection, call plans per purpose.
- **Platforms:** Sarvam Samvaad (code tools, variables, test calls, analytics), the Sarvam SDK for browser calls, Jev
  (TypeSafe) for classification and review, the Samvaad MCP server for configuration and test calls.
- **App:** FastAPI console with server-sent events, browser audio over WebSocket.
- **Media:** ElevenLabs and Sarvam Bulbul text-to-speech, ffmpeg for voice-over sync, ducking, HDR conversion and the
  final cut.
- **Workflow:** built with Claude Code as a pair programmer (analysis, code, reviews, testing, deployment through MCP),
  with offline and live test suites before every upload.

## What we would do next

- Back-fill switches Disha makes without logging, by comparing each seller turn's language after the call.
- Product-level catalog data (which products lack photos or prices), so Disha can name them.
- Run Disha against the current VANI bot on live traffic to measure the real lift in meetings.
