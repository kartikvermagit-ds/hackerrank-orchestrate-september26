import pandas as pd
from datetime import datetime

df = pd.read_csv('dataset/sample_requests.csv')
profs = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
events = pd.read_csv('dataset/financial_events.csv')

for idx, r in df.iterrows():
    u = r['user_id']
    p = profs.loc[u]
    bal = float(p['current_available_balance'])
    min_bal = float(p['minimum_balance_to_keep'])
    diff = bal - min_bal
    req_amt = float(r['requested_amount'])
    safe = float(r['amount_safe_to_pay'])
    print(f"{r['request_id']} ({u}): Req={req_amt}, Safe={safe}, Bal={bal}, Min={min_bal}, Bal-Min={diff:.2f}, Diff-Safe={diff - safe:.2f}")
