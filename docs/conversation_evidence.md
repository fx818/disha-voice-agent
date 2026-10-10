# C. Conversation evidence: what sellers say, and what works, per use-case theme

Scope: 269,455 answered VANI bot calls (Apr-Sep 2026). Each call is tagged with seller-side conversation themes, and the work then measures outcomes, objections, FAQs, live cues and openings per theme. This report builds on `outputs/evidence_report.md` (E1-E60) and does not repeat it. Where a number already appears there, it is cited as "(E#)".

Outputs:
- `outputs/segmentation/C_call_themes.parquet`: 269,455 rows. Columns: attempt_id, fk_glusr_usr_id, th_pricing, th_free_payment, th_profile, th_leads, th_not_using, th_callback, th_exec, th_wrong_ivr, th_identity, th_bot_doubt (a subset of identity), pitch_paid, pitch_profile, pitch_enquiry, pitch_payment_attempt, pitch_free_plan (what the bot pitched), n_themes.
- Scripts are in `outputs/segmentation/scripts/` (c1 extract evaluator, c2 theme tagging, c2b regex spot-check, c3 outcomes/openings, c4 objections/cues, c5 transcript questions, c6 duration adjustment). Intermediate tables are in `outputs/segmentation/work/*.csv`.

Strength scale (same as the shared brief): **strong** = n>=1000 and |z|>=3; **moderate** = |z|>=2 or n>=500; **weak** = otherwise. Everything here is correlational. No randomised persona experiment exists.

---

## 0. Method and caveats (read first)

**How themes are tagged.** A call gets a theme when any of three sources fires:
1. Seller-attributed sentences of `lead_call_summary`. Sentences whose subject is the agent ("The agent mentioned that the lead was exploring paid services") are excluded, so the bot's own pitch does not count as the seller raising pricing.
2. Seller turns in `call_turns` (Hinglish and Devanagari regexes; 11.8k calls).
3. Evaluator tags: topics T04/T05/T20-T23/T26/T30/T31, seller_questions categories, objection categories, se_contact, ivr, and non-outcome sub-dispositions (already_met_exec, in_touch_with_exec, business_closed, bad_past_experience, voicemail, wrong_number, alternate_number_or_not_dm).

A precision spot-check (c2b) was run on random matches. Arrowhead-era summaries call the agent "the bot" ("Seller asked the bot ..."), so summary-side bot doubt only counts explicit doubt phrasing ("asked if it was a bot / real person / human"). Without that fix, bot_doubt was inflated about 3x, almost all of it in arrowhead calls. Remaining noise: "callback" includes some "later" mentions inside meeting-agreed calls, and "identity" includes neutral "kaun bol rahe ho?".

| theme | from summary | from turns | from evaluator | any (final) |
|---|---:|---:|---:|---:|
| pricing / package / paid plan | 6,000 | 1,008 | 870 | **6,848** |
| free plan / payment for buyer contacts (BuyLeads) | 1,164 | 346 | 0 | **1,463** |
| profile / catalog / photos | 4,946 | 543 | 183 | **5,400** |
| enquiries / leads quality, not getting leads | 1,178 | 285 | 817 | **1,976** |
| not using IndiaMART / business closed / not a seller | 2,107 | 191 | 672 | **2,476** |
| callback / busy | 44,216 | 2,961 | 2,150 | **46,050** |
| already have / met executive | 7,962 | 924 | 6,149 | **10,912** |
| wrong number / IVR / not decision-maker | 4,390 | 95 | 9,329 | **11,442** |
| identity doubt (who is calling / AI / trust) | 4,398 | 842 | 1,108 | **6,139** |
| of which bot doubt (AI / robot / recorded / human?) | | | | 1,066 |

**Caveat 1: survivorship.** A theme can only be detected if the seller spoke. 71.2% of calls carry no theme. Those are mostly early drops: 34% end in under 10 s, with a median of 15 s. Theme calls are therefore longer than average. Meeting rates are reported against three baselines: all calls (11.5%), engaged calls of 10 s or more (15.5%), and a **duration-matched expectation** (the overall meeting rate in the same duration bins). Duration is partly a result of booking a meeting, so the duration-matched figure over-corrects. Read the true effect as lying between the engaged and duration-matched comparisons.

**Caveat 2: data coverage.** The objections and topics evaluators (5.2k and 6.4k calls) have **no** transcripts. The seller_questions rows with actual questions (7.6k rows) also have no transcripts. Bot responses after objections and answer adequacy are therefore measured two ways: (a) the topics timeline (next topic after an objection topic), and (b) objection and question turns detected directly in the 11.8k transcribed calls, with the next bot turn classified by regex.

**Caveat 3: labels differ by bot version.** In arrowhead and personalis, the `disposition_label` "Not Interested" is almost never used (0.6% and 5.5%, against 48% in main_vani). Not-interested rates can't be compared across versions; only meeting rate and early drop can.

---

## 1. Theme outcomes vs baseline

Baseline (all 269,455 calls): meeting 11.5%, not interested 43.2%, call later 16.2%, early drop (<10 s) 25.5%, median 22 s (E1). Engaged baseline (200,642 calls >=10 s): meeting 15.5%, NI 37.1%.

| theme | n | share | meeting | NI | call later | early drop | median s | meeting (engaged) vs rest-engaged | z | duration-matched expected meeting | first-attempt meeting | strength |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| pricing | 6,848 | 2.5% | **18.3%** | 27.3% | 20.1% | 0.6% | 86 | 18.4% vs 15.3% | +6.9 | 30.4% | 19.4% | strong |
| free_payment | 1,463 | 0.5% | **20.2%** | 27.3% | 22.1% | 0.4% | 79 | 20.2% vs 15.4% | +5.1 | 29.0% | 22.2% | strong |
| profile | 5,400 | 2.0% | **26.8%** | 24.2% | 17.0% | 0.6% | 81 | 26.9% vs 15.1% | +23.6 | 29.8% | 33.0% | strong |
| leads | 1,976 | 0.7% | 18.9% | 33.1% | 16.3% | 0.6% | 98 | 19.0% vs 15.4% | +4.4 | 33.7% | 21.0% | strong |
| not_using | 2,476 | 0.9% | **4.0%** | **56.7%** | 12.6% | 1.3% | 51 | 4.1% vs 15.6% | -15.7 | 22.9% | 4.8% | strong |
| callback | 46,050 | 17.1% | 8.2% | 16.3% | **62.5%** | 1.0% | 54 | 8.3% vs 17.6% | -48.1 | 23.1% | 10.3% | strong |
| exec | 10,912 | 4.0% | 7.8% | 19.6% | 15.8% | 0.3% | 59 | 7.9% vs 15.9% | -22.5 | 26.9% | 8.5% | strong |
| wrong_ivr | 11,442 | 4.2% | **1.1%** | 20.4% | 55.1% | 24.2% | 16 | 1.5% vs 16.1% | -36.9 | 7.2% | 2.0% | strong |
| identity | 6,139 | 2.3% | 8.4% | **52.7%** | 13.7% | 6.1% | 25 | 9.0% vs 15.6% | -13.8 | 14.2% | 10.9% | strong |
| bot_doubt (subset of identity) | 1,066 | 0.4% | 14.9% | 42.9% | 17.4% | 0.4% | 75 | 15.0% vs 15.5% | -0.4 | 30.0% | 18.2% | moderate (no gap) |
| no theme | 191,969 | 71.2% | 12.5% | 51.7% | 4.3% | 33.9% | 15 | | | | | |

