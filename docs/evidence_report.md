# Evidence report: what has worked on past VANI calls

Source: 269k answered bot calls (Apr-Sep 2026), 278k evaluator outputs, 139k transcript turns. All findings are correlational (no randomised persona experiment exists). Strength: strong: |z|>=3 and n>=1000; moderate: |z|>=2 or n>=500 descriptive; weak: otherwise.

**Not evidenced by the data (informed guesses in the generator):** voice gender, voice pitch / timbre, bot pace (no call varied it), warmth/empathy level (no labelled tone data).

## Evidence items

| id | claim | segment | n | value | baseline | strength | note |
|---|---|---|---|---|---|---|---|
| E1 | Baseline outcome rates over all answered bot calls | all | 269,455 | 0.115 |  | strong | early_drop=0.255, not_interested=0.432 |
| E2 | Meeting rate collapses and early hang-ups rise with every repeat attempt; repeat-call sellers need a shorter, different opening that acknowledges the earlier call | call_attempt_count>=4 vs 1 | 47,806 | 0.043 | 0.163 | strong | early_drop 43.9% vs 15.7%; median 12s vs 29s; z=66.6 → Repeat attempts: acknowledge prior call, cut opening to one line, faster pace. |
| E3 | Sellers who earlier said 'call later' convert better on the follow-up call than other repeat sellers | repeat calls with >=1 prior call-later | 53,582 | 0.066 | 0.056 | strong | z=6.9 → Open by referencing the callback they asked for; go straight to scheduling. |
| E4 | Sellers who hung up within 10 s before are much more likely to hang up early again | repeat calls with >=1 prior early drop | 58,904 | 0.504 | 0.249 | strong | meeting 3.1% vs 8.1%; z=98.2 → Fast hangers-up: value hook in the first sentence, faster pace, skip pleasantries. |
| E5 | Sellers who previously said not interested rarely convert on later calls | repeat calls with >=1 prior not-interested | 80,863 | 0.043 | 0.060 | strong | z=-12.7 → Low-pressure tone, one soft ask, then exit politely (escalation rule). |
| E6 | Outcomes for NCR_Punjab sellers | region=NCR_Punjab | 67,156 | 0.096 | 0.115 | strong | not_interested 51.8%, early_drop 28.6%, median 19s; z=-18.2 |
| E7 | Outcomes for Hindi_belt sellers | region=Hindi_belt | 86,303 | 0.130 | 0.115 | strong | not_interested 40.0%, early_drop 25.3%, median 22s; z=16.2 |
| E8 | Outcomes for West sellers | region=West | 89,659 | 0.114 | 0.115 | weak | not_interested 42.1%, early_drop 23.7%, median 24s; z=-1.1 |
| E9 | Outcomes for South sellers | region=South | 9,685 | 0.122 | 0.115 | moderate | not_interested 22.7%, early_drop 25.6%, median 20s; z=2.1 |
| E10 | Outcomes for East sellers | region=East | 16,048 | 0.119 | 0.115 | weak | not_interested 42.8%, early_drop 24.0%, median 24s; z=1.8 |
| E11 | Larger businesses (turnover >= 1.5 Cr) agree to meetings less often and hang up faster than micro sellers | turnover >= 1.5 Cr vs 0-40 L | 36,904 | 0.088 | 0.114 | strong | early_drop 27.2% vs 25.6%; z=-14.4 → Mid/large: formal register, business-outcome framing, crisp and respectful of time. |
| E12 | Outcomes for Trader - Wholesaler/Distributor | nature=Trader - Wholesaler/Distributor | 61,822 | 0.100 | 0.115 | strong | early_drop 27.2%, median 20s; z=-13.6 |
| E13 | Outcomes for Service Provider and Others | nature=Service Provider and Others | 40,648 | 0.126 | 0.115 | strong | early_drop 24.1%, median 23s; z=7.7 |
| E14 | Outcomes for Manufacturer | nature=Manufacturer | 63,791 | 0.108 | 0.115 | strong | early_drop 25.1%, median 22s; z=-6.5 |
| E15 | Outcomes for Trader - Retailer | nature=Trader - Retailer | 76,010 | 0.115 | 0.115 | weak | early_drop 26.1%, median 21s; z=0.3 |
| E16 | Highly engaged sellers (pickup ratio > 50%) vs sellers who never pick up | engagement=high vs never_picks | 7,621 | 0.135 | 0.096 | strong | z=11.3 |
| E17 | Sellers who replied to buyer enquiries in last 90 days vs those who replied to none | eng_enq_replies_90d>0 vs =0 | 100,231 | 0.099 | 0.083 | strong | z=9.2 → Active enquiry responders: lead with their enquiry count / buyer demand hook. |
| E18 | Sellers flagged as having already in touch with an IndiaMART executive | already_in_touch_with_executive=1 | 15,405 | 0.081 | 0.108 | strong | early_drop 18.6% vs 26.9%; median 39s; z=-10.3. Flag comes from the same Apr-Sep calls, so this partly describes the flagged call itself. |
| E19 | Sellers flagged as having asked not to be called | do_not_call_requested=1 | 5,719 | 0.020 | 0.108 | strong | early_drop 25.9% vs 26.3%; median 22s; z=-21.4. Flag comes from the same Apr-Sep calls, so this partly describes the flagged call itself. |
| E20 | Sellers flagged as having showed frustration on a past call | showed_frustration=1 | 458 | 0.063 | 0.106 | moderate | early_drop 12.9% vs 26.3%; median 43s; z=-3.0. Flag comes from the same Apr-Sep calls, so this partly describes the flagged call itself. |
| E21 | Sellers flagged as having asked whether they were talking to a bot | asked_if_talking_to_bot=1 | 351 | 0.111 | 0.106 | weak | early_drop 18.5% vs 26.3%; median 38s; z=0.3. Flag comes from the same Apr-Sep calls, so this partly describes the flagged call itself. |
| E22 | Calls at 11:00-12:59 have the worst outcomes (busiest trading hours) | hour in 11-12 | 68,497 | 0.071 | 0.130 | strong | early_drop 36.6% vs 21.8%; z=-42.2 → Live: in late-morning calls, start in short mode and offer a callback slot early. |
| E23 | Warm lead buckets (PAM, NUR, SCHD) convert better than average | redis_bucket in PAM/NUR/SCHD | 15,694 | 0.171 | 0.115 | strong | z=21.1 → Personalise the opening with the lead reason (e.g. paid-package interest). |
| E24 | 'personalis' script vs main_vani in the same days and hours | lead_bot_version=personalis | 452 | 0.142 | 0.123 | weak | 95% CI 11.2%-17.7%; z=1.1; first-attempt only: 17.9% (n=229) vs 16.2% (n=1164). Single-afternoon trial, not randomised. → Personalised openings are directionally better; evidence is suggestive, not conclusive. |
| E25 | 'base_vani' script vs main_vani in the same days and hours | lead_bot_version=base_vani | 289 | 0.183 | 0.123 | moderate | 95% CI 14.3%-23.2%; z=2.9; first-attempt only: 20.7% (n=227) vs 16.2% (n=1164). Single-afternoon trial, not randomised. |
| E26 | Objection 'Seller Unavailability & Scheduling Constraints': share of objection calls and meeting rate after it | objection=Seller Unavailability & Scheduling Constraints | 1,339 | 0.057 |  | moderate | present in 25.8% of analysed calls; sample quote: Abhi toh garmi ka mausam hai aur yahan pe store pe main akela hoon; Bhai gaya hua hai hospital apne kaam se... uski beti |
| E27 | Objection 'Callback / Deferred Engagement (Neutral)': share of objection calls and meeting rate after it | objection=Callback / Deferred Engagement (Neutral) | 1,217 | 0.057 |  | moderate | present in 23.5% of analysed calls; sample quote: Aap call karke mujhe time maang lijiye; Main free ho jaun na toh aapse main baat karunga |
| E28 | Objection 'Call Quality / Technical Failures': share of objection calls and meeting rate after it | objection=Call Quality / Technical Failures | 1,053 | 0.026 |  | moderate | present in 20.3% of analysed calls; sample quote: Hello, kya aap Bench Top |
| E29 | Objection 'No Seller Response / Engagement Drop': share of objection calls and meeting rate after it | objection=No Seller Response / Engagement Drop | 825 | 0.018 |  | moderate | present in 15.9% of analysed calls; sample quote: Main abhi call nahi utha pa raha hoon. Yeh mera Truecaller voicemail hai. |
| E30 | Objection 'Explicit Disinterest / Refusal': share of objection calls and meeting rate after it | objection=Explicit Disinterest / Refusal | 796 | 0.023 |  | moderate | present in 15.4% of analysed calls; sample quote: hame paid wala nahi karna abhi; abhi nahi karana ma'am hame |
| E31 | Objection 'Call Handling / Executive Gaps': share of objection calls and meeting rate after it | objection=Call Handling / Executive Gaps | 629 | 0.057 |  | moderate | present in 12.1% of analysed calls; sample quote: Hello, kya aap Naaz Cutlery se bol rahe hai? |
| E32 | Objection 'Existing Engagement / Past Experience': share of objection calls and meeting rate after it | objection=Existing Engagement / Past Experience | 372 | 0.049 |  | moderate | present in 7.2% of analysed calls; sample quote: Meeting ho gayi hai, ma'am. Meeting ho gayi hai.; Nai nai nai, ma'am. Meeting ho gayi hai. Thank you. |
| E33 | Objection 'Wrong Contact / Business Not Applicable': share of objection calls and meeting rate after it | objection=Wrong Contact / Business Not Applicable | 204 | 0.030 |  | weak | present in 3.9% of analysed calls; sample quote: Wrong number hai |
| E34 | The bot ignores or mishandles a seller turn in 33% of evaluated calls; no measurable change in meeting rate (gaps occur in long, engaged calls too) | calls with >=1 response gap | 5,578 | 0.233 | 0.231 | weak | top gap turn types: {'Objection': 3100, 'Question': 1575, 'Request': 1448}; 8% of missed turns were 'busy/later' statements; z=0.2 → Quality rule (not outcome-backed): acknowledge the seller's exact objection before re-asking. |
| E35 | Sellers do ask if they are talking to an AI; the current bot often answers by claiming to be a person | question category = AI Bot Confirmation | 163 | 0.058 |  | moderate | meeting rate in those calls 18.5%; 61% of answers deny being a bot (compliance risk) → Guardrail: never claim to be human; give an honest, brief identity answer and continue. |
| E36 | Calls where the bot used the 'T11_PAYMENT_INTEREST' hook | topic=T11_PAYMENT_INTEREST | 1,415 | 0.317 | 0.218 | weak | Topic presence is partly a result of the call going longer (survivorship); treat as directional. |
| E37 | Calls where the bot used the 'T14_PROFILE_VISIBILITY_IMPROVEMENT' hook | topic=T14_PROFILE_VISIBILITY_IMPROVEMENT | 1,860 | 0.273 | 0.218 | weak | Topic presence is partly a result of the call going longer (survivorship); treat as directional. |
| E38 | Sellers who say they are already in touch with / met an executive | se_contact != neither | 696 | 0.164 | 0.247 | moderate | Playbook: acknowledge the existing executive, offer the visit as a follow-up on new enquiries. |
| E39 | Where calls drop: share of dispositions that are drops at a given stage | disposition evaluator | 150,821 | 0.288 |  | strong | no_response=25.2%; dropped_mid_pitch=11.5%; dropped_after_indiamart_identity=10.0%; dropped_after_seller_identity=7.3% → The opening and the first pitch line are where most calls are lost. |
| E40 | Tamil Nadu sellers answer the (Hindi-speaking) bot mostly in ta-IN | state=Tamil Nadu | 160 | 0.719 | 0.181 | moderate | Hindi 18%, English 10%, regional detail {'en-IN': 0.1, 'hi-IN': 0.18, 'ta-IN': 0.72}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E41 | Gujarat sellers answer the (Hindi-speaking) bot mostly in hi-IN | state=Gujarat | 2,380 | 0.995 | 0.995 | moderate | Hindi 99%, English 0%, regional detail {'hi-IN': 0.99}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E42 | Maharashtra sellers answer the (Hindi-speaking) bot mostly in hi-IN | state=Maharashtra | 1,766 | 0.986 | 0.986 | moderate | Hindi 99%, English 1%, regional detail {'hi-IN': 0.99}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E43 | West Bengal sellers answer the (Hindi-speaking) bot mostly in hi-IN | state=West Bengal | 582 | 0.998 | 0.998 | moderate | Hindi 100%, English 0%, regional detail {'hi-IN': 1.0}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E44 | Telangana sellers answer the (Hindi-speaking) bot mostly in hi-IN | state=Telangana | 257 | 0.969 | 0.969 | moderate | Hindi 97%, English 3%, regional detail {'en-IN': 0.03, 'hi-IN': 0.97}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E45 | Punjab sellers answer the (Hindi-speaking) bot mostly in hi-IN | state=Punjab | 360 | 0.983 | 0.983 | moderate | Hindi 98%, English 1%, regional detail {'hi-IN': 0.98}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E46 | Odisha sellers answer the (Hindi-speaking) bot mostly in hi-IN | state=Odisha | 157 | 0.994 | 0.994 | moderate | Hindi 99%, English 1%, regional detail {'hi-IN': 0.99}. Bot always opened in Hindi, so Hindi share is biased upward. |
| E47 | Share of transcribed calls where the seller spoke a non-Hindi language at least once | all transcribed calls | 12,015 | 0.108 |  | moderate | Language-switch detection is needed live even though most calls stay in Hindi. |
| E48 | English-word share barely differs by turnover band (large vs micro) | turnover large vs micro | 536 | 0.086 | 0.088 | weak | Keyword-based estimate. → Turnover alone should not drive english_mix; use region and live detection. |
| E49 | Southern sellers use the most English among regions | region=South | 488 | 0.150 | 0.089 | moderate | Keyword-based estimate. → South: English-heavy fallback if regional language not used. |
| E50 | Seller speaking rate vs the bot's rate | seller turns | 40,201 | 2.528 | 3.111 | weak | by region {'East': 2.44, 'Hindi_belt': 2.59, 'NCR_Punjab': 2.61, 'Other': 2.52, 'South': 2.17, 'West': 2.5}. No call recorded different bot paces, so pace effects are an informed guess. → Pace setting = informed guess; live adaptation corrects it. |
| E51 | Sellers cut off the bot's first pitch line in 9% of transcribed calls | transcribed calls with a pitch line | 11,170 | 0.093 |  | moderate | meeting rate when pitch cut off 11.1% vs 26.3% when spoken in full → Front-load the value hook (enquiries in their city) in the first 8-10 words. |
| E52 | Among pitch lines spoken in full, length shows longer lines going with more meetings | full pitch line short vs long tercile | 3,385 | 0.169 | 0.325 | weak | median words 27 vs 54; z=-14.7. Longer lines carry more content (e.g. the lead reason), so this is confounded. → Pitch length itself is not evidenced; the generator keeps the hook early and adapts length live. |
| E53 | Calls where the bot repeated itself (loopy) convert worse | is_loopy | 1,736 | 0.436 | 0.185 | strong | z=23.6 → Never repeat the same pitch verbatim; rephrase or move on. |
| E54 | Calls where the seller had to repeat themselves | seller_had_to_repeat_count>0 | 2,157 | 0.281 | 0.206 | strong | z=7.8. Seller repeating = confusion/not-heard signal. |
| E55 | Live signal 'rush': how often it appears and what follows | seller turns with rush keywords | 3,884 | 0.306 | 0.259 | strong | meeting rate in calls with signal 13.3% vs 22.4%; z=6.6 |
| E56 | Live signal 'frustration': how often it appears and what follows | seller turns with frustration keywords | 567 | 0.423 | 0.259 | moderate | meeting rate in calls with signal 11.6% vs 22.4%; z=8.9 |
| E57 | Live signal 'confusion': how often it appears and what follows | seller turns with confusion keywords | 1,391 | 0.164 | 0.259 | strong | meeting rate in calls with signal 26.9% vs 22.4%; z=-8.0 |
| E58 | Live signal 'interest': how often it appears and what follows | seller turns with interest keywords | 2,939 | 0.194 | 0.259 | strong | meeting rate in calls with signal 40.8% vs 22.4%; z=-7.9 |
| E59 | Live signal 'bot_question': how often it appears and what follows | seller turns with bot_question keywords | 475 | 0.206 | 0.259 | moderate | meeting rate in calls with signal 24.5% vs 22.4%; z=-2.6 |
| E60 | Two consecutive 1-2 word seller replies after the opening | seller turns | 5,543 | 0.323 | 0.259 | strong | Disengagement / rush proxy. |

