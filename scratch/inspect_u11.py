import pandas as pd

samples = pd.read_csv('dataset/sample_requests.csv')
print('=== SAMPLE REQUEST 11 ===')
for col in samples.columns:
    val = samples[samples['request_id'] == 'request_11'][col].values[0]
    print(f'{col}: {val}')

profiles = pd.read_csv('dataset/financial_profiles.csv')
print('\n=== PROFILE 11 ===')
for col in profiles.columns:
    val = profiles[profiles['user_id'] == 'user_11'][col].values[0]
    print(f'{col}: {val}')

events = pd.read_csv('dataset/financial_events.csv')
u11_events = events[events['user_id'] == 'user_11'].sort_values('settlement_date')
print('\n=== EVENTS 11 (Income & Debits) ===')
for idx, row in u11_events.iterrows():
    print(f"{row['event_id']} | {row['settlement_date']} | {row['event_type']} | {row['category']} | {row['amount']} {row['currency']} | {row['direction']} | {row['status']} | {row['description']}")
