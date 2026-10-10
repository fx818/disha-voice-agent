from pathlib import Path
import pandas as pd
import numpy as np
import re,json,math,gc
from collections import Counter
O=Path('outputs/segmentation'); C=Path('outputs/cache')
cols=['attempt_id','fk_glusr_usr_id','redis_bucket','lead_bot_version','call_start_time','lead_call_duration','lead_call_summary','disposition_label','meeting_fixed']
d=pd.read_parquet(C/'bot_calls.parquet',columns=cols)
d['redis_bucket']=d.redis_bucket.fillna('<missing>');d['lead_bot_version']=d.lead_bot_version.fillna('<missing>')
N=len(d); labels=sorted(d.disposition_label.fillna('<missing>').unique())
def stats(g):
 return dict(n_calls=len(g),n_sellers=g.fk_glusr_usr_id.nunique(),meeting_n=int(g.meeting_fixed.eq(1).sum()),meeting_rate=float(g.meeting_fixed.eq(1).mean()),median_duration=float(g.lead_call_duration.median()),duration_n=int(g.lead_call_duration.notna().sum()),early_n=int(g.lead_call_duration.lt(10).sum()),early_rate=float(g.lead_call_duration.lt(10).sum()/g.lead_call_duration.notna().sum()),summary_n=int(g.lead_call_summary.fillna('').str.strip().ne('').sum()),disposition={str(k):int(v) for k,v in g.disposition_label.fillna('<missing>').value_counts().items()})
R={'all':stats(d),'buckets':{},'versions':{str(k):stats(g) for k,g in d.groupby('lead_bot_version')},'quality':{'duplicate_attempts':int(d.attempt_id.duplicated().sum()),'missing_sellers':int(d.fk_glusr_usr_id.isna().sum()),'meeting_disagreement':int((d.meeting_fixed.eq(1)!=d.disposition_label.eq('Meeting Fixed')).sum()),'date_min':str(d.call_start_time.min()),'date_max':str(d.call_start_time.max())}}
patterns={'paid':r'\bpaid\b','free plan':r'\bfree[ -](?:plan|account|listing|seller|member(?:ship)?)\b','payment':r'\bpayment\w*','buyer contact':r'\bbuyer[ -]contacts?\b','enquir':r'\b(?:enquir|inquir)\w*','PNS':r'\bpns\b','catalog':r'\bcatalog\w*','profile':r'\bprofile\w*','photo':r'\bphoto\w*','demo':r'\bdemo\w*','package':r'\bpackage\w*','renew':r'\brenew\w*','GST':r'\bgst\b','product':r'\bproduct\w*'}
stop=set('the a an and or to of in on at for from with by as is was were are be been being this that their they them he she his her it its i you your we our had has have did do does not no but then about regarding called call agent lead seller indiamart stated mentioned asked offered agreed would could will can said meeting executive sales schedule time thank ended discuss'.split())
semantic=set('paid free plan account listing seller user member membership subscription payment payments paying pay buyer buyers contact contacts enquiry enquiries inquiry inquiries pns catalog catalogue catalogues catalogs profile profiles photo photos demo booking booked package packages renew renewal gst product products buy buying purchase purchasing purchased buylead buyleads attempt attempts attempted interest interested exploring explored services service checking checked recently created registered registration increase improving improve visibility active activity updated update updating received receiving missed unanswered callback followup follow up new incomplete descriptions business online leads lead'.split())
counts={}; global_df=Counter(); text_n=0
for b,g in d.groupby('redis_bucket'):
 s=stats(g); texts=g.lead_call_summary.fillna(''); valid=texts.str.strip().ne(''); s['keywords']={k:int(texts.str.contains(p,case=False,regex=True).sum()) for k,p in patterns.items()}
 c=Counter()
 for t in texts:
  w=re.findall(r'[a-z]{3,}',t.lower()); terms={x for x in w if x not in stop};terms.update(x+' '+y for x,y in zip(w,w[1:]) if x not in stop and y not in stop); c.update(terms)
 counts[b]=c; global_df.update(c);text_n+=int(valid.sum()); R['buckets'][b]=s