## Baseline

269,455 answered bot calls to 130,129 sellers. Meeting fixed 11.5%, not interested 43.2%, call later 16.2%, early drop (<10 s) 25.5%, median duration 22 s.

## By call attempt number

|   call_attempt_count |      n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|---------------------:|-------:|:----------|:----------|:-------------|:-------------|-------------:|
|                    1 | 129449 | 16.3%     | 41.1%     | 16.6%        | 15.7%        |           29 |
|                    2 |  56089 | 9.4%      | 42.4%     | 17.2%        | 27.5%        |           20 |
|                    3 |  36111 | 7.2%      | 43.2%     | 16.2%        | 33.2%        |           16 |
|                    4 |  19118 | 5.7%      | 47.2%     | 14.9%        | 38.5%        |           14 |
|                    5 |  11859 | 5.1%      | 47.7%     | 14.5%        | 41.7%        |           13 |
|                    6 |   6324 | 2.7%      | 51.7%     | 13.2%        | 47.8%        |           10 |
|                   10 |    547 | 2.4%      | 66.9%     | 11.7%        | 54.5%        |            8 |
|                    7 |   3978 | 2.3%      | 50.2%     | 13.2%        | 50.4%        |            9 |
|                    9 |    904 | 1.7%      | 53.2%     | 13.9%        | 51.8%        |            9 |
|                    8 |   2754 | 1.3%      | 51.9%     | 11.4%        | 54.9%        |            8 |

