import pandas as pd

events = pd.read_csv('dataset/financial_events.csv')
for u in ['user_08', 'user_18', 'user_21', 'user_22']:
    print(f"\n================ {u} ================")
    uev = events[events['user_id'] == u].copy()
    uev['amount'] = uev['amount'].astype(float)
    for _, e in uev.iterrows():
        print(f"{e['event_id']} | {e['event_date']} | {e['category']} | {e['direction']} | {e['status']} | {e['amount']} | {e['currency']} | {e['description']}")