R['keyword_all']={k:sum(x['keywords'][k] for x in R['buckets'].values()) for k in patterns}
for b,s in R['buckets'].items():
 n=s['summary_n']; rest=text_n-n;c=counts[b]; terms=[]
 for t,a in c.items():
  if a<max(2,min(20,math.ceil(n*.005))):continue
  if not all(w in semantic for w in t.split()):continue
  r=global_df[t]-a; score=math.log((a+.5)/(n-a+.5))-math.log((r+.5)/(rest-r+.5));terms.append(dict(term=t,n=a,rate=a/n,rest_n=r,rest_rate=r/rest,log_odds=score))
 s['distinctive_words']=sorted([x for x in terms if ' ' not in x['term']],key=lambda x:x['log_odds'],reverse=True)[:8]
 s['distinctive_bigrams']=sorted([x for x in terms if ' ' in x['term']],key=lambda x:x['log_odds'],reverse=True)[:8]
 # Extract short clauses starting at a generic role or topic, avoiding named business introductions.
 g=d[(d.redis_bucket==b)&d.lead_call_duration.gt(30)&d.lead_call_summary.notna()].copy();s['long_summary_n']=len(g)
 reps=[]
 for row in g.sample(frac=1,random_state=42).itertuples():
  t=row.lead_call_summary
  clauses=re.findall(r'(?:Seller |The lead |The agent offered |The agent proposed |The agent suggested |regarding their |to improve their |to discuss their )[^.!?\n]+',t)
  chosen=next((x for x in clauses if any(w in x.lower() for w in ['paid','free','payment','catalog','profile','demo','enquir','inquir','buylead','package'])),clauses[0] if clauses else '')
  if not chosen:chosen=t
  chosen=re.sub(r'\b\d[\d\s+()\-]{5,}\d\b','[number removed]',chosen)[:150]
  # Only lower-case content after opening; capitals can contain real names/locations.
  chosen=re.sub(r'\b[A-Z][A-Za-z&.]*\b',lambda m: m.group() if m.group() in {'The','Seller','He','She','They','I','IndiaMART','IndiaMart','PNS','GST'} else '[redacted]',chosen)
  chosen=re.sub(r'(?:\[redacted\]\s*){2,}','[redacted] ',chosen)
  reps.append({'attempt_id':int(row.attempt_id),'duration':row.lead_call_duration,'snippet':chosen})
  if len(reps)==8:break
 s['representatives']=reps
# Evaluators: filtered reads, sequential agents; sample up to 100 matched unique attempts per bucket.
lookup=d[['attempt_id','redis_bucket']].drop_duplicates('attempt_id')
for agent in ['topics','disposition']:
 e=pd.read_parquet(C/'evaluator.parquet',columns=['attempt_id','agent_output'],filters=[('eval_agent','==',agent)])
 raw_n=len(e);dup=int(e.attempt_id.duplicated().sum());e=e.drop_duplicates('attempt_id').merge(lookup,on='attempt_id',how='inner',validate='one_to_one'); totals=Counter();sample_total=0
 for b,s in R['buckets'].items():
  g=e[e.redis_bucket==b];sample=g.sample(min(100,len(g)),random_state=42);cc=Counter();parsed=0
  for t in sample.agent_output:
   try: obj=json.loads(t)
   except (ValueError,TypeError):continue
   if not isinstance(obj,dict):continue
   parsed+=1
   if agent=='topics': cc.update(set(x.get('topic_id') for x in obj.get('discussion_timeline',[]) if x.get('topic_id')))
   else:cc.update([str(obj.get('disposition','<missing>'))+' / '+str(obj.get('sub_disposition','<missing>'))])
  s['eval_'+agent]={'available':len(g),'sample_n':len(sample),'parsed_n':parsed,'counts':dict(cc)};totals.update(cc);sample_total+=parsed
 R[agent+'_all']={'raw_n':raw_n,'duplicate_attempts':dup,'matched_n':len(e),'sample_n':sample_total,'counts':dict(totals)}
 del e;gc.collect()
# Explicit status assertions only; generic paid/package/renewal pitches do not establish status.
free=re.compile(r"\b(?:(?:currently |only |still )?(?:using|uses|on|having|have|has|testing|updating|update|continue with|remain on|used|done) (?:a |the |their |his |her )?(?:free[ -](?:plan|account|listing|membership))|free seller|not a paid member)\b",re.I)
paid=re.compile(r"\b(?:(?:already |currently )?(?:has|have|using|on) (?:an? |the )?(?:existing )?paid (?:subscription|plan|membership)|(?:is|are|as) a paid (?:seller|member|subscriber|customer|user)|already paid for (?:a |the )?(?:[a-z-]+ )?subscription|lead had a paid subscription)\b",re.I)
records=[]
for row in d.itertuples():
 t=row.lead_call_summary or ''
 if not isinstance(t,str):continue
 fm=free.search(t);pm=paid.search(t)
 if pm:
  context=t[max(0,pm.start()-45):pm.end()+90].lower()
  if re.search(r'not |never |another (?:account|company|firm)|other (?:account|company|firm)|expired|previous|cancel',context):pm=None
 if fm:
  context=t[max(0,fm.start()-35):fm.end()+35].lower()
  if re.search(r'last month|2016|previous|want to|wants to|interested in|how to',context):fm=None
 # Suppress direct negation of matched paid statement.
 if pm and re.search(r'\b(?:not|never|unpaid)\b',pm.group().lower()):pm=None
 for status,m in [('free',fm),('paid',pm)]:
  if m:records.append((row.fk_glusr_usr_id,status,str(row.attempt_id),str(row.call_start_time),m.group().lower()))