## By region

| region     |     n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:-----------|------:|:----------|:----------|:-------------|:-------------|-------------:|
| Hindi_belt | 86303 | 13.0%     | 40.0%     | 15.6%        | 25.3%        |           22 |
| South      |  9685 | 12.2%     | 22.7%     | 11.7%        | 25.6%        |           20 |
| Other      |   603 | 12.1%     | 41.0%     | 20.9%        | 29.7%        |           20 |
| East       | 16048 | 12.0%     | 42.8%     | 20.0%        | 24.0%        |           24 |
| West       | 89659 | 11.4%     | 42.1%     | 17.1%        | 23.7%        |           24 |
| NCR_Punjab | 67156 | 9.6%      | 51.8%     | 15.5%        | 28.6%        |           19 |

## By state (n>=1500)

| seller_state   |     n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:---------------|------:|:----------|:----------|:-------------|:-------------|-------------:|
| Odisha         |  3040 | 14.8%     | 42.3%     | 18.0%        | 24.7%        |           24 |
| Uttarakhand    |  1754 | 14.2%     | 46.4%     | 16.5%        | 25.2%        |           22 |
| Jharkhand      |  1787 | 14.0%     | 44.7%     | 18.7%        | 23.5%        |           23 |
| Bihar          |  3109 | 14.0%     | 37.8%     | 18.0%        | 22.1%        |           26 |
| Madhya Pradesh |  9552 | 13.9%     | 46.1%     | 16.2%        | 25.3%        |           21 |
| Tamil Nadu     |  4163 | 13.6%     | 0.6%      | 4.9%         | 24.7%        |           18 |
| Uttar Pradesh  | 46841 | 13.3%     | 44.3%     | 16.9%        | 24.4%        |           23 |
| Chhattisgarh   |  1976 | 13.1%     | 45.5%     | 16.8%        | 23.5%        |           23 |
| Assam          |  2024 | 12.1%     | 43.9%     | 17.8%        | 28.7%        |           21 |
| Gujarat        | 51037 | 11.5%     | 42.9%     | 17.2%        | 23.7%        |           24 |
| Rajasthan      | 20730 | 11.3%     | 26.2%     | 11.6%        | 27.8%        |           20 |
| Maharashtra    | 38615 | 11.3%     | 41.0%     | 17.0%        | 23.8%        |           23 |
| West Bengal    | 10976 | 11.2%     | 42.7%     | 21.0%        | 22.8%        |           25 |
| Telangana      |  5449 | 11.1%     | 39.5%     | 16.8%        | 26.3%        |           22 |
| Punjab         |  8612 | 10.8%     | 46.8%     | 18.1%        | 26.4%        |           20 |
| Haryana        | 17377 | 10.8%     | 50.2%     | 14.8%        | 28.4%        |           19 |
| Delhi          | 40301 | 8.8%      | 53.6%     | 15.2%        | 29.3%        |           19 |

