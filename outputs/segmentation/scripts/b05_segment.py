import pandas as pd, numpy as np, sys, json
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
P='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/cache/sellers.parquet'
O='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/segmentation/'
WRITE='--write' in sys.argv
drop=['seller_locality','seller_pincode','seller_city','seller_district','past_objections','past_questions_asked','top_category_2','top_category_3','nature_of_business_secondary']
import pyarrow.parquet as pq
cols=[c for c in pq.ParquetFile(P).schema_arrow.names if c not in drop]
df=pd.read_parquet(P,columns=cols)
h=pd.read_parquet(O+'scripts/_tmp_bot_hist.parquet')
df=df.merge(h,on='fk_glusr_usr_id',how='left'); del h
N=len(df)
# ---------- data availability ----------
df['has_eng']=df.eng_call_attempts_90d.notna()
df['has_catalog']=df.eng_product_count.notna()
sparse=['eng_activity_30d','eng_callback_90d','eng_callback_1yr','eng_meetings_1yr','eng_hot_meetings_1yr','eng_enq_received_90d','eng_enq_received_1yr',
        'eng_enq_replies_90d','eng_enq_replies_1yr','eng_pns_received_90d','eng_pns_received_1yr','eng_pns_answered_90d','eng_pns_answered_1yr','eng_ni_count_1yr','eng_np_count_1yr']
for c in sparse:  # inside the engagement block a null is a structural zero; outside it stays unknown
    df[c]=df[c].mask(df.has_eng & df[c].isna(),0)
df['data_tier']=np.select([df.has_eng&df.has_catalog,df.has_eng,df.has_catalog],['eng+catalog','eng_only','catalog_only'],'profile_only')
# ---------- derived ----------
df['reply_ratio_1yr']=(df.eng_enq_replies_1yr/df.eng_enq_received_1yr).where(df.eng_enq_received_1yr>=3)
df['pns_answer_ratio_1yr']=(df.eng_pns_answered_1yr/df.eng_pns_received_1yr).where(df.eng_pns_received_1yr>=3)
prof=['business_type','annual_turnover','nature_of_business','gst_registration_year','top_category_1']
df['n_missing_profile']=df[prof].isna().sum(axis=1)
df['new_business_gst']=df.gst_registration_year>=2025
REF=pd.Timestamp('2026-09-30')
# ---------- thresholds ----------
T=dict(warm_recency_days=60, fp_enq90=3, fp_pns90=3, fp_reply=0.44, fp_pns_ans=0.54, fp_cqs=15, fp_products=12,
       ln_recv=3, ln_reply=0.25, ln_pns_ans=0.33, pe_cqs=9, pe_products=5, pe_cqs_noedit=15, pe_missing=2)
def flags(d, disp, last_time, ref):
    f=pd.DataFrame(index=d.index)
    rec=(ref-last_time).dt.days<=T['warm_recency_days']
    f['f_warm']=disp.isin(['Meeting Fixed','Call Later / Busy']) & rec
    act=(d.eng_activity_30d>0)|(d.eng_products_modified_90d>0)
    demand=(d.eng_enq_received_90d>=T['fp_enq90'])|(d.eng_pns_received_90d>=T['fp_pns90'])
    resp=(d.reply_ratio_1yr>=T['fp_reply'])|(d.pns_answer_ratio_1yr>=T['fp_pns_ans'])
    catalog=(d.eng_cqs>=T['fp_cqs'])|(d.eng_product_count>=T['fp_products'])
    f['f_free_to_paid']=d.has_eng & act & demand & resp & catalog
    f['f_lead_nonconsumption']=d.has_eng & (((d.eng_enq_received_1yr>=T['ln_recv'])&(d.reply_ratio_1yr<T['ln_reply'])) |
                                            ((d.eng_pns_received_1yr>=T['ln_recv'])&(d.pns_answer_ratio_1yr<T['ln_pns_ans'])))
    f['f_dormant']=d.has_eng & (d.eng_activity_30d==0)&(d.eng_enq_received_90d==0)&(d.eng_pns_received_90d==0)&(d.eng_enq_replies_90d==0)&(d.eng_pns_answered_90d==0)&(d.eng_products_modified_90d.fillna(0)==0)
    f['f_profile_enrichment']=(d.has_catalog & ((d.eng_cqs<=T['pe_cqs'])|(d.eng_product_count<=T['pe_products'])|((d.eng_products_modified_90d==0)&(d.eng_cqs<T['pe_cqs_noedit'])))) | (d.n_missing_profile>=T['pe_missing'])
    f['f_low_demand_active']=d.has_eng & d.has_catalog & (d.eng_enq_received_90d==0)&(d.eng_pns_received_90d==0) & ((d.eng_products_modified_90d>0)|(d.eng_activity_30d>0)) & ~f.f_profile_enrichment & ~f.f_dormant
    return f
