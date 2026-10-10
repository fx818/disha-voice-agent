# Disha / PS04 code and prompt review

Reviewed 9 October 2026. No implementation, prompt, build output, or test files were edited. References are repository-relative and refer to the reviewed versions. Recommendations below are not applied changes.

## Summary

| ID | Severity | Area | File:line | Issue | Suggested fix |
|---|---|---|---|---|---|
| R01 | critical | Startup correctness | `samvaad/code_tool/disha_tools_src.py:332` | Valid JSON with the wrong shape crashes before the first word; generator fallback does not protect downstream access. | Validate the input envelope and install a safe opening before optional work; contain all enrichment failures. |
| R02 | high | Contact policy | `samvaad/code_tool/disha_tools_src.py:398` | SUPPRESS, ROUTE_TO_HUMAN and COOL_OFF are merely logged; a DNC seller still gets a pitch. | Enforce eligibility before dialing; require and verify an upstream contact gate. |
| R03 | high | Prompt / purpose | `samvaad/disha_prompt.md:26` | Fixed visit objective and mandatory scheduling override reactivation, discovery and lead-help goals. | Define a terminal path per use case and let the selected goal control the flow. |
| R04 | high | Truthfulness | `samvaad/code_tool/disha_tools_src.py:94` | Notes/openings assert enquiries, interest and causes without corresponding factual evidence. | Separate observed facts from inferred intent; ask when evidence is absent. |
| R05 | high | Scheduling | `samvaad/disha_prompt.md:108` | Relative-date instruction has no explicit date/timezone input or deterministic resolution; silent Sunday-to-Monday shifts are not prohibited. | Supply call-local time, resolve dates deterministically, and obtain consent for any change. |
| R06 | high | Callback / refusal | `samvaad/disha_prompt.md:75` | Busy/callback and refusal branches contradict guardrails and persona escalation rules. | Use one precedence-ordered policy for callback, DNC, frustration and refusals. |
| R07 | high | Language / opening | `samvaad/code_tool/disha_tools_src.py:265` | Non-Hindi and history openings bypass the use-case hook; unsupported opening languages receive Hindi text. | Compose openings from purpose, history and an actually supported language together. |
| R08 | high | Live language | `samvaad/code_tool/disha_tools_src.py:433` | Invalid/disallowed/missing language targets silently fail while guidance says to follow the new language. | Normalize aliases, report applied/failed status and return an allowed-language fallback. |
| R09 | high | Switch evidence | `samvaad/code_tool/disha_tools_src.py:444` | No explicit reason, turn anchor, before/after delivery, or reconciliation of platform-driven switches. | Add a structured reason and outcome; reconcile observed language changes and transcript turns. |
| R10 | high | Deployment contract | `samvaad/code_tool/disha_tools_src.py:138` | Undeclared variables silently remove the persona or final switch log; tests declare everything themselves. | Validate the deployed declaration/tool contract and retain diagnostic data internally. |
| R11 | high | Startup latency | `samvaad/code_tool/disha_tools_src.py:185` | Four-second per-operation HTTP timeout blocks the first word and exceeds the test's three-second target. | Use an overall startup budget and precomputed fallback, preferably pre-call classification. |
| R12 | medium | History accuracy | `samvaad/code_tool/disha_tools_src.py:241` | Lifetime meeting counts override later refusals; callback timing is invented; contacted sellers become new sellers. | Use dated, confirmed, unresolved history rather than lifetime counts. |
| R13 | medium | Numeric / schema validation | `samvaad/code_tool/disha_tools_src.py:350` | NaN, infinity, invalid probabilities and raw company values are not sanitized. | Enforce finite typed values, valid ranges and strict JSON serialization. |
| R14 | medium | Decision boundaries | `samvaad/code_tool/disha_tools_src.py:206` | Margin search misses joint flips, mishandles floating boundaries and sometimes falsely says rules decided. | Enumerate joint plausible outcomes and record the actual tie-break decision. |
| R15 | medium | Missing / stale data | `samvaad/code_tool/disha_tools_src.py:169`; `tools/export_profiles.py:27` | One missing section masks all other evidence; exported relative ages never advance. | Distinguish unknown from absent, add as-of timestamps and refresh eligibility/history. |
| R16 | medium | Lifecycle robustness | `samvaad/code_tool/disha_tools_src.py:453` | Null internal state or mixed timezone timestamps can crash logging outside the verification catch. | Validate internal state and isolate duration/verification from base-log persistence. |
| R17 | medium | Switch verification | `samvaad/code_tool/disha_tools_src.py:459` | Global signal support is scored, not switch timing or whether delivery actually changed. | Verify the anchored seller turn and following agent response separately; record verification status. |
| R18 | medium | Payload bounds | `samvaad/code_tool/disha_tools_src.py:400` | Profile/spec/log size is unbounded; complete transcript and growing questions are sent on end. | Budget bytes and switch count, cap verification input, and test actual platform limits. |
| R19 | medium | Build safety | `tools/build_code_tool.py:34` | Text slicing/replacements and shared globals are brittle; compilation does not establish bundle safety. | Add AST allowlist/collision checks, exact match assertions and an in-memory reproducibility check. |
| R20 | medium | Facts / honesty | `generator/fixed_script.py:24`; `samvaad/disha_prompt.md:71` | Two fact sources disagree; free-plan wording, executive caller number and follow-up promises are ambiguous/unsupported. | Use one approved fact contract and explicitly distinguish requests from completed actions. |
| R21 | medium | Persona distinctness | `samvaad/code_tool/disha_tools_src.py:378`; `outputs/demo_profiles.json:4` | Demo labels do not match actual personas; notes conflict with applied style; live pace changes are not measured. | Show actual applied personas, align notes and demonstrate distinct audible delivery. |
| R22 | medium | Evidence / languages | `generator/generate.py:590`; `outputs/demo_profiles.json:22` | Evidence IDs lack precise call linkage in runtime; all three demo sellers start in Hindi. | Provide a compact decision-to-evidence index and two-language recordings with switch timing. |
| R23 | medium | Test coverage | `samvaad/code_tool/test_disha_tools.py:65` | Curated live smoke test omits failure shapes, policy conflicts, all-signal coverage and platform behavior. | Add deterministic adversarial tests and a small deployed voice acceptance suite. |
| R24 | low | Conversation flow | `samvaad/code_tool/disha_tools_src.py:256`; `samvaad/disha_prompt.md:92` | Opening asks multiple questions; meeting confirmation repeats; unclear speech has no bounded exit. | Ask one opening question, confirm once, and add IVR/silence/unintelligible-audio handling. |

