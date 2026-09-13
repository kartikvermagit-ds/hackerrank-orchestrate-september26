import pandas as pd

preds = pd.read_csv('scratch/sample_eval_preds.csv').set_index('request_id')
gt = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

for rid in gt.index:
    p_row = preds.loc[rid]
    g_row = gt.loc[rid]
    diffs = []
    if str(p_row['affordability_status']).strip() != str(g_row['affordability_status']).strip():
        diffs.append(f"status: GT='{g_row['affordability_status']}' vs PR='{p_row['affordability_status']}'")
    if str(p_row['recommended_payment_method']).strip() != str(g_row['recommended_payment_method']).strip():
        diffs.append(f"method: GT='{g_row['recommended_payment_method']}' vs PR='{p_row['recommended_payment_method']}'")
    if str(p_row['payment_plan']).strip() != str(g_row['payment_plan']).strip():
        diffs.append(f"plan: GT='{g_row['payment_plan']}' vs PR='{p_row['payment_plan']}'")
    gt_d = str(g_row['earliest_date_for_full_payment']).strip() if pd.notna(g_row['earliest_date_for_full_payment']) else ""
    pr_d = str(p_row['earliest_date_for_full_payment']).strip() if pd.notna(p_row['earliest_date_for_full_payment']) else ""
    if gt_d != pr_d:
        diffs.append(f"date: GT='{gt_d}' vs PR='{pr_d}'")
    if str(p_row['spending_changes_needed']).strip() != str(g_row['spending_changes_needed']).strip():
        diffs.append(f"chg: GT='{g_row['spending_changes_needed']}' vs PR='{p_row['spending_changes_needed']}'")
    if diffs:
        print(f"{rid}: {', '.join(diffs)}")