## By turnover band

| turnover_band   |      n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:----------------|-------:|:----------|:----------|:-------------|:-------------|-------------:|
| unknown         |  29277 | 18.4%     | 36.4%     | 16.2%        | 21.7%        |           29 |
| micro           | 161463 | 11.4%     | 43.6%     | 16.1%        | 25.6%        |           22 |
| small           |  41811 | 9.5%      | 44.7%     | 16.6%        | 26.4%        |           20 |
| mid             |  22689 | 8.8%      | 46.2%     | 16.3%        | 27.8%        |           19 |
| large           |  14215 | 8.8%      | 43.1%     | 15.7%        | 26.2%        |           19 |

## By nature of business

| nature_of_business              |     n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:--------------------------------|------:|:----------|:----------|:-------------|:-------------|-------------:|
| Service Provider and Others     | 40648 | 12.6%     | 42.0%     | 15.9%        | 24.1%        |           23 |
| Trader - Retailer               | 53631 | 12.1%     | 44.4%     | 15.1%        | 25.9%        |           22 |
| Manufacturer                    | 63791 | 10.8%     | 43.3%     | 16.9%        | 25.1%        |           22 |
| Trader - Wholesaler/Distributor | 46858 | 10.4%     | 44.2%     | 16.2%        | 26.8%        |           21 |
| Retailer                        | 22379 | 10.3%     | 43.4%     | 16.4%        | 26.5%        |           20 |
| Wholesaler/Distributor          | 14964 | 8.7%      | 44.5%     | 15.9%        | 28.3%        |           19 |

