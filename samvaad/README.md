# Samvaad (Disha's agent)

| Path | What it is |
|---|---|
| [`disha_prompt.md`](disha_prompt.md) | Disha's prompt, deployed to the agent's draft. `{{persona_notes}}` must appear only once. |
| [`code_tool/disha_tools_src.py`](code_tool/disha_tools_src.py) | Code tool source: OnStart (purpose via Jev, persona, call plan, seller brief, opening), `persona_switch` (live switch log), OnEnd (switch verification and call review via Jev) |
| `code_tool/disha_tools.py` | The single file uploaded to Samvaad, built by `tools/build_code_tool.py` (bundles the generator) |
| [`code_tool/test_disha_offline.py`](code_tool/test_disha_offline.py) | Offline tests (no network) |
| [`code_tool/test_disha_tools.py`](code_tool/test_disha_tools.py) | Live tests against Jev |
| `prompt_history/` | Earlier prompt versions, one file per change |

```bash
.venv/bin/python -I tools/build_code_tool.py                  # then upload code_tool/disha_tools.py to the draft
.venv/bin/python -I samvaad/code_tool/test_disha_offline.py
```
