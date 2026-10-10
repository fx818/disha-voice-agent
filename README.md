# Disha: an adaptive voice agent for IndiaMART seller calls

Disha is one Samvaad (Sarvam) voice agent whose persona is rebuilt for every seller before she speaks, adapts live
during the call, and learns from each call for the next one. Built for PS04 (seller-fit adaptive voice persona) on the
PS07 data pack.

- **Agent:** `Disha---Ind-85eb0f30-d809` on Samvaad. v1 is committed ("Version1 before Fix loop"); the current work
  is on draft **v2**, which the console uses (`DISHA_APP_VERSION=2`).
- **Decision model:** Jev (TypeSafe, `api.typesafe.ai/v1/systemone`) picks the call purpose before the call and
  reviews the call after it.
- **Conversation:** Sarvam on Samvaad: speech recognition, the conversation LLM and the voice.
- **Persona:** evidence-based rules (`generator/generate.py`), so every choice can be traced to past calls.

## Start here

| I want to… | Open |
|---|---|
| See a persona for a real seller, with the reason for every choice | [`samples/personas/PERSONA_SPECS.md`](samples/personas/PERSONA_SPECS.md) |
| See live switch logs from real calls | [`samples/switch_logs/SWITCH_LOGS.md`](samples/switch_logs/SWITCH_LOGS.md) |
| See the evidence behind the choices | [`docs/evidence_report.md`](docs/evidence_report.md) |
| Read the generator | [`generator/generate.py`](generator/generate.py) |
| Read what runs on Samvaad | [`samvaad/code_tool/disha_tools_src.py`](samvaad/code_tool/disha_tools_src.py), [`samvaad/disha_prompt.md`](samvaad/disha_prompt.md) |

## Submission deliverables

| Deliverable | Where |
|---|---|
| Persona generator running on sample seller files | `generator/generate.py` (also bundled into the Samvaad code tool and run before every call) |
| Persona spec per sample seller, with the reason for each choice | [`samples/personas/`](samples/personas/) (anonymised; the real specs are generated locally to `outputs/`) |
| Live demo on Sarvam, contrasting sellers, mid-call switch | `Disha Final Demo.mp4` (explainer + Demo 1 + Demo 2) |
| Switch log: signal, change, reason for every switch | [`samples/switch_logs/`](samples/switch_logs/); written on every call as `switch_log_json` and shown on the console's switch timeline |
| One-slide presentation | Claude artifact "Disha One-Slide Summary" (export to PDF/PPTX from its Share menu) |

## How a call works

1. **Sort the sellers** (offline, `outputs/segmentation/scripts/`, see [`docs/segmentation_and_call_plans.md`](docs/segmentation_and_call_plans.md)): a contact gate (SUPPRESS: do not call;
   ROUTE_TO_HUMAN: executive only; COOL_OFF: one soft ask; OK_TO_CALL), then a rules-based call purpose.
2. **Prepare the seller file**: one compact `seller_profile` JSON per seller (about 3 KB), the only per-call input.
3. **Start the call** from the Disha Console (browser or phone) or the Samvaad dashboard.
4. **OnStart code tool** (on Samvaad, before the first word): contact rule, call purpose via Jev, persona generator,
   purpose adjustments, nudge budget, call plan, seller brief, learned fixes, opening line.
5. **The conversation**: live persona switches on six signals, each logged through the `persona_switch` tool.
6. **OnEnd code tool**: one Jev request verifies each switch and reviews the call (`call_review`).
7. **Fix loop**: safe fixes go into the seller's next call; patterns across 2+ sellers become rules you approve in
   the console's Insights panel.

## How the persona is generated

### 1. Evidence from past calls (offline, once)

269,455 answered VANI calls (April to September 2026), their evaluator outputs and 139k transcript turns were analysed
into **60 evidence items** (`outputs/evidence.json`, readable in [`docs/evidence_report.md`](docs/evidence_report.md)), each with a sample size,
a baseline and a strength (strong, moderate, weak). All findings are correlational. Examples:

