import pandas as pd

df = pd.read_csv('dataset/sample_requests.csv')
for idx, r in df.iterrows():
    print(f"{r['request_id']} | Safe: {r['amount_safe_to_pay']} | Status: {r['affordability_status']} | Method: {r['recommended_payment_method']} | Plan: {r['payment_plan']} | Earliest: {r['earliest_date_for_full_payment']} | Changes: {r['spending_changes_needed']}")
    print(f"  Explanation: {r['decision_explanation']}\n")
