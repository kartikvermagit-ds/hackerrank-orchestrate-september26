import os
import sys
import pandas as pd
import numpy as np

# Ensure code/ is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import run_pipeline

def evaluate_sample_requests(dataset_dir: str = 'dataset'):
    print("==================================================")
    print("Evaluating Buy or Wait on sample_requests.csv...")
    print("==================================================")

    sample_path = os.path.join(dataset_dir, 'sample_requests.csv')
    ground_truth = pd.read_csv(sample_path)
    
    # Run predictions on sample_requests.csv
    pred_path = os.path.join(dataset_dir, 'sample_predictions.csv')
    preds = run_pipeline(dataset_dir=dataset_dir, requests_file='sample_requests.csv', output_file=pred_path)

    # Compare columns
    cols_to_compare = [
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed'
    ]

    total_rows = len(ground_truth)
    scores = {}

    print("\n--- Detailed Comparison per Request ---")
    for idx, gt_row in ground_truth.iterrows():
        req_id = gt_row['request_id']
        pred_row = preds[preds['request_id'] == req_id].iloc[0]

        row_diffs = []
        # Safe amount
        gt_safe = float(gt_row['amount_safe_to_pay'])
        pred_safe = float(pred_row['amount_safe_to_pay'])
        if abs(gt_safe - pred_safe) > 1.0:
            row_diffs.append(f"safe_amt (gt={gt_safe:.2f}, pred={pred_safe:.2f})")

        # Affordability status
        if str(gt_row['affordability_status']).strip() != str(pred_row['affordability_status']).strip():
            row_diffs.append(f"status (gt={gt_row['affordability_status']}, pred={pred_row['affordability_status']})")

        # Payment method
        if str(gt_row['recommended_payment_method']).strip() != str(pred_row['recommended_payment_method']).strip():
            row_diffs.append(f"method (gt={gt_row['recommended_payment_method']}, pred={pred_row['recommended_payment_method']})")

        # Payment plan
        if str(gt_row['payment_plan']).strip() != str(pred_row['payment_plan']).strip():
            row_diffs.append(f"plan (gt={gt_row['payment_plan']}, pred={pred_row['payment_plan']})")

        # Earliest date
        gt_date = "" if pd.isna(gt_row['earliest_date_for_full_payment']) else str(gt_row['earliest_date_for_full_payment']).strip()
        pred_date = "" if pd.isna(pred_row['earliest_date_for_full_payment']) else str(pred_row['earliest_date_for_full_payment']).strip()
        if gt_date != pred_date:
            row_diffs.append(f"earliest_date (gt={gt_date}, pred={pred_date})")

        # Spending changes
        if str(gt_row['spending_changes_needed']).strip() != str(pred_row['spending_changes_needed']).strip():
            row_diffs.append(f"changes (gt={gt_row['spending_changes_needed']}, pred={pred_row['spending_changes_needed']})")

        status_str = "MATCH" if not row_diffs else "DIFF: " + ", ".join(row_diffs)
        print(f"[{idx+1:02d}] {req_id}: {status_str}")

    print("\n--- Summary Benchmark Metrics ---")
    for col in cols_to_compare:
        if col == 'amount_safe_to_pay':
            diffs = np.abs(ground_truth[col].astype(float) - preds[col].astype(float))
            exact_matches = (diffs < 1.0).sum()
            mae = diffs.mean()
            print(f"  - {col}: Exact Match = {exact_matches}/{total_rows} ({exact_matches/total_rows*100:.1f}%), MAE = {mae:.2f}")
        elif col == 'earliest_date_for_full_payment':
            gt_s = ground_truth[col].fillna("").astype(str).str.strip()
            pr_s = preds[col].fillna("").astype(str).str.strip()
            matches = (gt_s == pr_s).sum()
            print(f"  - {col}: Exact Match = {matches}/{total_rows} ({matches/total_rows*100:.1f}%)")
        else:
            gt_s = ground_truth[col].astype(str).str.strip()
            pr_s = preds[col].astype(str).str.strip()
            matches = (gt_s == pr_s).sum()
            print(f"  - {col}: Exact Match = {matches}/{total_rows} ({matches/total_rows*100:.1f}%)")

if __name__ == '__main__':
    evaluate_sample_requests()
