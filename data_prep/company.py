"""Extract a company name per seller from bot openings and call summaries (no company column exists)."""
import re

import pandas as pd

from data_prep import load as L

TURN_PATS = [re.compile(r"kya aap (.{2,60}?) se bol rahe", re.I),
             re.compile(r"kya meri baat (.{2,60}?) (?:mein|se|me) ho rahi", re.I)]
SUM_PATS = [re.compile(r"(?:speaking (?:to|with)|were (?:from|with)|was (?:from|with)|is from|"
                       r"lead from|representative (?:of|from)|associated with|reached) "
                       r"((?:[A-Z0-9][\w&.'-]*\s?){1,6})"),
            re.compile(r"(?:agent|executive) (?:called|contacted|reached out to) ((?:[A-Z0-9][\w&.'-]*\s?){1,6})")]
STOP = {"The", "IndiaMART", "Indiamart", "India", "The Lead", "Lead", "He", "She", "They", "Sales", "A", "An"}


def _clean(name):
    name = re.split(r"\.\s", name)[0]
    name = re.sub(r"\s+(but|and|to|regarding|about|for|who|which|however)\b.*$", "", name.strip(" .,'\"?"))
    name = re.sub(r"^(the|a|an)\s+", "", name, flags=re.I).strip(" .,")
    if len(name) < 3 or name in STOP or name.lower().startswith(("indiamart", "the lead", "lead")):
        return None
    return name


def company_names():
    def build():
        rows = []
        t = L.call_turns()
        b = t[(t.speaker == "bot") & (t.turn_no <= 3)]
        for uid, txt in zip(b.fk_glusr_usr_id, b.text.fillna("")):
            for p in TURN_PATS:
                m = p.search(txt)
                if m and (n := _clean(m.group(1))):
                    rows.append((uid, n, 3))
        c = L.bot_calls()[["fk_glusr_usr_id", "lead_call_summary"]].dropna()
        for uid, txt in zip(c.fk_glusr_usr_id, c.lead_call_summary):
            for p in SUM_PATS:
                m = p.search(txt)
                if m and (n := _clean(m.group(1))):
                    rows.append((uid, n, 1))
                    break
        df = pd.DataFrame(rows, columns=["fk_glusr_usr_id", "company", "w"])
        df["key"] = df.company.str.lower()
        agg = df.groupby(["fk_glusr_usr_id", "key"]).agg(company=("company", "first"), w=("w", "sum")).reset_index()
        best = agg.sort_values("w", ascending=False).drop_duplicates("fk_glusr_usr_id")
        return best[["fk_glusr_usr_id", "company", "w"]]
    return L._cached("company_names", build)