- Sellers who hung up within 10 s before hang up early again 50% of the time vs 25% → short, fast opening.
- Larger businesses (turnover ≥ 1.5 Cr) book fewer meetings → formal, business-value framing.
- Sellers spoke Hindi in 97–100% of transcribed calls in every state with enough calls; Tamil Nadu is the exception
  (72% Tamil) → start language by state.

Per-purpose evidence and call plans: [`docs/segmentation_and_call_plans.md`](docs/segmentation_and_call_plans.md) and [`docs/conversation_evidence.md`](docs/conversation_evidence.md).

### 2. The generator (`generator/generate.py`, no LLM)

The first matching rule picks one headline persona:

| If the seller… | Persona |
|---|---|
| refused before, was frustrated, or asked not to be called | **Calm repair**: empathy first, one soft ask |
| is a mid or large business, or a Limited Company | **Consultative**: formal, business-value framing |
| hangs up fast, or has been called many times | **Brisk**: point in the first sentence, short turns |
| engaged before (picks up, replies to enquiries) or asked for a callback | **Warm & engaged**: upbeat, moves to scheduling |
| none of the above | **Friendly default** |

Then each part is chosen with a reason, a confidence and evidence ids: voice and pace, language (start language,
English-word mix, formality, which languages to switch to), tone (warmth, empathy, energy), opening approach,
personalisation hooks, objection playbook (with the past success rate of each answer) and escalation rules.

**Not evidenced by the data:** voice gender, pitch, pace and tone levels (no past call varied them). These are informed
guesses, marked low confidence, and live switching corrects them. Disha's voice is fixed on the platform; only pace
changes per seller.

### 3. What OnStart adds on Samvaad (`samvaad/code_tool/disha_tools_src.py`)

- **Call purpose from Jev:** one request with four yes/no signals (pending commitment, ignoring leads, upgrade intent,
  inactive business) and a catalog-need score (0 to 3) → one of six purposes: `warm_followup`, `lead_engagement`,
  `free_to_paid`, `reactivation`, `profile_onboarding`, `discovery`. Cross-checked with the rules: if Jev is borderline,
  the rules decide; if Jev is slow (over 1.5 s) or fails, the rules decide. If the fallback would be `discovery` and
  the product data shows clear catalog gaps, the call becomes `profile_onboarding`.
- **Purpose adjustments:** pace and style per purpose (e.g. reactivation slower and softer, free to paid a little faster).
- **Nudge budget:** nudges allowed after a refusal, fixed per purpose from 12,354 past calls
  (`outputs/segmentation/N01_nudges.csv`): warm follow-up and free to paid 2; profile and discovery 1; lead engagement
  and reactivation 0. Lowered by the contact policy, history and the fix loop; never above 2.
- **Call plan per purpose:** the steps Disha follows, the seller replies to expect with example lines, and the
  success outcome (`CALL_PLANS`).
- **Seller brief:** what the seller sells, catalog counts, enquiries and the last two call summaries, with rules on how
  to use them naturally (never read out, never "our records show").
- **Product data** (`product data.csv`, about 1,000 sellers): products, products without a photo, without a price.
  Used in the profile-help purpose line, e.g. "Jaisa ki main dekh pa rahi hoon, aapke catalogue mein 15 products hain,
  jinmein se 12 mein photo nahi hai…". Only the counts are known, never which products.
- **Opening line:** "Hello sir, main Disha baat kar rahi hoon IndiaMART se. {company} se baat ho rahi hai?" (Hindi;
  English, Tamil and 8 more languages have their own).
- **Fixes from the fix loop:** start language, pace, simpler words, fewer nudges, notes. The contact policy is never
  overridden.

### 4. Input to `generate.py`

`generate_persona(row)` takes one flat seller row (a dict). `--seller-id N` builds the row from the PS07 data
(`seller_row()`). Fields read:

