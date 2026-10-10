# Disha: an adaptive voice agent for IndiaMART seller calls

One Samvaad (Sarvam) voice agent that builds a persona for each seller before she speaks, adapts live during the call,
and improves with every call. PS04 (seller-fit adaptive voice persona) on the PS07 data pack.

- **Agent:** `Disha---Ind-85eb0f30-d809` on Samvaad · **v2 "Final Agent"** (committed) · **v3** draft (latest)
- **Persona:** evidence-based rules (`generator/generate.py`), every choice traced to past calls
- **Decisions:** Jev (TypeSafe) picks the call purpose before the call and reviews the call after it
- **Conversation:** Sarvam on Samvaad: speech recognition, LLM, voice

![Disha one-slide summary](Disha_One_Slide.png)

[`Disha_One_Slide.pdf`](Disha_One_Slide.pdf) · [`Disha_One_Slide.png`](Disha_One_Slide.png)

## Start here

| I want to… | Open |
|---|---|
| See a persona for a real seller, with the reason for every choice | [`samples/personas/PERSONA_SPECS.md`](samples/personas/PERSONA_SPECS.md) |
| See switch logs from live calls | [`samples/switch_logs/SWITCH_LOGS.md`](samples/switch_logs/SWITCH_LOGS.md) |
| See the evidence behind the choices | [`docs/evidence_report.md`](docs/evidence_report.md) |
| Try Disha myself | [Test Disha on Samvaad](#test-disha-on-samvaad) |
| Generate a persona | [Generate a persona](#generate-a-persona) |
| Understand Jev | [Jev: where and why](#jev-where-and-why) |
| Read the code | [`generator/generate.py`](generator/generate.py) · [`samvaad/code_tool/disha_tools_src.py`](samvaad/code_tool/disha_tools_src.py) · [`samvaad/disha_prompt.md`](samvaad/disha_prompt.md) |

## Deliverables

| Deliverable | Where |
|---|---|
| Persona generator on sample seller files | [`generator/generate.py`](generator/generate.py) (also runs inside Disha before every call) |
| Persona spec per sample seller, with reasons | [`samples/personas/`](samples/personas/) (anonymised) |
| Live demo on Sarvam, contrasting sellers, mid-call switch | `Disha Final Demo.mp4` (explainer + Demo 1 + Demo 2) |
| Switch log (signal, change, reason) | [`samples/switch_logs/`](samples/switch_logs/) · `switch_log_json` on every call |
| One-slide presentation | [`Disha_One_Slide.pdf`](Disha_One_Slide.pdf) |

## How a call works

1. **Sort sellers** (offline): contact gate (SUPPRESS / ROUTE_TO_HUMAN / COOL_OFF / OK_TO_CALL), then a call purpose
2. **Seller file:** one `seller_profile` JSON (~3 KB), the only per-call input
3. **OnStart** (before the first word): contact rule → Jev purpose → persona → nudge budget → call plan → seller brief → opening
4. **Conversation:** live switches on 6 signals, each logged by `persona_switch`
5. **OnEnd:** one Jev request verifies each switch and reviews the call
6. **Fix loop:** fixes go into the seller's next call; patterns across 2+ sellers become rules you approve

## How the persona is generated

### Evidence (offline)

- **Data:** 269,455 answered VANI calls (Apr–Sep 2026), evaluator outputs, 139k transcript turns
- **Output:** 60 evidence items, each with n, baseline and strength ([`docs/evidence_report.md`](docs/evidence_report.md)); all correlational
- **Examples:**
  - fast hang-ups repeat: 50% vs 25% hang up early again → short, fast opening
  - turnover ≥ 1.5 Cr books fewer meetings → formal, business-value framing
  - Hindi in 97–100% of calls in every state; Tamil Nadu 72% Tamil → start language by state
- **Per-purpose evidence and call plans:** [`docs/segmentation_and_call_plans.md`](docs/segmentation_and_call_plans.md) · [`docs/conversation_evidence.md`](docs/conversation_evidence.md)

### The generator (rules, no LLM)

| If the seller… | Persona |
|---|---|
| refused before, was frustrated, or asked not to be called | **Calm repair**: empathy first, one soft ask |
| is mid/large (≥ 1.5 Cr) or a Limited Company | **Consultative**: formal, business-value framing |
| hangs up fast or has been called many times | **Brisk**: point first, short turns |
| engaged before or asked for a callback | **Warm & engaged**: upbeat, moves to scheduling |
| none of the above | **Friendly default** |

- Then voice and pace, language (start, English mix, formality, switch-ready), tone, opening, personalisation, objection playbook (with past success rates), escalation rules
- Every choice has a **reason, confidence and evidence id**
- **Informed guesses** (no past call varied them): voice gender, pitch, pace and tone levels → marked low confidence; the voice itself is fixed on the platform, only pace changes

### What OnStart adds on Samvaad

- **Call purpose (Jev):** 4 yes/no signals + catalog score (0–3) → one of 6 purposes (`warm_followup`, `lead_engagement`, `free_to_paid`, `reactivation`, `profile_onboarding`, `discovery`)
  - Jev borderline, slow (> 1.5 s) or failing → rules decide
  - discovery + clear catalog gaps → profile help
- **Purpose adjustments:** pace and style per purpose (reactivation slower, free to paid quicker)
- **Nudge budget** (12,354 past calls, `N01_nudges.csv`): warm follow-up / free to paid 2 · profile / discovery 1 · lead engagement / reactivation 0; lowered by policy, history and the fix loop; max 2
- **Call plan per purpose:** steps, expected seller replies with example lines, success outcome
- **Seller brief:** what they sell, catalog counts, enquiries, last 2 call summaries; used naturally, never read out
- **Product data** (~1,000 sellers: products, without photo, without price): "Jaisa ki main dekh pa rahi hoon, aapke catalogue mein 15 products hain, jinmein se 12 mein photo nahi hai…" (counts only, never which products)
- **Opening:** "Hello sir, main Disha baat kar rahi hoon IndiaMART se. {company} se baat ho rahi hai?" (11 languages)
- **Fix loop changes:** start language, pace, simpler words, fewer nudges; never the contact policy

## Generate a persona

`generate_persona(row)` takes **one flat seller row** (JSON object) and returns the persona spec.

| You have | Run |
|---|---|
| A **GLID** + PS07 data locally | `.venv/bin/python -m generator.generate --seller-id <GLID>` |
| A **seller-row JSON** (no data needed) | `.venv/bin/python -m generator.generate --row generator/example_seller_row.json` |
| Python | `from generator.generate import generate_persona; spec = generate_persona(row)` |

- **Schema:** [`generator/seller_row.schema.json`](generator/seller_row.schema.json) · **example:** [`generator/example_seller_row.json`](generator/example_seller_row.json) (→ brisk, Hindi, pace 1.35: 4 of 7 calls ended within 10 s)
- **All fields optional**, `null` allowed (`{}` → friendly default); extra fields ignored
- **Output:** `seller_id`, `seller_snapshot`, `delivery_profile`, `voice`, `language`, `tone`, `plan` (`opening`, `personalisation`, `objection_playbook`, `escalation_rules`, `target_call_sec`), `guardrails`, `facts`, `evidence_refs`; written to `outputs/personas/<id>.json`
- **On Samvaad** the row sits inside `seller_profile`: `{"v": 1, "seller_id", "gen": <row>, "jev": <state for Jev>, "rules": {"use_case", "contact_policy", "gate_reason"}}` (`tools/export_profiles.py`)
- **Full specs** (generator + OnStart, live Jev, console running): `.venv/bin/python -I tools/export_specs.py [GLID ...]` → `outputs/` (real) + `samples/personas/` (anonymised)

<details>
<summary><b>Input fields (type, values, effect)</b></summary>

| Field(s) | Type and values | Used for |
|---|---|---|
| `fk_glusr_usr_id` | integer (GLID) | the spec's `seller_id` |
| `company` | string | confirming the business by name |
| `seller_state`, `seller_city`, `seller_locality` | strings, e.g. `"Uttar Pradesh"` | region and start language |
| `annual_turnover` | `"0 - 40 L"`, `"40 L - 1.5 Cr"`, `"1.5 - 5 Cr"`, `"5 - 25 Cr"`, `"25 - 100 Cr"`, `"100 - 500 Cr"`, `"> 500 Cr"` | ≥ 1.5 Cr → consultative |
| `business_type` | `"Proprietorship"`, `"Partnership"`, `"Limited Company"`, `"Others"` | Limited Company → consultative |
| `nature_of_business` | e.g. `"Manufacturer"`, `"Trader - Retailer"`, `"Trader - Wholesaler/Distributor"`, `"Service Provider and Others"` | business kind, formality |
| `top_category_1..3`, `top_category_group` | strings | what they sell |
| `gst_registration_year` | integer | how new the business is |
| `eng_pickup_ratio_1yr` | 0–100 | > 50 → engaged |
| `eng_enq_received_90d`, `eng_enq_replies_90d` | counts | 3+ replies → engaged |
| `eng_cqs`, `eng_product_count` | 0–100, count | catalog hooks |
| `bot_answered`, `bot_attempts` | counts | history; repeat attempts → brisk |
| `avg_answered_call_sec` | seconds | < 12 → brisk |
| `calls_meeting_fixed`, `calls_not_interested`, `calls_call_later` | counts | refusals → calm repair; callbacks → warm |
| `ctx_early_calls` | count of calls < 10 s | fast hang-up → brisk |
| `ctx_last_bucket` | trigger code, e.g. `"PIM"`, `"PAM"`, `"OLP"`, `"NUR"`, `"SCHD"` | why IndiaMART called; PAM/NUR/SCHD → warm |
| `past_dispositions_detailed`, `past_objections`, `past_questions_asked` | `"label (count); label (count)"` | objection playbook, opening |
| `asked_if_talking_to_bot`, `showed_frustration`, `already_in_touch_with_executive`, `do_not_call_requested` | 0 or 1 | frustration / do-not-call → calm repair |

</details>

## Jev: where and why

Jev (TypeSafe System One, `api.typesafe.ai/v1/systemone`) returns typed judgements with probabilities. Used twice per
call, from the code tool only.

| Where | When | Gets | Returns | Used for |
|---|---|---|---|---|
| **Call purpose** (`OnStart`) | before the first word | profile, catalog, buyer demand, call history with summaries, objections, questions | 4 yes/no signals with probabilities + catalog score 0–3 | one of 6 purposes; high confidence only if Jev and rules agree; borderline / slow → rules |
| **Switch check + call review** (`OnEnd`) | after hang-up, one request | transcript, switch log, OnStart's choices | per switch: `verified_signal`, applied; call: purpose in hindsight, language, faster / slower / simpler, irritation, goal met | `switch_log_json`, `call_review` → fix loop |

**Why Jev, not only rules**
- Reads free text (summaries, objections, questions) that rules can't
- Probabilities show close calls → rules decide, confidence medium
- Same model checks transcripts after the call
- Fast: 0.33 s median, ~1.6k in / 170 out tokens, 2,100 sellers in 90 s, 0 errors
- Questions are plain text in the code (`NOULS`, `CATALOG_LEVELS`): no retraining

**Validation** ([`docs/jev_validation.md`](docs/jev_validation.md), 2,100-seller September holdout)
- Outcome separation: Jev 0.093 vs rules 0.089 (Cramér's V; tie, slight lean to Jev)
- Agreement with rules: 70% (κ 0.64); where they disagree, Jev separates better (0.113 vs 0.101)
- Sharper groups: Jev profile-help sellers book 20.2% vs 16.0%
- → Jev first, rules as cross-check and fallback

## During the call

- **Switches:** rush, confusion, frustration, interest, language, bot question → `persona_switch` first, then the new style
- **Language:** follows the seller's latest turn, switches back if they do
- **Always:** no price · visits Mon–Sat 11 am–5 pm · a limit explained once, then taken forward ("main apne manager se confirm karke batati hoon…") · no fillers ("Arre") · one closing thank-you in the call's language · dates from the call calendar, never Sunday
- **Not the right person:** employee → ask for the owner · ex-employee → ask once for the owner's number (`contact_referred`) · otherwise apologise and close

## After the call

- **`switch_log_json`:** time, signal, seller words, change, reason, language before/after, Jev score
- **`call_review`:** purpose in hindsight, language, faster/simpler, irritation, nudges used, fixes for next call
- **Outcomes:** `disposition` (meeting_scheduled, rescheduled, callback_requested, declined, business_closed, voicemail_left, no_answer, contact_referred, wrong_number), `meeting_date`, `meeting_time`, `call_summary`, `seller_notes` ("Pending confirmation:" for requests taken forward), `alternate_contact`
- **Fix loop** (`ui/learning.py`): per-seller fixes → next call; patterns in 2+ sellers → rules after approval

## Test Disha on Samvaad

1. **Access:** be a member of the Samvaad workspace (secret, code tool, prompt and defaults are already set up)
2. **Open** "Disha - IndiaMART Seller Persona Agent" → **v2 "Final Agent"** (stable) or the **v3 draft** (latest)
3. **Pick a test mode:**

| Mode | How | Good for |
|---|---|---|
| Chat | the agent's test chat; type as the seller ("haan bataiye") | quick checks, no audio |
| Browser call | test call in the browser with a mic | voice, interruptions, language switches |
| Phone call | test call to a **verified** number | the real phone experience |

4. **Variables are prefilled** with a demo seller (free to paid, brisk, Hindi) → just start the call
5. **Another seller:** replace `seller_profile` with that seller's JSON (from the Disha Console, "Full seller_profile", or `tools/export_profiles.py`); Disha rebuilds everything else at call start
6. **Results:** the call under the agent's interactions/analytics: transcript, `disposition`, `call_summary`, `switch_log_json`, `call_review`

**Try on a call:**
- speak English → language switch
- "abhi busy hoon" → rush, two slots
- "kya bol rahe ho?" → confusion
- "aap bot ho?" → honest answer
- ask for a 7 pm visit twice → taken forward, not refused again

## Samvaad setup

- **Code tool:** edit `disha_tools_src.py` → `tools/build_code_tool.py` → upload `samvaad/code_tool/disha_tools.py` (Tools → Upload Python file)
- **Secret:** `TYPESAFE_API_KEY` in the workspace
- **Prompt:** `samvaad/disha_prompt.md` → draft via `configure_agent`; `{{persona_notes}}` exactly once (the notes are ~7 KB and inserted at every mention)
- **Defaults:** every variable prefilled with the demo seller; console phone calls restore it afterwards (`DISHA_DEFAULT_SELLER`)

## Disha Console (`ui/`)

- `http://localhost:7862`
- Seller list (demo, custom, product-data, any GLID) · OnStart preview with the recorded Jev request and answers
- Browser call (live transcript + switches) · phone call (`DISHA_TEST_PHONE`; transcript and switches after hang-up)
- Call output and review · fix loop per seller · Insights (rule approval) · animated Flow

## Explainer video

- `outputs/video/`: script (`voiceover_script_en.json`, 2:00), `make_voiceover.py` (ElevenLabs or Sarvam Bulbul v3), `mix_final.py` (music ducked under the voice)
- Final cut: explainer (ElevenLabs voice) → "Demo 1" card ("Let's see the demo") → Video 1 → "Demo 2" card → Video 2 (HDR → SDR, portrait on blurred background, −14 LUFS)

## Layout

```
README.md
Disha_One_Slide.pdf / .png   one-slide summary
samples/        persona specs + switch logs (anonymised)   ← start here
docs/           evidence, segmentation and call plans, conversation evidence, Jev validation
generator/      persona generator, schema, example row, fixed script (facts, guardrails)
samvaad/        prompt (+ prompt_history/) and code tool with tests
ui/             Disha Console
tools/          build_code_tool · export_profiles · export_product_sellers · export_specs
data_prep/      data loaders
outputs/        local only; analysis and video scripts are in git
legacy/         v1 Pipecat agent, Samvaad v1 (not used)
```

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # or uv
cp .env.example .env                                     # fill in your keys
.venv/bin/python -I tools/build_code_tool.py             # code tool to upload to Samvaad
.venv/bin/python -I samvaad/code_tool/test_disha_offline.py
.venv/bin/python -I ui/server.py                         # console at http://localhost:7862
```

## Known limits

- Evidence is correlational (no past persona experiment)
- Voice, pace and tone levels are informed guesses
- Disha sometimes adapts without calling `persona_switch`; the post-call summary still records it
- Jev and rules can disagree; the spec says which decided

## Not in this repository

- Seller data (PS07, `product data.csv`, and derived profiles, specs, call logs, transcripts, reviews) and `.env`
- Needed locally for the console, live tests, spec export and analysis; not for the offline tests or the code