## Verification performed and limits

- Inspected all eight requested file groups and the installed SDK implementation in `.venv/lib/python3.12/site-packages/sarvam_conv_ai_sdk/tool.py`.
- Rebuilt the upload text **in memory**, calling `generator_bundle()` but not the builder's `main()`. It is byte-for-byte equal to the checked-in `disha_tools.py`: **83,546 bytes**. The current uploaded file imports only stdlib, `httpx`, `pydantic`, and `sarvam_conv_ai_sdk`; its generator is inlined, with no runtime file I/O or `__file__` use. Current top-level generator/tool definitions have **no name collisions**. In particular, `LANG_NAME`, `_num`, and `opening` are not currently overwritten by tool definitions.
- All current `LANG_NAME` values are valid SDK 1.1.1 `SarvamToolLanguageName` values, including `Odia`. There is **no confirmed enum-value mismatch** in the current mapping. This does not establish that every language is enabled on the deployed agent. `SarvamOnStartToolContext` does not expose `allowed_languages`; its setter simply assigns the enum.
- Ran the permitted local test with bytecode writes disabled. An initial buffered run was interrupted when it did not return promptly; an unbuffered retry, bounded by `timeout --signal=INT 45s`, reached the final **SOME CHECKS FAILED** summary. Jev DNS resolution failed in this environment. Each demo `OnStart` used its rules fallback after approximately **4.01–4.03 seconds**, so the Jev-success and under-three-second assertions failed. Final verification scores were absent because Jev was unreachable. The retry printed its summary but then remained in asyncio shutdown; the outer deadline interrupted shutdown and returned exit code 124. Thus the suite did not exit cleanly. This is not evidence that the remote API itself is broken.
- That retry passed bundled/full-row generator parity for all three sellers, fixed-speaker checks, empty/malformed-JSON fallback, rules fallback, the supported English language switch, timed switch recording, turn count, and the three existing `decide()` examples. These passes do not validate actual voice quality, live model tool invocation, or deployed variable persistence.
- Additional read-only, in-memory SDK probes reproduced R01, R08, R13, R14 and R16. No API key was printed. Actual platform variable declarations, payload limits, tool registration names, automatic language events and recordings were not available as a verified deployment snapshot; associated findings explicitly require deployment verification.

## Findings

### R01 — Critical: OnStart is not fail-safe for valid JSON of the wrong shape

**Locations:** `samvaad/code_tool/disha_tools_src.py:330–336,368–387`; uploaded equivalents `samvaad/code_tool/disha_tools.py:942–948,980–999`.

**Reproduced:** `seller_profile` values `null`, `[]`, `1` and `"hello"` all raise `AttributeError` at `prof.get(...)`. `{"rules":[1]}` fails at `rules.get(...)`. `{"gen":[1]}` first triggers the caught generator error, then raises again at the unprotected `gen.get("company")`. The current test only covers syntactically invalid JSON, which follows a different path. A list/dict rules label can also fail dictionary membership in the fallback path.

Because the greeting is not installed until line 405, these exceptions violate the first-word availability requirement. Merely expanding the JSON exception catch will not fix them.

**Fix:** Validate `v`, envelope, nested dictionaries and label types before use. Normalize invalid/missing fields to safe typed defaults. Establish a neutral opening and existing/default language first. Enclose optional classification, generation, formatting and application in a last-resort fallback boundary that returns the context without reusing invalid data. Keep cancellation semantics appropriate to the platform. Test every stage independently, including generator failure followed by fallback formatting.

### R02 — High: the contact gate is not enforced

**Locations:** `samvaad/code_tool/disha_tools_src.py:335–364,398`; `generator/generate.py:183,500`; `tools/export_profiles.py:67,140–143`; `outputs/segmentation/FINAL_SEGMENTATION.md:14–18,153`.

