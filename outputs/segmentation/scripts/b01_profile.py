import pandas as pd, numpy as np
P='/home/imart/Downloads/Persona Files-20261001T083848Z-1-001/Persona Files/persona-agent/outputs/cache/sellers.parquet'
df=pd.read_parquet(P)
df=df.drop(columns=['seller_locality','seller_pincode','seller_city','past_objections','past_questions_asked','past_dispositions_detailed'])
print(df.memory_usage(deep=True).sum()/1e6,'MB')
num=df.select_dtypes('number').columns
pd.set_option('display.width',250); pd.set_option('display.max_rows',200)
rows=[]
for c in num:
    s=df[c]; nn=s.notna()
    q=s.quantile([.1,.25,.5,.75,.9,.95,.99]).values
    rows.append([c,round(nn.mean()*100,1),round((s==0).sum()/max(nn.sum(),1)*100,1)]+list(np.round(q,2))+[round(s.mean(),2)])
print(pd.DataFrame(rows,columns=['col','fill%','zero%_of_filled','p10','p25','p50','p75','p90','p95','p99','mean']).to_string())
for c in ['business_type','annual_turnover','nature_of_business','top_category_group','seller_state']:
    print(c, 'fill', round(df[c].notna().mean()*100,1)); print(df[c].value_counts(dropna=False).head(15))
# eng missing co-pattern
e=[c for c in df.columns if c.startswith('eng_')]
print('rows all eng missing', df[e].isna().all(1).mean(), 'any eng present', df[e].notna().any(1).mean())
print(df[e].notna().sum().sort_values())
