"""Disha console: pick a seller, see what goes to Jev and to Disha, start a call, watch it live, read the output.

Run:  .venv/bin/python -I ui/server.py   → open http://localhost:7862

- Seller list: outputs/demo_profiles.json + outputs/custom_profiles.md + outputs/product_sellers.json, plus any
  seller id (built on demand).
- Preview: runs the uploaded code tool's OnStart locally (live Jev, same code as on Samvaad) and records the exact
  Jev request and answers.
- Laptop call: Samvaad SDK websocket with seller_profile as the only per-call variable; live transcript over SSE.
- Phone call (your verified number, DISHA_TEST_PHONE): Samvaad MCP place_test_call (ui/samvaad_mcp.py), the only route to a free test call while the
  workspace has no telephony connection. With SAMVAAD_CONNECTION_ID + SAMVAAD_AGENT_NUMBER in .env it uses the
  public Instant Outbound REST API instead.
- Output: Samvaad analytics REST (interaction variables + transcript) once the call ends; polled during phone calls.
"""
import asyncio
import importlib.util
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ui"))
load_dotenv(ROOT / ".env", override=True)

from sarvam_conv_ai_sdk import AsyncSamvaadAgent  # noqa: E402
from sarvam_conv_ai_sdk.messages.config import InteractionConfig  # noqa: E402
from sarvam_conv_ai_sdk.messages.types import InteractionType, Role, UserIdentifierType  # noqa: E402

import learning  # noqa: E402
import samvaad_mcp  # noqa: E402
from events import bus  # noqa: E402  (ui/events.py)
from sarvam_conv_ai_sdk.audio_interface import AsyncAudioInterface  # noqa: E402

APP_ID = os.getenv("DISHA_APP_ID", "Disha---Ind-85eb0f30-d809")
APP_VERSION = int(os.getenv("DISHA_APP_VERSION", "1"))
PHONE = os.getenv("DISHA_TEST_PHONE", "")  # your verified test number, from .env
# The seller prefilled on the Samvaad dashboard for anyone testing Disha there; restored after each console phone call
DEFAULT_SELLER = os.getenv("DISHA_DEFAULT_SELLER", "")  # seller id from .env; empty = leave the default alone
ORG, WS, KEY = os.environ["SAMVAAD_ORG_ID"], os.environ["SAMVAAD_WORKSPACE_ID"], os.environ["SAMVAAD_API_KEY"]
ANALYTICS = f"https://apps.sarvam.ai/api/analytics/v1/{ORG}/{WS}/{APP_ID}"
OUTBOUND = f"https://apps.sarvam.ai/api/outbounds/v1/orgs/{ORG}/workspaces/{WS}/outbounds"
RUNS = ROOT / "outputs" / "console_runs"
OUTPUT_VARS = ["disposition", "call_summary", "meeting_date", "meeting_time", "seller_notes", "alternate_contact", "use_case",
               "use_case_confidence", "use_case_reason", "persona_style", "seller_history", "switch_log_json",
               "persona_switch_log", "jev_signals", "persona_spec", "persona_notes", "company_name", "city",
               "call_review", "seller_id"]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TEST = _load("test_disha_tools", ROOT / "samvaad" / "code_tool" / "test_disha_tools.py")
T = TEST.T  # the built upload file, samvaad/code_tool/disha_tools.py
_jev_call = T.jev_call
_jev_log: dict = {}


async def _recording_jev_call(api_key, state, questions):
    _jev_log.clear()
    _jev_log.update({"url": T.JEV_URL, "model": T.JEV_MODEL, "state": state, "questions": questions})
    t = time.time()
    try:
        ans = await _jev_call(api_key, state, questions)
        _jev_log.update({"answers": ans, "secs": round(time.time() - t, 2)})
        return ans
    except Exception as e:
        _jev_log.update({"error": f"{type(e).__name__}: {e}", "secs": round(time.time() - t, 2)})
        raise


T.jev_call = _recording_jev_call
app = FastAPI()


# ---- sellers ------------------------------------------------------------------------------------

