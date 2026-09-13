import pandas as pd

df = pd.read_csv('dataset/sample_requests.csv')
for idx, r in df.iterrows():
    print(f"{r['request_id']}: safe={r['amount_safe_to_pay']}, req={r['requested_amount']}, status={r['affordability_status']}, method={r['recommended_payment_method']}, chng={r['spending_changes_needed']}")
