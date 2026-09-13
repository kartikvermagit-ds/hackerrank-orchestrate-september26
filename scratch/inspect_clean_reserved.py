import pandas as pd

p = pd.read_csv('dataset/financial_profiles.csv')
e = pd.read_csv('dataset/financial_events.csv')
r = pd.read_csv('dataset/sample_requests.csv')

users = ['user_06', 'user_08', 'user_14', 'user_15', 'user_18', 'user_21', 'user_22']

for u in users:
    req = r[r['user_id'] == u].iloc[0]
    prof = p[p['user_id'] == u].iloc[0]
    headroom = prof['current_available_balance'] - prof['minimum_balance_to_keep']
    reserved = headroom - float(req['amount_safe_to_pay'])
    print(f"=== {u} ({req['request_id']}) req_date: {req['request_date']} reserved: {reserved:.2f} ===")
    u_events = e[e['user_id'] == u]
    # Check pending
    pending = u_events[u_events['status'] == 'pending']
    for _, ev in pending.iterrows():
        print(f"  PENDING: {ev['event_id']} {ev['category']} {ev['amount']} {ev['description']}")
    # Check debits in the current month or scheduled
    sched = u_events[u_events['status'] == 'scheduled']
    for _, ev in sched.iterrows():
        print(f"  SCHED: {ev['event_id']} {ev['event_date']} {ev['category']} {ev['amount']} {ev['description']}")
    # Check debits in preceding month
    sub = u_events[(u_events['direction'] == 'debit') & (u_events['status'] == 'settled')]
    sub = sub.sort_values('event_date').tail(15)
    for _, ev in sub.iterrows():
        print(f"  SETTLED: {ev['event_id']} {ev['event_date']} {ev['category']} {ev['amount']} {ev['description']}")