`rules.contact_policy` and its reason do not affect execution; only the policy is copied into `jev_signals`. A supplied SUPPRESS profile still receives an opening. A prior DNC flag becomes `previously_declined` and a repair persona, after which the deployed prompt permits mentioning the visit again. The default demo picker filters OK_TO_CALL, but explicit `--ids` exports do not enforce that condition, and manually supplied profiles bypass selection entirely.

**Fix:** Enforce SUPPRESS/COOL_OFF/ROUTE_TO_HUMAN in the dialer or campaign admission layer before a call exists. Carry a dated eligibility result and test rejection of unsafe profiles. If OnStart cannot cancel safely, document that dependency and prevent launch in the integration layer; do not pretend that a softer pitch satisfies DNC. Record new DNC/human-handoff outcomes through a supported post-call mechanism. No upstream gate is proven by these reviewed files.

### R03 — High: the selected use case cannot reliably control the conversation

**Locations:** `samvaad/disha_prompt.md:7,11,26–31,71–78,102,105`; `samvaad/code_tool/disha_tools_src.py:105–123,127–130`.

The adaptation section names different goals, but Environment and Objective always seek a profile-enrichment visit. Guardrail 105 says the core scheduling flow is always followed and persona notes never override branches. Reactivation asks for information and one ask only, yet a closed/seasonal seller still enters a meeting-oriented interest/refusal flow. Discovery has no explicit qualification-to-purpose transition. Lead-engagement questions about the account risk being redirected as out of scope under line 102. Even generic interest/rush guidance always jumps to a slot, whether that is the appropriate outcome or not.

**Fix:** Specify permissible outcomes per use case: qualification, lead-help/handoff, callback, meeting request, closed-business disposition, and polite exit. Make visit phases conditional on actual seller interest in a visit. Include closed/seasonal/new-business, existing paid customer, existing executive and human-request branches. The background explicitly warns that free_to_paid is inferred intent, not known subscription status; do not claim the seller is on a free plan.

### R04 — High: inferred purpose leaks into asserted seller facts

**Locations:** `samvaad/code_tool/disha_tools_src.py:85,92–95,99,107,116`; `generator/generate.py:364–385,545–547,557–570`; `generator/fixed_script.py:33–36`; `samvaad/disha_prompt.md:76`.

The lead-engagement approach requires naming a specific enquiry, but the input contains aggregate counts/categories rather than a verified individual enquiry. It also directs Disha to give missing profile details as **the cause** of irrelevant leads, without diagnosing that cause. Generator openings and hooks assert current buyer demand from city/category alone, including zero/unknown enquiry sellers. A warm-followup label can produce “called at your request” without an actual callback request; a free-to-paid classification is not proof that the seller viewed paid services. The reactivation hook asserts a long contact gap from inactivity, although those are separate facts. The refusal nudge adds an unqualified claim that many sellers receive noticeably more enquiries.

These are consequential factual claims, not delivery changes. `FS.FACTS` labels the generic enquiry hook a fact even though it is conditional on seller data. Aggregate historical bot utterances do not authorize repeating them as true in every new call.

**Fix:** Represent each speakable fact with source, timestamp and confidence, separate from routing hypotheses. Only assert observed actions. Use questions such as whether enquiries are relevant when no concrete enquiry exists. Phrase profile completeness as a possible contributor, not a diagnosed cause or guaranteed improvement. Do not assert missing photos merely because product count is low.

### R05 — High: relative-date scheduling lacks a reliable clock and consent rule

**Locations:** `samvaad/disha_prompt.md:81–89,92,108`; `samvaad/code_tool/disha_tools_src.py:396–410`.

The prompt says to use the current date but the reviewed tool does not supply a call-local date, weekday or timezone, nor a resolver for relative dates. There is no explicit rule to preserve the seller's requested date when it falls on Sunday. The reported “day after tomorrow” Sunday → Monday error is consistent with this gap, though it was not independently reproduced from a recording here. For a Friday **2026-10-09** call in Asia/Kolkata, day after tomorrow is **Sunday 2026-10-11**, not Monday 12 October. No reviewed fact bans Sunday visits.

**Fix:** Supply an authoritative local call timestamp/timezone and resolve relative dates to ISO dates plus weekdays in code. Store the seller's phrase and proposed normalized value separately. If availability or weekday/date conflicts exist, ask rather than moving the date silently. Confirm a full date/time once; never treat a proposed alternative as consent. Test midnight boundaries, today/tomorrow/day-after, Hindi “kal/parson” ambiguity, Sunday, festivals, month/year changes and explicit weekday/date disagreement. If no calendar integration exists, preserve the agreed request without claiming verified executive availability.

### R06 — High: callback, refusal and de-escalation policies conflict

**Locations:** `samvaad/disha_prompt.md:11,13,15,18,75–77,101,104–105`; `generator/generate.py:440–442,504–530`; `samvaad/code_tool/disha_tools_src.py:127–129`.

