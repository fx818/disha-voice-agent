import json
from pathlib import Path
import pandas as pd
p=Path('outputs/segmentation');r=json.loads((p/'A_decoder_evidence.json').read_text());m=json.loads((p/'A_bucket_map.json').read_text());s=pd.read_parquet(p/'A_seller_paid_status.parquet');orig=pd.read_parquet('outputs/cache/sellers.parquet',columns=['fk_glusr_usr_id'])
assert sum(v['n_calls'] for v in m.values())==269455
assert sum(v['n_calls'] for v in r['versions'].values())==269455
assert set(m)==set(r['buckets']) and len(m)==18
assert len(s)==149363 and s.fk_glusr_usr_id.is_unique and set(s.fk_glusr_usr_id)==set(orig.fk_glusr_usr_id)
assert list(s.columns)==['fk_glusr_usr_id','paid_status','evidence']
assert s.paid_status.isin(['free','paid','unknown']).all()
for v in s.evidence:json.loads(v)
for b,v in r['buckets'].items():
 assert len(v['representatives'])==min(8,v['long_summary_n']),(b,len(v['representatives']))
 assert all(x['duration']>30 for x in v['representatives'])
 assert sum(v['disposition'].values())==v['n_calls']
 assert 0<=m[b]['meeting_rate']<=1
print('PASS: totals, code coverage, schema, seller uniqueness/coverage, evidence JSON, all representative counts/durations, disposition totals, rates.')
print('Status',s.paid_status.value_counts().to_dict());print('Baseline',r['all']);print('Report bytes',(p/'A_bucket_decoder.md').stat().st_size)
print('Status by bucket',r['status']['by_bucket'])
