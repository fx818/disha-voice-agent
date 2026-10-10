"""Loaders for the PS07 dataset. Stack split files and cache as parquet."""
import glob
import json
import os
from pathlib import Path

import pandas as pd

DATA_ROOT = Path(os.environ.get(
    "PS_DATA_ROOT",
    "/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files",
))
D1 = DATA_ROOT / "Seller-Fit Adaptive Voice Persona - Dataset 1 of 3"
D2 = DATA_ROOT / "Seller-Fit Adaptive Voice Persona - Dataset 2 of 3"
D3 = DATA_ROOT / "Seller-Fit Adaptive Voice Persona - Dataset 3 of 3"
CACHE = Path(__file__).resolve().parent.parent / "outputs" / "cache"


def _cached(name, build):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    df = build()
    df.to_parquet(p, index=False)
    return df


def _stack(pattern, **kw):
    files = sorted(glob.glob(str(pattern)))
    return pd.concat([pd.read_csv(f, **kw) for f in files], ignore_index=True)


def sellers():
    return _cached("sellers", lambda: _stack(D1 / "ps07_seller_files_part*.csv",
                                             dtype={"fk_glusr_usr_id": "int64", "seller_pincode": "string"}))


def bot_calls():
    def build():
        df = _stack(D2 / "ps07_bot_calls_*.csv")
        df["call_start_time"] = pd.to_datetime(df["call_start_time"])
        return df
    return _cached("bot_calls", build)


def evaluator(agent=None):
    df = _cached("evaluator", lambda: _stack(D3 / "ps07_evaluator_outputs_*.csv"))
    if agent:
        df = df[df.eval_agent == agent].copy()
        df["out"] = df.agent_output.map(_safe_json)
    return df


def call_turns():
    return _cached("call_turns", lambda: pd.read_csv(D1 / "ps07_call_turns.csv"))


def executive_calls():
    return _cached("exec_calls", lambda: pd.read_csv(D1 / "ps07_executive_calls.csv"))


def _safe_json(s):
    try:
        return json.loads(s)
    except Exception:
        return {}
