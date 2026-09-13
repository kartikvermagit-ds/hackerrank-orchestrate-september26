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
"""

import os
import sys

# Ensure parent code directory is on sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_code_dir = os.path.dirname(current_dir)
repo_root = os.path.dirname(parent_code_dir)
if parent_code_dir not in sys.path:
    sys.path.insert(0, parent_code_dir)

# Import implementation from evaluation/evaluate.py
eval_script_path = os.path.join(repo_root, 'evaluation')
if eval_script_path not in sys.path:
    sys.path.insert(0, eval_script_path)

from evaluate import evaluate_sample_requests

if __name__ == '__main__':
    evaluate_sample_requests()
