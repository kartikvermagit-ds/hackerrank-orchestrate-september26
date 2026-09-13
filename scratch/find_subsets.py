import pandas as pd
from itertools import combinations

events = pd.read_csv('dataset/financial_events.csv')
profiles = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
sample_df = pd.read_csv('dataset/sample_requests.csv')

def find_subsets(target, amounts, items):
    found = []
    n = len(amounts)
    for r in range(1, min(6, n + 1)):
        for combo in combinations(range(n), r):
            s = sum(amounts[i] for i in combo)
            if abs(s - target) < 0.05:
                found.append([items[i] for i in combo])
    return found

for r_id in ['request_22', 'request_08', 'request_18', 'request_21', 'request_15']:
    row = sample_df[sample_df['request_id'] == r_id].iloc[0]
    u = row['user_id']
    req_date = row['request_date']
    p = profiles.loc[u]
    diff = float(p['current_available_balance']) - float(p['minimum_balance_to_keep'])
    safe = float(row['amount_safe_to_pay'])
    target = diff - safe
    print(f"\nTarget for {r_id} ({u}, req_date={req_date}): {target:.2f}")
    uev = events[events['user_id'] == u].copy()
    uev['amount'] = uev['amount'].astype(float)
    # let's look at all unique events
    items = []
    amounts = []
    for _, e in uev.iterrows():
        items.append(f"{e['event_id']}:{e['category']}:{e['amount']}:{e['status']}:{e['event_date']}")
        amounts.append(e['amount'])
    subsets = find_subsets(target, amounts, items)
    for s in subsets[:5]:
        print("  Found subset:", s)
