# Disha: an adaptive voice agent for IndiaMART seller calls

Disha is one Samvaad (Sarvam) voice agent whose persona is rebuilt for every seller before she speaks, adapts live
during the call, and learns from each call for the next one.

## How a call works

1. **Sort the sellers**: a contact gate (do not call / executive only / go gently / OK), then a call purpose.
2. **Prepare the seller file**: one compact `seller_profile` JSON per seller.
3. **Start the call** from the Disha Console (browser or phone).
4. **OnStart code tool** (on Samvaad, before the first word): contact rule, call purpose via Jev (TypeSafe),
   persona generator, nudge budget, learned fixes, opening line.
5. **The conversation**: live persona switches (rush, confusion, frustration, interest, language, bot question).
6. **OnEnd code tool**: one Jev request verifies each switch and reviews the call.
7. **Fix loop**: safe fixes go into the seller's next call; patterns across sellers become rules you approve.

## Layout

| Path | What it is |
|---|---|
| `generator/` | Persona generator (evidence-backed delivery, language, tone, plan) |
| `samvaad/code_tool/disha_tools_src.py` | Samvaad code tool source (OnStart, PersonaSwitch, OnEnd) |
| `tools/build_code_tool.py` | Builds the single uploadable `samvaad/code_tool/disha_tools.py` |
| `samvaad/disha_prompt.md` | Disha's prompt |
| `ui/` | Disha Console: seller list, Jev preview, live call screen, call output, Insights, Flow |
| `outputs/segmentation/scripts/` | Data analysis and segmentation scripts |
| `outputs/video/` | Voice-over build and mix scripts for the explainer video |

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # or uv
cp .env.example .env   # fill in your keys
.venv/bin/python -I tools/build_code_tool.py            # build the code tool to upload to Samvaad
.venv/bin/python -I samvaad/code_tool/test_disha_offline.py
.venv/bin/python -I ui/server.py                        # console at http://localhost:7862
```

## Not in this repository

Seller data (the PS07 datasets and everything derived from it: profiles, call logs, transcripts, reviews) and
`.env` are kept out on purpose. The console, the live tests and the analysis scripts need that data locally;
the offline code-tool tests and the code itself do not.
