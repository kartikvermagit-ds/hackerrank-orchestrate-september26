import os, sys
import pandas as pd

profiles = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
requests = pd.read_csv('dataset/sample_requests.csv')
events = pd.read_csv('dataset/financial_events.csv')

for rid in ['request_05', 'request_10', 'request_18', 'request_19', 'request_20', 'request_23', 'request_24', 'request_25']:
    req = requests[requests['request_id'] == rid].iloc[0]
    uid = req['user_id']
    prof = profiles.loc[uid]
    
    avail = prof['current_available_balance']
    min_bal = prof['minimum_balance_to_keep']
    headroom = avail - min_bal
    gt_safe = req['amount_safe_to_pay']
    diff = headroom - gt_safe
    
    # user events before and around request_date
    u_evs = events[events['user_id'] == uid]
    pend_debits = u_evs[(u_evs['status'] == 'pending') & (u_evs['direction'] == 'debit')]['amount'].sum()
    
    print(f"{rid} ({uid}, date={req['request_date']}):")
    print(f"  avail={avail}, min_bal={min_bal}, headroom={headroom}, gt_safe={gt_safe}")
    print(f"  diff = headroom - gt_safe = {diff}")
    print(f"  pending_debits = {pend_debits}")
    print(f"  diff - pending_debits = {diff - pend_debits}")
    print()