| Field(s) | Used for |
|---|---|
| `company` | company name (from past call openings and summaries) |
| `seller_state`, `seller_city`, `seller_locality` | where the seller is; state sets language and region |
| `annual_turnover`, `business_type`, `nature_of_business` | size and kind of business |
| `top_category_1..3`, `top_category_group` | what they sell |
| `gst_registration_year` | how new the business is |
| `eng_pickup_ratio_1yr`, `eng_enq_received_90d`, `eng_enq_replies_90d` | engagement with IndiaMART and buyers |
| `eng_cqs`, `eng_product_count` | catalog quality score and products listed |
| `bot_answered`, `bot_attempts`, `avg_answered_call_sec` | past VANI bot calls |
| `calls_meeting_fixed`, `calls_not_interested`, `calls_call_later` | past call outcomes |
| `ctx_early_calls`, `ctx_last_bucket` | from the call log: hang-ups under 10 s, last call trigger |
| `past_dispositions_detailed`, `past_objections`, `past_questions_asked` | evaluator outputs from past calls |
| `asked_if_talking_to_bot`, `showed_frustration`, `already_in_touch_with_executive`, `do_not_call_requested` | flags from past calls |

Missing fields are allowed: the affected choices fall back to defaults and are marked low confidence.

```bash
.venv/bin/python -m generator.generate --seller-id <seller_id>   # one seller → outputs/personas/<id>.json
.venv/bin/python -I tools/export_specs.py [seller ids]          # full specs (needs the console running)
```

`tools/export_specs.py` writes the complete spec (generator + OnStart, live Jev) for each seller to
`outputs/personas/<id>.json` and one readable `outputs/PERSONA_SPECS.md`. The default sample set (seller ids in `DISHA_SPEC_SELLERS` in `.env`) covers five contrasting sellers: free to paid
(brisk), profile help, warm follow-up in Tamil, reactivation and lead engagement. The main spec is built from the seller data; what the fix loop learned from
test calls is listed separately per seller.

## During the call

- **Live switches:** every seller turn is checked for rush, confusion, frustration, interest, a language change, or a
  bot question. Disha calls `persona_switch` first (signal, the seller's words, the change, the reason; for language,
  the new language), then replies in the new style. The switch is logged with its time.