Line 75 treats “call later” as an opportunity to offer meeting slots; guardrail 101 requires accepting it immediately and ending. The latter also ends without collecting the requested callback time, undermining the secondary objective. The ordinary decline branch permits two nudges after an initial refusal, while generated escalation says stop after two refusals and repair says stop on the first. Previously-declined handling is inconsistent between line 11 and line 77. Mandatory tool-first logging can also delay immediate exit on DNC/distress if treated as stronger than the exit branch.

**Fix:** One ordered policy: emergency/DNC/hostility exits; explicit callback request gets at most a necessary time clarification and exits; rush without a callback request gets one concise permission-based option; first refusal closes repair calls, and the agreed refusal cap governs others. Logging must not block urgent closure. Avoid requiring a meeting slot from a seller who has only agreed to a later phone call.

### R07 — High: opening selection loses purpose and can mismatch spoken language

**Locations:** `samvaad/code_tool/disha_tools_src.py:231–232,259–269,405–409`; `generator/generate.py:362–385,417–423`.

`choose_opening()` takes the generator line for every non-Hindi start and for AI-disclosure/repair/callback openings. Thus an English/Tamil reactivation call can begin by pitching buyer demand and a meeting, contrary to its goal. AI disclosure need not replace the actual purpose, but currently does. The generator supplies templates only for Hindi, Tamil and English. A persona selecting Gujarati or Marathi receives a Hindi `example_line` with a comment saying it will be delivered in the target language; passing that string to `set_initial_bot_message` does not implement translation. A read-only probe confirmed Hindi text for forced Gujarati/Marathi personas.

**Fix:** Assemble identity/disclosure, supported history and use-case purpose into a single localized opening. Add reviewed templates for enabled languages, or choose an explicit language/text fallback together. Select the start language from deployment-supported languages. Do not rely on a TTS language setting to translate text. Test purpose × language × opening-history combinations, including reactivation and AI disclosure.

### R08 — High: failed language changes look like successful adaptations

**Locations:** `samvaad/code_tool/disha_tools_src.py:425–446`; `samvaad/disha_prompt.md:17–18`.

Only an exact case-insensitive enum **display name** in `allowed_languages` matches. With Hindi/English enabled, requests for `en-IN`, Gujarati, or no target leave the SDK language at Hindi, yet return “Continue in the seller's language” and append a language switch with the supplied change. There is no explicit `applied=false`, failure reason or requested target in that record. The LLM can consequently generate English while the configured output language remains Hindi. The success path for `english` is correct and passed the test.

**Fix:** Map supported names/codes/aliases to SDK enums; require a target for language signals. Persist requested, previous, actual and failure reason. Tell the model explicitly when the request cannot be applied and offer supported alternatives. Do not log a successful switch until the language actually changed. Verify the exposed deployed tool name is `persona_switch`; direct `PersonaSwitch.run()` tests do not establish registration naming.

### R09 — High: the switch log is incomplete for the PS04 requirement

**Locations:** `samvaad/code_tool/disha_tools_src.py:422–447,467`; `samvaad/disha_prompt.md:18–19`.

The required schema includes signal, change **and reason**. The tool accepts words and change but no reason; a keyword and quote do not consistently explain why that delivery change was appropriate. No seller-turn ID, interaction ID, before/after delivery state or applied status is stored. Time begins before Jev/generation, so startup latency is included in switch times; wall-clock adjustments can also distort elapsed values.

The stated platform behavior permits `change_output_language`/automatic language changes without calling this tool. Prompt wording alone cannot guarantee those events enter `switches`. Suppressing repeat signals for two turns can also omit a second genuine language change; combined signals have no structured representation.

**Fix:** Add an explicit short reason, event source, turn/interaction anchor and requested/applied before/after values. Observe or reconcile platform language events; if no event stream exists, compare actual language whenever the custom tool runs and reconcile transcript evidence at end, clearly marking inferred events and unknown timing. Always log actual language transitions regardless of signal debounce. Use a call-relative monotonic time origin where supported. Keep mid-call data in internal variables, honoring the workspace restriction.

### R10 — High: declaration failures silently discard core outputs

**Locations:** `samvaad/code_tool/disha_tools_src.py:138–143,396–403,469`; `samvaad/code_tool/test_disha_tools.py:38–50`.

`_set` appropriately catches the SDK's undeclared-variable `ValueError`, but only prints a warning. If `persona_notes` or `use_case` is missing, the custom first line/pace can be applied while the model follows empty/default prompt inputs. If `switch_log_json` is missing, OnEnd returns successfully with no persisted review artifact. The test's manually declared VARS list makes these conditions impossible in the harness. The actual deployed Disha declaration set is not established by this test.

**Fix:** Maintain one required declaration schema and compare it to the actual deployed configuration before a demo. Verify the custom tool's name/schema, OnStart/OnEnd attachment, allowed languages and prompt variables as one contract. Return structured startup diagnostics and preserve the persona/log in internal state as a recovery aid. Check final post-call persistence separately; internal state by itself is not a judge-accessible artifact. No mid-call agent-variable writes are needed.

### R11 — High: the startup latency budget is internally inconsistent

**Locations:** `samvaad/code_tool/disha_tools_src.py:44,185–190,349`; `samvaad/code_tool/test_disha_tools.py:93`.