evidence={}
for sid,status,aid,dt,phrase in records:
 v=evidence.setdefault(sid,{'free':[],'paid':[]});v[status].append({'attempt_id':aid,'date':dt,'signal':phrase,'confidence':'low_unverified_summary'})
sellers=pd.read_parquet(C/'sellers.parquet',columns=['fk_glusr_usr_id']);universe=pd.Index(sellers.fk_glusr_usr_id).union(pd.Index(d.fk_glusr_usr_id.unique()))
rows=[]
for sid in universe:
 v=evidence.get(sid,{'free':[],'paid':[]});status='unknown' if bool(v['free'])==bool(v['paid']) else ('free' if v['free'] else 'paid')
 ev={'rule':'conflicting_status_assertions' if v['free'] and v['paid'] else ('explicit_summary_assertion' if status!='unknown' else 'no_explicit_status_assertion'),'free_calls':len(v['free']),'paid_calls':len(v['paid']),'examples':(v['free'][:2]+v['paid'][:2])}
 rows.append((sid,status,json.dumps(ev,separators=(',',':'))))
out=pd.DataFrame(rows,columns=['fk_glusr_usr_id','paid_status','evidence']);out.to_parquet(O/'A_seller_paid_status.parquet',index=False)
R['status']={'universe_n':len(out),'seller_file_n':len(sellers),'counts':out.paid_status.value_counts().to_dict(),'signal_call_n':len(set(x[2] for x in records)),'free_signal_calls':sum(x[1]=='free' for x in records),'paid_signal_calls':sum(x[1]=='paid' for x in records),'conflict_sellers':sum(bool(v['free']) and bool(v['paid']) for v in evidence.values()),'phrases':dict(Counter(x[4] for x in records))}
R['status']['by_bucket']={}
for bucket,g in d.groupby('redis_bucket'):
 aids=set(g.attempt_id.astype(str));R['status']['by_bucket'][bucket]={st:sum(x[1]==st and x[2] in aids for x in records) for st in ['free','paid']}
# Stability across observed answered calls only.
sc=d.groupby(['fk_glusr_usr_id','redis_bucket']).size();tot=sc.groupby(level=0).sum(); nb=sc.groupby(level=0).size();dominant=sc.groupby(level=0).max()/tot;multi=tot.gt(1)
sorted_d=d.sort_values(['fk_glusr_usr_id','call_start_time','attempt_id']);same=sorted_d.fk_glusr_usr_id.eq(sorted_d.fk_glusr_usr_id.shift());changed=sorted_d.redis_bucket.ne(sorted_d.redis_bucket.shift())&same
R['stability']={'called_sellers':len(tot),'multi_bucket_sellers':int(nb.gt(1).sum()),'repeat_sellers':int(multi.sum()),'single_call_sellers':int(tot.eq(1).sum()),'bucket_count_distribution':{str(k):int(v) for k,v in nb.value_counts().sort_index().items()},'dominant_share_mean':float(dominant.mean()),'repeat_dominant_share_mean':float(dominant[multi].mean()),'repeat_dominant_share_median':float(dominant[multi].median()),'adjacent_pairs':int(same.sum()),'changed_pairs':int(changed.sum()),'missing_time':int(d.call_start_time.isna().sum()),'tied_seller_time_rows':int(d.duplicated(['fk_glusr_usr_id','call_start_time'],keep=False).sum())}
R['stability']['transitions']=sorted_d.loc[changed].assign(previous=sorted_d.redis_bucket.shift()[changed]).groupby(['previous','redis_bucket']).size().sort_values(ascending=False).head(10).to_dict();R['stability']['transitions']={f'{a}->{b}':int(n) for (a,b),n in R['stability']['transitions'].items()}
(O/'A_decoder_evidence.json').write_text(json.dumps(R,indent=2));print(json.dumps({'quality':R['quality'],'status':R['status'],'stability':R['stability']},indent=2))
for b,s in R['buckets'].items(): print(b,s['n_calls'],[(x['term'],x['n'],round(x['rest_rate'],3)) for x in s['distinctive_bigrams'][:5]], 'topics',s['eval_topics'])
