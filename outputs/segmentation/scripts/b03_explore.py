import pandas as pd, numpy as np
P='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/cache/sellers.parquet'
df=pd.read_parquet(P,columns=None)
df=df.drop(columns=['seller_locality','seller_pincode','seller_city','seller_district'])
core=df.eng_call_attempts_90d.notna(); cat=df.eng_product_count.notna()
print(pd.crosstab(core,cat))
print(df.past_dispositions_detailed.dropna().head(10).tolist())
print(df.past_dispositions_detailed.str.contains('callback_requested',na=False).mean())
for k in ['meeting_fixed','callback_requested','not_interested','already_in_touch','wrong_number','call_dropped','ivr']:
    print(k, df.past_dispositions_detailed.str.contains(k,na=False).mean().round(3))
print(df.past_questions_asked.dropna().head(5).tolist())
print(df.past_objections.dropna().head(5).tolist())
c=core
x=df[c]
# activity among core: null->0
a=x.eng_activity_30d.fillna(0); print('activity30 >0 among core',(a>0).mean(), a[a>0].quantile([.25,.5,.75]).tolist())
er=x.eng_enq_received_90d.fillna(0); rp=x.eng_enq_replies_90d.fillna(0)
print('enq90>0',(er>0).mean(), er[er>0].quantile([.25,.5,.75,.9]).tolist())
r1=x.eng_enq_received_1yr.fillna(0); rp1=x.eng_enq_replies_1yr.fillna(0)
ratio=(rp1/r1).where(r1>=3); print('reply ratio 1yr (recv>=3) q', ratio.quantile([.1,.25,.5,.75,.9]).round(2).tolist(), 'n',ratio.notna().sum())
ratio9=(rp/er).where(er>=3); print('reply ratio 90 (recv>=3) q', ratio9.quantile([.1,.25,.5,.75,.9]).round(2).tolist(), ratio9.notna().sum())
pr=x.eng_pns_received_90d.fillna(0); pa=x.eng_pns_answered_90d.fillna(0)
print('pns90>0',(pr>0).mean(), pr[pr>0].quantile([.25,.5,.75,.9]).tolist())
pratio=(pa/pr).where(pr>=2); print('pns ans ratio 90 (recv>=2)', pratio.quantile([.1,.25,.5,.75,.9]).round(2).tolist(), pratio.notna().sum())
p1=x.eng_pns_received_1yr.fillna(0); pa1=x.eng_pns_answered_1yr.fillna(0)
pr1=(pa1/p1).where(p1>=3); print('pns ans ratio 1yr (recv>=3)', pr1.quantile([.1,.25,.5,.75,.9]).round(2).tolist(), pr1.notna().sum())
print('pickup90 among core', x.eng_pickup_ratio_90d.describe())
print('cqs by quantiles (catalog present)', df.eng_cqs.quantile([.1,.2,.25,.33,.5,.67,.75]).tolist())
print('product count q', df.eng_product_count.quantile([.1,.2,.25,.33,.5]).tolist())
print('no edits 90d share (cat present)', (df.loc[cat,'eng_products_modified_90d']==0).mean(), 'no edits 1yr', (df.loc[cat,'eng_products_modified_1yr']==0).mean())
miss=df[['business_type','annual_turnover','nature_of_business','gst_registration_year','top_category_1']].isna()
print('n missing profile fields'); print(miss.sum(1).value_counts().sort_index())
print(pd.crosstab(miss.sum(1)>=1, core))
# bot history
print('MF>0',(df.calls_meeting_fixed>0).mean(),'CL>0',(df.calls_call_later>0).mean(),'either',((df.calls_meeting_fixed>0)|(df.calls_call_later>0)).mean())
print('eng_meetings_1yr>0',(df.eng_meetings_1yr>0).mean(),'eng_callback_90d>0',(df.eng_callback_90d>0).mean())
ans=df.bot_answered.replace(0,np.nan)
print('baseline MF rate per answered call', df.calls_meeting_fixed.sum()/df.bot_answered.sum(),'NI', df.calls_not_interested.sum()/df.bot_answered.sum())