## By 1-yr pickup ratio on IndiaMART calls (engagement)

| engagement   |      n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:-------------|-------:|:----------|:----------|:-------------|:-------------|-------------:|
| medium       |  15629 | 18.1%     | 40.6%     | 16.1%        | 21.2%        |           29 |
| unknown      |  62378 | 15.0%     | 42.2%     | 15.6%        | 20.2%        |           25 |
| high         |   7621 | 13.5%     | 57.2%     | 14.2%        | 29.9%        |           22 |
| low          |  71515 | 9.9%      | 43.6%     | 16.4%        | 27.4%        |           21 |
| never_picks  | 112312 | 9.6%      | 42.9%     | 16.6%        | 27.6%        |           20 |

## By hour of day (IST)

|   hour |     n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|-------:|------:|:----------|:----------|:-------------|:-------------|-------------:|
|      9 | 26059 | 13.9%     | 42.1%     | 17.2%        | 20.3%        |           24 |
|     10 | 21514 | 11.7%     | 39.6%     | 15.7%        | 25.8%        |           22 |
|     11 | 40707 | 6.3%      | 56.0%     | 14.8%        | 39.6%        |           14 |
|     12 | 27790 | 8.2%      | 42.3%     | 15.3%        | 32.3%        |           17 |
|     13 | 20675 | 11.8%     | 42.1%     | 17.1%        | 22.9%        |           23 |
|     14 | 24729 | 12.6%     | 42.9%     | 16.9%        | 20.7%        |           24 |
|     15 | 23970 | 13.4%     | 41.2%     | 16.6%        | 19.3%        |           25 |
|     16 | 24523 | 13.4%     | 41.1%     | 16.4%        | 20.7%        |           25 |
|     17 | 20676 | 13.6%     | 39.4%     | 16.1%        | 21.5%        |           25 |
|     18 | 15868 | 13.2%     | 38.6%     | 16.6%        | 23.0%        |           24 |
|     19 | 13487 | 13.8%     | 38.7%     | 16.8%        | 23.2%        |           24 |
|     20 |  9450 | 12.9%     | 37.5%     | 16.6%        | 22.7%        |           23 |

## By hot-lead bucket (redis_bucket)

| redis_bucket   |     n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:---------------|------:|:----------|:----------|:-------------|:-------------|-------------:|
| NUR            |  1524 | 31.2%     | 30.1%     | 19.8%        | 14.8%        |           49 |
| PAM            | 10906 | 16.0%     | 44.2%     | 15.2%        | 22.1%        |           27 |
| SCHD           |  3264 | 14.3%     | 33.1%     | 17.0%        | 22.7%        |           23 |
| PUA            | 85848 | 12.7%     | 41.4%     | 17.1%        | 23.8%        |           24 |
| OLP            | 10177 | 11.4%     | 42.6%     | 15.3%        | 25.5%        |           22 |
| PANF           |   939 | 10.5%     | 47.3%     | 15.1%        | 29.3%        |           19 |
| PIM            | 93210 | 10.5%     | 44.3%     | 15.7%        | 27.4%        |           21 |
| UA             | 60334 | 10.1%     | 44.8%     | 16.0%        | 26.0%        |           20 |
| PUT            |  1622 | 7.2%      | 60.9%     | 16.7%        | 25.0%        |           20 |
| ENQR           |   607 | 5.3%      | 18.6%     | 15.2%        | 31.6%        |           15 |

## Bot versions, matched window (28-30 Sep, 14:00-21:00)

| lead_bot_version   |    n | meeting   | early_drop   | not_int   |   median_sec |   first_attempt |
|:-------------------|-----:|:----------|:-------------|:----------|-------------:|----------------:|
| arrowhead          |  480 | 12.9%     | 23.5%        | 4.8%      |           19 |        0.541667 |
| base_vani          |  289 | 18.3%     | 11.8%        | 13.1%     |           37 |        0.785467 |
| main_vani          | 1987 | 12.3%     | 25.6%        | 8.5%      |           21 |        0.585808 |
| personalis         |  452 | 14.2%     | 35.2%        | 5.5%      |           18 |        0.506637 |
| summary_va         |   91 | 3.3%      | 42.9%        | 8.8%      |           13 |        0        |

