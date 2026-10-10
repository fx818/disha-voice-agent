"""Precision spot-check: print random seller-sentence matches per theme."""
import os, re, sys, random, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyarrow.parquet as pq
from c2_themes import SUM, THEMES, split_summary, CACHE
s = pq.read_table(os.path.join(CACHE, "bot_calls.parquet"), columns=["lead_call_summary"])["lead_call_summary"].to_pylist()
random.seed(3); s = [x for x in random.sample(s, 60000) if isinstance(x, str)]
sel = [split_summary(x)[0] for x in s]
for th in THEMES:
    rx = re.compile(SUM[th], re.I)
    hits = [x for x in sel if rx.search(x)]
    print("=====", th, len(hits))
    for h in random.sample(hits, min(6, len(hits))):
        m = rx.search(h); print("  [", m.group(0), "]", h[:260])
