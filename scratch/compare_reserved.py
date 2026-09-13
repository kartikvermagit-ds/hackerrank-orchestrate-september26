import pandas as pd
import numpy as np

# Let's inspect the ratio between PR_safe and GT_safe across all 25 samples
preds = pd.read_csv('scratch/sample_eval_preds.csv').set_index('request_id')
gt = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')
p = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')

for rid in gt.index:
    g = gt.loc[rid]
    pr = preds.loc[rid]
    uid = g['user_id']
    prof = p.loc[uid]
    
    gt_safe = float(g['amount_safe_to_pay'])
    pr_safe = float(pr['amount_safe_to_pay'])
    req_amt = float(g['requested_amount'])
    raw_head = prof['current_available_balance'] - prof['minimum_balance_to_keep']
    
    gt_res = raw_head - gt_safe
    pr_res = raw_head - pr_safe
    
    print(f"{rid:<11} | req={req_amt:<9.2f} | GT_safe={gt_safe:<10.2f} | PR_safe={pr_safe:<10.2f} | GT_res={gt_res:<10.2f} | PR_res={pr_res:<10.2f} | Diff_res={gt_res - pr_res:<10.2f}")
