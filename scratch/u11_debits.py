import pandas as pd

events = pd.read_csv('dataset/financial_events.csv')
u11 = events[events['user_id'] == 'user_11'].copy()
u11['amount'] = u11['amount'].astype(float)

print("All user_11 debit events by category (unique amounts or recent amounts):")
recent = u11[(u11['event_date'] >= '2025-04-01') & (u11['event_date'] <= '2025-05-03')]
for _, e in recent.iterrows():
    print(f"  {e['event_id']} | {e['event_date']} | {e['category']} | {e['direction']} | {e['amount']} | {e['description']}")

print("\nApril 2025 debits sum by category:")
apr_debits = u11[(u11['event_date'] >= '2025-04-01') & (u11['event_date'] < '2025-05-01') & (u11['direction'] == 'debit')]
print(apr_debits.groupby('category')['amount'].sum())
print("Total April debits:", apr_debits['amount'].sum())