The local test demands less than three seconds, while the Jev timeout alone is four seconds, before formatting and context application. In this review, DNS failures caused approximately four seconds of silence before the fallback greeting. HTTPX's operation timeouts also do not represent one overall end-to-end classification deadline: multiple phases or a slowly progressing response can use more total time.

**Fix:** Precompute classification/persona before dialing where possible. Otherwise wrap the entire optional remote classification in an overall deadline below the startup budget, including client setup, and immediately use a validated rules/default result on expiry. Keep a prepared safe greeting. Test connect, read, malformed response and slow-progress failures with deterministic mocks; assert fallback latency separately from healthy-service latency. Apply a separate bounded budget to OnEnd verification so evidence persistence does not depend on network health.

### R12 — Medium: seller_history is neither recent nor reliably interested

**Locations:** `samvaad/code_tool/disha_tools_src.py:235–247`; `generator/generate.py:176,598–602`; `samvaad/disha_prompt.md:11,62`; `outputs/demo_profiles.json:27`.

Any historical meeting count wins over callbacks and refusals. Demo seller 205877878 has two meeting labels, two refusals and a latest call outcome of Not Interested, yet maps to `previously_contacted_interested`. Summaries themselves show that some disposition labels reflect disconnects, so neither old interest nor refusal should be asserted without confirmation. Four previously answered calls with no selected outcomes become `new_seller`. `previous_meeting_attended` is supported by the prompt but never emitted. Parsed `callback_requested` can select a callback opening while `spec_history` sees zero `call_later` and returns new_seller. A callback count does not establish that this call is at the seller's promised time.

**Fix:** Carry latest dated seller-confirmed outcome, attended-vs-booked distinction, unresolved callback/meeting status and requested slot. Resolve conflicts by recency and evidence quality. Use neutral “we spoke earlier” or confirmation questions when necessary; never promise timing from a lifetime count. Retain a separate contacted/no-specific-outcome status.

### R13 — Medium: invalid numerical and text values can create false confidence or nonsense speech

**Locations:** `samvaad/code_tool/disha_tools_src.py:332,350–363,374–375,397–400`; `generator/generate.py:90–104,549,598`; `tools/export_profiles.py:45–52,143`.

Python's default JSON parser accepts NaN/Infinity. A reproduced `{"gen":{"company":NaN}}` call spoke `nan` as the business name: generator `_str` sanitized it, but OnStart reused raw `gen.company`. Lists/dictionaries can similarly appear as names. `_num` removes NaN but accepts infinity, which can fail `int(...)` later and discard the whole persona. Jev scores are float-converted but never required to be finite or within [0,1]/[0,3]; NaN comparisons silently route to defaults, potentially with high confidence when the rules agree. Default `json.dumps` can then emit nonstandard NaN.

The exporter rejects non-finite JSON at serialization, but this can abort an export rather than produce a clear field error; `_clean` also does not generally handle every pandas nullable scalar and `default=str` can hide unsupported types as strings.

**Fix:** Validate at boundaries, normalize names/cities once, reject booleans as numeric signals, require finite bounded scores and use `allow_nan=False` for runtime artifacts. Invalid API answers should trigger low-confidence fallback. Treat malformed individual seller fields as missing without discarding unrelated valid persona evidence.

### R14 — Medium: decide() does not implement its complete stated margin policy

**Locations:** `samvaad/code_tool/disha_tools_src.py:200–220,350–363`; `samvaad/code_tool/test_disha_tools.py:151–156`.

**Reproduced:** with pending_commitment=0.51, ignores_leads=0.51, all other signals absent/low, catalog=2 and rule=profile_onboarding, the result is `(warm_followup, True)`. Both near-threshold signals could move below 0.5, producing profile_onboarding, but the loop only changes one at a time, so that plausible label is omitted. At exactly 0.55, binary floating arithmetic makes `abs(.55-.5) > .05`, producing `borderline=False`. Rounding answers to two decimals before classification changes the effective decision and margin boundaries further.

When borderline is true but the rule is outside `near`, Jev correctly remains selected; nevertheless line 363 says “the rules decided.” This is a false explanation. The existing test explicitly exercises this situation without checking the explanation.

**Fix:** Define inclusive precision and intended joint-vs-single-signal uncertainty explicitly. Enumerate combinations of near-threshold outcomes (only five dimensions), or document a deliberately narrower policy. Use unrounded validated scores for decisions and round only for display. Return separate `borderline`, `rule_used`, raw-label and candidate-label fields. Treat agreement-based “high” as agreement, not a calibrated probability of correctness.

### R15 — Medium: missingness and stale relative ages distort categorization

**Locations:** `samvaad/code_tool/disha_tools_src.py:169–174,342–344`; `tools/export_profiles.py:27,138–143`; `outputs/demo_profiles.json:9,18,27`; background `outputs/segmentation/FINAL_SEGMENTATION.md:183`.

If `catalog` is missing but recent history clearly records a callback, `no_data()` catches KeyError and returns true for the whole seller, skips Jev and ignores the supplied rules label. Partial input is conflated with absence of all evidence. String flags such as `"false"` also have the wrong truthiness without validation.