ORDER=[('f_warm','warm_followup'),('f_free_to_paid','free_to_paid'),('f_lead_nonconsumption','lead_nonconsumption'),('f_dormant','dormant_reactivation'),('f_profile_enrichment','profile_enrichment'),('f_low_demand_active','low_demand_visibility')]
def primary(f,d):
    p=pd.Series('insufficient_data',index=f.index)
    for col,name in reversed(ORDER): p=p.mask(f[col],name)
    p=p.mask((p=='insufficient_data') & (d.has_eng|d.has_catalog),'uncategorised_other')
    return p
f=flags(df,df.h_last_disp,df.h_last_time,REF); df=df.join(f); df['primary_category']=primary(f,df)
df['f_suppress']=(df.do_not_call_requested==1)|(df.already_in_touch_with_executive==1)|(df.showed_frustration==1)|df.past_dispositions_detailed.str.contains('wrong_number',na=False)
df['paid_status_hint']=pd.Series(pd.NA,index=df.index,dtype='string')  # hook: filled by paid/free inference agent
fl=[c for c,_ in ORDER]
print('THRESH',T)
print('\n== flag sizes (any) =='); print((df[fl+['f_suppress']].mean()*100).round(1))
print('\n== primary sizes =='); vc=df.primary_category.value_counts(); print(pd.DataFrame({'n':vc,'pct':(vc/N*100).round(1)}))
print('\n== by tier =='); print(pd.crosstab(df.primary_category,df.data_tier))
ov=pd.DataFrame({a:[(df[a]&df[b]).sum() for b in fl] for a in fl},index=fl); print('\n== overlap counts =='); print(ov)
print('\n== overlap % of row flag =='); print((ov.div(np.diag(ov),axis=0)*100).round(0))
# ---------- validation ----------
def val(g):
    a=g.bot_answered.sum()
    return pd.Series({'sellers':len(g),'answered_calls':a,'mf_rate':g.calls_meeting_fixed.sum()/a,'ni_rate':g.calls_not_interested.sum()/a,
        'cl_rate':g.calls_call_later.sum()/a,'avg_call_sec':g.avg_answered_call_sec.mean(),'answer_rate':g.bot_answer_rate.mean(),'dnc%':g.do_not_call_requested.mean()})
V=df.groupby('primary_category').apply(val); V.loc['ALL']=val(df); V.loc['ALL_non_warm']=val(df[~df.f_warm]); V.loc['new_business_gst']=val(df[df.new_business_gst]); V.loc['old_business_gst']=val(df[~df.new_business_gst]); V.loc['suppress_overlay']=val(df[df.f_suppress])
print('\n== validation: whole-history bot outcomes by primary =='); print(V.round(3))
VF=pd.concat({c:val(df[df[c]]) for c in fl},axis=1).T; print('\n== validation by flag (any) =='); print(VF.round(3))
# temporal: bot-derived flag (warm) from pre-Sep calls only, outcomes = Sep calls
t=df[df.pre_n.notna()&df.sep_n.notna()].copy()
ft=flags(t,t.pre_last_disp,t.pre_last_time,pd.Timestamp('2026-08-31')); t['p_t']=primary(ft,t)
def tv(g): return pd.Series({'sellers':len(g),'sep_calls':g.sep_n.sum(),'sep_mf':g.sep_mf.sum()/g.sep_n.sum(),'sep_ni':g.sep_ni.sum()/g.sep_n.sum(),'sep_cl':g.sep_cl.sum()/g.sep_n.sum(),'sep_dur':g.sep_dur.mean()})
TV=t.groupby('p_t').apply(tv); TV.loc['ALL']=tv(t); print('\n== temporal validation (flags from pre-Sep, outcome Sep calls) =='); print(TV.round(3))
if '--diag' in sys.argv:
    for c in ['uncategorised_other','insufficient_data','profile_enrichment']:
        g=df[df.primary_category==c]
        print('\n##',c,len(g)); print(g[['eng_cqs','eng_product_count','eng_products_modified_90d','eng_activity_30d','eng_enq_received_90d','eng_enq_received_1yr','eng_pns_received_1yr','reply_ratio_1yr','pns_answer_ratio_1yr','gst_registration_year','bot_answered','h_days_since_last']].describe().round(2).to_string())
        print(g.h_last_disp.value_counts(normalize=True,dropna=False).round(3).to_dict()); print('new_gst',g.new_business_gst.mean().round(3),'nmiss>=1',(g.n_missing_profile>=1).mean().round(3))
