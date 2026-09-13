"""
Evaluation Script for Buy or Wait Financial Decision Agent
==========================================================
Runs the solution against dataset/sample_requests.csv and compares
the generated recommendations against the provided ground truth.

Reports separately:
- amount_safe_to_pay accuracy
- affordability_status accuracy
- recommended_payment_method accuracy
- payment_plan accuracy
- earliest_date_for_full_payment accuracy
- spending_changes_needed accuracy
- overall exact-row match

Discrepancies are reported with detailed diagnostics to help
identify and isolate actual logic bugs without hardcoding.
"""

import os
import sys
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

# Ensure code/ is on python search path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
code_dir = os.path.join(repo_root, 'code')
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from main import run_pipeline

def evaluate_sample_requests(dataset_dir: str = None,
                             pred_output_path: str = None) -> Dict[str, Any]:
    """Run pipeline on sample_requests.csv and benchmark metrics against ground truth."""
    if dataset_dir is None:
        dataset_dir = os.path.join(repo_root, 'dataset')
    if pred_output_path is None:
        scratch_dir = os.path.join(repo_root, 'scratch')
        os.makedirs(scratch_dir, exist_ok=True)
        pred_output_path = os.path.join(scratch_dir, 'sample_eval_predictions.csv')

    print("================================================================================")
    print("         BUY OR WAIT EVALUATION HARNESS: dataset/sample_requests.csv            ")
    print("================================================================================")
    print(f"Dataset path: {dataset_dir}")
    print(f"Predictions:  {pred_output_path}")

    # 1. Load ground truth
    sample_csv_path = os.path.join(dataset_dir, 'sample_requests.csv')
    if not os.path.exists(sample_csv_path):
        raise FileNotFoundError(f"Missing sample ground truth at {sample_csv_path}")

    ground_truth = pd.read_csv(sample_csv_path)
    total_requests = len(ground_truth)
    print(f"Loaded {total_requests} sample ground-truth requests.\n")

    # 2. Run prediction pipeline
    preds = run_pipeline(
        dataset_dir=dataset_dir,
        requests_file='sample_requests.csv',
        output_file=pred_output_path
    )

    # Align predictions by request_id
    preds_indexed = preds.set_index('request_id')

    # Metrics accumulators
    matched_safe_amt = 0
    matched_status = 0
    matched_method = 0
    matched_plan = 0
    matched_earliest_date = 0
    matched_spending_changes = 0
    matched_exact_rows = 0

    discrepancies: List[Tuple[str, List[str]]] = []

    print("\n" + "=" * 80)
    print(f"{'REQ ID':<12} | {'SAFE AMT':<8} | {'STATUS':<8} | {'METHOD':<8} | {'PLAN':<8} | {'DATE':<8} | {'CHNG':<8} | OVERALL")
    print("-" * 80)

    for idx, gt_row in ground_truth.iterrows():
        req_id = gt_row['request_id']
        if req_id not in preds_indexed.index:
            raise KeyError(f"Missing prediction for request_id '{req_id}'")

        pr_row = preds_indexed.loc[req_id]

        row_diffs = []

        # 1. amount_safe_to_pay (float comparison with tolerance 1.0)
        gt_safe = float(gt_row['amount_safe_to_pay'])
        pr_safe = float(pr_row['amount_safe_to_pay'])
        safe_amt_ok = abs(gt_safe - pr_safe) <= 1.0
        if safe_amt_ok:
            matched_safe_amt += 1
        else:
            row_diffs.append(f"safe_amt [GT: {gt_safe:.2f} vs PRED: {pr_safe:.2f}]")

        # 2. affordability_status
        gt_status = str(gt_row['affordability_status']).strip()
        pr_status = str(pr_row['affordability_status']).strip()
        status_ok = (gt_status == pr_status)
        if status_ok:
            matched_status += 1
        else:
            row_diffs.append(f"status [GT: '{gt_status}' vs PRED: '{pr_status}']")

        # 3. recommended_payment_method
        gt_method = str(gt_row['recommended_payment_method']).strip()
        pr_method = str(pr_row['recommended_payment_method']).strip()
        method_ok = (gt_method == pr_method)
        if method_ok:
            matched_method += 1
        else:
            row_diffs.append(f"method [GT: '{gt_method}' vs PRED: '{pr_method}']")

        # 4. payment_plan
        gt_plan = str(gt_row['payment_plan']).strip()
        pr_plan = str(pr_row['payment_plan']).strip()
        plan_ok = (gt_plan == pr_plan)
        if plan_ok:
            matched_plan += 1
        else:
            row_diffs.append(f"plan [GT: '{gt_plan}' vs PRED: '{pr_plan}']")

        # 5. earliest_date_for_full_payment
        gt_ed = "" if pd.isna(gt_row['earliest_date_for_full_payment']) else str(gt_row['earliest_date_for_full_payment']).strip()
        pr_ed = "" if pd.isna(pr_row['earliest_date_for_full_payment']) else str(pr_row['earliest_date_for_full_payment']).strip()
        ed_ok = (gt_ed == pr_ed)
        if ed_ok:
            matched_earliest_date += 1
        else:
            row_diffs.append(f"earliest_date [GT: '{gt_ed}' vs PRED: '{pr_ed}']")

        # 6. spending_changes_needed
        gt_sc = str(gt_row['spending_changes_needed']).strip()
        pr_sc = str(pr_row['spending_changes_needed']).strip()
        sc_ok = (gt_sc == pr_sc)
        if sc_ok:
            matched_spending_changes += 1
        else:
            row_diffs.append(f"spending_changes [GT: '{gt_sc}' vs PRED: '{pr_sc}']")

        # Overall exact-row match
        row_exact = (safe_amt_ok and status_ok and method_ok and plan_ok and ed_ok and sc_ok)
        if row_exact:
            matched_exact_rows += 1

        mark = lambda ok: "MATCH" if ok else "DIFF"
        print(f"{req_id:<12} | {mark(safe_amt_ok):<8} | {mark(status_ok):<8} | {mark(method_ok):<8} | {mark(plan_ok):<8} | {mark(ed_ok):<8} | {mark(sc_ok):<8} | {'EXACT' if row_exact else 'MISMATCH'}")

        if not row_exact:
            discrepancies.append((req_id, row_diffs))

    # Calculate percentages
    acc_safe = (matched_safe_amt / total_requests) * 100.0
    acc_status = (matched_status / total_requests) * 100.0
    acc_method = (matched_method / total_requests) * 100.0
    acc_plan = (matched_plan / total_requests) * 100.0
    acc_ed = (matched_earliest_date / total_requests) * 100.0
    acc_sc = (matched_spending_changes / total_requests) * 100.0
    acc_overall = (matched_exact_rows / total_requests) * 100.0

    print("\n" + "=" * 80)
    print("                     EVALUATION ACCURACY SUMMARY                                ")
    print("=" * 80)
    print(f"  - amount_safe_to_pay accuracy:           {matched_safe_amt:>2}/{total_requests} ({acc_safe:6.2f}%)")
    print(f"  - affordability_status accuracy:         {matched_status:>2}/{total_requests} ({acc_status:6.2f}%)")
    print(f"  - recommended_payment_method accuracy:   {matched_method:>2}/{total_requests} ({acc_method:6.2f}%)")
    print(f"  - payment_plan accuracy:                 {matched_plan:>2}/{total_requests} ({acc_plan:6.2f}%)")
    print(f"  - earliest_date_for_full_payment accuracy:{matched_earliest_date:>2}/{total_requests} ({acc_ed:6.2f}%)")
    print(f"  - spending_changes_needed accuracy:      {matched_spending_changes:>2}/{total_requests} ({acc_sc:6.2f}%)")
    print("-" * 80)
    print(f"  - overall exact-row match:               {matched_exact_rows:>2}/{total_requests} ({acc_overall:6.2f}%)")
    print("=" * 80)

    if discrepancies:
        print("\n--- Discrepancy Breakdown for Bug Diagnosis ---")
        for r_id, diffs in discrepancies:
            print(f"Request {r_id}:")
            for d in diffs:
                print(f"   * {d}")
    else:
        print("\nAll 25 sample requests matched ground truth perfectly across all fields!")

    return {
        'total_requests': total_requests,
        'amount_safe_to_pay_accuracy': acc_safe,
        'affordability_status_accuracy': acc_status,
        'recommended_payment_method_accuracy': acc_method,
        'payment_plan_accuracy': acc_plan,
        'earliest_date_for_full_payment_accuracy': acc_ed,
        'spending_changes_needed_accuracy': acc_sc,
        'overall_exact_row_match_accuracy': acc_overall,
        'discrepancies': discrepancies
    }

if __name__ == '__main__':
    evaluate_sample_requests()
