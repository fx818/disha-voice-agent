# per-seller bot-call history features, full and pre-Sep, plus Sep outcomes (for temporal validation)
import pandas as pd, numpy as np
P='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/cache/'
O='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/segmentation/'
b=pd.read_parquet(P+'bot_calls.parquet',columns=['fk_glusr_usr_id','call_start_time','disposition_label','lead_call_duration','redis_bucket'])
b=b.sort_values(['fk_glusr_usr_id','call_start_time'])
b['mf']=(b.disposition_label=='Meeting Fixed').astype('int8')
b['ni']=(b.disposition_label=='Not Interested').astype('int8')
b['cl']=(b.disposition_label=='Call Later / Busy').astype('int8')
END=b.call_start_time.max()
def agg(x,pfx):
    g=x.groupby('fk_glusr_usr_id')
    r=pd.DataFrame({pfx+'n':g.size(),pfx+'mf':g.mf.sum(),pfx+'ni':g.ni.sum(),pfx+'cl':g.cl.sum(),
                    pfx+'last_disp':g.disposition_label.last(),pfx+'last_time':g.call_start_time.last(),pfx+'dur':g.lead_call_duration.mean()})
    return r
cut=pd.Timestamp('2026-09-01')
full=agg(b,'h_'); pre=agg(b[b.call_start_time<cut],'pre_'); post=agg(b[b.call_start_time>=cut],'sep_')
out=full.join(pre,how='left').join(post,how='left')
# trigger mix for profiling (top bucket)
out['h_top_bucket']=b.groupby('fk_glusr_usr_id').redis_bucket.agg(lambda s:s.value_counts().index[0] if s.notna().any() else None)
out['h_days_since_last']=(END-out.h_last_time).dt.days
out=out.reset_index()
out.to_parquet(O+'scripts/_tmp_bot_hist.parquet',index=False)
print(len(out)); print(out.h_last_disp.value_counts(normalize=True)); print(out.h_days_since_last.describe())
print('sellers with pre & sep calls', (out.pre_n.notna()&out.sep_n.notna()).sum())
