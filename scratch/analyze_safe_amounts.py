import pandas as pd
import numpy as np

df = pd.read_csv('dataset/sample_requests.csv')
p = pd.read_csv('dataset/financial_profiles.csv')
e = pd.read_csv('dataset/financial_events.csv')

print(f"{'REQ_ID':<11} | {'USER':<8} | {'REQ_DATE':<10} | {'REQ_AMT':<9} | {'GT_SAFE':<10} | {'RAW_HEAD':<10} | {'RESERVED':<10}")
print("-" * 85)

for idx, r in df.iterrows():
    prof = p[p['user_id'] == r['user_id']].iloc[0]
    headroom_raw = prof['current_available_balance'] - prof['minimum_balance_to_keep']
    gt_safe = float(r['amount_safe_to_pay'])
    reserved = headroom_raw - gt_safe
    print(f"{r['request_id']:<11} | {r['user_id']:<8} | {r['request_date']:<10} | {r['requested_amount']:<9.2f} | {gt_safe:<10.2f} | {headroom_raw:<10.2f} | {reserved:<10.2f}")