Export ages are permanently computed against 2026-10-01. Profiles do not include an as-of timestamp that lets runtime advance “days ago”; on 9 October they are already eight days stale, affecting the 60-day commitment window and contact eligibility. Generator history is lifetime aggregate data. The inactivity question demands 90 days without activity, but the exported activity counter covers 30 days (the export delegates to `outputs/segmentation/scripts/j01_jev_validate.py:97`); the other 90-day metrics do not prove 90 days of activity absence.

**Fix:** Evaluate independently validated evidence groups and distinguish unknown from confirmed zero. Preserve usable history when one section is absent. Export dated observations/as-of, refresh or reject stale profiles, and supply a matching activity horizon or explicitly mark 90-day activity unknown. Parse v=1 as a schema version rather than ignoring it. Avoid claiming that agreement of inferred rules and Jev establishes factual certainty.

### R16 — Medium: OnEnd and PersonaSwitch have unprotected state/date failure paths

**Locations:** `samvaad/code_tool/disha_tools_src.py:154–158,429–447,453–469`; SDK `tool.py:188–193`.

`_internal` returns an existing `None` rather than the default. Both tools do `list(None)` if `switches` is null; this was reproduced with a valid SDK context. Invalid `t0` can fail timestamp subtraction. OnEnd's try/catch protects only Jev verification, not transcript access, list conversion, duration computation or serialization. SDK datetime fields accept both aware and naive datetimes; an end time with a timezone and a naive start time reproducibly raises TypeError at subtraction and loses the log. In contrast, missing/null transcript timestamps are normally rejected by SDK construction, so they are not asserted here as ordinary valid-context runtime inputs.

**Fix:** Validate/reset internal state on every lifecycle entry. Build and preserve a minimal log before optional duration/verification. Normalize timestamps consistently or record duration unavailable with an explicit error. One malformed event should not discard the rest. Add duplicate/retried invocation handling so lifecycle retries do not double-log switches or reset useful evidence unexpectedly.

### R17 — Medium: Jev verification cannot demonstrate well-timed, enacted switches

**Locations:** `samvaad/code_tool/disha_tools_src.py:455–468`.

The verifier receives the whole transcript and signal/words/change, but no switch time or turn index, even though local elapsed time exists. It asks whether a signal occurs somewhere, not whether the switch followed it promptly, whether the next agent utterance applied the change, or whether the quoted words match the cited turn. Repeated “busy” turns could validate a delayed or misplaced switch. `en_text` is English transcript text, so it is insufficient to independently establish original spoken language or natural Hinglish. A network failure leaves `verified` missing; partial API results can leave a mix of verified and unverified events without status explanation.

**Fix:** Validate quote/turn correspondence, support, timing and observed application separately using a bounded surrounding-turn window. Preserve original-language transcript/event metadata when the platform exposes it. Record verification status (`verified`, `unavailable`, `invalid_response`) and model/version plus score; a score alone is not ground truth or a causal effectiveness claim. Save the base log before verification. For pace/naturalness, use audio evidence rather than an English transcript.

### R18 — Medium: no explicit size budget exists for runtime artifacts

**Locations:** `samvaad/code_tool/disha_tools_src.py:291–305,397–400,443–469`; `tools/export_profiles.py:143–145`.

Current input profiles are roughly 3.1–3.4 KB. Observed fallback personas produce approximately 4.0–4.2 KB of notes and 9.2–9.4 KB of spec per seller. Persona notes are interpolated repeatedly in the prompt (including lines 7 and 9), adding context overhead. There are no field or profile-size limits, and switch arrays grow without a cap. OnEnd sends the full transcript plus a question per switch in one request, so long/looping calls increase latency, payload size and verification risk. Only seller_words/change are truncated, potentially removing useful evidence.

**Fix:** Set documented byte budgets for individual agent variables and total tool response based on measured platform limits; do not guess a specific limit from the SDK, which does not enforce one locally. Cap/compact notes, events and verification windows while preserving original evidence references. Expose overflow/truncation explicitly. A large or rejected optional artifact must not prevent the greeting or base end log.

### R19 — Medium: the builder is currently correct but lacks safeguards against future edits

**Locations:** `tools/build_code_tool.py:25–28,34–49,54–70`; current bundle `samvaad/code_tool/disha_tools.py:40–652`.

The docstring is removed using the next triple quote, a specific comment ends the retained source, import/lazy-region blocks require exact text, and evidence replacement uses an indentation-sensitive regex. Some edits fail fast, which is good, but duplicate matches and new runtime imports/I/O are not rejected generally. The evidence success check merely finds `return EVIDENCE`; `compile()` proves syntax, not self-containment or semantic equivalence. Generator and tool definitions share globals, so a future tool helper named `_num` or `opening` could silently change generator behavior. Fixed-script constants are a manual subset and can become incomplete if generator dependencies expand.

**Fix:** Add AST checks for imports, filesystem calls, `__file__`, duplicate global definitions and undefined bundle dependencies. Assert replacement counts and required sections exactly. Prefer an explicitly delimited/pure generator module or AST extraction to textual surgery. Check regenerated text against the uploaded artifact without overwriting it; test parity on varied synthetic rows as well as demos. Write build output atomically. The current artifact passed reproducibility/self-containment/collision inspection; this is a robustness risk, not a claim that current names collide.

