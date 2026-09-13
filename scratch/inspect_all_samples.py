import pandas as pd
samples = pd.read_csv('dataset/sample_requests.csv')
for _, r in samples.iterrows():
    print(f"{r['request_id']} | req_date: {r['request_date']} | due_date: {r['desired_completion_date']} | amt: {r['requested_amount']} | safe_amt: {r['amount_safe_to_pay']} | status: {r['affordability_status']} | method: {r['recommended_payment_method']} | earliest: {r['earliest_date_for_full_payment']} | plan: {r['payment_plan']} | changes: {r['spending_changes_needed']}")
