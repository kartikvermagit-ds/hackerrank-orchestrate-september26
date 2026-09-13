import pandas as pd

events = pd.read_csv('dataset/financial_events.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv')

for r_id in ['request_04', 'request_14', 'request_18', 'request_19', 'request_23']:
    row = sample_df[sample_df['request_id'] == r_id].iloc[0]
    u = row['user_id']
    safe = float(row['amount_safe_to_pay'])
    uev = events[(events['user_id'] == u) & (events['status'] == 'settled')].copy()
    uev['amount'] = uev['amount'].astype(float)
    sal = uev[uev['category'] == 'salary']['amount'].iloc[-1]
    debits = uev[uev['direction'] == 'debit']
    # sum debits by month
    debits['month'] = debits['event_date'].str[:7]
    monthly_debits = debits.groupby('month')['amount'].sum()
    print(f"\n=== {r_id} ({u}) safe={safe:.2f} salary={sal:.2f} sal - safe={sal - safe:.2f} ===")
    print("Monthly debits:")
    print(monthly_debits.tail(5))
