# Seller use-case segmentation for VANI voice agents

**Data:** 149,363 sellers · 269,455 answered bot calls (Apr–Sep 2026) · 278k evaluator outputs · 139k transcript turns · 67k executive calls (Aug–Sep).
**Output file:** `seller_use_case.csv` / `.parquet`, one row per seller: `route`, `contact_policy`, `use_case`, `use_case_confidence`, `secondary_use_cases`, and the features behind them.
**Detail reports:** `A_bucket_decoder.md` (campaign triggers, paid/free), `B_seller_segments.md` (profile rules), `C_conversation_evidence.md` (themes, objections, FAQs, live cues, openings), `D_suppression_routing.md` (contact gate, fatigue, timing).
**Rebuild:** `scripts/e01_final_assign.py` (assignment), then `scripts/e02_holdout.py` (validation).

All findings are correlational. No randomised persona test exists. Strength labels: strong = n ≥ 1000 and a clear gap; moderate = smaller n or a smaller gap; weak = directional.

---

## 1. How a seller is routed

```
seller ──► [1] Contact gate (D) ── SUPPRESS / ROUTE_TO_HUMAN / COOL_OFF ──► no bot call (or wait)
              │ OK_TO_CALL
              ▼
          [2] Use case = first match, in priority order:
              warm_followup ► lead_engagement ► free_to_paid ► reactivation ► profile_onboarding ► discovery
              │
              ▼
          [3] Category persona = call goal, opening, playbook, escalation (this doc, section 4)
              + per-seller voice and language (state, turnover, past behaviour) from the existing generator
              + live adaptation (frustration / confusion / interest / rush / language switch)
```

Each seller's category is built from two kinds of signal:
- **Why the call is happening:** the latest campaign trigger, `redis_bucket`.
- **The seller's state:** engagement, catalog and past call themes.

Neither is enough alone. There is no paid/free column, and the trigger codes are undocumented, so they were decoded from 259k call summaries.

**Language is set per seller, not per category.** The regional mix is almost identical in every category (Hindi belt 54–58%, Gujarat ~18%, Maharashtra ~16%), so each category fixes what the call is for and how it runs. Voice and language come from the seller's own data.

## 2. The categories

| # | Use case | Sellers | % | OK to call | Defining signal |
|---|---|---:|---:|---:|---|
| 1 | **Warm follow-up** | 22,760 | 15.2 | 19,094 | Last call was Meeting Fixed or Call Later within 60 days, or trigger SCHD (demo booked) or OLPR (recent BuyLead purchase) |
| 2 | **Lead engagement** (not consuming leads) | 11,295 | 7.6 | 8,321 | ≥3 enquiries/yr with reply ratio < 0.25, or ≥3 PNS calls/yr with answer ratio < 0.33, or trigger PNSM/PNSR/ENQR |
| 3 | **Free → Paid conversion** | 54,024 | 36.2 | 41,562 | Monetisation trigger: PIM (explored paid services), PAM (paid-package interest), OLP (tried to buy BuyLeads), PANF, PNCHF; or an active, well-catalogued seller with steady enquiries; or PUA (viewed BuyLeads) + past pricing talk |
| 4 | **Re-activation** (dormant) | 12,794 | 8.6 | 10,715 | Zero activity, enquiries, replies, PNS and edits over 90 days, or said "business band / kaam chhod diya" on a past call |
| 5 | **Profile enrichment and onboarding** | 28,541 | 19.1 | 23,945 | cqs ≤ 9, ≤ 5 products, no edits with cqs < 15, ≥ 2 profile fields missing; good catalog but zero enquiries; trigger NUR (new registration) or PUT; past catalog talk |
| 6 | **Discovery** (fallback) | 19,949 | 13.4 | 18,614 | No engagement or catalog data and no specific trigger. A short qualification call that tags the seller into 1–5 |
| — | **Contact gate** (applies to all categories) | 27,112 | 18.2 | — | SUPPRESS 4,457 · ROUTE_TO_HUMAN 4,726 · COOL_OFF 17,929 |