How to read it:
- **Profile/catalog talk is the most convertible theme.** Meeting rate is 26.8% (33.0% on first attempt). That is close to the duration-matched expectation (lift 0.90), so these calls are long and they do convert.
- **Pricing, free-plan and lead-quality talk** convert above the engaged baseline (18-20%). Against duration-matched calls they convert only about 0.56-0.70x. The seller is engaged but sceptical, so these calls need objection handling, not more pitch.
- **Not-using, wrong-number/IVR, executive-contact and "who is this?" identity calls** are the clear losers (1-8%), even though they are long. These belong in suppression or re-routing overlays, not a sales persona. **Bot doubt itself is not a loser**: sellers who ask "AI ho?" book meetings at the engaged baseline rate (15.0% vs 15.5%, n=1,066), so the right move is an honest answer, not an exit.
- Callback/busy is the single largest theme (17% of calls). Only 8% convert in-call, while 62.5% end as call-later. Those sellers convert better on the follow-up call (E3).

**Where themes concentrate (lift = theme share in bucket / overall bucket share; >1.5 in bold).**

| theme | PIM | PUA | UA | PAM | OLP | NUR | PANF | ENQR | PNSR/PNSM | PNCHF |
|---|---|---|---|---|---|---|---|---|---|---|
| pricing | **1.55** | 0.58 | 0.52 | **2.64** | 0.85 | 1.11 | 1.38 | 0.45 | 0.8/- | - |
| free_payment | 0.79 | **1.54** | 0.34 | 1.22 | **2.43** | 0.85 | 1.18 | 0.30 | - | - |
| profile | 1.00 | 1.10 | 0.85 | 1.16 | 0.93 | **2.03** | 0.74 | 0.66 | -/0.39 | - |
| leads | 1.07 | 0.92 | 1.06 | 0.76 | 0.94 | 0.63 | 0.73 | 1.35 | 0.45/- | - |
| not_using | 0.69 | 1.08 | **1.53** | 0.42 | 0.66 | 0.64 | - | **3.23** | **2.90/2.96** | - |
| exec | 1.20 | 0.93 | 0.70 | 1.18 | 1.32 | 1.04 | 1.45 | 0.28 | 0.33/0.19 | 10.2% of calls (2.5x) |
| wrong_ivr | 0.92 | 0.93 | 1.23 | 0.74 | 1.05 | 0.93 | 1.20 | **2.29** | **1.73/2.29** | - |
| identity | 0.94 | 1.01 | 1.04 | 1.16 | 0.94 | 0.78 | 0.70 | **2.39** | **2.49/1.71** | - |
| bot_doubt | 0.96 | 1.11 | 0.83 | 1.41 | 0.82 | **1.82** | 1.35 | 1.25 | **3.37**/- | - |

Implications:
- PAM and PIM sellers raise price: PAM is 2.6x more likely to talk pricing (6.7% of PAM calls).
- OLP and PUA sellers raise free plan and BuyLeads.
- ENQR and PNS-trigger calls are disproportionately "not using / wrong number / who is this". For ENQR, the call reason itself seems to be mis-targeted (ENQR meeting rate is 5.3%, E-table).

**Theme co-occurrence (row theme -> share also tagged with column theme).**
- Pricing calls: 31% also callback, 21% also exec, 11.5% also profile.
- Leads calls: 27.5% pricing, 31% callback, 24% exec.
- Free_payment calls: 30% pricing.
- Pricing, free plan and lead quality form one "value-for-money" cluster. A Free->Paid persona must handle all three.

**Bot pitch vs theme (engaged calls, meeting rate).**
- Across all engaged calls, the three main pitches perform alike: paid 22.0%, profile 21.4%, enquiry 20.1%.
- Within the pricing theme, a **profile-improvement pitch** converts better than a paid-package pitch: 22.1% (n=2,746) vs 16.0% (n=2,636).
- Within the profile theme, the opposite holds: paid pitch 32.0% (n=750) vs profile pitch 23.8% (n=2,439). This is moderate evidence, confounded by bucket.
- **The "you tried to buy a BuyLead / payment attempt for buyer contacts" pitch performs worst:** n=459 calls (69% OLP), meeting **4.6%**, NI 61%, against OLP overall at 11.4% (z≈-4.7, moderate).
- The free-plan framing is the best: n=441, meeting 31.1%, NI 26%. Weak to moderate evidence (summary-detected).

---

## 2. Objection library

### 2a. Objection categories (objections evaluator; 5,233 calls, of which 4,126 had at least one objection; 24.0% of all 5,233 evaluated calls booked a meeting)