## Bot versions, all time (not comparable: different periods)

| lead_bot_version   |      n | meeting   | not_int   | call_later   | early_drop   |   median_sec |
|:-------------------|-------:|:----------|:----------|:-------------|:-------------|-------------:|
| base_vani          |    289 | 18.3%     | 13.1%     | 18.7%        | 11.8%        |           37 |
| personalis         |    452 | 14.2%     | 5.5%      | 15.5%        | 35.2%        |           18 |
| main               |   5573 | 14.0%     | 50.1%     | 18.4%        | 24.5%        |           23 |
| last_met_a         |    723 | 11.9%     | 0.0%      | 7.6%         | 23.7%        |           22 |
| main_vani          | 208605 | 11.6%     | 48.4%     | 17.2%        | 26.3%        |           22 |
| last_met_d         |  23046 | 11.1%     | 53.2%     | 20.9%        | 20.1%        |           25 |
| arrowhead          |  30676 | 10.7%     | 0.6%      | 5.4%         | 24.4%        |           21 |
| summary_va         |     91 | 3.3%      | 8.8%      | 20.9%        | 42.9%        |           13 |

## Objection categories (objections evaluator, 5.2k calls)

| category                                       |    n | meeting_after   |
|:-----------------------------------------------|-----:|:----------------|
| Seller Unavailability & Scheduling Constraints | 1339 | 5.7%            |
| Callback / Deferred Engagement (Neutral)       | 1217 | 5.7%            |
| Call Quality / Technical Failures              | 1053 | 2.6%            |
| No Seller Response / Engagement Drop           |  825 | 1.8%            |
| Explicit Disinterest / Refusal                 |  796 | 2.3%            |
| Call Handling / Executive Gaps                 |  629 | 5.7%            |
| Existing Engagement / Past Experience          |  372 | 4.9%            |
| Wrong Contact / Business Not Applicable        |  204 | 3.0%            |
| Not Ready / Needs Time / Early-Stage Seller    |  198 | 8.1%            |
| Product / Service / Business Mismatch          |  134 | 7.5%            |
| Information / Trust / Privacy Concerns         |   51 | 3.9%            |
| Others                                         |   37 | 10.8%           |

## Objection mix by region (row %)

| region     |   Call Handling / Executive Gaps |   Call Quality / Technical Failures |   Callback / Deferred Engagement (Neutral) |   Existing Engagement / Past Experience |   Explicit Disinterest / Refusal |   Information / Trust / Privacy Concerns |   No Seller Response / Engagement Drop |   Not Ready / Needs Time / Early-Stage Seller |   Others |   Product / Service / Business Mismatch |   Seller Unavailability & Scheduling Constraints |   Wrong Contact / Business Not Applicable |
|:-----------|---------------------------------:|------------------------------------:|-------------------------------------------:|----------------------------------------:|---------------------------------:|-----------------------------------------:|---------------------------------------:|----------------------------------------------:|---------:|----------------------------------------:|-------------------------------------------------:|------------------------------------------:|
| East       |                              7.6 |                                10.4 |                                       20.8 |                                     6.7 |                              9.6 |                                      0   |                                   10.7 |                                           6.2 |      1.1 |                                     2.2 |                                             21.9 |                                       2.8 |
| Hindi_belt |                              9.2 |                                12.3 |                                       19.5 |                                     5.8 |                             10.6 |                                      1.1 |                                   11.7 |                                           3.1 |      0.4 |                                     1.8 |                                             21.5 |                                       2.9 |
| NCR_Punjab |                             10.6 |                                17.2 |                                       15.9 |                                     4.7 |                             11.2 |                                      0.8 |                                   14.5 |                                           2.1 |      0.4 |                                     1.9 |                                             17.9 |                                       3   |
| Other      |                              0   |                                 0   |                                       33.3 |                                     0   |                             16.7 |                                      0   |                                   16.7 |                                           0   |      0   |                                     0   |                                             33.3 |                                       0   |
| South      |                              0   |                                 8.5 |                                       11.9 |                                     6.8 |                             25.4 |                                      1.7 |                                   11.9 |                                           6.8 |      0   |                                     6.8 |                                             18.6 |                                       1.7 |
| West       |                              8.5 |                                10.4 |                                       20   |                                     6.2 |                             14   |                                      0.6 |                                    9.4 |                                           3.2 |      0.8 |                                     2.2 |                                             21.2 |                                       3.4 |

## Objection mix by turnover band (row %)

