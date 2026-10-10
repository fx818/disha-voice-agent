# Samples

What Disha produces for real sellers from the PS07 data, anonymised for this repository (company names become
"Seller A", "Seller B", ...; seller ids and phone numbers are removed). Everything else is exactly what the code builds.

| Folder | What is in it |
|---|---|
| [`personas/`](personas/) | Persona spec per sample seller: every choice (call purpose, persona, voice, language, tone, opening, conversation plan, nudges) with its reason, confidence and evidence ids. Start with [`personas/PERSONA_SPECS.md`](personas/PERSONA_SPECS.md); one JSON per seller. |
| [`switch_logs/`](switch_logs/) | Switch logs from live calls on Samvaad, including the two calls in the demo video. Start with [`switch_logs/SWITCH_LOGS.md`](switch_logs/SWITCH_LOGS.md). |

Regenerate the persona samples with `.venv/bin/python -I tools/export_specs.py` (needs the seller data locally and the
Disha Console running; it writes the real specs to `outputs/` and this anonymised copy here).