| objection category | calls | share of evaluated calls | meeting in call | early drop | top reason buckets (share of category) | representative quotes |
|---|---:|---:|---:|---:|---|---|
| Seller Unavailability & Scheduling | 1,325 | 25.3% | 5.7% | 2.5% | busy at shop / customers 37%; travelling / out of town 32%; health / family / festival 8% | "Ma'am abhi time nahi hai"; "Actually main abhi out of station hoon"; "अभी मैं थोडा बाहर हूँ ऑन द रोड हूँ" |
| Callback / Deferred (neutral) | 1,207 | 23.1% | 5.7% | 2.9% | asked for a callback time 74% | "Monday ko call kijiyega"; "वीकेंड पे बात कर लेंगे"; "Subah mein 10 baje kar do" |
| Call Quality / Technical | 1,053 | 20.1% | 2.6% | 24.6% | disconnect / no audio 84%; IVR "person you are trying to reach is not available" | (system messages; no seller quote) |
| No Seller Response / Drop | 819 | 15.7% | 1.8% | 11.2% | seller silent after the bot's time ask; 33% tagged business-closed or not-seller | bot: "Kya aap abhi bhi line par hain?" (repeated) |
| Explicit Disinterest / Refusal | 790 | 15.1% | 2.3% | 0.9% | no need 9%; cost 7%; repeated calls | "नहीं नहीं कोई जरूरत नहीं"; "filhaal toh nahi karna hai mujhe"; "20 बार ऐसा फोन आया, मैंने मना किया" |
| Call Handling / Bot gaps | 624 | 11.9% | 5.7% | 14.6% | bot didn't propose a time, or ignored a constraint | "Puri baat toh kariye na"; "Aap itni jaldi mein kyun baat kar rahe ho bhai?" |
| Existing Engagement / Past Experience | 369 | 7.1% | 4.9% | 0.8% | already met / in touch with exec 30%; bad experience / no leads 14%; cost 7% | "meri already meeting ho chuki hai"; "At present aapki team hamare paas aa chuki hai"; "एक लीड आप लोग १०-१२ आदमी को भेजता है" |
| Wrong Contact / Not Applicable | 204 | 3.9% | 3.0% | 8.8% | not a seller / closed 18%; wrong person 15% | "Wrong number laga diya aapne"; "I am only a purchaser, not seller"; "Bhaiya ko phone karke tab kijiyega" |
| Not Ready / Early-stage | 196 | 3.7% | 8.1% | 0.5% | cost / cash 32%; needs time 24% | "32,000 rupees toh mere paas abhi hand to hand hai nahi"; "फ्री ऑफ कॉस्ट वाली कोई स्कीम हो तो बताइएगा तो जुड़ेंगे" |
| Product / Business Mismatch | 130 | 2.5% | 7.5% | 0% | B2C / retail only, GeM only, different line | "Hum retail hai aur hum wholesale nahi bechte"; "90% jo aapki buy leads aati hai vo toh fake hoti hai" |
| Information / Trust / Privacy | 50 | 1.0% | 3.9% | 2.0% | AI / human doubt 47%; "how do I know you're IndiaMART" | "Aisa lag raha hai AI se baat kar rahe ho. Aap human ho?"; "मेरे को कैसे मालूम पड़ेगा कि आप इंडियामार्ट से बोल रहे हो?" |

The evaluator's meeting rates are within-call (objection present, so meetings are rare). Use them to rank how hard each objection is, not as absolute values. The categories match E26-E33. New here are the reason buckets and the quotes.

### 2b. What the bot did next (topics timeline; 6.4k calls). Strength: moderate.

| after seller objection topic (N, meeting in call) | bot's next topic | n | meeting |
|---|---|---:|---:|
| T21 busy / call later (1,448; 9.3%) | T23 asks a callback date/time | 538 | **2.4%** |
| | T24 asks a meeting date/time | 124 | **33.1%** |
| | T25 confirms a meeting slot | 69 | 46.4% |
| | T14 profile-visibility value | 31 | 25.8% |
| | T08 enquiry-volume hook | 94 | 10.8% |
| | call ended (no bot follow-up) | 216 | 1.4% |
| T19 not interested (778; 2.9%) | call ended | 188 | 0.0% |
| | T08 enquiry hook | 140 | 4.3% |
| | T14 profile value | 34 | 5.9% |
| | T29 close | 129 | 0.0% |
| T22 no need for paid services (126; 14.3%) | T08 enquiry hook | 30 | 10.0% |
| T17 competitor reference (293; 15.8%) | T15 request to meet | 20 | 25.0% |
| | call ended | 58 | 3.4% |
| T13 seller says already active on IndiaMART (627; 33.9%) | T15 request to meet | 415 | 37.1% |
| | T10 schedule a demo | 30 | 51.7% |
| T32 network issues (634; 18.0%) | T07 re-introduce IndiaMART | 140 | 22.1% |
| | call ended | 176 | 1.2% |

Key reading for "busy": **converting "busy" into a concrete meeting slot ask (T24) is followed by meetings 14x more often than asking for a callback time (T23)**, at 33% vs 2.4%. This is partly selection: sellers who say "busy, but tomorrow is fine" get T24. A hard "not interested" is almost never recovered (2.9%). After a network glitch, re-introducing works (22%) where letting the call end does not.

### 2c. Objection -> bot response -> outcome (transcripts; 11.8k calls; first objection turn per call; next bot turn classified)

Response patterns, as classified by regex:
- `free_no_charge_reframe`: "meeting bilkul free hai, koi charge nahi"
- `short_meeting_time_ask`: "kal 15-20 minute / kis din"
- `enquiry_value_hook`: "aapki category mein N buyer enquiry"
- `empathy_ack`: "koi baat nahi / samajh sakti hoon"
- `callback_time_ask`: "rough time bata dijiye, call back kar lungi"
- `exit_close`: "dhanyavaad, din shubh ho"
- `online_or_phone_option`

| seller objection cue (calls; meeting in call) | best response (meeting, n) | typical / worst response (meeting, n) |
|---|---|---|
| busy / later (2,794; 13.3%) | short meeting time ask **32.3%** (133); free reframe 24.2% (153); empathy ack 17.2% (711) | callback time ask 6.2% (418); exit 4.4% (114); bot silent 2.4% (206) |
| not interested (1,244; 7.6%) | free reframe 15.1% (86); enquiry hook 10.4% (463) | empathy only 7.4% (215); exit 3.3% (151); silent 1.6% (125) |
| no need for paid / cost (330; 31.5%) | **free reframe 50.4%** (115) | enquiry hook 19.1% (68); empathy only 13.8% (58) |
| already met exec (531; 12.6%) | enquiry hook 19.8% (111) ("naye enquiries...") | empathy 13.1% (107); exit 2.7% (73) |
| no leads / bad experience (207; 27.5%) | free reframe 35.3% (34); enquiry hook 28.4% (81) | empathy only 19.6% (51) |
| business closed / not using (134; 10.4%) | empathy ack 9.8% (51) | everything <10%; treat as exit |
| wrong person (263; 16.0%) | empathy + "when is the owner free / give a day" 20.3% (59) | exit 8.3% (48) |
| identity / trust (917; 20.6%) | short meeting ask 31.4% (86); enquiry hook 21.0% (205) | identity answer only 17.4% (333) |

Caveats: "short meeting time ask" and "exit_close" are partly reverse-caused. The bot asks for a time when the seller is already warming up, and closes once a meeting is booked. The cleanest contrasts are within the same objection: free-reframe vs empathy-only on cost, and slot-ask vs callback-ask on busy. Both are consistent across themes (table 6). Strength is moderate: n 50-700 per cell, and the direction is replicated by the topic timeline in 2b.

