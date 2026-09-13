import pandas as pd

df = pd.read_csv('dataset/sample_requests.csv')
profs = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
events = pd.read_csv('dataset/financial_events.csv')

for r_id in ['request_08', 'request_18', 'request_21', 'request_22', 'request_06', 'request_14', 'request_15', 'request_07', 'request_19', 'request_24']:
    row = df[df['request_id'] == r_id].iloc[0]
    u = row['user_id']
    req_date = row['request_date']
    p = profs.loc[u]
    diff = float(p['current_available_balance']) - float(p['minimum_balance_to_keep'])
    safe = float(row['amount_safe_to_pay'])
    target_deduction = diff - safe
    print(f"\n=== {r_id} ({u}) req_date={req_date} target_deduction={target_deduction:.2f} ===")
    uev = events[events['user_id'] == u].copy()
    uev['amount'] = uev['amount'].astype(float)
    # Print all events around req_date or all recurring events
    # Let's see all categories and amounts
    # Find subset of amounts or sum of debit events
    debits = uev[uev['direction'] == 'debit']
    # check if any single event or combination matches target_deduction exactly!
    print(f"Checking single events matching {target_deduction:.2f}:")
    matches = uev[abs(uev['amount'] - target_deduction) < 0.01]
    for _, m in matches.iterrows():
        print(f"  EXACT MATCH: {m['event_id']} | {m['event_date']} | {m['category']} | {m['status']} | {m['amount']} | {m['description']}")
    
    # Check debits on or after req_date
    future_debits = debits[debits['event_date'] >= req_date].sort_values('event_date')
    print("Future debits:")
    for _, fd in future_debits.head(10).iterrows():
        print(f"  {fd['event_id']} | {fd['event_date']} | {fd['category']} | {fd['status']} | {fd['amount']} | {fd['description']}")