def _sellers() -> dict[str, dict]:
    out = {}
    for p in json.loads((ROOT / "outputs" / "demo_profiles.json").read_text()):
        out[str(p["seller_id"])] = {"seller_id": str(p["seller_id"]), "company": p.get("company"), "city": p.get("city"),
                                    "state": p.get("state"), "group": "Demo", "label": p.get("label"),
                                    "profile": p["profile"]}
    md = (ROOT / "outputs" / "custom_profiles.md").read_text()
    for head, body in re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", md, re.S | re.M):
        m = re.search(r"```json\n(.+?)\n```", body, re.S)
        if not m:
            continue
        prof = json.loads(m.group(1))
        gen = prof.get("gen") or {}
        sid = str(prof["seller_id"])
        tests = re.search(r"\*\*Tests:\*\* (.+?)\s*$", body, re.M)
        out.setdefault(sid, {"seller_id": sid, "company": gen.get("company"), "city": gen.get("seller_city"),
                             "state": gen.get("seller_state"), "group": "Custom",
                             "label": head.split(":")[0] + (f" · {tests.group(1)}" if tests else ""),
                             "profile": m.group(1)})
    prod = ROOT / "outputs" / "product_sellers.json"  # tools/export_product_sellers.py
    for p in json.loads(prod.read_text()) if prod.exists() else []:
        out.setdefault(str(p["seller_id"]), {"seller_id": str(p["seller_id"]), "company": p.get("company"),
                                             "city": p.get("city"), "state": p.get("state"), "group": "Product data",
                                             "label": p.get("label"), "profile": p["profile"]})
    for f in sorted(RUNS.glob("lookup_*.json")) if RUNS.is_dir() else []:
        p = json.loads(f.read_text())
        out.setdefault(p["seller_id"], p)
    return out


def _rules(profile: str) -> dict:
    return (json.loads(profile).get("rules") or {})


@app.get("/")
async def index():
    return FileResponse(ROOT / "ui" / "index.html")


@app.get("/flow")
async def flow():
    return FileResponse(ROOT / "ui" / "flow.html")


@app.get("/api/sellers")
async def sellers():
    return [{k: v for k, v in s.items() if k != "profile"} | _rules(s["profile"]) for s in _sellers().values()]


@app.get("/api/seller/{seller_id}")
async def seller(seller_id: str):
    s = _sellers().get(seller_id)
    if not s:
        raise HTTPException(404, "unknown seller; use Look up")
    return {**s, "profile_obj": json.loads(s["profile"]), "bytes": len(s["profile"].encode())}