Example exchanges (real, shortened):
- Cost, meeting booked: S: "Meeting rakh lo, par ... meeting charges ya kuch?" B: "Meeting bilkul free of cost hai, koi charge nahi lagega. Somvaar ko kaunsa time sahi rahega?"
- Not interested, meeting booked: S: "Mujhe package buy nahi karna. Bina package ke kuchh bataiye." B: "...executive ekdum free mein aapki profile improve karne ke tareeke bataenge. Ek baar mil kar dekh lijiye."
- Already met exec, meeting booked: S: "Already hamare ek dost hain, vo milke gaye." B: "Achha, hamare expert already mil chuke hain... unse milne ke baad business kaisa chal raha hai? IndiaMART se kuch benefit mehsoos hua?"
- No leads, meeting booked: S: "Humare ko aaj tak koi enquiry nahi aaya." B: "Kayi baar profile mein kuch details missing hoti hai jis se enquiry kam aati hai. Ek chhoti meeting mein executive ... madad karenge."
- Busy, dropped: S: "Abhi thoda sa ek meeting mein busy hoon." B: "Aap kaun sa time theek rahega shaam ko? Main usi samay call kar loongi." The call ended as call-later with no meeting.

---

## 3. Seller questions = FAQs every persona must handle

### 3a. Evaluator categories (seller_questions; 24.7k calls, 7.6k question rows; 22.8% of these calls booked a meeting)

| question category | rows | meeting in call | bot answer deflected to "executive will explain" | notes / examples |
|---|---:|---:|---:|---|
| Meeting Visit (when, where, who, online?) | 1,507 | **55.4%** | 40% | buying signal: "Online ya offline?"; "Kahan par milega woh?" |
| Clarification ("kya bola?") | 1,090 | 39.1% | 26% | |
| Identity Confirmation ("Kaun Payal?") | 1,060 | 18.4% | 15% | answering identity **and** linking it to an executive goes with 28.9% vs 16.5% (n=159/901) |
| Purpose Reason ("kya kaam hai?") | 828 | 23.2% | 40% | deflect + meeting ask 29.9% vs 18.8% |
| Service / Product Info | 738 | 28.7% | 45% | |
| Pricing / Payment | 403 | 23.1% | 31% | only **14.6%** of pricing answers gave a number; "executive will explain" 34.1% vs 18.2% |
| Location Confirmation | 385 | 30.9% | | |
| Callback Contact ("kab call karoge?") | 374 | 15.2% | | |
| Enquiry / Lead ("kitne buyers?", "kaunsi enquiry?") | 309 | 24.3% | 36% | |
| Benefit / Value ("kya fayda?") | 218 | 21.1% | 41% | |
| Frustrated User | 167 | 9.6% | | |
| AI Bot Confirmation | 162 | 18.5% | 7% | **55% of answers deny being an AI** (E35: 61%) |
| Problem Complaint (refund, payment stuck, name change) | 116 | 29.3% | 51% | "...koi refund hoga?" -> "IndiaMART ki policy mein refund nahi hota lekin executive..." |
| Profile Visibility | 110 | 29.1% | 57% | |

### 3b. Answer adequacy: did the seller keep talking after the bot's answer? (transcripts; questions detected by regex; first question of each type per call)

Baseline over all seller turns: the seller keeps talking after the next bot turn 79.4% of the time, and the call ends within 2 turns 24.3% of the time. The transcribed-call meeting rate is 23.4%.

| question type | n | meeting | seller continued after answer | call ended within 2 turns | how the bot answered |
|---|---:|---:|---:|---:|---|
| purpose / why ("kis baare mein?", "kya kaam hai?") | 949 | 28.5% | 88.6% | 15.7% | 36% routed to executive |
| who is calling | 759 | 20.0% | 85.2% | 16.9% | |
| meeting logistics | 393 | **55.0%** | 89.6% | 15.0% | |
| pricing / cost | 351 | 36.5% | 93.4% | 10.0% | 12.8% gave a price, 38.7% said "free" |
| enquiry / leads | 303 | 25.7% | 93.4% | 9.2% | |
| bot identity (AI?) | 207 | 22.2% | 88.9% | 17.9% | 34% denied AI, 34% admitted AI |
| profile / catalog | 132 | 34.8% | 93.2% | 13.6% | |
| benefit / how it works | 127 | 35.4% | 94.5% | 8.7% | |
| free or paid? | 48 | 29.2% | 89.6% | 10.4% | 48% said free |

Questions themselves are engagement signals: every type keeps the seller talking more than the 79% baseline. Differences between answer types:
- **Pricing question answered with "the meeting/visit is free, no charge":** meeting 50.0% vs 27.9% (n=136/215), and calls ended within 2 turns 5.9% vs 12.6%. Moderate.
- **Pricing question answered with an actual price number:** 33.3% vs 36.9% (n=45/306). Quoting a price neither helps nor hurts. Weak.
- **"Are you AI?":** when the bot **admitted** being an AI assistant, meeting was 30.0% vs 18.2% (n=70/137). When it **denied** being an AI, meeting was 14.1% vs 26.5% (n=71/136). Weak to moderate (small n), but it points the same way as the compliance guardrail in E35: honesty does not cost meetings.
- **"Who is calling?" / "AI?" answered without naming IndiaMART:** the seller continued only 67-70% of the time vs 88-96% with it, and calls ended within 2 turns 33-38% vs 12-14% (n=119/640, n=48/159). Moderate. Always name IndiaMART and the reason in the identity answer.
- **Enquiry question answered with a bare "N se zyada buyer enquiry" number:** meeting 10.8% vs 27.8% (n=37/266). Weak. A seller who asks "kaunsi enquiry?" wants specifics (product or city), not a repeated count.

Drop-after-answer examples:
- S: "Charge kya lagta hai isme?" B: "...yeh expert visit bilkul free service hai..." The seller hung up. Free is right, but no next step was offered.
- S: "Uh, packages kya kya hai?" B: "Theek hai, aapke sawal ke liye dhanyavad. Premium pla..." The answer was cut off.

---

## 4. Live signals in seller turns (transcripts; 64.3k seller turns, 11.8k calls)

Baseline: the call ends within 2 turns of a seller turn 24.3% of the time; meeting in transcribed calls is 23.4%. Keywords are from `outputs/live_thresholds.json`. The figures reproduce E55-E59 on this cut.

