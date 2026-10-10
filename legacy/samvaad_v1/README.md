# VANI persona agent — Samvaad version

Same persona generator and evidence as v1 (`agent/`), but the call runs on Sarvam's hosted
Voice Agents platform (Samvaad).

- **Demo agent (default):** `Paayal - IndiaMART Profile Enrichment Scheduler` (`Conversatio-5a1ffa80-ec16`,
  committed version 4). Prompt: `paayal_prompt.md` (the live version omits the `*Switch log:*` bullet until the
  `log_persona_switch` tool is added). Per call, `paayal_overrides()` sends `persona_style`, `seller_history`,
  `persona_notes` (the full spec with reasons and confidence), the persona's opening line, a female v4 voice and pace.
  Select it with `SAMVAAD_AGENT=paayal` and `SAMVAAD_PAAYAL_APP_ID` / `SAMVAAD_PAAYAL_APP_VERSION` in `.env`.
- **Earlier agent:** `VANI Seller-Fit Persona` (`VANI-Seller-a9d5d708-2376`, committed version 1), used with
  `SAMVAAD_AGENT=vani`. Prompt: `agent_prompt.md`. Config: `agent_config.json`.
- **Per call:** `persona_to_samvaad.py` turns `outputs/personas/<id>.json` into agent variables,
  the persona's opening line, the start language, a v4 voice and pace.
- **Live switches:** the agent calls its `log_persona_switch` API tool (signal, seller's words,
  change, reason) → `POST /samvaad/switch` on our server via a cloudflared tunnel. Language
  switches are done by Samvaad itself (no event is sent), so our local detector records them.

## Run a live demo (laptop mic)

```bash
cd persona-agent
tools/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:7861   # terminal 1, keep open
.venv/bin/python -m samvaad.server                                        # terminal 2
# open http://localhost:7861, pick a ★ seller, Start call, talk (headphones recommended)
```

**The tunnel URL changes every time cloudflared restarts.** The agent's `log_persona_switch`
tool must point at the current one (`<tunnel>/samvaad/switch`): ask Claude to update it via the
Samvaad MCP, or edit the tool URL in the Samvaad console, then commit a new version and set
`SAMVAAD_APP_VERSION` in `.env`. Without it the call still works; only agent-reported switches
are lost (the local detector still logs).

## Test without a mic

```bash
# stop samvaad.server first (the sim hosts the webhook itself); tunnel must be up
.venv/bin/python -m tools.sim_samvaad --seller 56730 --scenario hindi_mix
.venv/bin/python -m tools.sim_samvaad --seller 181758742 --scenario frustrated
```

Logs: `outputs/switch_logs/samvaad_<seller>_<id>.json` (agent switches, local detector hits,
transcript). Agent audio: `outputs/sim_calls/samvaad_*.wav`.