### R20 — Medium: canonical facts and action promises are inconsistent

**Locations:** `generator/fixed_script.py:24–38,54–55`; `samvaad/disha_prompt.md:2,31,46–54,71,74,87–89,103`; `generator/generate.py:512–514`.

Fixed facts specify about 15–20 minutes, phone meetings and 11 AM–5 PM. The deployed prompt specifies under 30 minutes, emphasizes physical visits and omits that hours restriction. Persona notes include some 11–5/phone advice, but not the full generated guardrails, so enforcement depends on which objections are selected. “Plans can bring more buyer enquiries, free of cost” can sound as if plans/enquiries are free instead of only the meeting. Line 88 says the executive calls **from** the registered number, though the registered number elsewhere is the seller's. A support-manager role should never become a claim to be a human manager.

Rescheduling, DNC noting, complaint routing and executive callbacks are spoken as arranged actions without a corresponding structured outcome writer in these tools. The prompt correctly disclaims an automated calendar invite; that should also constrain other promises. A separate platform summary/export may exist, but is not demonstrated by the reviewed lifecycle code. “No personal information” also needs a narrow permitted scope for ordinary business identity/location confirmation.

**Fix:** Choose and validate one fact/policy source and render both prompt and notes from it. Say explicitly that **only the meeting** is free. Correct the executive-calls-before-arriving wording. Record structured requested outcome/date/time/timezone/location/consent/DNC/handoff, and describe an action as a request until a real integration confirms it. Keep price bans intact; do not copy the contradictory price-range suggestion in the background segmentation playbook into deployed behavior.

### R21 — Medium: applied personas and demo labels diverge; distinctness is not demonstrated

**Locations:** `generator/generate.py:181–191,281–337,584`; `samvaad/code_tool/disha_tools_src.py:284–297,378–387,431–448`; `outputs/demo_profiles.json:4,13,22`.

The seller labeled “brisk, upgrade intent” actually generates **consultative**, warm_formal, applied pace 1.30; Limited Company outranks fast hangup. The “warm, second language” seller generates **brisk**, brief_direct, pace 1.35 and Hindi. Reactivation generates consultative then applies patient_gentle at 1.10, but notes retain the consultative profile label, original tone and original 1.25 pacing sentence before appending the adjustment. These are competing instructions. All five headline profiles collapse to four style enums, and goals/branches often collapse to scheduling.

PersonaSwitch returns natural-language guidance only; it does not change or record a numerical TTS pace. The SDK mid-call context does not expose an OnStart-style TTS override, so actual speed adaptation should not be claimed on the basis of a logged instruction. Keeping the platform speaker fixed is correct and should remain so.

**Fix:** Present one final applied delivery specification and retain the original as provenance, not competing instructions. Align demo labels with actual results or select contrasting sellers based on generated/applied personas. Demonstrate short/direct versus patient/repair versus consultative turn structures in audio. If runtime pace cannot be updated mid-call, implement brevity/pauses through supported delivery controls and clearly distinguish intended from observed pace change.

### R22 — Medium: evidence linkage and two-language proof are incomplete

**Locations:** `generator/generate.py:77–86,204–275,590–618`; `tools/build_code_tool.py:51–53`; `samvaad/code_tool/disha_tools_src.py:300–304,313–319`; `outputs/segmentation/J2_jev_validation_v2.md:3,68–90`.

The generator has useful aggregate evidence IDs and honestly marks tone/voice assumptions. However, the slim embedded evidence drops richer provenance, choices mostly share a flat `evidence_refs` list, and runtime notes omit personalisation/escalation reasons and most exact evidence identifiers. Exported summaries do not retain attempt IDs. Use-case delivery statistics are hard-coded separately from the evidence registry. A judge cannot easily trace “this choice for this seller” to a dated past-call excerpt. Observational meeting-rate associations do not show that a particular voice/pace intervention causes improvement.

All three supplied demos start in Hindi, including the one labeled second language. The harness changes an enum to English but does not generate or listen to audio. Language selection mostly uses state-level rates from Hindi-opening calls, not a seller's own recorded preference; it can reproduce the historical bot's language bias. The published Jev study used `jev-1.13.0`, whereas runtime uses `jev-latest` plus a new margin policy, so published results do not validate this exact runtime. The study itself appropriately says the improvement is not proven.

**Fix:** Produce a compact choice → seller field/past attempt/time/excerpt → aggregate evidence → confidence index; distinguish guesses and population priors. Keep source metadata outside the spoken prompt if size is a concern. Prefer explicit seller language preference over regional defaults. Record at least two complete audible language paths with native review of names, honorifics, Hinglish and switch continuity. Pin or record the served Jev version and evaluate the exact decision policy on an unselected holdout; demo selection for Jev/rules agreement is not an accuracy evaluation.

### R23 — Medium: the current test is a smoke test, not a fail-safe or rubric test

**Locations:** `samvaad/code_tool/test_disha_tools.py:35–50,65–113,116–156`; `tools/export_profiles.py:101–113`.