| cue | seller turns | calls | call ends within 2 turns | meeting in call | strongest keywords (turns; ends within 2; meeting) | what the bot did next that worked (first cue per call) |
|---|---:|---:|---:|---:|---|---|
| rush | 3,871 | 2,794 | 28.3% | 13.3% | "abhi nahi" 1,049; 30.8%; 10.4%. "baad mein" 879; 36.6%; 11.3%. "busy" 763; 31.6%; 13.1%. "bahar hoon" 486; 18.3%; 13.4%. "driv" 57; 45.6%. "abhi time nahi" 150; 2.3% meeting | slot ask 32.3% (133) > free reframe 24.2% > empathy 17.2% > enquiry hook 12.0% > callback ask 6.2% (418) > exit 4.4% > silence 2.4% |
| frustration | 546 | 423 | **40.5%** | 11.6% | "phone mat" 45; **64.4%**; 2.4%. "block" 20; 60%. "baar baar" 83; 51.8%. "call mat" 67; 50.7%. "pareshan" 98; 36.7%; 7.0% | callback ask 17.2% (29) ≈ empathy 14.5% (138) > enquiry hook 12.5% > exit 1.7% (58) |
| confusion | 1,389 | 1,132 | 15.3% | 26.9% | "kaun bol" 345; 18.6%; 15.0%. "kya?" 303; 7.9%; 40.1%. "samajh nahi" 63; 23.8%. "awaaz nahi" 19; 36.8%; 6.2% | slot ask 40.0% (100); online option 38.2%; empathy 30.3%. Identity answer only: 11.3% (177) |
| interest | 2,930 | 1,940 | 18.2% | **40.8%** | "address" 233; 81.6% meeting. "bhej do / dijiye" 319; 74.9%. "aa jaiye / aa jao" 80; ~70%. "theek hai ... kal / baje" 327; 59.2%. "kitne baje" 70; 58.8%. "charge" 190; 45.6%. "zaroor" 357; 12.4% (polite brush-off, not interest) | slot ask **69.5%** (259); free reframe 46.3%; empathy 38.3%; enquiry hook 23.8%; **price answer 17.2% (29)** |
| bot question | 462 | 298 | 18.2% | 24.5% | "ai" 247; "machine" 70; "insaan" 47 (7.4% meeting) | identity answer 22.2% (117); enquiry hook 31.4% (35) |
| language switch (any non-Hindi seller turn) | 1,131 | 764 | **42.2%** | 28.0% | English turns 591 (61% end within 2 turns); Tamil (romanised) 292 (18.5%; meeting 41.7%); Gujarati 112; Marathi 65 (36.9%); Bangla 54 | (no live switch exists; see below) |
| explicit language request | 27 | 23 | 14.8% | 30.4% | "Can you speak in English?"; "Hindi nahi aata madam, English ya Tamil"; "Bangla mein bolo na" | |

Notes:
- "zaroor" in the current interest list is a false positive: 12.4% meeting and 35.9% end within 2 turns. **Recommend removing it from `live_thresholds.json` interest keywords.** Strong buying cues are "address", "bhej do", "aa jaiye", "kitne baje" and "theek hai ... kal/baje". These should trigger an immediate slot and address confirmation, not more pitch.
- An **English-speaking seller is the riskiest language state**: 61% of English turns are followed by the call ending within 2 turns. The bot keeps answering in Hindi. This is moderate evidence (n=591 turns, 484 calls) and the strongest case for a live language switch: English, and Tamil or Bangla where the seller requests it. Tamil-speaking sellers who stay on the line convert well (41.7%).
- In frustration, an exit_close drops meetings to 1.7%, while empathy or a callback offer keeps about 15%. Frustration keywords "phone mat / call mat / block" should end the call politely and set do-not-call (64% of these calls end anyway).

---

## 5. Openings that work

### 5a. Bot versions (lead_bot_version)

| version | period | n | meeting | early drop | median s | first-attempt meeting (n) |
|---|---|---:|---:|---:|---:|---|
| main_vani | Apr-Sep | 208,605 | 11.6% | 26.3% | 22 | 16.7% (99,910) |
| arrowhead | Apr-Sep | 30,676 | 10.7% | 24.4% | 21 | 15.0% (13,985) |
| last_met_d | 16 Jun-14 Jul | 23,046 | 11.1% | 20.1% | 25 | 13.4% (12,070) |
| main | 29 Jun-7 Aug | 5,573 | 14.0% | 24.5% | 23 | 19.0% (2,723) |
| last_met_a | 10-15 Jul | 723 | 11.9% | 23.7% | 22 | 16.7% (305) |
| base_vani | 30 Sep | 289 | 18.3% | 11.8% | 37 | 20.7% (227) |
| personalis | 30 Sep | 452 | 14.2% | **35.2%** | 18 | 17.9% (229) |
| summary_va | 30 Sep | 91 | 3.3% | 42.9% | 13 | - |

Same-week comparison, arrowhead vs main_vani, Sep weeks 36-40, meeting rate:
- Arrowhead: 10.5% / 11.1% / 9.9% / 12.0% / 13.6%.
- main_vani: 11.9% / 10.6% / 8.8% / 11.5% / 11.0%.
- Arrowhead is ahead in 4 of 5 weeks by 0.5-2.6 pp (behind in week 36: 10.5% vs 11.9%), with lower early drop in 4 of 5 weeks (24.6-30.6% vs 27.7-31.9%). Moderate (about 2k vs 13k calls per week).
- The matched window of 28-30 Sep (E24/E25) shows base_vani 18.3% and personalis 14.2% vs main_vani 12.3%. Personalis has the **highest early drop (35%)**.

Within themes (engaged calls; arrowhead vs main_vani, meeting):
- Profile: 34.0% vs 23.5% (n=1,561 / 3,236)
- Pricing: 23.4% vs 17.4% (1,129 / 4,886)
- Leads: 26.7% vs 17.3% (273 / 1,360)
- Callback: 12.7% vs 8.0% (3,817 / 35,523)
- Exec: 13.4% vs 7.4% (744 / 8,615)
- Not using: 10.8% vs 3.5% (250 / 1,949)
- Identity: 16.6% vs 7.7% (435 / 4,467)
- Bot doubt: 28.8% vs 12.7% (118 / 818)

Arrowhead calls are longer once engaged, with a median of 76-160 s vs 50-96 s. Arrowhead's share of bot-doubt calls (11.2%) equals its share of all calls (11.4%), so sellers do not suspect it more. Strength is moderate (versions ran on different traffic mixes, and NI labels differ).

### 5b. First line and pitch hook (transcribed calls; transcripts are biased to longer calls, so early drop ≈0)

| greeting | n | meeting | no reply after pitch | NI | main user |
|---|---:|---:|---:|---:|---|
| "Hello ji, kya meri baat **X** se ho rahi hai?" | 2,095 | 29.5% | 11.1% | 6.7%* | arrowhead (1,744) |
| "Hello, kya aap **X** se bol rahe hain?" | 9,338 | 20.9% | 10.8% | 37.0% | main_vani, last_met_d |
| "Hello" only | 257 | 16.3% | 17.1% | 30.7% | |

*NI is not comparable across versions. Within main_vani, "kya meri baat X se" scores 27.5% (n=295) vs "kya aap X se bol rahe" 21.6% (n=8,396). Weak to moderate.