| turnover_band   |   Call Handling / Executive Gaps |   Call Quality / Technical Failures |   Callback / Deferred Engagement (Neutral) |   Existing Engagement / Past Experience |   Explicit Disinterest / Refusal |   Information / Trust / Privacy Concerns |   No Seller Response / Engagement Drop |   Not Ready / Needs Time / Early-Stage Seller |   Others |   Product / Service / Business Mismatch |   Seller Unavailability & Scheduling Constraints |   Wrong Contact / Business Not Applicable |
|:----------------|---------------------------------:|------------------------------------:|-------------------------------------------:|----------------------------------------:|---------------------------------:|-----------------------------------------:|---------------------------------------:|----------------------------------------------:|---------:|----------------------------------------:|-------------------------------------------------:|------------------------------------------:|
| large           |                              9.9 |                                11.8 |                                       15.5 |                                     7   |                             17.2 |                                      0.8 |                                   10.1 |                                           2   |      1.4 |                                     2.8 |                                             16.9 |                                       4.5 |
| micro           |                              9.1 |                                12.4 |                                       18.9 |                                     5.7 |                             11.5 |                                      0.7 |                                   11.8 |                                           3.3 |      0.6 |                                     2.3 |                                             20.8 |                                       2.9 |
| mid             |                              8.7 |                                16.5 |                                       17.6 |                                     4.6 |                             13.3 |                                      0.5 |                                   12.3 |                                           2   |      0.2 |                                     1.1 |                                             18.9 |                                       4.3 |
| small           |                              9.2 |                                14.2 |                                       19.3 |                                     5.6 |                             11.1 |                                      0.7 |                                   10.9 |                                           2.3 |      0.5 |                                     1.5 |                                             21.2 |                                       3.6 |
| unknown         |                              9.6 |                                11.2 |                                       18.4 |                                     6.1 |                             13.7 |                                      1.8 |                                   11.8 |                                           4.7 |      0.2 |                                     1.6 |                                             19.4 |                                       1.6 |

## Bot response gaps by seller turn type

| turn_type   |    n |   meeting |
|:------------|-----:|----------:|
| Objection   | 3100 |  0.144383 |
| Question    | 1575 |  0.320948 |
| Request     | 1448 |  0.365718 |
| Complaint   |  325 |  0.199377 |

## Questions sellers ask (seller_questions evaluator)

| category              |    n | meeting   |
|:----------------------|-----:|:----------|
| Meeting Visit         | 1510 | 55.4%     |
| Identity Confirmation | 1099 | 18.4%     |
| Clarification         | 1094 | 39.1%     |
| Purpose Reason        |  837 | 23.2%     |
| Service Product Info  |  740 | 28.7%     |
| Pricing Payment       |  404 | 23.1%     |
| Location Confirmation |  390 | 30.9%     |
| Callback Contact      |  375 | 15.2%     |
| Enquiry Lead          |  312 | 24.3%     |
| Benefit Value         |  219 | 21.1%     |
| Frustrated User       |  171 | 9.6%      |
| AI Bot Confirmation   |  163 | 18.5%     |

## Topics present in call vs meeting rate (topics evaluator; base 21.8%)

| topic                                 |    n | meeting   |
|:--------------------------------------|-----:|:----------|
| T25_MEETING_DATE_TIME_CONFIRMATION    | 1622 | 79.0%     |
| T29_CALL_CLOSURE_HELPLINE             | 2653 | 42.6%     |
| T24_MEETING_DATE_TIME_REQUEST         | 2950 | 41.5%     |
| T28_SELLER_ASK_MEETING_PURPOSE        |  338 | 40.2%     |
| T10_SCHEDULE_DEMO                     |  237 | 34.6%     |
| T15_REQUEST_TO_MEET                   | 3227 | 34.6%     |
| T13_SELLER_ACTIVE_ON_INDIAMART        |  622 | 33.9%     |
| T11_PAYMENT_INTEREST                  | 1415 | 31.7%     |
| T07_INDIAMART_INTRODUCTION            | 4732 | 27.8%     |
| T14_PROFILE_VISIBILITY_IMPROVEMENT    | 1860 | 27.3%     |
| T08_BUYER_ENQUIRIES_RECEIVED          | 1009 | 24.7%     |
| T16_LOCAL_BUYER_DEMAND_DISCUSSION     |  993 | 24.5%     |
| T02_PRODUCT_VERIFICATION              |  452 | 24.1%     |
| T03_LOCATION_VERIFICATION             | 1438 | 23.9%     |
| T26_SELLER_ENQUIRED_FOR_PAID_PACKAGE  |  111 | 22.5%     |
| T18_MEETING_FREE_OR_PAID              |  105 | 21.9%     |
| T01_CALL_OPENING_SELLER_ID            | 5977 | 21.9%     |
| T30_SELLER_POOR_EXPERIENCE            |  135 | 20.7%     |
| T32_NETWORK_ISSUES                    |  604 | 18.0%     |
| T05_WRONG_PRODUCTS_DIFFERENT_BUSINESS |  100 | 18.0%     |
| T20_OBJECTION_SELLER_IDENTIFIED_AI    |  115 | 17.4%     |
| T17_COMPETITOR_REFERENCE              |  292 | 15.8%     |
| T22_OBJECTION_NO_NEED_PAID_SERVICES   |  126 | 14.3%     |
| T31_NOT_RIGHT_CONTACT_PERSON          |  114 | 9.6%      |
| T21_OBJECTION_BUSY_CALL_LATER         | 1444 | 9.3%      |
| T19_OBJECTION_NOT_INTERESTED          |  770 | 2.9%      |
| T23_CALL_DATE_TIME_REQUEST            |  813 | 2.6%      |
| T04_WRONG_NUMBER                      |  161 | 2.5%      |

## Existing executive contact (se_contact evaluator)

| cat              |     n | meeting   |
|:-----------------|------:|:----------|
| in_touch_with_se |   696 | 16.4%     |
| meeting_done     |  1541 | 15.8%     |
| neither          | 14828 | 24.8%     |

