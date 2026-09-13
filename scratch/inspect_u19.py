import pandas as pd

profiles = pd.read_csv('dataset/financial_profiles.csv')
p19 = profiles[profiles['user_id'] == 'user_19'].iloc[0]
print("Profile 19:")
print(f"Balance: {p19['current_available_balance']}")
print(f"Min: {p19['minimum_balance_to_keep']}")
print(f"Diff: {p19['current_available_balance'] - p19['minimum_balance_to_keep']}")

events = pd.read_csv('dataset/financial_events.csv')
u19 = events[events['user_id'] == 'user_19'].sort_values('settlement_date')
print("\nRecent Debits before 2024-09-04:")
for idx, r in u19.iterrows():
    if '2024-08-01' <= str(r['settlement_date']) <= '2024-09-15':
        print(f"{r['event_id']} | {r['settlement_date']} | {r['category']} | {r['amount']} | {r['direction']} | {r['status']} | {r['description']}")