| pitch hook (first IndiaMART line) | first-attempt n | meeting | no reply after pitch | repeat-attempt n | meeting |
|---|---:|---:|---:|---:|---:|
| "haal hi mein ... (recent activity)" | 263 | **41.8%** | 11.4% | 135 | 26.7% |
| "aapne paid package kharidne ki koshish ki" (payment attempt) | 439 | 31.9% | 13.4% | 118 | 24.6% |
| "aap IndiaMART pe buy leads check kar rahe the" | 1,741 | 30.1% | 10.8% | 548 | 29.4% |
| "aap paid services explore kar rahe the" | 1,774 | 27.3% | 11.3% | 567 | 28.6% |
| "aapki category mein [city] mein N buyer enquiry" | 1,302 | 26.3% | 8.6% | 513 | 24.0% |
| "aap se pehle baat hui thi ..." (prior conversation) | - | - | - | 1,709 | **13.9%** (NI 38%) |
| other / generic | 734 | 23.2% | 23.8% | 892 | 15.8% |
| "aapne demo book kiya" | 40 | 37.5% | | | |
| "aapne account banaya" | 25 | 60.0% | | | |

Reading:
- **A specific, recent, seller-action hook beats a generic or city-enquiry hook.** Recent activity, payment attempt, BuyLeads check and demo booked all score 30-42% vs 23-26% for generic or city hooks. This is strong in direction and moderate in size: hooks are tied to trigger buckets, so part of the gap is the bucket.
- On repeat calls, **"aap se pehle baat hui thi"** (the current callback opener) scores only 13.9% vs 24-29% for re-using the action hook. A repeat-call persona should lead with the *seller's action / value*, not "we spoke earlier". This qualifies E3: callback sellers convert better than other repeat sellers, but not because of this sentence. Moderate (n=1,709).
- Generic hooks have twice the no-reply-after-pitch rate (23.8% vs 9-13%).

Pitch length (first IndiaMART line, transcribed calls):

| words | n | meeting | no reply after pitch |
|---|---:|---:|---:|
| ≤25 | 1,875 | 13.8% | 30.8% |
| 26-40 | 2,470 | 17.6% | 13.9% |
| 41-55 | 5,616 | 29.3% | 6.4% |
| >55 | 1,112 | 38.0% | 7.9% |

This mirrors E52. Short lines are mostly generic or repeat-call lines, so length is confounded with content. What the data does support: put a concrete reason and the meeting ask in the first pitch line.

---

## 6. Per-theme call plans (evidence-backed)

For each theme: outcome, top objections (share of that theme's objection-evaluated calls), recommended response pattern with evidence, FAQs (share of the theme's transcribed calls), live cues, and opening.

### 6.1 Pricing / package / paid plan -> Free->Paid persona (PAM, PIM, PANF)

- **Outcome:** n=6,848. Meeting 18.3% vs 11.5% overall (engaged 18.4% vs 15.3%, z=+6.9, strong). NI 27.3%, median 86 s. Duration-matched it converts at 0.6x, so these sellers engage but resist.
- **Objections:** Explicit refusal 51%, callback / deferred 38%, unavailability 35%, existing engagement 31%, not ready (cash) 30%. Quotes: "इतना पैसा भी नहीं है न एक साथ देने को... ₹36000 हुआ"; "Paid ke liye ... thoda sa turnover maintain ho mera to paid bhi le lenge"; "IndiaMART's charges too high".

| seller says | recommended response | evidence |
|---|---|---|
| "paid nahi lena / paise nahi / kitna charge?" | Separate meeting from purchase: "Meeting bilkul free hai, koi charge nahi; executive aapko options aur monthly plan samjha denge." Then a slot ask. | Cost cue + free reframe 53% (n=106) vs empathy-only 13% (n=53) in this theme; 50% vs 28% on transcript pricing questions. Moderate |
| "monthly kitna?" / "packages kya hain?" | One honest range in a single sentence (e.g. "monthly option bhi hai"), then "exact plan executive batayenge, kal kis time?" Don't stop after the number. | Price answers alone: 17% meeting when interest was shown (n=29); executive-explains + ask 34% vs 18%. Weak to moderate |
| busy | Slot ask ("kal 15-20 min, subah ya shaam?"), not a callback-time ask | Slot ask 47% (n=15) vs exit 0% in theme; global 32% vs 6%. Moderate |
| "already met exec" | Ask how it went and offer a follow-up on new enquiries | 25% vs exit 0%. Weak |

- **FAQs:** pricing/cost 30.5% of the theme's transcribed calls (36.6% meeting); purpose 18.6%; who's calling 11.2%; enquiry/leads 9.8%; meeting logistics 5.5% (63.5% meeting).
- **Live cues:** interest 47% of calls (34.4% meeting); rush 33%; frustration 7.4%. The "charge"/"kitna" keywords mean engaged, not won (45.6% / 29.9% meeting). Go to the free-meeting reframe plus a slot ask.
- **Opening:** pitch type matters inside this theme. A profile/visibility pitch got 22.1% vs a paid-package pitch 16.0% (n≈2.7k each, moderate). Lead with the seller's action ("aapne paid package dekha / kharidne ki koshish ki", 31.9% first attempt), but frame the meeting as profile and enquiry help, not a sale. Arrowhead-style greeting: 23.4% vs 17.4%.

### 6.2 Free plan / payment for buyer contacts (BuyLeads) -> Free->Paid persona (OLP, PUA)

- **Outcome:** n=1,463. Meeting 20.2% (engaged 20.2% vs 15.4%, z=+5.1, strong). NI 27.3%. Small but warm.
- **Objections** (n=35 objection calls, weak): refusal 69%, not ready 54%, callback 37%. Quotes: "फ्री ऑफ कॉस्ट वाली कोई स्कीम हो तो बताइएगा"; "Seller ... insisted on no payment, wants free listing removed"; "startup ... requested free services for at least a month".
- **Response:** on busy, a free reframe got 31% (n=16) vs a callback-time ask 6% (n=17). On "not interested", the enquiry hook got 21% (n=29). Weak.
- **Opening caution:**
  - **Don't open with "aapne BuyLead kharidne ki koshish ki / payment attempt for buyer contacts"** in the summary wording: 4.6% meeting, NI 61%, n=459, vs OLP 11.4% (moderate).
  - The transcript hook "aap buy leads check kar rahe the" gets 30.1% (first attempt, n=1,741), and a free-plan framing gets 31.1% (n=441).
  - Mention the activity neutrally ("aap buy leads dekh rahe the"), not the failed payment.
- **FAQs:** purpose 22%; pricing 19.6%; enquiry/leads 12.9%; free-or-paid 8.2%. "Free mein IndiaMART deta hai kya?" is answered "registration aur basic listing free hai" and the call continues.
- **Live cues:** frustration 9.9% (second only to the leads theme); non-Hindi turns 14.4%, the highest of all themes.

### 6.3 Profile / catalog / photos -> Profile-enrichment persona (NUR, PUA)

