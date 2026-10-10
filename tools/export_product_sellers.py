"""Pick test sellers from `product data.csv` for the Disha Console ("Product data" group).

A good test seller can be talked to properly for its call purpose:
  - contact policy OK_TO_CALL, a company name, at least one real call (>= 30 s) and no wrong-number summary
    (export_profiles.candidates);
  - in a state where past calls were in Hindi (so a Hindi/English speaker can test it);
  - answered at least 2 bot calls with an average answered call of 30 s or more, no frustration on record, and the
    latest call did not end in Not Interested;
  - for profile onboarding: clear catalog gaps (a quarter of products without a photo or half without a price).
Ranked by answered calls, then average call length. With --verify, each candidate is run through
Disha's OnStart with live Jev (as the console preview does) and kept only when the purpose Disha
actually picks matches its rules label and it starts in Hindi or English.

Usage: .venv/bin/python -I tools/export_product_sellers.py [--verify]   -> outputs/product_sellers.json
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import export_profiles as ex  # noqa: E402
from data_prep.load import product_gaps  # noqa: E402

PER_USE_CASE = {"profile_onboarding": 5, "free_to_paid": 3, "lead_engagement": 3, "warm_followup": 2,
                "reactivation": 2}
HINDI_STATES = {"Uttar Pradesh", "Delhi", "Haryana", "Rajasthan", "Madhya Pradesh", "Bihar", "Uttarakhand",
                "Himachal Pradesh", "Jharkhand", "Chhattisgarh", "Punjab", "Chandigarh", "Gujarat", "Maharashtra"}
OUT = ROOT / "outputs" / "product_sellers.json"


def strong_gaps(r) -> bool:
    return r.products_without_image / r.total_product_count >= 0.25 or r.products_without_price / r.total_product_count >= 0.5


_TEST = None


def live_check(profile: str) -> tuple[str, str]:
    """(use case, start language) Disha picks for this profile: OnStart run locally with live Jev, as the console
    preview does."""
    global _TEST
    if _TEST is None:
        spec = importlib.util.spec_from_file_location("test_disha_tools", ROOT / "samvaad" / "code_tool" / "test_disha_tools.py")
        _TEST = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_TEST)
    ctx, _ = asyncio.run(_TEST.on_start(profile))
    lang = getattr(ctx.initial_language_name, "value", str(ctx.initial_language_name))
    return ctx.agent_variables["use_case"], lang


def pick(verify=False) -> list[tuple[int, str]]:
    gaps = product_gaps().set_index("fk_glusr_usr_id")
    sel = pd.read_parquet(ex.CACHE / "sellers.parquet").set_index("fk_glusr_usr_id")
    calls = pd.read_parquet(ex.CACHE / "bot_calls.parquet", columns=["fk_glusr_usr_id", "call_start_time", "disposition_label"])
    last = calls.sort_values("call_start_time").groupby("fk_glusr_usr_id").disposition_label.last()
    items = []
    for uc, n in PER_USE_CASE.items():
        rows = []
        for sid in ex.candidates(uc):
            if sid not in gaps.index or sid not in sel.index:
                continue
            s, g = sel.loc[sid], gaps.loc[sid]
            if (s.seller_state not in HINDI_STATES or (s.bot_answered or 0) < 2 or (s.avg_answered_call_sec or 0) < 30
                    or (s.showed_frustration or 0) > 0 or last.get(sid) == "Not Interested"):
                continue
            if uc == "profile_onboarding" and not strong_gaps(g):
                continue
            rows.append((sid, s.bot_answered, s.avg_answered_call_sec))
        rows.sort(key=lambda r: (-r[1], -r[2]))
        keep = []
        for sid, _, _ in rows:
            if len(keep) == n:
                break
            if verify:
                got, lang = live_check(ex.build_profiles([(sid, uc)])[0]["profile"])
                if got != uc or lang not in ("Hindi", "English"):
                    print(f"  skip {sid}: Disha picks {got} in {lang}")
                    continue
            keep.append(sid)
        items += [(sid, uc) for sid in keep]
        print(f"{uc}: {len(rows)} good, kept {len(keep)}")
    return items


def main():
    items = pick(verify="--verify" in sys.argv)
    gaps = product_gaps().set_index("fk_glusr_usr_id")
    out = []
    for prof in ex.build_profiles(items):
        sid = prof["seller_id"]
        g = gaps.loc[sid]
        uc = dict(items)[sid]
        out.append({**prof, "label": f"{uc.replace('_', ' ')} · {int(g.total_product_count)} products, "
                                     f"{int(g.products_without_image)} no photo, {int(g.products_without_price)} no price"})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {OUT} ({len(out)} sellers)")


if __name__ == "__main__":
    main()