- **Priority order:** an existing commitment comes first. Fix lead consumption before selling more leads, since a seller who ignores enquiries won't buy more. A closed shop goes to re-activation before catalog work.
- **Overlap:** 39% of sellers match two or more categories. The rest are kept in `secondary_use_cases` and give the persona extra hooks, e.g. a free → paid seller with a thin catalog gets the profile-fix angle.
- **Confidence:**
  - **high:** the seller-profile rule and the trigger or past-call theme agree.
  - **medium:** only one of them fires.
  - **low:** discovery, and PUA-only free → paid.
- **Free → Paid is the largest category (36%)** because PIM and PUA dominate the bot campaigns.
  - It means a seller showing upgrade intent, not a confirmed free seller. Only about 330 sellers state their plan in a summary (31 free, 303 paid).
  - Before production, join the real subscription flag. It would move paid sellers into a renewal/upsell persona.

## 3. Do the categories behave differently? (holdout)

Categories were rebuilt from data before 1 Sep only, then scored on each seller's **first September call** (37,337 sellers).

| Use case | Sellers | Meeting | Not interested | Call later | Early drop (<10 s) | Median sec |
|---|---:|---:|---:|---:|---:|---:|
| Profile / onboarding | 12,230 | **20.2%** | 16.6% | 18.1% | 13.3% | 35 |
| Discovery | 7,150 | 18.8% | 19.2% | 15.2% | 13.4% | 31 |
| Warm follow-up | 3,590 | 17.7% | 23.7% | **22.4%** | 15.8% | 35 |
| Re-activation | 4,584 | 13.5% | 19.8% | 18.5% | 17.4% | 26 |
| Lead engagement | 3,938 | 10.7% | 21.5% | 16.2% | 20.5% | 22 |
| Free → Paid | 5,845 | **8.5%** | **28.5%** | 12.6% | **25.6%** | 19 |

The spread is 2.4× in meeting rate and 2× in early drop (strong, n in thousands per row). The categories need different personas:
- **Free → paid sellers** hang up fastest and push back most, so they need a quick hook and a non-sales framing.
- **Profile sellers** are the most receptive.
- **Warm sellers** most often defer again, so they need the concrete-slot rule.
- **Discovery's high rate** reflects first-ever calls (first attempts convert at 17% vs 4% by attempt 4+). It is not a sign that the category is well targeted.

## 4. Persona and call plan per category

Common to every category:
- **Guardrails:** personas change delivery, never facts, prices or compliance lines. Say honestly that the caller is IndiaMART's AI assistant if asked. No pressure after two refusals.
- **Shared modules:**
  - **Busy:** ask for a concrete slot, never "rough time bata dijiye".
  - **Identity question:** one line naming IndiaMART and the reason for the call.
  - **IVR / wrong number:** exit at once.
  - **Not the owner:** ask when the owner is free, then end.

Voice gender, pitch and pace are **informed guesses**: no past call varied them. They are a starting point for live adaptation.

### 4.1 Warm follow-up: "Reliable coordinator"
- **Goal:** confirm the meeting or callback the seller agreed to, and lock a slot. Check the meeting really exists, because the bot's own Meeting Fixed label is sometimes wrong.
- **Voice / tone:** calm, warm, medium pace, neutral formality. It should sound like continuity, not a new pitch.
- **Opening:** start with the seller's original action or value, then add the reminder. "Namaste ji, aap buy leads dekh rahe the, aapne kaha tha is time baat karein. Kal 11 baje ya 4 baje, kaunsa theek rahega?"
  - Don't lead with "aap se pehle baat hui thi": it got 13.9% meetings vs 24–29% for an action-or-value opening (moderate).
- **Objection playbook:**
  - **Busy again:** two-option slot ask. Slot ask 32–33% vs callback ask 2–6% (moderate).
  - **Already met an executive:** "unse milne ke baad naye enquiries aaye?" (~20% vs 3% for exiting), then hand off to the same executive.
- **Escalation:** second deferral → route to an executive's calendar. Meeting confirmed → push to MERP.
- **Call:** ~45 s target. Call 19:00–20:00 or at the time the seller named; that time overrides the call gap.