- **Outcome:** n=5,400. **Meeting 26.8%** (first attempt 33.0%; engaged z=+23.6, strong). NI 24.2%. Converts close to duration-matched expectation (0.90).
- **Objections:** product/business mismatch 55% ("Hum retail hai aur hum wholesale nahi bechte"; "mera koi flour mill ka nahi hai", meaning wrong products listed); refusal 49%; unavailability 32%; existing engagement 29%.
- **Response:**
  - Mismatch is an *opening*, not a dead end: fix the wrong-products issue in the meeting. Mismatch calls book at 7.5%, vs 2.3% for refusals.
  - "Not interested": enquiry hook 26% (n=57) vs exit 7%.
  - Cost: free reframe 52% (n=31) vs empathy 18%.
  - Busy: slot ask 36% vs callback ask 10% (n=29).
  - Identity doubt: enquiry hook 43% (n=23).
- **FAQs:** purpose 21.5%; profile/catalog 16% ("Iska photo kaise add kare?"; "Humari kaunsi profile?", 34.8% meeting); pricing 12%; enquiry 11.5%; meeting logistics 6.8% (67.9%).
- **Live cues:** interest 42% (41.3% meeting); rush 29%.
- **Opening:** pitch_paid 32.0% (n=750) vs pitch_profile 23.8% (n=2,439) inside this theme. A seller who talks catalog responds to "improve visibility -> more enquiries -> executive will set it up for free". Arrowhead 34.0% vs main_vani 23.5% (moderate). Recent-activity hook 39.6% (n=53).

### 6.4 Enquiries / lead quality / not getting leads -> Lead non-consumption or re-engagement persona

- **Outcome:** n=1,976. Meeting 18.9% (z=+4.4, strong). NI 33.1%. Duration-matched 0.56x, the most "talkative but sceptical" theme. Median 98 s.
- **Objections:** refusal 44%, existing engagement / past experience 43%, callback 33%, unavailability 33%, mismatch 20%. Quotes: "एक लीड आप लोग १०-१२ आदमी को भेजता है"; "90% jo aapki buy leads aati hai vo toh fake hoti hai"; "Hum judkar dekh chuke hain... humein koi benefit nahi mila".
- **Response:**
  - No-leads complaint: free reframe 35% (n=34) / enquiry hook 28% (n=81) vs empathy-only 19% (n=47).
  - The pattern that books meetings is acknowledge, give a **cause** ("profile mein details missing hone se enquiry kam aati hai"), then offer a free fix by the executive.
  - "Not interested": free reframe 27% vs 0% for generic. Weak to moderate.
- **FAQs:** purpose 22%; enquiry/leads 17% ("Kaunsi enquiry aayi hai?"); pricing 17%. A bare enquiry count as the answer gets 10.8% vs 27.8%: give product or city specifics.
- **Live cues:** interest keywords in 57% of calls but only 24.9% meeting (they ask about leads to complain). Frustration 14.4%, the highest of all themes.
- **Opening:** paid-explore hook 28.1% vs city-enquiry hook 14.3% vs prior-conversation 16.9%. For these sellers, "N buyer enquiries in your category" backfires (14%, n=63, weak): it contradicts what they experience. Arrowhead 26.7% vs main_vani 17.3%.

### 6.5 Not using IndiaMART / business closed / not a seller -> Dormant persona with a fast-exit rule

- **Outcome:** n=2,476. **Meeting 4.0%, NI 56.7%** (z=-15.7, strong). Duration-matched 0.18x. Over-represented in ENQR (3.2x), PNSR/PNSM (2.9x) and UA (1.5x).
- **Objections:** wrong contact / not applicable 62%, refusal 40%, mismatch 17%. Quotes: "Ab yeh kaam chhod diya"; "Now I want to retire"; "I am only a purchaser, not seller"; "mill hi band hai".
- **Response:**
  - Nothing works well: empathy 9.8% (n=51), enquiry hook 0% (n=14).
  - Use one empathetic check: "Kya aap abhi kisi aur vyavsay mein hain?" If temporarily closed (season, illness), ask when it reopens and schedule a callback. If permanently closed, stop, and offer profile deactivation or update.
  - Arrowhead did better (10.8% vs 3.5%) by not exiting immediately. Weak.
- **FAQs:** purpose 19.5% (5.5% meeting).
- **Live cues:** low interest (25%).

### 6.6 Callback / busy -> Warm follow-up persona, plus a busy-handling module in every persona

- **Outcome:** n=46,050 (17% of calls). Meeting 8.2%, call-later 62.5%. In-call conversion is low, but these sellers convert better on follow-up (E3: 6.6% vs 5.6%).
- **Objections:** unavailability 72%, callback 66% (busy at shop 37%, travelling 32%, health/festival 8%).
- **Response (strongest evidence in the report):**

| busy variant | do | don't | evidence |
|---|---|---|---|
| "abhi busy / baad mein / bahar hoon" | One line of empathy, then a **specific slot ask for the meeting** ("kal subah 11 ya shaam 4, 15-20 min?") | Ask "rough time bata dijiye, main call back kar loongi" | In theme: slot ask 30% (n=125); across all calls, callback ask 6.2% (n=418); topics: T24 33% vs T23 2.4% (n=538). Strong in direction, moderate in size |
| "driving / meeting mein hoon" | Offer a 2-minute call-back the same day, and keep it | Pitch. "driv" ends within 2 turns 46% | Moderate |
| any rush | Never go silent: silence after a rush turn gives 2.4% meeting (n=206) | | Moderate |

- **FAQs:** purpose 9.8%; who's calling 7.2%; meeting logistics 3.2% (35.9%).
- **Live cues:** rush 61% of calls.
- **Opening on the follow-up call:**
  - "Aap se pehle baat hui thi ..." got 6.8% in this theme (n=819) vs the BuyLeads or paid-explore action hook at 14-15% (n≈920 each).
  - Open with the action or value, then mention "aapne kaha tha is time call karun".
  - Recent-activity hook 28.4% (n=141).
  - Arrowhead 12.7% vs main_vani 8.0% (strong, n=3.8k/35.5k).

### 6.7 Already have / met an executive -> Route to the existing executive (overlay); sales persona only with a "new enquiries" angle

- **Outcome:** n=10,912. Meeting 7.8% (z=-22.5, strong). Concentrated in PNCHF (10% of those calls), PANF and OLP.
- **Objections:** existing engagement 60%, refusal 34%, unavailability 34%, callback 32%. Quotes: "meri already meeting ho chuki hai"; "At present aapki team hamare paas aa chuki hai"; "अरे नहीं आज आने वाला है इंडिया मार्ट से आदमी".
- **Response:**
  - Enquiry hook ("unse milne ke baad naye enquiries aaye? profile update hua?") got 19.8% (n=111) vs empathy 13.1% vs exit 2.7% (n=73).
  - In-theme, a free reframe gets 19%, while exit gets 3%.
  - Never repeat the full pitch: in the "kal 15-20 minute" example the seller had just said the executive was mid-conversation.
  - Recommended: acknowledge, ask about the outcome, and offer a follow-up visit by the *same* executive. Hand off if a meeting is already scheduled.