The three curated profiles are selected to agree with Jev. The test depends on live Jev, `.env`, cached full seller data and a handwritten declaration list. It never invokes the model with the prompt, listens to audio, or tests deployed tool names. Its all-company-openings assertion would reject the generator's legitimate repair opening, which omits the company and leaves identity confirmation to Phase 1. Its unreachable-service case can be an immediate refusal rather than a true timeout. Import-time key loading also prevents straightforward isolated offline tests when `.env` is absent.

**Required missing cases:**

1. Envelope null/scalar/list; malformed nested gen/jev/rules; missing and null fields; unknown schema version; invalid labels; oversized input; NaN/Infinity/boolean/negative counts; generator exception after partial work; missing secret and undeclared outputs.
2. API HTTP errors, malformed/partial JSON, null/string/out-of-range scores, true slow response and total deadline; all six routes, explicit no-data versus partial data, joint margins and exact boundary values.
3. SUPPRESS/COOL_OFF/ROUTE_TO_HUMAN, past DNC, newer refusal after a meeting, attended versus booked, stale callbacks, existing paid seller, business closure and subscription uncertainty.
4. Every signal (confusion/frustration/interest are absent), combined/repeated signals, stronger repeats, original-language quotes, invalid/disallowed/code-form targets, automatic platform language switches and no-op switch status.
5. Null/corrupt internal state, empty transcript, timezone mismatch, missing verification answers, verification failure, duplicate OnEnd, missing log declaration and log-size overflow.
6. Purpose × opening × language assertions and guardrail checks: no invented demand, no price/plan-free implication, callback versus meeting consent, refusal caps, Friday→Sunday, weekday/date conflicts, one confirmation and no repeat pitch after switching.
7. Actual deployed lifecycle persistence and at least two-language audio acceptance: correct speaker retained, audible persona differences, correct switch timing and natural code mixing.

**Fix:** Separate deterministic offline tests with mocked API answers from an optional live smoke test. Add focused deployment/audio acceptance scripts with captured artifacts. Test fallback safety and latency without requiring network success. Keep full-row/bundle parity and speaker-preservation checks, which are valuable.

### R24 — Low: avoidable loops and missing telephony exits

**Locations:** `samvaad/code_tool/disha_tools_src.py:254–256`; `samvaad/disha_prompt.md:37,57,59,82–94,98,109`.

Most use-case openings combine identity confirmation and permission/purpose questions before the seller can answer. Phase 3 confirms the selected date/time, then Phase 4 recaps and asks for confirmation again despite the zero-loop policy. The unclear-response guardrail says the call is never ended; there is no bounded silence/ASR-failure or explicit IVR path, although the background calls for an IVR exit. These affect naturalness and can inflate call length/log size.

**Fix:** Ask a single opening question and make the next prompt step depend on its answer. Confirm the complete meeting request once, with another confirmation only after a correction. Add a brief retry limit for unintelligible speech and separate silence/voicemail/IVR handling, closing without falsely labeling the seller uninterested. Urgent exits need not stack a long warm close.

## PS04 scoring exposure

| Rubric weight | What is present | Main likely deductions / needed proof |
|---|---|---|
| Persona fit — 25% | Seller features, language/formality, pace/tone reasons, personalisation and playbooks. | Incorrect history/facts, competing purpose/style instructions, population language defaults over individual preference; R03–R04, R12, R21. |
| Well-timed mid-call switches — 25% | Five signals plus bot question; internal event storage; language mutation. | Missing automatic events/reasons, unsupported-switch false positives, no turn anchoring or proof of applied timing/pace; R08–R09, R17. |
| Distinctness — 20% | Five delivery profiles and use-case pace adjustments. | Misleading demo labels, repeated scheduling behavior, contradictory applied notes; demonstrate audible contrast with fixed speaker; R03, R21. |
| Natural voice in 2+ languages — 15% | Valid language enum mapping; Hindi/Tamil/English templates; English switch test. | All demos start Hindi; no audio/native review; Hindi text can be assigned to a regional start; R07, R22. |
| Evidence — 15% | Aggregate statistics, evidence IDs and explicit low-confidence guesses. | Weak choice-to-call traceability, non-anchored Jev verification and validation-version drift; R09, R17, R22. |

No numerical score is assigned without deployed calls/recordings. The implementation contains meaningful rubric components, but a logged intention or generated spec is not proof of audible, correctly timed behavior.

## Top 5 fixes before demo

1. **Make OnStart safe and fast:** typed envelope/field validation, safe greeting first, an overall deadline and tested low-confidence fallback. Verify all deployed variable declarations and lifecycle/tool bindings.
2. **Unify policy and purpose:** enforce contact eligibility before dialing; remove fixed-visit overrides; resolve callback/refusal conflicts; eliminate unsupported seller-fact claims and clarify that only the meeting is free.
3. **Make scheduling deterministic:** inject Asia/Kolkata call time, preserve the seller's relative-date meaning, never move Sunday silently, and confirm one explicit date/time request once.
4. **Make switching auditable:** normalize/validate language targets, record reason/turn/before/after/applied status, capture platform language changes, and preserve a base log even if verification fails.
5. **Demonstrate the rubric with real artifacts:** choose correctly labeled contrasting personas, align applied notes/openings, record two natural language paths and all five signals, and attach a concise evidence index with deterministic regression results.