- **Language:** she replies in the language of the seller's latest turn and switches back if they do.
- **Rules that always hold:** no price is ever quoted; visits Monday to Saturday, 11 am to 5 pm; a limit is explained
  once, and if the seller keeps pressing, the request is taken forward ("main apne manager se confirm karke batati
  hoon…") instead of refused again; no fillers such as "Arre"; one closing thank-you in the call's language ("Thank
  you sir!" in Hindi and English); dates only from the call calendar, never a Sunday visit.
- **Not the right person:** a polite check for an employee first; an employee is asked for the owner; an ex-employee
  is asked once for the owner's current number (`alternate_contact`, outcome `contact_referred`); otherwise a short
  apology and close.

## After the call

- **Switch log** (`switch_log_json`): every switch with time, signal, seller words, change, reason, language before
  and after, and Jev's verification score.
- **Call review** (`call_review`, same Jev request): was the purpose right in hindsight, the seller's language, signs
  of wanting faster or simpler, irritation from pushing, nudges used, and the fixes for the next call.
- **Outcome variables:** `disposition` (meeting_scheduled, rescheduled, callback_requested, declined, business_closed,
  voicemail_left, no_answer, contact_referred, wrong_number), `meeting_date`, `meeting_time`, `call_summary`,
  `seller_notes` (with "Pending confirmation:" for requests taken forward), `alternate_contact`.
- **Fix loop** (`ui/learning.py`): fixes per seller go into the next call's `seller_profile`; patterns from 2+ sellers
  become suggested rules, applied only after approval in Insights.

## Samvaad setup

- Upload `samvaad/code_tool/disha_tools.py` to the Disha draft (Tools → Upload Python file) after every rebuild.
  The workspace secret `TYPESAFE_API_KEY` must exist.
- The prompt source is `samvaad/disha_prompt.md` (deployed to the draft with `configure_agent`). `{{persona_notes}}`
  appears exactly once in it; every other reference says "the persona notes" (the notes are about 7 KB and are
  inserted at every mention).
- **Dashboard defaults:** the draft is prefilled with one demo seller (free to paid, brisk, Hindi), so
  anyone can place a test call or chat without entering anything. Console phone calls borrow the same
  `seller_profile` default and put the demo seller back afterwards (`DISHA_DEFAULT_SELLER` in `.env`).

## Disha Console (`ui/`)

`http://localhost:7862`: seller list (demo, custom, product-data sellers, any seller id), local OnStart preview with
the recorded Jev request and answers, browser call (live transcript and switches) and phone call to the verified test
number (`DISHA_TEST_PHONE`; Samvaad gives phone calls no live feed, so the transcript and switch timeline appear after
hang-up), call output and review, the fix loop per seller, Insights (rule approval) and an animated Flow page.

## Explainer video

`outputs/video/`: `voiceover_script_en.json` (2:00, one line per scene), `make_voiceover.py` (ElevenLabs Sarah with an
Indian English accent, or Sarvam Bulbul v3 voices with `--lang en-IN`), `mix_final.py` (film music ducked under the
voice). Final cut: the explainer with the ElevenLabs voice, a 1.8 s "Demo 1" card with "Let's see the demo", Video 1, a
1 s "Demo 2" card, Video 2 (HDR converted to SDR, portrait video on a blurred background, audio levelled to −14 LUFS).

## Layout

```
README.md
samples/              persona specs and switch logs for sample sellers (anonymised)  ← start here
docs/                 evidence report, segmentation and call plans, conversation evidence, Jev validation
generator/            persona generator (evidence-based rules) and the fixed script (facts, guardrails)
samvaad/              Disha's prompt and the Samvaad code tool (OnStart, persona_switch, OnEnd) with tests
  prompt_history/     earlier prompt versions
ui/                   Disha Console (seller list, preview, browser and phone calls, outputs, Insights, Flow)
tools/                build the code tool, export seller files, pick test sellers, export persona specs
data_prep/            data loaders (PS07 files, product data)
outputs/              local outputs; only the analysis and video scripts are in git
  segmentation/scripts/   data analysis and segmentation scripts
  video/              voice-over build and mix scripts
legacy/               earlier versions (v1 Pipecat agent, Samvaad v1), not used by Disha
```

| Path | What it is |
|---|---|
| `tools/build_code_tool.py` | Builds the single uploadable `samvaad/code_tool/disha_tools.py` |
| `tools/export_profiles.py` | Builds `seller_profile` JSON from the data (plus product data) |
| `tools/export_product_sellers.py` | Picks good test sellers from the product data (`--verify` checks them with live Jev) |
| `tools/export_specs.py` | Exports the full persona specs (real to `outputs/`, anonymised to `samples/personas/`) |

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # or uv
cp .env.example .env   # fill in your keys
.venv/bin/python -I tools/build_code_tool.py            # build the code tool to upload to Samvaad
.venv/bin/python -I samvaad/code_tool/test_disha_offline.py
.venv/bin/python -I ui/server.py                        # console at http://localhost:7862
```

## Known limits

- All evidence is correlational: no past call ran a controlled persona experiment.
- Voice, pace and tone levels are informed guesses (marked low confidence).
- Disha sometimes adapts without calling `persona_switch`, so the timed switch log can miss a switch that the
  post-call summary (`persona_switch_log`) still records.
- Jev and the rules can disagree; the spec says which one decided and why.

## Not in this repository

Seller data (the PS07 datasets, `product data.csv` and everything derived from them: profiles, persona specs, call
logs, transcripts, reviews) and `.env` are kept out on purpose. The console, the live tests, the spec export and the
analysis scripts need that data locally; the offline code-tool tests and the code itself do not.
