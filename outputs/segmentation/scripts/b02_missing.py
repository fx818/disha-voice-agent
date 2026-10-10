import pandas as pd, numpy as np
P='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/cache/'
e=[c for c in pd.read_parquet(P+'sellers.parquet',columns=None).columns] if False else None
import pyarrow.parquet as pq
cols=[c for c in pq.ParquetFile(P+'sellers.parquet').schema_arrow.names if c.startswith('eng_')]+['fk_glusr_usr_id','gst_registration_year','bot_answered','calls_meeting_fixed','do_not_call_requested']
df=pd.read_parquet(P+'sellers.parquet',columns=cols)
core=df.eng_call_attempts_90d.notna()
print('core block present',core.mean())
for c in [x for x in cols if x.startswith('eng_')]:
    print(f'{c:30s} fill_in_core={df.loc[core,c].notna().mean():.3f} fill_outside_core={df.loc[~core,c].notna().mean():.3f}')
cat=df.eng_product_count.notna()
print(pd.crosstab(core,cat,normalize=True))
print(pd.crosstab(core,df.eng_cqs.notna()))
print('cqs present but product missing',(df.eng_cqs.notna()&~cat).sum())
print('gst year dist'); print(df.gst_registration_year.value_counts().sort_index().tail(12))
print('bot_answered by core'); print(df.groupby(core)[['bot_answered','calls_meeting_fixed']].mean())
print('dnc fill by core', df.groupby(core).do_not_call_requested.apply(lambda s:s.notna().mean()))
b=pd.read_parquet(P+'bot_calls.parquet',columns=['fk_glusr_usr_id','call_start_time','disposition_label','lead_call_duration','redis_bucket'])
print(b.dtypes); print(b.call_start_time.min(), b.call_start_time.max())
b['m']=pd.to_datetime(b.call_start_time,errors='coerce').dt.to_period('M'); print(b.m.value_counts().sort_index())
print(b.disposition_label.value_counts())
print(b.lead_call_duration.describe())
