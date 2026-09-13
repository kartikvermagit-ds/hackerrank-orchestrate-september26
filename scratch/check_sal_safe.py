import pandas as pd

df = pd.read_csv('dataset/sample_requests.csv')
events = pd.read_csv('dataset/financial_events.csv')
profs = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')

for r_id in ['request_05', 'request_10', 'request_20', 'request_25']:
    row = df[df['request_id'] == r_id].iloc[0]
    u = row['user_id']
    safe = float(row['amount_safe_to_pay'])
    uev = events[events['user_id'] == u]
    sal = uev[uev['category'] == 'salary']
    print(f"{r_id} ({u}): safe={safe}")
    if len(sal) > 0:
        print("  salaries:", sal['amount'].tolist())
    else:
        print("  income events:", uev[uev['direction'] == 'credit']['amount'].tolist())
