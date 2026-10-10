# Jev vs rules: second run (tuned questions)

Same 2100 holdout sellers as run 1 · answered: 2100 · errors: 0 · model jev-1.13.0 · median latency 0.33s · mean tokens in/out 1568/168  
Sellers with no engagement, catalog or call data (sent to discovery in code): 192

## Separation of September outcomes

| Method | Cramér's V | 95% CI | V minus rules (95% CI) | Meeting spread | Discovery share |
|---|---|---|---|---|---|
| rule_use_case | 0.089 | 0.083–0.120 | — | 10.3 pts | 16.7% |
| jev_v1_signals | 0.083 | 0.077–0.113 | -0.006 (-0.027 to +0.013) | 15.8 pts | 2.2% |
| jev_v1_choice | 0.085 | 0.079–0.117 | -0.004 (-0.025 to +0.016) | 13.0 pts | 4.8% |
| jev_v2_signals | 0.093 | 0.085–0.123 | +0.003 (-0.015 to +0.021) | 14.8 pts | 22.1% |
| jev_v2_choice | 0.086 | 0.078–0.115 | -0.004 (-0.024 to +0.014) | 12.0 pts | 18.9% |

## Outcomes per category (run 2)

### rule_use_case

| rule_use_case      |   sellers |   meeting |   not_interested |   early_drop |   median_sec |
|:-------------------|----------:|----------:|-----------------:|-------------:|-------------:|
| discovery          |       350 |      18   |             19.7 |         13.4 |         28.5 |
| free_to_paid       |       350 |       7.7 |             30.3 |         21.7 |         22   |
| lead_engagement    |       350 |      10   |             22.6 |         21.4 |         21   |
| profile_onboarding |       350 |      16   |             20.3 |         16.3 |         28   |
| reactivation       |       350 |      13.1 |             20   |         15.4 |         26   |
| warm_followup      |       350 |      16.6 |             21.4 |         16.3 |         30.5 |

### jev_v2_signals

| jev_v2_signals     |   sellers |   meeting |   not_interested |   early_drop |   median_sec |
|:-------------------|----------:|----------:|-----------------:|-------------:|-------------:|
| discovery          |       464 |      16.2 |             22.2 |         17.5 |           26 |
| free_to_paid       |       203 |       5.4 |             31   |         23.2 |           19 |
| lead_engagement    |       365 |       8.8 |             23   |         17.3 |           22 |
| profile_onboarding |       188 |      20.2 |             19.1 |         14.4 |           30 |
| reactivation       |       442 |      14.3 |             19.9 |         16.5 |           26 |
| warm_followup      |       438 |      15.1 |             21.9 |         17.1 |           32 |

### jev_v2_choice

| jev_v2_choice      |   sellers |   meeting |   not_interested |   early_drop |   median_sec |
|:-------------------|----------:|----------:|-----------------:|-------------:|-------------:|
| discovery          |       397 |      17.1 |             18.1 |         15.1 |           30 |
| free_to_paid       |       281 |       6.8 |             28.8 |         23.5 |           19 |
| lead_engagement    |       549 |       9.5 |             25   |         17.7 |           23 |
| profile_onboarding |       571 |      15.8 |             20.8 |         16.6 |           26 |
| reactivation       |         3 |       0   |              0   |          0   |           21 |
| warm_followup      |       299 |      18.7 |             20.4 |         16.1 |           35 |

## Agreement with rules

- jev_v1_signals: 55.5% exact, Cohen's κ 0.47
- jev_v1_choice: 49.3% exact, Cohen's κ 0.39
- jev_v2_signals: 70.0% exact, Cohen's κ 0.64
- jev_v2_choice: 56.5% exact, Cohen's κ 0.48

Rows = rules, columns = Jev run 2 (signals):

| rule_use_case      |   discovery |   free_to_paid |   lead_engagement |   profile_onboarding |   reactivation |   warm_followup |
|:-------------------|------------:|---------------:|------------------:|---------------------:|---------------:|----------------:|
| discovery          |         252 |              0 |                52 |                   14 |             28 |               4 |
| free_to_paid       |          75 |            169 |                22 |                   20 |              5 |              59 |
| lead_engagement    |          44 |             18 |               248 |                    3 |             15 |              22 |
| profile_onboarding |          89 |              4 |                28 |                  146 |             71 |              12 |
| reactivation       |           1 |              5 |                15 |                    0 |            322 |               7 |
| warm_followup      |           3 |              7 |                 0 |                    5 |              1 |             334 |

## Did the fixes work?

- No-data sellers: 192; their meeting rate 21.4%. Run 1 sent 192 of them to reactivation.
- inactive_business ≥ 0.5 among sellers with data: run 2 32%
- catalog_need score (0 well built … 3 almost nothing) mean by rule category: {'discovery': 1.86, 'free_to_paid': 0.9, 'lead_engagement': 0.69, 'profile_onboarding': 1.62, 'reactivation': 1.6, 'warm_followup': 1.07}
- share with catalog_need ≥ 1.5: 43%
- Direct choice confidence: median 0.66, share ≥ 0.6 58%
## Reading

- **The fixes worked.** Agreement with rules rose from 55% (κ 0.47) to 70% (κ 0.64). No-data sellers (192,
  21.4% meeting) now go to discovery instead of reactivation; inactive_business fires for 32% of sellers with
  data (was 48% of all); the catalog Score now discriminates (mean 0.69 for lead-engagement sellers vs 1.86
  for rule-discovery sellers).
- **Separation: Jev signals 0.093 vs rules 0.089** (difference +0.003, 95% CI −0.015 to +0.021). A tie with a
  slight lean to Jev; not a proven improvement at n = 2,100.
- **Where they disagree (629 sellers), Jev's labels separate outcomes a little better** (V 0.113 vs 0.101);
  where they agree (1,471), V is 0.105. Directional only.
- **The signal design beats the direct Choice** (0.093 vs 0.086, κ 0.64 vs 0.48); the Choice almost never picks
  reactivation (3 sellers).
- **Sharper groups:** Jev profile_onboarding books 20.2% vs 16.0% for rules; Jev free_to_paid 5.4% / 31% NI vs
  7.7% / 30%.
- **Cost:** ~1.57k input + 168 output tokens per seller, 0.33 s median, 2,100 sellers in 90 s, 0 errors.
