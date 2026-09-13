import pandas as pd

df = pd.read_csv('dataset/sample_requests.csv')
events = pd.read_csv('dataset/financial_events.csv')
profs = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')

for idx, r in df.iterrows():
    u = r['user_id']
    safe = float(r['amount_safe_to_pay'])
    req_amt = float(r['requested_amount'])
    p = profs.loc[u]
    bal = float(p['current_available_balance'])
    min_bal = float(p['minimum_balance_to_keep'])
    
    uev = events[events['user_id'] == u]
    sal = uev[uev['category'] == 'salary']
    sal_amt = sal['amount'].iloc[-1] if len(sal) > 0 else 0
    
    ratio_sal = safe / sal_amt if sal_amt > 0 else 0
    ratio_req = safe / req_amt
    diff = bal - min_bal
    ratio_diff = safe / diff if diff > 0 else 0
    
    print(f"{r['request_id']} | Safe: {safe:10.2f} | Req: {req_amt:10.2f} | Sal: {sal_amt:10.2f} | r_sal: {ratio_sal:.4f} | r_req: {ratio_req:.4f} | r_diff: {ratio_diff:.4f} | status: {r['affordability_status']}")
