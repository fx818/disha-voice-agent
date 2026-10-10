from pathlib import Path
import json
O=Path('outputs/segmentation');r=json.loads((O/'A_decoder_evidence.json').read_text()); B=r['buckets']; A=r['all'];N=A['n_calls']
# Expansion guesses are deliberately separate from observed campaign meaning.
M={
'PIM':('Paid Interest Marker (suffix unverified)','Explored paid services; payment-interest sales outreach','high','free->paid'),
'PUA':('Platform User Activity (tentative)','Viewed or checked BuyLeads; active-user sales outreach, not proven non-consumption','med','free->paid'),
'UA':('User Activity (tentative)','Local buyer-demand pitch and catalog-improvement meeting; exact trigger unknown','low','generic sales meeting'),
'PAM':('Package-interest Marker (tentative)','Interest in purchasing a paid package','high','free->paid'),
'OLP':('Online Lead Purchase/payment (tentative)','BuyLead purchase or payment attempt; monetization intent, not completed subscription','high','free->paid'),
'SCHD':('Scheduled demo','Follow up on a booked/requested demo','high','warm follow-up'),
'PUT':('Profile Update Trigger (tentative)','Profile/catalog improvement and enquiry-demand pitch; underlying trigger uncertain','low','profile enrichment'),
'NUR':('New User Registration','Recently created account; onboarding and profile visibility','high','profile enrichment'),
'PANF':('Package-interest, not-followed-up? (unverified)','Paid-package outreach; free-plan status is not established by this code','med','free->paid'),
'ENQR':('Enquiry Received (tentative)','Buyer-enquiry-triggered profile/meeting outreach; unread/unanswered status unproven','med','generic sales meeting'),
'PNSR':('PNS Received (tentative; PNS expansion unverified)','PNS-related outreach; missed-versus-received distinction unresolved','low','lead non-consumption'),
'PNSM':('PNS Missed (tentative; PNS expansion unverified)','Likely missed PNS opportunity recovery; received/missed evaluator label is shared','low','lead non-consumption'),
'PNCHF':('Expansion unresolved','Paid-package interest with profile-improvement sales pitch; exact trigger unresolved','med','free->paid'),
'OLPR':('Online Lead Purchase Recent (tentative)','Recent BuyLead purchase; follow-up sales meeting, not proof of subscription','med','warm follow-up'),
'NVGT':('Navigation trigger? (unverified)','Sparse generic sales/profile outreach; no supported specific trigger','low','generic sales meeting'),
'TF':('Tele-follow-up? (unverified)','Sparse profile/catalog outreach; no supported specific trigger','low','generic sales meeting'),
'UATF':('User Activity / Tele-follow-up? (unverified)','Tiny sample; profile/catalog pitch observed','low','generic sales meeting'),
'NS':('Expansion unresolved','One call; insufficient evidence to decode','low','generic sales meeting')}
def pct(n,d):return f'{100*n/d:.2f}%' if d else '—'
def nr(n,d):return f'{n:,}/{d:,} ({pct(n,d)})'
def table(h,rows):return '| '+' | '.join(h)+' |\n|'+'|'.join(['---']*len(h))+'|\n'+'\n'.join('| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows)+'\n'
def strength(n,p,q):return 'strong' if n>=1000 and abs(p-q)>=.05 else ('moderate' if n>=100 and abs(p-q)>=.03 else 'weak')
order=sorted(B,key=lambda b:-B[b]['n_calls'])
out=['# Campaign bucket decoder','Data: answered bot calls, '+r['quality']['date_min']+' through '+r['quality']['date_max']+'. Inferences describe campaign pitches, not documented trigger definitions or verified seller attributes.',
'## Conclusions',f"Coverage: {N:,} calls, {A['n_sellers']:,} called sellers, {len(B)} buckets and {len(r['versions'])} bot versions. Baseline meeting_fixed: {nr(A['meeting_n'],N)}; early drop: {nr(A['early_n'],A['duration_n'])}; median duration {A['median_duration']:.0f}s.",
'PIM/PAM/OLP provide the clearest monetization-intent signals; SCHD is demo follow-up; NUR is new-user onboarding. PUA is BuyLead activity. NUR should not be treated as warm follow-up merely because its meeting rate is high. Supporting counts, rates, rest-of-corpus baselines and strengths are below.',
'No bucket establishes dormant re-activation. PNSM/PNSR are provisional lead non-consumption routes; enquiry receipt alone (ENQR) does not establish non-consumption. Catalog/profile pitches occur across campaigns, so they do not establish an incomplete catalog. Verify engagement/profile fields before assigning these seller-level categories.',
'## Call outcomes',
'Rates use all calls in each row; duration statistics use non-null duration. Mix cells are count (percent). meeting_fixed uses its numeric flag, not disposition_label. Global row is the baseline; seller counts overlap across buckets/versions. Outcome differences are descriptive, not causal campaign effects.']
labels=['Not Interested','General (talked)','Call Later / Busy','Meeting Fixed']
def statrow(k,s):return [k,f"{s['n_calls']:,}",f"{s['n_sellers']:,}",f"{s['meeting_n']:,} ({100*s['meeting_rate']:.2f}%)",f"{s['median_duration']:.1f}",f"{s['early_n']:,} ({100*s['early_rate']:.2f}%)"]+[f"{s['disposition'].get(l,0):,} ({pct(s['disposition'].get(l,0),s['n_calls'])})" for l in labels]
h=['Group','Calls','Sellers','Meeting flag','Median s','<10s','Not interested','General','Later/busy','Meeting label']
out += [table(h,[statrow('ALL',A)]+[statrow(b,B[b]) for b in order]),'### Bot versions',table(h,[statrow(k,s) for k,s in sorted(r['versions'].items(),key=lambda x:-x[1]['n_calls'])])]
out+=['## Proposed code map','Confidence refers to operational meaning, not the guessed literal expansion. All acronym expansions except transparent SCHD/NUR remain undocumented. Free→paid is a campaign routing category, not a free-status label. Low-confidence codes should retain a generic fallback.',table(['Code','Best-guess expansion','Meaning','Confidence','Draft category'],[[b,*M[b]] for b in order])]
mp={b:{'meaning':M[b][1],'confidence':M[b][2],'category':M[b][3],'n_calls':B[b]['n_calls'],'meeting_rate':B[b]['meeting_rate']} for b in order};(O/'A_bucket_map.json').write_text(json.dumps(mp,indent=2)+'\n')
out+=['## Summary keyword rates', 'Each cell is matching-call count (percent of nonempty summaries). Case-insensitive regex; enquir includes inquiry spellings, catalog includes catalogue, other stems as requested. Literal keywords can occur in denials, pitches or business names (especially renew/GST/product); they are not verified seller attributes. ALL is the baseline; exact regexes are in the analysis script.']
keys=list(r['keyword_all']);out += [table(['Bucket','Nonempty summaries']+keys,[[b,f"{s['summary_n']:,}"]+[f"{s['keywords'][k]} ({pct(s['keywords'][k],s['summary_n'])})" for k in keys] for b,s in [('ALL',{'summary_n':A['summary_n'],'keywords':r['keyword_all']})]+[(b,B[b]) for b in order]])]
out+=['## Distinctive language and evaluator checks', 'Words/bigrams are ranked by smoothed document log-odds versus all other nonempty summaries: log((a+0.5)/(n−a+0.5)) minus the same log-odds outside the bucket. Minimum document frequency max(2,min(20,ceil(0.005n))). A documented campaign-vocabulary allowlist excludes names, locations and product names; adjacent bigrams only. Repeated sellers/templates remain, so this is campaign language rather than independent seller testimony.',
'Evaluators are loaded separately with pyarrow eval_agent filters, deduplicated by attempt_id and joined to calls. Random seed 42; up to 100 available calls per bucket per evaluator, sampled independently of duration and outcome. Baselines below are pooled stratified samples excluding the current bucket, not population-weighted estimates. Topics can overlap; disposition/sub-disposition is single-valued. No evaluator coverage is explicitly shown as unavailable.',
'Evidence strength: strong = n≥1,000 and absolute rate gap≥5 percentage points; moderate = n≥100 and gap≥3 points; otherwise weak. This is a descriptive threshold, not a significance test or confidence in exact acronym spelling.']
for b in order:
 s=B[b];out+=['### '+b]
 terms=s['distinctive_words'][:4]+s['distinctive_bigrams'][:4]
 out+=[table(['Term','Bucket n / summary n (%)','Rest n / summary n (%)','Log-odds','Strength'],[[x['term'],nr(x['n'],s['summary_n']),nr(x['rest_n'],A['summary_n']-s['summary_n']),f"{x['log_odds']:.2f}",strength(s['summary_n'],x['rate'],x['rest_rate'])] for x in terms]) if terms else 'No term clears the minimum frequency threshold.']
 for agent in ['topics','disposition']:
  e=s['eval_'+agent];base=r[agent+'_all'];den=base['sample_n']-e['parsed_n']
  cc=e['counts']
  if agent=='topics':cc={k:v for k,v in cc.items() if k.startswith(('T08_','T09_','T10_','T11_','T12_','T13_','T14_','T16_','T26_'))}
  items=sorted(cc.items(),key=lambda x:-x[1])[:4]
  out += [f"**{agent}**: available {nr(e['available'],s['n_calls'])}; sampled {e['sample_n']}, parsed {e['parsed_n']}. Baseline availability {nr(base['matched_n'],N)}."]
  if items:out += [table(['Label','Bucket sample n/N (%)','Rest sample n/N (%)','Strength'],[[k,nr(v,e['parsed_n']),nr(base['counts'].get(k,0)-v,den),strength(e['parsed_n'],v/e['parsed_n'],(base['counts'].get(k,0)-v)/den if den else 0)] for k,v in items])]
  else:out+=['No relevant labels available in this sample.']
 out += [f"**Short summary excerpts**: {len(s['representatives'])} selected from {nr(s['long_summary_n'],s['n_calls'])} calls with duration >30s and a summary (global baseline {nr(sum(x['long_summary_n'] for x in B.values()),N)}). Fixed-seed random calls; excerpts show substantive clauses where possible, capped at 150 characters and names/numbers redacted. Illustrative, not prevalence evidence. "+('Fewer than eight eligible calls exist.' if s['long_summary_n']<8 else '')]
 out += [table(['Attempt','Seconds','Excerpt'],[[x['attempt_id'],x['duration'],x['snippet']] for x in s['representatives']]) if s['representatives'] else 'No eligible long-call summary.']
S=r['status'];T=S['universe_n']
out+=['## Inferred paid/free status', 'Conservative, historical, summary-based tags—not verified current subscriptions. Match explicit use/ownership of a free listing/plan, or an existing paid plan/subscription or explicit paid-customer/user assertion; reject nearby negation, past-only free references and another-company/account paid references. Conflicting free/paid assertions remain unknown. Calls stating “already paid” without identifying a subscription remain unknown. Bot-introduction assertions that a lead is a paid customer/user are unverified and may reflect summary/template errors; do not use these tags for billing, entitlement or suppression decisions. All tags carry low-confidence evidence. Another-account/firm subscriptions are excluded where stated. Evidence JSON preserves source attempt, date and matched phrase.',
'Bucket-only signals: PIM/PAM/OLP/PUA/PANF suggest conversion intent but cannot distinguish free users from paid users considering another purchase. OLPR suggests a BuyLead purchase, not subscription ownership. “Package”, “payment”, “renew” and “free visit” alone are insufficient. PANF is not automatically free.',
 table(['Status','Seller n / all sellers (%)','Interpretation'],[[k,nr(S['counts'].get(k,0),T),v] for k,v in [('free','Explicit free-use assertion'),('paid','Explicit paid-status assertion'),('unknown','No qualifying assertion or conflict')]]),
 f"Signal coverage: free assertions {nr(S['free_signal_calls'],N)}, paid assertions {nr(S['paid_signal_calls'],N)}; conflicts {nr(S['conflict_sellers'],T)}. Baseline is all calls/sellers, respectively. Weak evidence for true subscription prevalence: these counts are text-detectable lower-coverage estimates, not population estimates. {T-A['n_sellers']:,}/{T:,} sellers have no answered call here and remain unknown.",
 table(['Bucket','Free assertions / calls (%)','Paid assertions / calls (%)'],[[b,nr(S['by_bucket'][b]['free'],B[b]['n_calls']),nr(S['by_bucket'][b]['paid'],B[b]['n_calls'])] for b in order]),
 table(['Matched phrase','Calls / all calls (%)'],[[k,nr(v,N)] for k,v in sorted(S['phrases'].items(),key=lambda x:-x[1])])]
q=r['stability']; out+=['## Seller bucket stability',table(['Measure','Count/rate','Baseline / interpretation'],[
['Multiple buckets',nr(q['multi_bucket_sellers'],q['called_sellers']),'All called sellers; descriptive strong coverage'],
['Multiple buckets among repeat sellers',nr(q['multi_bucket_sellers'],q['repeat_sellers']),'Removes one-call sellers who cannot switch'],
['Single-call sellers',nr(q['single_call_sellers'],q['called_sellers']),'Stability not observable'],
['Consecutive calls change bucket',nr(q['changed_pairs'],q['adjacent_pairs']),'Within-seller chronological pairs'],
['Mean dominant-bucket share',f"{q['dominant_share_mean']:.2%}",'Called sellers equally weighted'],
['Repeat-seller mean / median dominant share',f"{q['repeat_dominant_share_mean']:.2%} / {q['repeat_dominant_share_median']:.2%}",'Baseline = all-called mean above']]),table(['Distinct buckets','Sellers / called sellers (%)'],[[k,nr(v,q['called_sellers'])] for k,v in q['bucket_count_distribution'].items()]),table(['Top change','n / changed adjacent pairs (%)'],[[k,nr(v,q['changed_pairs'])] for k,v in q['transitions'].items()]),
'Use redis_bucket as a per-call trigger, not a permanent seller segment. For seller routing, combine latest supported trigger with engagement/profile data and explicit recent callback history; preserve secondary flags. A modal bucket describes history but can hide a recent shift. No code alone confirms dormancy or paid status. Transition comparisons describe answered calls only, not all attempts.']
out+=['## Reproduction and data checks',f"Run `.venv/bin/python -I outputs/segmentation/scripts/decode_buckets.py`, then `.venv/bin/python -I outputs/segmentation/scripts/render_bucket_report.py`. Reads project only the needed parquet columns; evaluator reads are filtered and sequential. Detailed counts: `A_decoder_evidence.json`. All writes remain under outputs/segmentation/.",f"Unique attempt IDs: duplicates={r['quality']['duplicate_attempts']}; missing seller IDs={r['quality']['missing_sellers']}; non-null durations={nr(A['duration_n'],N)}; nonempty summaries={nr(A['summary_n'],N)}. Flag/label disagreement={nr(r['quality']['meeting_disagreement'],N)}. Chronology: {q['missing_time']} missing timestamps, {q['tied_seller_time_rows']} tied seller/time rows; attempt_id breaks ties.",f"Evaluator matched/raw: topics {r['topics_all']['matched_n']:,}/{r['topics_all']['raw_n']:,}, disposition {r['disposition_all']['matched_n']:,}/{r['disposition_all']['raw_n']:,}. Duplicate attempt records discarded: topics {r['topics_all']['duplicate_attempts']}, disposition {r['disposition_all']['duplicate_attempts']}. Existing evidence_report.md used for context; new counts calculated from cache."]
(O/'A_bucket_decoder.md').write_text('\n\n'.join(out)+'\n');print('Wrote decoder and map; status:',S['counts'])