@app.post("/api/lookup/{seller_id}")
async def lookup(seller_id: str):
    """Build a profile for any seller id from the local data (same exporter as the demo set)."""
    if not seller_id.isdigit():
        raise HTTPException(400, "seller id must be a number")
    if seller_id in _sellers():
        return {"seller_id": seller_id}
    exp = _load("export_profiles", ROOT / "tools" / "export_profiles.py")
    try:
        prof = (await asyncio.to_thread(exp.build_profiles, [(int(seller_id), "lookup")]))[0]
    except (Exception, SystemExit) as e:  # the generator raises SystemExit for an unknown seller
        raise HTTPException(404, f"could not build a profile for {seller_id}: {e}")
    RUNS.mkdir(parents=True, exist_ok=True)
    rec = {"seller_id": seller_id, "company": prof.get("company"), "city": prof.get("city"), "state": prof.get("state"),
           "group": "Looked up", "label": "looked up by id", "profile": prof["profile"]}
    (RUNS / f"lookup_{seller_id}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return {"seller_id": seller_id}


_previews: dict[str, dict] = {}
_preview_lock = asyncio.Lock()


def _with_contact(s: dict, contact) -> dict:
    """The seller with an optional contact {name, phone} added to its profile (the PS07 data has neither)."""
    c = {k: str(v).strip() for k, v in (contact or {}).items() if k in ("name", "phone") and str(v or "").strip()}
    if not c:
        return s
    prof = json.loads(s["profile"])
    prof["contact"] = c
    return {**s, "profile": json.dumps(prof, ensure_ascii=False, separators=(",", ":"))}


def _prepare(s: dict, body: dict) -> tuple[dict, dict]:
    """The seller as it will be sent: contact details plus fixes learned from earlier calls (step 2 and 3)."""
    s = _with_contact(s, (body or {}).get("contact"))
    prof, info = learning.profile_with_learning(json.loads(s["profile"]), (body or {}).get("use_learned", True))
    if info:
        s = {**s, "profile": json.dumps(prof, ensure_ascii=False, separators=(",", ":"))}
    return s, info


@app.post("/api/preview/{seller_id}")
async def preview(seller_id: str, request: Request):
    """What Disha will get: OnStart run locally with live Jev (the request and answers are recorded)."""
    s = _sellers().get(seller_id)
    if not s:
        raise HTTPException(404)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    s, learned_info = _prepare(s, body)
    async with _preview_lock:  # the Jev recorder is shared
        _jev_log.clear()
        ctx, dt = await TEST.on_start(s["profile"])
        jev = dict(_jev_log)
    av = dict(ctx.agent_variables)
    tts = ctx.text_to_speech_config
    out = {"seconds": round(dt, 2), "opening": ctx.initial_bot_message,
           "language": getattr(ctx.initial_language_name, "value", str(ctx.initial_language_name)),
           "pace": tts.speech_settings.pace if tts and tts.speech_settings else None,
           "variables": {k: v for k, v in av.items() if k != "seller_profile"},
           "jev": jev or {"skipped": "Jev not called (contact policy, no data or no profile); see jev_signals"},
           "sent_to_samvaad": {"app_id": APP_ID, "app_version": APP_VERSION,
                               "agent_variables": {"seller_profile": s["profile"]}}}
    for k in ("persona_spec", "jev_signals"):
        try:
            out["variables"][k] = json.loads(av.get(k) or "null")
        except ValueError:
            pass
    out["learning"] = learned_info
    _previews[seller_id] = out
    return out


# ---- calls --------------------------------------------------------------------------------------

class BrowserAudio(AsyncAudioInterface):
    """Bridges the page's mic and speaker to the SDK over a local websocket. The browser captures with echo
    cancellation and noise suppression (like Samvaad's own web call), sends 20 ms PCM16 frames at 16 kHz, and plays
    the agent audio it gets back (4-byte little-endian sample rate + PCM16). Text frames carry control messages."""

    def __init__(self):
        self.ws: WebSocket | None = None
        self.connected = asyncio.Event()
        self.input_callback = None

    async def start(self, input_callback):
        self.input_callback = input_callback

    async def feed(self, pcm: bytes):
        if self.input_callback and pcm:
            await self.input_callback(pcm, len(pcm) // 2)

    async def output(self, audio: bytes, sample_rate=None):
        if self.ws:
            try:
                await self.ws.send_bytes(int(sample_rate or 22050).to_bytes(4, "little") + audio)
            except Exception:
                self.ws = None

    def interrupt(self):
        # seller barged in: the page drops whatever agent audio it still has queued
        if self.ws:
            asyncio.ensure_future(self._send_text('{"type":"interrupt"}'))

    async def _send_text(self, text):
        try:
            await self.ws.send_text(text)
        except Exception:
            pass

    async def stop(self):
        ws, self.ws = self.ws, None
        if ws:
            try:
                await ws.send_text('{"type":"end"}')
                await ws.close()
            except Exception:
                pass


def _find_tool_call(x, depth=0):
    """(name, args) of the first tool call found anywhere in a raw platform message, else None."""
    if depth > 6:
        return None
    if isinstance(x, dict):
        fn = x.get("function") if isinstance(x.get("function"), dict) else {}
        name = x.get("tool_name") or x.get("name") or fn.get("name")
        if isinstance(name, str) and name:
            args = next((x[k] for k in ("arguments", "args", "tool_args", "parameters", "input", "params")
                         if k in x), None)
            if args is None and isinstance(x.get("function"), dict):
                args = x["function"].get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"raw": args}
            return name, args if isinstance(args, dict) else {}
        for v in x.values():
            if (hit := _find_tool_call(v, depth + 1)):
                return hit
    elif isinstance(x, list):
        for v in x:
            if (hit := _find_tool_call(v, depth + 1)):
                return hit
    return None


class LiveAgent(AsyncSamvaadAgent):
    """The SDK only surfaces audio and transcripts; this also forwards the platform messages it drops
    (interaction_connected with the variables OnStart set, tool calls, language changes) to the page."""

    call = None

    async def _route_message(self, message):
        try:
            if self.call and isinstance(message, dict):
                await self.call.on_raw(str(message.get("type", "")), message)
        except Exception as e:
            print(f"[console] raw event failed: {type(e).__name__}: {e}")
        await super()._route_message(message)


class Call:
    def __init__(self, seller: dict, mode: str):
        self.sid, self.seller, self.mode = str(uuid.uuid4()), seller, mode
        self.started = time.time()
        self.started_utc = datetime.now(timezone.utc)
        self.interaction_id = None
        self.transcript: list[dict] = []
        self.agent = None
        self.audio = BrowserAudio() if mode == "laptop" else None
        self.task = None
        self.output = None
        self.ended = False
        self.raw_events: list[dict] = []
        self.live_switches: list[dict] = []

    def t(self):
        return round(time.time() - self.started, 1)

    async def end(self):
        """Hang up a browser call / stop watching a phone call. Never leaves a stuck call behind: the SDK does not
        always signal the disconnect after stop(), so the task is cancelled if it has not finished within 3 s."""
        if not self.task or self.task.done():
            return
        if self.agent:
            try:
                await asyncio.wait_for(self.agent.stop(), 3)
            except Exception:
                pass
            try:
                await asyncio.wait_for(asyncio.shield(self.task), 3)
                return
            except Exception:
                pass
        self.task.cancel()  # a browser call's `finally` still fetches the output; a phone watch just stops
        if self.mode != "laptop":
            self.emit("status", {"text": "stopped watching this call"})
            self.emit("ended", {})

    def emit(self, kind, data):
        bus.emit(self.sid, kind, data)

    # browser mic/speaker -> local websocket -> SDK websocket: live transcript
    async def run_laptop(self):
        self.emit("status", {"text": "waiting for the browser microphone…"})
        try:
            await asyncio.wait_for(self.audio.connected.wait(), 20)
        except asyncio.TimeoutError:
            self.emit("status", {"error": "the page did not connect its microphone"})
            self.ended = True
            self.emit("ended", {})
            return
        cfg = InteractionConfig(org_id=ORG, workspace_id=WS, app_id=APP_ID, version=APP_VERSION,
                                user_identifier=f"console-{self.seller['seller_id']}",
                                user_identifier_type=UserIdentifierType.CUSTOM, interaction_type=InteractionType.CALL,
                                sample_rate=16000, agent_variables={"seller_profile": self.seller["profile"]})
        self.agent = LiveAgent(api_key=SecretStr(KEY), config=cfg, audio_interface=self.audio,
                               transcript_callback=self.on_transcript, event_callback=self.on_event)
        self.agent.call = self
        self.emit("status", {"text": "connecting to Samvaad…"})
        try:
            await self.agent.start()
            if not await self.agent.wait_for_connect(20):
                self.emit("status", {"error": "could not connect to Samvaad"})
                return
            self.emit("status", {"text": "live: speak now", "phase": "live"})
            await self.agent.wait_for_disconnect()
        except Exception as e:
            self.emit("status", {"error": f"{type(e).__name__}: {e}"})
        finally:
            try:
                await self.agent.audio_interface.stop()
            except Exception:
                pass
            self.emit("status", {"text": "call ended, fetching output…", "phase": "ended"})
            await self.fetch_output()

    async def on_raw(self, kind: str, msg: dict):
        if "audio" in kind:
            return
        if "interaction_connected" in kind:
            av = msg.get("agent_variables") or {}
            spec, sig = {}, {}
            try:
                spec = json.loads(av.get("persona_spec") or "{}")
                sig = json.loads(av.get("jev_signals") or "{}")
            except ValueError:
                pass
            ap = spec.get("applied") or {}
            self.interaction_id = msg.get("interaction_id") or self.interaction_id
            self.emit("connected", {
                "interaction_id": self.interaction_id, "company": av.get("company_name"), "city": av.get("city"),
                "use_case": av.get("use_case"), "confidence": av.get("use_case_confidence"),
                "reason": av.get("use_case_reason"), "style": av.get("persona_style"),
                "history": av.get("seller_history"), "language": msg.get("initial_language_name") or ap.get("start_language"),
                "pace": ap.get("pace"), "opening": ap.get("opening_line"), "signals": sig.get("signals") or {},
                "jev_source": sig.get("source"), "policy": (spec.get("contact_policy") or {}).get("policy"),
                "learned": ap.get("learned_overrides") or [], "nudge_budget": ap.get("nudge_budget")})
            if ap.get("opening_line"):  # the SDK does not echo the opening line as a transcript
                row = {"t": 0, "who": "Disha", "text": ap["opening_line"]}
                self.transcript.append(row)
                self.emit("transcript", row)
            return
        self.raw_events.append({"t": self.t(), "type": kind, "msg": msg})
        self.emit("raw", {"t": self.t(), "type": kind})
        hit = _find_tool_call(msg) if "tool" in kind or "function" in kind else None
        if hit and hit[0] == "persona_switch":
            a = hit[1]
            sw = {"t_sec": self.t(), "signal": str(a.get("signal") or "?").lower(), "seller_words": a.get("seller_words"),
                  "change": a.get("change"), "reason": a.get("reason"), "new_language": a.get("new_language"),
                  "source": "live"}
            self.live_switches.append(sw)
            self.emit("switch", sw)
            if a.get("new_language"):
                self.emit("language", {"language": a["new_language"]})
        elif "language" in kind:
            data = msg.get("data") if isinstance(msg.get("data"), dict) else msg
            lang = data.get("language_name") or data.get("language") or data.get("new_language")
            if lang:
                self.emit("language", {"language": lang})

    async def on_transcript(self, msg):
        text = (msg.content or "").strip()
        if text:
            row = {"t": self.t(), "who": "Disha" if msg.role == Role.BOT else "Seller", "text": text}
            self.transcript.append(row)
            self.emit("transcript", row)

    async def on_event(self, ev):
        iid = getattr(ev, "interaction_id", None)
        if iid and iid != self.interaction_id:
            self.interaction_id = iid
            self.emit("status", {"interaction_id": iid})

    # phone: MCP test call (or REST outbound), then poll analytics
    async def run_phone(self):
        try:
            if not PHONE:
                raise RuntimeError("set DISHA_TEST_PHONE (your verified number) in .env")
            if os.getenv("SAMVAAD_CONNECTION_ID") and os.getenv("SAMVAAD_AGENT_NUMBER"):
                async with httpx.AsyncClient(timeout=30, headers={"X-API-Key": KEY}) as c:
                    r = await c.post(OUTBOUND, json={
                        "app_config": {"app_id": APP_ID, "app_version": APP_VERSION,
                                       "connection_config": {"connection_id": os.environ["SAMVAAD_CONNECTION_ID"],
                                                             "agent_phone_number": os.environ["SAMVAAD_AGENT_NUMBER"]},
                                       "agent_variables": {"seller_profile": self.seller["profile"]}},
                        "user_config": {"user_phone_number": PHONE}})
                    r.raise_for_status()
                    res = r.json()
            else:
                # place_test_call ignores per-call variables (checked 2026-10-09: calls ran with the draft default),
                # so the draft's seller_profile default is set to this seller first
                self.emit("status", {"text": "setting this seller on Disha's draft…"})
                await samvaad_mcp.call_tool("configure_agent", {"agent_id": APP_ID, "config": {"llm_config": {
                    "agent_config": {"agent_variables": {"seller_profile": {
                        "name": "seller_profile", "value": self.seller["profile"]}}}}}})
                res = await samvaad_mcp.call_tool("place_test_call", {
                    "app_id": APP_ID, "app_version": APP_VERSION, "phone_numbers": [PHONE],
                    "app_variables": {"seller_profile": self.seller["profile"]}})
            self.emit("status", {"text": f"ringing {PHONE[:-4]}xxxx… answer your phone", "phase": "ringing", "placed": res})
        except Exception as e:
            self.emit("status", {"error": f"call not placed: {type(e).__name__}: {e}"})
            self.ended = True
            self.emit("ended", {})
            return
        try:
            await self.poll_phone()
        finally:
            await restore_default_seller()

    async def poll_phone(self):
        """The REST API has no live stream for phone calls: find the interaction, then show the transcript as soon
        as Samvaad publishes it (normally right after hang-up)."""
        seen, deadline = 0, time.time() + 20 * 60
        while time.time() < deadline:
            await asyncio.sleep(4)
            try:
                if not self.interaction_id:
                    it = await self._find_interaction()
                    if it:
                        self.interaction_id = it["interaction_id"]
                        self.emit("status", {"interaction_id": self.interaction_id, "text": "call found on Samvaad", "phase": "found"})
                    continue
                msgs = await self._transcript()
                for m in msgs[seen:]:
                    row = {"t": None, "who": "Disha" if m.get("role") == "assistant" else "Seller",
                           "text": m.get("content", "")}
                    self.transcript.append(row)
                    self.emit("transcript", row)
                seen = max(seen, len(msgs))
                it = await self._find_interaction(self.interaction_id)
                if it and it.get("end_datetime") and (it.get("agent_variables") or {}).get("disposition") is not None:
                    self.emit("status", {"text": "call ended, fetching output…", "phase": "ended"})
                    await self.fetch_output()
                    return
            except Exception as e:
                self.emit("status", {"text": f"waiting for Samvaad ({type(e).__name__})"})
        self.emit("status", {"error": "no call output after 20 minutes"})

    async def _find_interaction(self, iid=None):
        cond = [{"id": "1", "field": "interaction_id", "operator": "equals", "value": iid}] if iid else None
        params = {"start_datetime": (self.started_utc - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "end_datetime": (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "limit": 5, "sort_by": "start_datetime", "sort_order": "desc"}
        if cond:
            params["filter_conditions"] = json.dumps(cond)
        async with httpx.AsyncClient(timeout=20, headers={"X-API-Key": KEY}) as c:
            r = await c.get(f"{ANALYTICS}/interactions", params=params)
            r.raise_for_status()
            items = r.json().get("items") or []
        if iid:
            return next((i for i in items if i["interaction_id"] == iid), None)
        # the newest phone interaction that started after this call was placed (browser calls are "console-…")
        t0 = (self.started_utc - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%S")
        return next((i for i in items if not str(i.get("user_identifier", "")).startswith("console-")
                     and str(i.get("start_datetime") or "") >= t0), None)

    async def _transcript(self):
        async with httpx.AsyncClient(timeout=20, headers={"X-API-Key": KEY}) as c:
            r = await c.get(f"{ANALYTICS}/transcripts/{self.interaction_id}")
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.json().get("messages") or []

    async def fetch_output(self):
        # Samvaad publishes the interaction record some time after hang-up (seen: more than 30 s), and OnEnd's Jev
        # check lands a few seconds later still, so wait up to 2 minutes for a record that OnEnd has finished.
        it, t0, seen_log = None, time.time(), None
        while self.interaction_id and time.time() - t0 < 120:
            try:
                it = await self._find_interaction(self.interaction_id) or it
            except Exception as e:
                print(f"[console] interaction lookup failed: {type(e).__name__}: {e}")
            av = (it or {}).get("agent_variables") or {}
            if it and it.get("end_datetime") and av.get("switch_log_json"):
                seen_log = seen_log or time.time()
                if av.get("call_review") or "call_review" not in av or time.time() - seen_log > 15:
                    break
            self.emit("status", {"text": f"waiting for Samvaad to publish the call record… {int(time.time() - t0)} s",
                                 "phase": "ended"})
            await asyncio.sleep(4)
        av = dict((it or {}).get("agent_variables") or {})
        out = {k: av.get(k) for k in OUTPUT_VARS if k in av}
        for k in ("switch_log_json", "jev_signals", "persona_spec", "call_review"):
            try:
                out[k] = json.loads(out[k]) if isinstance(out.get(k), str) and out[k] else out.get(k)
            except ValueError:
                pass
        meta = {k: (it or {}).get(k) for k in ("interaction_id", "duration_in_seconds", "start_datetime",
                                                 "end_datetime", "language_name", "num_messages", "ended_by",
                                                 "failure_reason", "channel_type")}
        try:
            transcript = await self._transcript() if self.interaction_id else []
        except Exception:
            transcript = []
        self.output = {"meta": meta, "output": out, "transcript": transcript,
                       "pending": bool(self.interaction_id) and not it, "interaction_id": self.interaction_id,
                       "learning_used": getattr(self, "learning", {}) or {}}
        if it:
            self.output.update(await review_and_learn(self.seller, self.interaction_id, out, transcript))
        RUNS.mkdir(parents=True, exist_ok=True)
        path = RUNS / f"call_{self.seller['seller_id']}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps({"seller_id": self.seller["seller_id"], "mode": self.mode, **self.output,
                                    "live_transcript": self.transcript, "live_switches": self.live_switches,
                                    "raw_events": self.raw_events}, ensure_ascii=False, indent=1, default=str))
        self.ended = True
        self.emit("output", {**self.output, "saved": str(path.relative_to(ROOT))})
        self.emit("ended", {})


def _call1_from_vars(av: dict) -> dict:
    """What Call 1 decided, rebuilt from the interaction's variables (for calls reviewed by the console)."""
    spec = av.get("persona_spec") if isinstance(av.get("persona_spec"), dict) else {}
    ap = spec.get("applied") or {}
    return {"use_case": av.get("use_case"), "use_case_confidence": av.get("use_case_confidence"),
            "use_case_reason": (av.get("use_case_reason") or "")[:400], "persona_style": av.get("persona_style"),
            "pace": ap.get("pace"), "start_language": ap.get("start_language"), "opening_line": ap.get("opening_line"),
            "contact_policy": (spec.get("contact_policy") or {}).get("policy"),
            "learned_overrides": ap.get("learned_overrides") or [], "nudge_budget": ap.get("nudge_budget")}


async def review_and_learn(seller: dict, iid: str, out: dict, transcript: list) -> dict:
    """Step 1 and 2 after a call: use Samvaad's review (OnEnd) or, if the uploaded code tool predates the review,
    run the same review here; then store it and update this seller's fixes for the next call."""
    review = out.get("call_review") if isinstance(out.get("call_review"), dict) else None
    if not review or review.get("status") == "unavailable":
        turns = [{"i": i, "role": "agent" if m.get("role") == "assistant" else "seller", "text": m.get("content", "")}
                 for i, m in enumerate(transcript or [])]
        if sum(1 for t in turns if t["role"] == "seller") >= T.REVIEW_MIN_SELLER_TURNS:
            try:
                sl = out.get("switch_log_json") if isinstance(out.get("switch_log_json"), dict) else {}
                review, _ = await asyncio.wait_for(T.review_call(
                    TEST.KEY, _call1_from_vars(out), turns, trail=T.language_trail(sl.get("switches")),
                    translated=False), 15)
                review["source"] = "console"
            except Exception as e:
                review = {"version": 1, "status": "unavailable", "why": f"{type(e).__name__}: {e}"[:200]}
        else:
            review = review or {"version": 1, "status": "skipped", "why": "fewer than 3 seller turns"}
    if seller.get("seller_id") == "lookup":  # a past interaction opened by id: find its seller
        seller = _sellers().get(str(out.get("seller_id") or "")) or {}
    next_fixes = learning.record(seller, iid, review) if seller.get("profile") else {}
    return {"review": review, "next_call": next_fixes}


current: dict = {"call": None}


async def restore_default_seller():
    """Put the dashboard's prefilled seller back (phone calls borrow the draft's seller_profile default)."""
    s = _sellers().get(DEFAULT_SELLER)
    if not s:
        return
    try:
        await samvaad_mcp.call_tool("configure_agent", {"agent_id": APP_ID, "config": {"llm_config": {"agent_config": {
            "agent_variables": {"seller_profile": {"name": "seller_profile", "value": s["profile"]}}}}}})
    except Exception as e:  # never fail a call over the dashboard default
        print(f"[console] could not restore the default seller: {type(e).__name__}: {e}")


@app.post("/api/call")
async def start_call(body: dict):
    s = _sellers().get(str(body.get("seller_id")))
    mode = body.get("mode")
    if not s or mode not in ("laptop", "phone"):
        raise HTTPException(400, "seller_id and mode (laptop|phone) required")
    policy = _rules(s["profile"]).get("contact_policy")
    if policy in ("SUPPRESS", "ROUTE_TO_HUMAN") and not body.get("allow_blocked"):
        raise HTTPException(403, "This seller asked not to be called (SUPPRESS); they must not be dialled."
                            if policy == "SUPPRESS" else
                            "This seller should be handled by an IndiaMART executive (ROUTE_TO_HUMAN), not the bot.")
    prev = current["call"]
    if prev:
        await prev.end()  # one call at a time: a new call always ends (or stops watching) the previous one
    s, info = _prepare(s, body)
    call = Call(s, mode)
    call.learning = info
    current["call"] = call
    call.task = asyncio.create_task(call.run_laptop() if mode == "laptop" else call.run_phone())
    return {"session_id": call.sid}


@app.post("/api/hangup")
async def hangup():
    c = current["call"]
    if c:
        await c.end()
    return {"ok": True}


@app.get("/api/output/{interaction_id:path}")
async def output_for(interaction_id: str):
    """Output of any past Disha interaction (e.g. a call placed from the Samvaad UI)."""
    c = Call({"seller_id": "lookup", "profile": "{}"}, "lookup")
    c.lookup = True
    c.interaction_id = interaction_id
    c.started_utc = datetime.now(timezone.utc) - timedelta(days=7)
    c.emit = lambda *a: None
    await c.fetch_output()
    return c.output


@app.get("/api/learned/{seller_id}")
async def get_learned(seller_id: str):
    s = _sellers().get(seller_id)
    _, info = _prepare(s, {}) if s else ({}, {})
    return {"own": learning.learned(seller_id), "applied": info.get("overrides") or {}, "rules": info.get("rules") or [],
            "history": learning.history(seller_id)[-5:]}


@app.delete("/api/learned/{seller_id}")
async def clear_learned(seller_id: str):
    learning.clear(seller_id)
    return {"ok": True}


@app.get("/api/insights")
async def insights():
    return learning.insights()


@app.post("/api/insights/{rule_id}/{action}")
async def rule_action(rule_id: str, action: str):
    if action not in ("approved", "dismissed", "reset"):
        raise HTTPException(400, "action must be approved, dismissed or reset")
    try:
        learning.set_status(rule_id, action)
    except KeyError:
        raise HTTPException(404, "unknown suggestion")
    return learning.insights()


@app.post("/api/review/call/{interaction_id:path}")
async def rereview(interaction_id: str):
    """Review one call again with the console's review (original-language transcript + language trail)."""
    c = Call({"seller_id": "lookup", "profile": "{}"}, "lookup")
    c.interaction_id, c.started_utc = interaction_id, datetime.now(timezone.utc) - timedelta(days=7)
    it = await c._find_interaction(interaction_id)
    if not it:
        raise HTTPException(404, "interaction not found")
    av = dict(it.get("agent_variables") or {})
    out = {k: av.get(k) for k in OUTPUT_VARS if k in av}
    for k in ("persona_spec", "switch_log_json"):
        try:
            out[k] = json.loads(out[k]) if isinstance(out.get(k), str) and out[k] else out.get(k)
        except ValueError:
            pass
    out["call_review"] = None  # force the console's review
    seller = _sellers().get(str(av.get("seller_id") or "")) or {"seller_id": "lookup"}
    return await review_and_learn(seller, interaction_id, out, await c._transcript())


@app.post("/api/review/recent")
async def review_recent(body: dict | None = None):
    """Review Disha's recent calls that have no stored review yet (so step 3 has data from earlier calls)."""
    days = int((body or {}).get("days", 3))
    done, sellers = learning.reviewed_ids(), _sellers()
    params = {"start_datetime": (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "end_datetime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 100}
    async with httpx.AsyncClient(timeout=30, headers={"X-API-Key": KEY}) as c:
        r = await c.get(f"{ANALYTICS}/interactions", params=params)
        r.raise_for_status()
        items = r.json().get("items") or []
    todo = [i for i in items if i["interaction_id"] not in done and (i.get("duration_in_seconds") or 0) >= 20
            and str((i.get("agent_variables") or {}).get("seller_id") or "") in sellers]
    results = []

    async def one(i):
        c = Call(sellers[str(i["agent_variables"]["seller_id"])], "lookup")
        c.interaction_id = i["interaction_id"]
        av = dict(i.get("agent_variables") or {})
        out = {k: av.get(k) for k in OUTPUT_VARS if k in av}
        for k in ("persona_spec", "call_review"):
            try:
                out[k] = json.loads(out[k]) if isinstance(out.get(k), str) and out[k] else out.get(k)
            except ValueError:
                pass
        res = await review_and_learn(c.seller, c.interaction_id, out, await c._transcript())
        results.append({"interaction_id": c.interaction_id, "company": c.seller.get("company"),
                        "status": res["review"].get("status")})

    for k in range(0, len(todo), 4):  # a few at a time
        await asyncio.gather(*(one(i) for i in todo[k:k + 4]), return_exceptions=True)
    return {"checked": len(items), "reviewed": sum(1 for x in results if x["status"] == "reviewed"),
            "skipped": sum(1 for x in results if x["status"] != "reviewed"), "calls": results}


@app.websocket("/ws/audio/{session_id}")
async def audio_ws(ws: WebSocket, session_id: str):
    c = current["call"]
    if not c or c.sid != session_id or not c.audio:
        await ws.close(code=4404)
        return
    await ws.accept()
    c.audio.ws = ws
    c.audio.connected.set()
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes"):
                await c.audio.feed(msg["bytes"])
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        c.audio.ws = None
        if c.agent and c.task and not c.task.done():  # page closed or hung up: end the call
            try:
                await c.agent.stop()
            except Exception:
                pass


@app.get("/api/events/{session_id}")
async def events(session_id: str, request: Request):
    async def stream():
        q = bus.subscribe(session_id)
        try:
            while not await request.is_disconnected():
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(session_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "7862")))