- **FAQs:** purpose 12.9% (10% meeting, the lowest); who's calling 7.9%; pricing 6.6%.
- **Live cues:** rush 28%, frustration 7.8%.
- **Opening:** prior-conversation hook 9.8% vs paid-explore 19.0% vs BuyLeads 17.8%. Arrowhead 13.4% vs main_vani 7.4%.

### 6.8 Wrong number / IVR / not the decision-maker -> Suppression / route overlay

- **Outcome:** n=11,442. **Meeting 1.1%**, early drop 24.2%, median 16 s (strong). The 55% call-later rate comes from "owner not here".
- **Objections:** wrong contact 61%, unavailability 25%, no response 18%. Quotes: "Wrong number laga diya aapne"; "वो तो हमको नहीं पता हस्बैंड को ही पता होगा"; "Bhaiya ko phone karke tab kijiyega"; IVR "The person you are trying to reach is not available".
- **Response:**
  - Not the decision-maker (family member or staff): ask when the owner is available, or for the owner's number, then end. Empathy + "when is he free" got 20.3% (n=59) across all calls.
  - True wrong number: apologise once and end with a do-not-call flag. In-theme exit gets 0% and nothing else beats 7%.
  - Detect IVR or voicemail from phrases ("person you are trying to reach", "please hold", "kripya") and hang up without pitching.

### 6.9 Identity doubt / bot doubt -> Guardrail module for every persona

- **Outcome:** identity n=6,139, meeting 8.4%, **NI 52.7%**, early drop 6.1% (z=-13.8, strong). Over-represented in ENQR, PNSR and PNSM (lift 1.7-2.5): sellers who don't recognise why IndiaMART is calling.
- **Bot doubt** (n=1,066): meeting 14.9%, the same as the engaged baseline (z=-0.4). A seller asking "AI ho?" is still in play.
- **Objections:** unavailability 39%, callback 35%, refusal 25%, call quality 20%, bot gaps 19%, trust/privacy 6.6% (bot_doubt: 20%). Quotes: "Aisa lag raha hai AI se baat kar rahe ho. Aap human ho?"; "मेरे को कैसे मालूम पड़ेगा कि आप इंडियामार्ट से बोल रहे हो?"; "Ye computer call hai ya khud bol rahe ho?"; "Automatic message kyu jaana chahiye".
- **Response:**
  - Answer honestly in one sentence that names IndiaMART and the reason: "Main IndiaMART ki AI assistant hoon, aapki category ki buyer enquiries ke liye call kiya hai". Then a slot ask.
  - Admitting AI: 30% vs 18% (weak). Denying: 14% vs 27% (weak). Answers that don't name IndiaMART end within 2 turns 33-38% vs 12-14% (moderate).
  - Busy inside identity calls: slot ask 43% (n=14) vs bot silence 0% (n=19).
  - Cost inside identity calls: free reframe 41% (n=22).
- **FAQs:** who's calling 66.7% of identity transcribed calls (19.8% meeting); AI? 23% (71% of bot-doubt calls); purpose 12%; pricing 8% (37.5%).
- **Live cues:** confusion 45.7% of identity calls. "kaun bol" is the top confusion keyword (345 turns, 15% meeting). Bot-doubt calls have the highest frustration rate after leads (12.3%) and 16.4% non-Hindi turns.
- **Opening:**
  - Arrowhead-style "Hello ji, kya meri baat X se ho rahi hai?" does better than "kya aap X se bol rahe hain" (identity theme 16.6% vs 7.7%, n=435 / 4,467, moderate).
  - Action hooks beat generic hooks here too: BuyLeads 27.4%, paid-explore 26.0%, generic 17.5%, prior-conversation 10.3%.
  - Avoid a bare "Hello" opener (16.3%, 17% no reply).

---

## 7. Evidence summary (decision-relevant, ranked)

| # | finding | n | rate vs baseline | strength |
|---|---|---:|---|---|
| C1 | Profile/catalog talk is the most convertible theme | 5,400 | 26.8% vs 11.5% (engaged 26.9 vs 15.1) | strong |
| C2 | Not-using, wrong-number/IVR, exec-contact and "who is this" themes rarely convert; route or suppress. Bot doubt alone converts at baseline | 2.5k-11.4k each; bot doubt 1,066 | 1.1-9.0% vs 15.5% engaged; bot doubt 15.0% | strong |
| C3 | On "busy", a concrete meeting-slot ask beats a callback-time ask | 538 / 124 (topics); 418 / 133 (turns) | 2.4% vs 33%; 6.2% vs 32% | moderate (partly selection) |
| C4 | On cost or "paid nahi", the "meeting is free, no charge" reframe | 115 | 50% vs 31.5% for cost objections (empathy-only 14%) | moderate |
| C5 | Repeat-call opener "aap se pehle baat hui thi" underperforms the action hook | 1,709 | 13.9% vs 24-29% | moderate |
| C6 | "You tried to buy a BuyLead / payment attempt" pitch | 459 | 4.6% vs OLP 11.4%; NI 61% | moderate |
| C7 | Specific recent-action hooks beat generic or city-enquiry hooks on first attempt | 263-1,741 | 30-42% vs 23-26% | moderate (bucket-confounded) |
| C8 | English-speaking sellers drop fast when the bot stays in Hindi | 591 turns / 484 calls | 61% end within 2 turns vs 24% | moderate |
| C9 | Identity answers must name IndiaMART and the reason; admitting AI does not hurt | 759 + 207 | ends within 2 turns 33-38% vs 12-14%; 30% vs 18% | moderate / weak |
| C10 | "zaroor" is not an interest cue; "address / bhej do / aa jaiye / kitne baje" are | 357 vs 70-319 | 12% vs 59-82% meeting | moderate |
| C11 | Arrowhead ("kya meri baat X se ho rahi hai" + longer, conversational turns) beats main_vani within every theme | 118-38k per cell | e.g. profile 34.0 vs 23.5; callback 12.7 vs 8.0; identity 16.6 vs 7.7 | moderate |
| C12 | Frustration "phone mat / call mat / block" -> polite exit plus DNC; an exit_close after frustration gives 1.7% | 45-98 turns | 51-64% end within 2 turns | moderate |

Inferences, not tested:
- That a free reframe *causes* meetings. The seller asking "is it chargeable?" is itself a warm signal.
- That the language-switch effect would hold with a live switch (no call ever switched language).