if WRITE:
    V.to_csv(O+'scripts/_val_hist.csv'); TV.to_csv(O+'scripts/_val_temporal.csv'); VF.to_csv(O+'scripts/_val_flag.csv'); ov.to_csv(O+'scripts/_overlap.csv')
    keep=['fk_glusr_usr_id','primary_category']+fl+['f_suppress','paid_status_hint','data_tier','has_eng','has_catalog',
      'eng_cqs','eng_product_count','eng_products_modified_90d','eng_products_modified_1yr','eng_activity_30d','eng_enq_received_90d','eng_enq_received_1yr',
      'eng_enq_replies_1yr','reply_ratio_1yr','eng_pns_received_90d','eng_pns_received_1yr','eng_pns_answered_1yr','pns_answer_ratio_1yr','eng_pickup_ratio_90d',
      'n_missing_profile','gst_registration_year','new_business_gst','h_last_disp','h_days_since_last','h_top_bucket','bot_answered','calls_meeting_fixed','calls_call_later','calls_not_interested']
    df[keep].rename(columns={'h_last_disp':'last_bot_disposition','h_days_since_last':'days_since_last_bot_call','h_top_bucket':'top_redis_bucket'}).to_parquet(O+'B_seller_segments.parquet',index=False)
    # profiles
    S={'business_type':'business_type','annual_turnover':'annual_turnover','nature_of_business':'nature_of_business','top_category_group':'top_category_group','top_redis_bucket':'h_top_bucket'}
    def region(s):
        hindi={'Uttar Pradesh','Delhi','Rajasthan','Haryana','Madhya Pradesh','Bihar','Uttarakhand','Chhattisgarh','Jharkhand','Himachal Pradesh','Chandigarh','Punjab','Jammu & Kashmir','Jammu and Kashmir'}
        south={'Tamil Nadu','Karnataka','Kerala','Telangana','Andhra Pradesh','Puducherry','Pondicherry'}
        east={'West Bengal','Odisha','Assam','Jharkhand','Tripura','Meghalaya','Manipur','Nagaland','Mizoram','Arunachal Pradesh','Sikkim'}
        return np.where(s.isin(hindi),'Hindi belt (+Punjab)',np.where(s.isin(['Gujarat']),'Gujarat',np.where(s.isin(['Maharashtra','Goa']),'Maharashtra/Goa',np.where(s.isin(south),'South',np.where(s.isin(east),'East/NE','Other/unknown')))))
    df['region']=region(df.seller_state); S['region']='region'; S['seller_state']='seller_state'
    res={}
    for cat,g in df.groupby('primary_category'):
        r={'n':len(g)}
        for k,c in S.items():
            vc=g[c].value_counts(normalize=True,dropna=False).head(4 if k!='region' else 6)
            r[k]='; '.join(f"{i} {v*100:.0f}%" for i,v in vc.items())
        r['new_business_gst%']=round(g.new_business_gst.mean()*100,1)
        r['median_cqs']=g.eng_cqs.median(); r['median_products']=g.eng_product_count.median()
        r['median_enq_1yr']=g.eng_enq_received_1yr.median(); r['suppress%']=round(g.f_suppress.mean()*100,1)
        res[cat]=r
    base={'region':'; '.join(f"{i} {v*100:.0f}%" for i,v in df.region.value_counts(normalize=True).items()),'new_business_gst%':round(df.new_business_gst.mean()*100,1),'suppress%':round(df.f_suppress.mean()*100,1)}
    res['ALL']=base
    json.dump(res,open(O+'scripts/_profiles.json','w'),indent=1,default=str)
    print(json.dumps(res,indent=1,default=str))
