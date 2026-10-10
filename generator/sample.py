"""Pick a contrasting sample of real sellers and write their persona specs + index.json."""
import json
from pathlib import Path

from generator.generate import generate_persona, seller_row, seller_table, write

# (label, demo, filter on the seller table). The first match with enough data is used.
PICKS = [
    ("DEMO · Delhi-NCR micro retailer who hangs up fast", True,
     lambda d: d[(d.seller_state.isin(["Delhi", "Haryana", "Uttar Pradesh"])) & (d.annual_turnover == "0 - 40 L")
                 & d.nature_of_business.astype(str).str.contains("Retail") & (d.avg_answered_call_sec < 12)
                 & (d.ctx_early_calls >= 2) & (d.do_not_call_requested != 1) & (d.showed_frustration != 1)
                 & (d.calls_not_interested < 2) & d.company.notna() & d.eng_enq_received_90d.notna()]),
    ("DEMO · Tamil Nadu manufacturer, large business", True,
     lambda d: d[(d.seller_state == "Tamil Nadu") & d.nature_of_business.astype(str).str.contains("Manufact")
                 & d.company.notna() & (d.bot_answered >= 1) & d.eng_pickup_ratio_1yr.notna()
                 & (d.showed_frustration != 1) & (d.calls_not_interested < 2) & (d.avg_answered_call_sec >= 20)]),
    ("DEMO · West-India seller who asked 'is this a bot?' and showed frustration", True,
     lambda d: d[(d.seller_state.isin(["Gujarat", "Maharashtra"])) & (d.asked_if_talking_to_bot == 1)
                 & (d.showed_frustration == 1) & d.company.notna()]),
    ("Maharashtra large manufacturer (Ltd company)", False,
     lambda d: d[(d.seller_state == "Maharashtra") & d.annual_turnover.isin(["5 - 25 Cr", "25 - 100 Cr"])
                 & (d.business_type == "Limited Company") & d.company.notna() & (d.bot_answered >= 1)]),
    ("Gujarat wholesaler, small turnover", False,
     lambda d: d[(d.seller_state == "Gujarat") & d.nature_of_business.astype(str).str.contains("Wholesal")
                 & (d.annual_turnover == "40 L - 1.5 Cr") & d.company.notna() & (d.bot_answered >= 2)
                 & (d.calls_not_interested == 0) & (d.ctx_early_calls == 0)]),
    ("UP seller who asked for a callback", False,
     lambda d: d[(d.seller_state == "Uttar Pradesh") & (d.calls_call_later >= 2) & d.company.notna()
                 & (d.calls_not_interested == 0) & (d.ctx_early_calls <= 1) & (d.annual_turnover == "0 - 40 L")]),
    ("Seller already in touch with an IndiaMART executive", False,
     lambda d: d[(d.already_in_touch_with_executive == 1) & d.company.notna() & (d.seller_state == "Rajasthan")]),
    ("Highly engaged service provider (replies to enquiries)", False,
     lambda d: d[d.nature_of_business.astype(str).str.contains("Service") & (d.eng_pickup_ratio_1yr > 60)
                 & (d.eng_enq_replies_90d >= 5) & d.company.notna() & (d.ctx_early_calls == 0)
                 & (d.calls_not_interested == 0)]),
    ("West Bengal trader", False,
     lambda d: d[(d.seller_state == "West Bengal") & d.company.notna() & (d.bot_answered >= 2)
                 & (d.calls_not_interested == 0)]),
    ("Karnataka seller (little language evidence)", False,
     lambda d: d[(d.seller_state == "Karnataka") & d.company.notna() & (d.bot_answered >= 1)]),
    ("Punjab partnership firm", False,
     lambda d: d[(d.seller_state == "Punjab") & (d.business_type == "Partnership") & d.company.notna()
                 & (d.bot_answered >= 1) & (d.calls_not_interested == 0)]),
    ("Seller who asked not to be called", False,
     lambda d: d[(d.do_not_call_requested == 1) & d.company.notna() & (d.seller_state == "Delhi")]),
    ("Repeat-attempt seller (6+ dials) in Madhya Pradesh", False,
     lambda d: d[(d.seller_state == "Madhya Pradesh") & (d.bot_attempts >= 6) & d.company.notna()
                 & (d.calls_not_interested <= 1)]),
    ("Warm paid-interest lead (PAM bucket), Telangana", False,
     lambda d: d[(d.ctx_last_bucket == "PAM") & (d.seller_state == "Telangana") & d.company.notna()]),
    ("Sparse-data seller (no engagement, no turnover)", False,
     lambda d: d[d.annual_turnover.isna() & d.eng_pickup_ratio_1yr.isna() & (d.bot_answered == 0)
                 & (d.seller_state == "Bihar")]),
]


def write_sample(out_dir):
    d = seller_table().reset_index(drop=True)
    index, used = [], set()
    for label, demo, flt in PICKS:
        cand = flt(d)
        cand = cand[~cand.fk_glusr_usr_id.isin(used)]
        if cand.empty:
            print("no seller for:", label)
            continue
        # prefer sellers with more answered calls, deterministic tie-break
        # prefer sellers with a typical amount of history (2-5 answered calls), deterministic tie-break
        cand = cand.assign(_typ=(cand.bot_answered - 3).abs()).sort_values(["_typ", "fk_glusr_usr_id"])
        sid = int(cand.iloc[min(len(cand) - 1, 0)].fk_glusr_usr_id)
        used.add(sid)
        spec = generate_persona(seller_row(sid))
        write(spec, out_dir)
        index.append(dict(seller_id=str(sid), label=label, demo=demo, company=spec["seller_snapshot"]["company"],
                          city=spec["seller_snapshot"]["city"], profile=spec["delivery_profile"]["id"],
                          language=spec["language"]["language_code"], speaker=spec["voice"]["speaker"],
                          pace=spec["voice"]["pace"]))
    Path(out_dir, "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    for i in index:
        print(("*" if i["demo"] else " "), i["seller_id"], i["profile"], i["language"], i["speaker"], i["pace"],
              "|", i["label"], "|", i["company"], i["city"])
