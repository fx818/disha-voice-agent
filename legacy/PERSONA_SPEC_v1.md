# Persona spec contract

The generator writes one JSON per seller to `outputs/personas/<seller_id>.json`.
The live agent (`agent/`) reads it. Every setting carries `reason` (tied to seller data)
and `confidence` (`high` = backed by past-call evidence, `medium` = weak evidence,
`low` = default / informed guess, e.g. because a field was missing).

```json
{
  "seller_id": "39323",
  "seller_snapshot": {"company": "...", "city": "Jaipur", "state": "Rajasthan", "business_type": "...",
                      "turnover": "...", "nature": "...", "top_categories": ["..."], "segment": "short label"},
  "voice": {
    "speaker": "priya",          // bulbul:v3 voice id
    "gender": "female",
    "pace": 1.0,                 // 0.5–2.0
    "temperature": 0.6,          // expressiveness 0.01–1.0
    "reason": "...", "confidence": "medium"
  },
  "language": {
    "language_code": "hi-IN",    // Sarvam code used for TTS
    "english_mix": 0.3,          // 0 = pure regional, 1 = full English (Hinglish share)
    "formality": "formal",       // formal (aap, ji) | neutral | casual
    "reason": "...", "confidence": "medium"
  },
  "tone": {
    "warmth": "high",            // low | medium | high
    "empathy": "medium",
    "energy": "calm",            // calm | neutral | upbeat
    "reason": "...", "confidence": "low"
  },
  "plan": {
    "opening":        {"approach": "...", "example_line": "...", "reason": "...", "confidence": "..."},
    "personalisation": [{"hook": "...", "reason": "..."}],
    "objection_playbook": [{"objection": "busy / call later", "approach": "...", "reason": "...", "evidence": "..."}],
    "escalation_rules":  [{"trigger": "...", "action": "...", "reason": "..."}],
    "target_call_sec": 60
  },
  "guardrails": ["Personas change delivery only, never facts, pricing or compliance statements.", "..."],
  "evidence_refs": ["E3", "E7"]   // ids into outputs/evidence.json
}
```

Fixed facts the bot may state (identical for every persona) live in `generator/fixed_script.py`.
