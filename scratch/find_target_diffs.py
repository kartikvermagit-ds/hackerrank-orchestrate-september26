import pandas as pd

events = pd.read_csv('dataset/financial_events.csv')
requests = pd.read_csv('dataset/sample_requests.csv')
profiles = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')

targets = {
    'request_08': ('user_08', 452.00, '2025-02-07'),
    'request_14': ('user_14', 1134.00, '2025-08-04'),
    'request_15': ('user_15', 487.00, '2026-01-06'),
    'request_18': ('user_18', 624.00, '2026-07-07'),
    'request_21': ('user_21', 568.00, '2026-04-03'),
    'request_22': ('user_22', 157.00, '2024-12-05'),
    'request_24': ('user_24', 20625.00, '2026-01-04'),
}

for rid, (uid, target_diff, rdate) in targets.items():
    ue = events[events['user_id'] == uid]
    debits = ue[ue['direction'] == 'debit']
    print(f"=== {rid} ({uid}, req_date={rdate}, target_diff={target_diff}) ===")
    
    # Check all debits around req_date
    recent = debits.copy()
    recent['event_date'] = pd.to_datetime(recent['event_date'])
    rdt = pd.to_datetime(rdate)
    
    # debits in the previous 30 days
    m1 = recent[(recent['event_date'] >= rdt - pd.Timedelta(days=30)) & (recent['event_date'] < rdt)]
    print(f"Past 30d debits sum: {m1['amount'].sum():.2f}")
    
    # Check recurring monthly debits
    # print all unique amounts and descriptions
    print(debits[['event_date', 'category', 'description', 'amount', 'status', 'flexibility']].tail(15).to_string())
    print()
