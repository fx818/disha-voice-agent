# Switch logs from live calls

Every switch Disha makes is logged by the `persona_switch` tool during the call (time, signal, the seller's words, the change, the reason, language before and after) and checked by Jev after the call (`verified_signal`: how strongly the transcript supports the signal). The post-call summary (`persona_switch_log`) is written by Samvaad's post-call LLM.

## demo-1: Demo 1 in the video: free to paid, brisk seller (Seller A in the persona samples)

Purpose `free_to_paid` · outcome `callback_requested` · 104 s · [demo-1.json](demo-1.json)

No switch was logged by the tool during this call.

Post-call summary: language switch -> change made to Bengali -> user spoke in Bengali

Call summary: The agent spoke with the business owner and then their sales executive; the executive requested a callback today at 5 PM to schedule the meeting.

## demo-2: Demo 2 in the video: profile help (Seller B in the persona samples)

Purpose `profile_onboarding` · outcome `meeting_scheduled` · 77 s · [demo-2.json](demo-2.json)

No switch was logged by the tool during this call.

Post-call summary: none

Call summary: The agent contacted the seller from the seller's company to offer free profile enrichment for their Acrylic Paints catalogue, and a meeting was scheduled.

## call-rush: Lead engagement seller, phone call (no video)

Purpose `lead_engagement` · outcome `callback_requested` · 92 s · [call-rush.json](call-rush.json)

| Time | Signal | Seller said | Change | Reason | Jev |
|---|---|---|---|---|---|
| 21.6 s | rush | हाँ बताइए सर, जल्दी बताइए। | dropping pleasantries, moving straight to point | User sounds hurried and asked to be quick. | 0.86 |

Post-call summary: rush -> change made -> agent acknowledged the user's busy status and shifted to scheduling a future callback

Call summary: The seller was too busy to talk and requested a callback for next week, though they did not specify a particular day or time.

## Known gap

In demo-1 the seller handed the phone to a colleague who spoke Bengali. Disha switched to Bengali and handled a busy reply, but did not call `persona_switch`, so the timed log is empty; only the post-call summary records the language switch. A post-call backfill (compare each seller turn's language with the previous one and add missed switches, marked as detected after the call) is the planned fix.