### 4.2 Lead engagement: "Business coach"
- **Goal:** get the seller to reply to the enquiries and PNS calls they already receive. Find out why they don't (fake, irrelevant, too many sellers per lead). Offer a free profile fix so the leads they get are relevant.
- **Voice / tone:** composed, empathetic, slower pace. These are the most sceptical talkers, with the highest frustration (14%), and include the largest, most established sellers.
- **Opening:** name a specific recent enquiry (product or city), not a count. Generic "N enquiries" backfires: 14% vs 28% (weak). Avoid a vague "kaun bol raha hai" moment: ENQR/PNS triggers carry 2× the identity confusion.
- **Objection playbook:**
  - **"Leads fake / 10 logon ko jaati hai":** acknowledge, give the cause ("profile mein details missing hone se galat enquiry aati hai"), then a free fix by an executive. 28–35% vs 19% for empathy alone (moderate).
- **Escalation:** two frustration cues → apologise, offer an executive callback, set COOL_OFF.
- **Call:** ~60 s. Allow longer listening turns.

### 4.3 Free → Paid conversion: "Growth advisor"
- **Goal:** turn shown intent (looked at paid plans, tried to buy BuyLeads) into a free meeting where an executive explains plans. The bot never quotes or negotiates price beyond the fixed script.
- **Voice / tone:** confident, brisk, upbeat, crisp. This category hangs up fastest (25.6% early drop) and pushes back most.
- **Opening:** first sentence names the seller's action neutrally, with a value hook. "Aap paid package / buy leads dekh rahe the — aapki category mein enquiries badhane ke liye 15 min ki free meeting kar sakte hain."
  - **Never** say "aapne payment karne ki koshish ki": 4.6% meetings and 61% not-interested on n=459 (moderate).
  - Frame the meeting as profile and enquiry help, not a sale: 22% vs 16% for a paid-package pitch.
- **Objection playbook:**
  - **"Paise nahi / kitna charge?":** "Meeting bilkul free hai, koi charge nahi; executive options aur monthly plan samjha denge", then a slot ask. 50% vs 14% for empathy alone (moderate, partly reverse-caused).
  - **"Monthly kitna?":** give one honest range from the fixed script, then hand to the executive. Don't stop after the number.
  - **"Free mein kya milta hai?":** "Registration aur basic listing free hai", then continue.
- **Escalation:**
  - Secondary flag thin catalog → switch to the profile-fix angle.
  - Two refusals → exit with a 30-day cool-off.
  - Buying cues ("address / kitne baje / aa jaiye") → confirm the slot at once; these cues carry 59–82% meeting rates.
- **Call:** ~40 s. Highest risk of a rush or language switch: 14% non-Hindi turns on BuyLead calls.

### 4.4 Re-activation: "Respectful check-in"
- **Goal:** find out whether the business is temporarily slow, has changed line, or is closed, then act on the answer:
  - **Temporarily slow:** reschedule.
  - **Changed line:** offer a catalog update.
  - **Closed:** offer profile deactivation, then suppress.
- **Voice / tone:** soft, slow, high empathy, formal (aap/ji). These are the oldest businesses. The theme converts at 4% with 57% not-interested, so the aim is information, not a sale.
- **Opening:** "Namaste ji, IndiaMART se. Kaafi samay se aapke account par activity nahi dikhi — sab theek hai, kaam chal raha hai?"
- **Objection playbook:**
  - **"Kaam band":** one empathetic follow-up, "abhi koi aur vyavsay?", then exit.
  - The enquiry hook gets 0%; don't push it.
- **Escalation:**
  - Business closed → SUPPRESS.
  - Seasonal → callback on the date given.
  - New line of business → move to profile_onboarding.
- **Call:** ~30 s; one ask only.

### 4.5 Profile enrichment and onboarding: "Friendly onboarding guide"
- **Goal:** a free executive visit or call to fix the catalog: photos, products, GST/turnover fields, wrong products listed. NUR (new registration) sellers book meetings at 31%, the best of any trigger.
- **Voice / tone:** warm, encouraging, simple words, a bit slower. 30% of these sellers are new businesses (GST 2025+), who convert at 15% vs 10% overall.
- **Opening:**
  - Use the seller's own gap: "aapki profile mein abhi 3 products hain aur photos nahi — inhe theek karne se enquiries badhti hain; executive free mein set kar denge."
  - The Arrowhead greeting ("Hello ji, kya meri baat X se ho rahi hai?") beats main_vani: 34% vs 23.5%.