## Who ended the call (execdrop evaluator)

| who    |   share |
|:-------|--------:|
| EXEC   |   0.556 |
| SYSTEM |   0.349 |
| SELLER |   0.095 |

## Detailed dispositions (top 15)

| subd                             |   share |
|:---------------------------------|--------:|
| no_response                      |  0.2519 |
| none                             |  0.1863 |
| dropped_mid_pitch                |  0.1148 |
| flat_refusal_or_no_requirement   |  0.1011 |
| dropped_after_indiamart_identity |  0.0998 |
| dropped_after_seller_identity    |  0.0733 |
| callback_with_datetime           |  0.0625 |
| callback_without_datetime        |  0.0615 |
| already_met_exec                 |  0.0189 |
| voicemail                        |  0.0111 |
| in_touch_with_exec               |  0.0109 |
| business_closed                  |  0.0045 |
| bad_past_experience              |  0.0031 |
| using_competitor                 |  0.0003 |

## Language sellers actually speak on calls, by state (share of calls; keyword-detected)

| seller_state                             |   bn-IN |   en-IN |   gu-IN |   hi-IN |   kn-IN |   mr-IN |   ta-IN |   te-IN |   n_calls |
|:-----------------------------------------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|--------:|----------:|
| Gujarat                                  |       0 |       0 |       0 |      99 |       0 |       0 |       0 |       0 |      2380 |
| Uttar Pradesh                            |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |      2040 |
| Maharashtra                              |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |      1766 |
| Delhi                                    |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |      1139 |
| Rajasthan                                |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |       848 |
| West Bengal                              |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |       582 |
| Haryana                                  |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |       527 |
| Madhya Pradesh                           |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |       391 |
| Punjab                                   |       0 |       1 |       0 |      98 |       0 |       0 |       0 |       0 |       360 |
| Telangana                                |       0 |       3 |       0 |      97 |       0 |       0 |       0 |       0 |       257 |
| Tamil Nadu                               |       0 |      10 |       0 |      18 |       0 |       0 |      72 |       0 |       160 |
| Odisha                                   |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |       157 |
| Bihar                                    |       0 |       1 |       0 |      99 |       0 |       0 |       0 |       0 |       155 |
| Assam                                    |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        95 |
| Jharkhand                                |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        90 |
| Uttarakhand                              |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        84 |
| Chhattisgarh                             |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        83 |
| Chandigarh                               |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        42 |
| Dadra and Nagar Haveli and Daman and Diu |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        25 |
| Himachal Pradesh                         |       0 |       0 |       0 |     100 |       0 |       0 |       0 |       0 |        17 |

## English-word share in seller speech by turnover band

| band    |   mean |   size |
|:--------|-------:|-------:|
| large   |  0.086 |    536 |
| micro   |  0.088 |   7018 |
| mid     |  0.085 |    924 |
| small   |  0.08  |   1731 |
| unknown |  0.1   |   1604 |

## English-word share in seller speech by region

| region     |   mean |   size |
|:-----------|-------:|-------:|
| East       |  0.067 |    861 |
| Hindi_belt |  0.082 |   3889 |
| NCR_Punjab |  0.098 |   2204 |
| Other      |  0.087 |     26 |
| South      |  0.15  |    488 |
| West       |  0.087 |   4345 |

## Seller speech rate (words/sec) by region; bot median 3.11 w/s

| region     |   median |   size |
|:-----------|---------:|-------:|
| East       |     2.44 |   2940 |
| Hindi_belt |     2.59 |  13703 |
| NCR_Punjab |     2.61 |   6716 |
| Other      |     2.52 |     75 |
| South      |     2.17 |   1550 |
| West       |     2.5  |  14998 |

## Length of the bot's first IndiaMART pitch line vs outcome (pitch lines spoken in full; 9% of pitch lines were cut off by the seller)

| pitch_len   |    n | meeting   | ended_within_4_turns   |   pitch_words |
|:------------|-----:|:----------|:-----------------------|--------------:|
| short       | 3385 | 16.9%     | 16.3%                  |            27 |
| medium      | 3665 | 29.7%     | 7.5%                   |            49 |
| long        | 3086 | 32.5%     | 5.8%                   |            54 |

## Bot reply latency (p50 per call) vs meeting rate

| lat_band   |    n | meeting   |
|:-----------|-----:|:----------|
| <=1s       | 8644 | 24.8%     |
| 1-1.5s     | 1604 | 24.3%     |
| 1.5-2s     | 1029 | 22.5%     |
| 2-3s       |  609 | 14.0%     |
| >3s        |  380 | 5.0%      |

## Live signals in seller turns (baseline: call ends within 2 turns 25.9%, meeting 22.4%)

| signal       |   seller_turns |   share_turns |   calls |   ends_within_2_turns |   meeting_in_call |
|:-------------|---------------:|--------------:|--------:|----------------------:|------------------:|
| rush         |           3884 |         0.06  |    2802 |                 0.306 |             0.133 |
| frustration  |            567 |         0.009 |     439 |                 0.423 |             0.116 |
| confusion    |           1391 |         0.022 |    1134 |                 0.164 |             0.269 |
| interest     |           2939 |         0.045 |    1945 |                 0.194 |             0.408 |
| bot_question |            475 |         0.007 |     310 |                 0.206 |             0.245 |