- **Objection playbook:**
  - **"Hum retail hai / yeh product hamara nahi":** treat it as a catalog fix, not a refusal.
  - **"Photo kaise add karein?":** explain in one line, then offer a visit.
  - **"Cost?":** free reframe (52% vs 18%).
- **Escalation:** confused → slow down, one step at a time, offer a WhatsApp guide via the executive. Interested → confirm the slot.
- **Call:** ~60 s.

### 4.6 Discovery: "Neutral qualifier"
- **Goal:** two or three questions (what you sell, are you getting enquiries, are you using IndiaMART), then tag the seller into categories 1–5 and offer the matching next step.
- **Voice / tone:** neutral defaults, marked low confidence. Live adaptation does most of the work.
- **Call:** ~40 s.

## 5. Contact gate (before any category)

| Policy | Sellers | Main reasons | Evidence |
|---|---:|---|---|
| SUPPRESS | 4,457 | Asked not to be called; wrong number on the last call; business closed | Later meeting rates 1.9–3.1% vs 6.0% for repeat calls (strong) |
| ROUTE_TO_HUMAN | 4,726 | Open complaint or service ticket; frustration; already working with an executive | Customer-care guardrail rather than outcomes (complaint sellers convert normally) |
| COOL_OFF | 17,929 | 3+ not-interested → 90 days; 2 not-interested, or 4+ calls in 30 days → 30 days; IVR-only → 14 days; bot within 7 days of an executive call → wait 7 days | 2 not-interested → 2.3%; 3 → 1.7% (strong); after an executive call, 6.6% vs 9.8% (moderate) |

- **Not suppression reasons:** asking "are you a bot?" (11.1% vs 11.5%), "already met an executive" alone (5.5%), and a callback request.
- **Fatigue:** meeting rate falls 17.4% → 8.6% → 6.3% → 4.7% → 3.9% by answered call number, and 96% of meetings happen within 4 calls. Today, 59% of repeat calls go out within 2 days, but the rate rises with the gap (2.9% at < 1 h, 9% at 7–14 days).
  - **Rule:** at most 4 answered calls per 30 days; ≥ 3 days' gap (7 preferred); a callback request overrides the gap.
- **Calling window:** on first calls, 19:00–20:00 converts best for every business type (20.4% vs 16–17% at 13–16h). Weekends beat weekdays every month.

## 6. Live adaptation cues (all categories)

| Signal | Cue (seller turn) | Evidence | Persona change |
|---|---|---|---|
| Interest | "address", "bhej do", "aa jaiye", "kitne baje" | 59–82% meeting | Stop pitching, confirm slot |
| False interest | "zaroor" | 12% meeting | Do **not** treat as interest; drop from `live_thresholds.json` |
| Rush | "busy", "baad mein", "driving" | Silence after a rush turn → 2.4% | Shorten; one-line slot ask, or a 2-min same-day callback if driving |
| Frustration | "phone mat", "call mat", "block" | End within 2 turns 51–64% | Apologise, exit, flag DNC |
| Confusion | "kaun bol", "kya?" | Answers not naming IndiaMART end within 2 turns 33–38% vs 12–14% | Slow down; one line: IndiaMART + reason |
| Language switch | English replies | 61% end within 2 turns when the bot stays in Hindi (vs 24%) | Switch to English / the seller's language |

## 7. What to fix before production
1. **Join the real subscription status.** Free → Paid is inferred from intent triggers. A paid flag would split it into conversion vs renewal/upsell.
2. **Confirm the trigger code meanings with the campaign team.** PIM, PAM, OLP, SCHD and NUR are high confidence; PUA, PANF, ENQR and the PNS codes are medium or low.
3. **Treat the eng_* snapshot as undated.** Re-score categories on fresh engagement data before each campaign.
4. **A/B the persona choices.** Effects like the free reframe and the slot ask are partly reverse-caused: the bot asks when the seller is already warm. A per-category A/B test would make them causal.
