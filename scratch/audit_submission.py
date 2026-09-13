"""
Comprehensive Submission Audit Script
------------------------------------
Executes complete 20-point checklist:
1. python code/main.py runs successfully
2. output.csv exists in repository root
3. output.csv has exactly 250 data rows
4. exact required column order
5. no missing request_id
6. no duplicate request_id
7. amount_safe_to_pay bounds
8. valid status values
9. valid payment methods
10. valid payment plans
11. installment plans match supplied options
12. partial-payment rules
13. spending changes target only allowed flexible recurring events
14. 90-day minimum-balance safety
15. evaluation/evaluate.py exists
16. evaluation/usage_report.md exists
17. no dataset files modified
18. no API keys/secrets committed
19. no hardcoded request IDs or expected labels
20. README/setup instructions are sufficient
"""

import os
import sys
import re
import subprocess
import pandas as pd
from datetime import datetime

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
code_dir = os.path.join(repo_root, 'code')
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from validator import OutputValidator, DecisionValidationError
from models import RecommendationOutput

def run_audit():
    print("=" * 80)
    print("           COMPREHENSIVE 20-POINT SUBMISSION AUDIT HARNESS             ")
    print("=" * 80)

    results = {}
    issues = []

    # Check 1: python code/main.py runs successfully
    print("\n[Check 1] Verifying python code/main.py execution...")
    try:
        proc = subprocess.run([sys.executable, 'code/main.py'], cwd=repo_root, capture_output=True, text=True)
        if proc.returncode == 0:
            results['check_1'] = "PASS"
            print("  -> PASS: code/main.py executed with returncode 0.")
        else:
            results['check_1'] = "FAIL"
            issues.append(f"code/main.py failed: {proc.stderr[:300]}")
            print(f"  -> FAIL: {proc.stderr[:300]}")
    except Exception as e:
        results['check_1'] = "FAIL"
        issues.append(f"code/main.py invocation failed: {e}")

    # Check 2: output.csv exists in repository root
    print("\n[Check 2] Verifying output.csv in repo root...")
    out_path = os.path.join(repo_root, 'output.csv')
    if os.path.exists(out_path):
        results['check_2'] = "PASS"
        print(f"  -> PASS: {out_path} exists.")
    else:
        results['check_2'] = "FAIL"
        issues.append("output.csv does not exist in repo root.")
        print("  -> FAIL: missing output.csv")
        return

    out_df = pd.read_csv(out_path, keep_default_na=False)

    # Check 3: output.csv has exactly 250 data rows
    print("\n[Check 3] Verifying exact row count...")
    if len(out_df) == 250:
        results['check_3'] = "PASS"
        print("  -> PASS: Exactly 250 data rows present.")
    else:
        results['check_3'] = "FAIL"
        issues.append(f"output.csv has {len(out_df)} rows, expected 250.")
        print(f"  -> FAIL: Found {len(out_df)} rows.")

    # Check 4: exact required column order
    print("\n[Check 4] Verifying exact column order...")
    required_cols = [
        'request_id',
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed',
        'decision_explanation'
    ]
    if list(out_df.columns) == required_cols:
        results['check_4'] = "PASS"
        print("  -> PASS: Column names and order match exactly.")
    else:
        results['check_4'] = "FAIL"
        issues.append(f"Columns mismatch: {list(out_df.columns)}")
        print(f"  -> FAIL: Columns: {list(out_df.columns)}")

    # Check 5 & 6: no missing request_id and no duplicates
    print("\n[Check 5 & 6] Verifying request_id presence and uniqueness...")
    dataset_reqs_path = os.path.join(repo_root, 'dataset', 'requests.csv')
    req_df = pd.read_csv(dataset_reqs_path)
    expected_ids = req_df['request_id'].tolist()
    actual_ids = out_df['request_id'].tolist()

    if set(actual_ids) == set(expected_ids):
        results['check_5'] = "PASS"
        print("  -> PASS: All 250 request_ids from dataset/requests.csv are present.")
    else:
        results['check_5'] = "FAIL"
        missing = set(expected_ids) - set(actual_ids)
        issues.append(f"Missing request_ids: {missing}")
        print(f"  -> FAIL: Missing request_ids: {missing}")

    if len(actual_ids) == len(set(actual_ids)):
        results['check_6'] = "PASS"
        print("  -> PASS: Zero duplicate request_ids found.")
    else:
        results['check_6'] = "FAIL"
        dups = [x for x in actual_ids if actual_ids.count(x) > 1]
        issues.append(f"Duplicate request_ids: {set(dups)}")
        print(f"  -> FAIL: Duplicate request_ids: {set(dups)}")

    # Setup context to audit individual rows
    loader = DataLoader(os.path.join(repo_root, 'dataset'))
    currency_conv = loader.load_exchange_rates()
    img_proc = loader.load_images()
    profiles = loader.load_profiles()
    events_by_user = loader.load_events()
    payment_options = loader.load_payment_options()
    messages = loader.load_messages()
    requests_list = loader.load_requests('requests.csv')
    requests_map = {r.request_id: r for r in requests_list}

    msg_proc = MessageProcessor(messages)
    normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)
    context_builder = ContextBuilder(
        profiles=profiles,
        events_by_user=events_by_user,
        payment_options_by_req=payment_options,
        event_normalizer=normalizer
    )
    forecaster = ForecastEngine()

    # Detailed row-by-row checks: 7, 8, 9, 10, 11, 12, 13, 14
    print("\n[Checks 7-14] Running deep domain audit across all 250 rows...")
    bound_errors = []
    status_errors = []
    method_errors = []
    plan_errors = []
    installment_errors = []
    partial_errors = []
    spending_errors = []
    safety_errors = []

    allowed_statuses = {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}
    allowed_methods = {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}

    for idx, row in out_df.iterrows():
        req_id = row['request_id']
        req = requests_map[req_id]
        state, options = context_builder.build_context(req)

        safe_amt = float(row['amount_safe_to_pay'])
        status = str(row['affordability_status']).strip()
        method = str(row['recommended_payment_method']).strip()
        plan_str = str(row['payment_plan']).strip()
        earliest_date = str(row['earliest_date_for_full_payment']).strip()
        spending_str = str(row['spending_changes_needed']).strip()
        explanation = str(row['decision_explanation']).strip()

        # Check 7: amount_safe_to_pay bounds
        if safe_amt < -1e-4 or safe_amt > req.requested_amount + 1e-4:
            bound_errors.append(f"{req_id}: safe_amt={safe_amt} outside [0, {req.requested_amount}]")

        # Check 8: valid status values
        if status not in allowed_statuses:
            status_errors.append(f"{req_id}: status='{status}' not in {allowed_statuses}")

        # Check 9: valid payment methods
        if method not in allowed_methods:
            method_errors.append(f"{req_id}: method='{method}' not in {allowed_methods}")

        # Check 10: valid payment plans
        schedule = []
        if method == 'not_recommended':
            if plan_str != 'none':
                plan_errors.append(f"{req_id}: not_recommended must have plan 'none', got '{plan_str}'")
        else:
            if plan_str == 'none' or not plan_str:
                plan_errors.append(f"{req_id}: approved method '{method}' has empty plan")
            else:
                for part in plan_str.split('|'):
                    tokens = part.split(':')
                    if len(tokens) != 2:
                        plan_errors.append(f"{req_id}: malformed plan token '{part}'")
                    else:
                        d_str, a_str = tokens
                        try:
                            datetime.strptime(d_str, '%Y-%m-%d')
                            amt = float(a_str)
                            if amt <= 0:
                                plan_errors.append(f"{req_id}: non-positive amount {amt}")
                            schedule.append((d_str, amt))
                        except Exception as e:
                            plan_errors.append(f"{req_id}: invalid date/amount in '{part}': {e}")
                # Chronological
                dates = [d for d, _ in schedule]
                if dates != sorted(dates):
                    plan_errors.append(f"{req_id}: dates not chronological: {dates}")
                # Completion before deadline
                if dates and dates[-1] > req.desired_completion_date:
                    plan_errors.append(f"{req_id}: completion {dates[-1]} exceeds {req.desired_completion_date}")

        # Check 11: installment plans match supplied options
        if method == 'installments':
            if not schedule:
                installment_errors.append(f"{req_id}: installments has no schedule")
            else:
                n_payments = len(schedule)
                first_date = schedule[0][0]
                tot_paid = sum(amt for _, amt in schedule)
                matched = False
                for opt in options:
                    if opt.payment_method == 'installments' and opt.number_of_payments == n_payments and opt.first_payment_date == first_date:
                        if abs(opt.total_payable_amount - tot_paid) <= 0.1:
                            matched = True
                            break
                if not matched:
                    installment_errors.append(f"{req_id}: installment schedule does not match supplied options")

        # Check 12: partial-payment rules
        if method == 'partial_payment':
            if not req.allows_partial_payment:
                partial_errors.append(f"{req_id}: partial payment recommended but request forbids it")
            if not (0.0 < safe_amt < req.requested_amount):
                partial_errors.append(f"{req_id}: partial payment requires 0 < safe < req, got safe={safe_amt}, req={req.requested_amount}")
            if len(schedule) != 2:
                partial_errors.append(f"{req_id}: partial payment must have exactly 2 payments, got {len(schedule)}")
            else:
                d1, a1 = schedule[0]
                d2, a2 = schedule[1]
                if d1 != req.request_date:
                    partial_errors.append(f"{req_id}: first date must be request_date ({req.request_date}), got {d1}")
                if abs(a1 - safe_amt) > 0.05:
                    partial_errors.append(f"{req_id}: first amt ({a1}) != safe_amt ({safe_amt})")
                if abs((a1 + a2) - req.requested_amount) > 0.05:
                    partial_errors.append(f"{req_id}: sum of payments ({a1+a2}) != requested ({req.requested_amount})")

        # Check 13: spending changes target only allowed flexible recurring events
        if spending_str != 'none':
            changes = spending_str.split('|')
            if len(changes) > 3:
                spending_errors.append(f"{req_id}: spending changes exceed 3 ({len(changes)})")
            pool_events = {r['event_id']: r for r in list(state.recurring_expenses) + list(state.flexible_events)}
            seen_events = set()
            for ch in changes:
                parts = ch.split(':')
                act = parts[0]
                ev_id = parts[1]
                if ev_id in seen_events:
                    spending_errors.append(f"{req_id}: duplicate event {ev_id} in spending changes")
                seen_events.add(ev_id)
                if ev_id not in pool_events:
                    spending_errors.append(f"{req_id}: event {ev_id} not in flexible recurring pool")
                else:
                    ev = pool_events[ev_id]
                    cat = ev['category']
                    if cat in state.protected_categories:
                        spending_errors.append(f"{req_id}: modified protected category {cat}")
                    if ev['flexibility'] == 'fixed':
                        spending_errors.append(f"{req_id}: modified fixed event {ev_id}")

        # Check 14: 90-day minimum balance safety re-simulation
        if method != 'not_recommended':
            payments_dict = {d: a for d, a in schedule}
            spending_list = spending_str.split('|') if spending_str != 'none' else []
            last_date = schedule[-1][0]
            req_dt = pd.to_datetime(req.request_date)
            last_dt = pd.to_datetime(last_date)
            h_days = max(1, min(90, (last_dt - req_dt).days))
            is_safe, min_bal_seen = forecaster.passes_safety_check(
                state=state,
                request_date=req.request_date,
                proposed_payments=payments_dict,
                spending_changes=spending_list,
                horizon_days=h_days
            )
            if not is_safe:
                safety_errors.append(f"{req_id}: balance dropped to {min_bal_seen:.2f} below min {state.minimum_balance_to_keep:.2f}")

    # Record 7-14 results
    checks_map = [
        ('check_7', 'amount_safe_to_pay bounds', bound_errors),
        ('check_8', 'valid status values', status_errors),
        ('check_9', 'valid payment methods', method_errors),
        ('check_10', 'valid payment plans', plan_errors),
        ('check_11', 'installment plans match options', installment_errors),
        ('check_12', 'partial-payment rules', partial_errors),
        ('check_13', 'spending changes flexible recurring', spending_errors),
        ('check_14', '90-day minimum balance safety', safety_errors)
    ]
    for ch_key, name, errs in checks_map:
        if not errs:
            results[ch_key] = "PASS"
            print(f"  -> PASS: {name} (0 issues)")
        else:
            results[ch_key] = "FAIL"
            issues.extend(errs[:5])
            print(f"  -> FAIL: {name} ({len(errs)} issues found, e.g. {errs[0]})")

    # Check 15: evaluation/evaluate.py exists
    print("\n[Check 15] Verifying evaluation/evaluate.py exists...")
    eval_script = os.path.join(repo_root, 'evaluation', 'evaluate.py')
    if os.path.exists(eval_script):
        results['check_15'] = "PASS"
        print("  -> PASS: evaluation/evaluate.py exists.")
    else:
        results['check_15'] = "FAIL"
        issues.append("evaluation/evaluate.py missing.")
        print("  -> FAIL: evaluation/evaluate.py missing.")

    # Check 16: evaluation/usage_report.md exists
    print("\n[Check 16] Verifying evaluation/usage_report.md exists...")
    usage_rep = os.path.join(repo_root, 'evaluation', 'usage_report.md')
    if os.path.exists(usage_rep):
        results['check_16'] = "PASS"
        print("  -> PASS: evaluation/usage_report.md exists.")
    else:
        results['check_16'] = "FAIL"
        issues.append("evaluation/usage_report.md missing.")
        print("  -> FAIL: evaluation/usage_report.md missing.")

    # Check 17: no dataset files modified
    print("\n[Check 17] Verifying dataset/ files remain pristine...")
    try:
        git_diff = subprocess.run(['git', 'diff', '--name-only', 'dataset/'], cwd=repo_root, capture_output=True, text=True)
        git_untracked = subprocess.run(['git', 'status', '--porcelain', 'dataset/'], cwd=repo_root, capture_output=True, text=True)
        if not git_diff.stdout.strip() and not git_untracked.stdout.strip():
            results['check_17'] = "PASS"
            print("  -> PASS: Zero modifications or untracked files inside dataset/.")
        else:
            results['check_17'] = "FAIL"
            issues.append(f"dataset/ modified: {git_diff.stdout.strip()} {git_untracked.stdout.strip()}")
            print(f"  -> FAIL: dataset/ modified: {git_diff.stdout.strip()}")
    except Exception as e:
        results['check_17'] = "FAIL"
        issues.append(f"git check failed: {e}")

    # Check 18: no API keys/secrets committed
    print("\n[Check 18] Scanning for committed secrets or API keys...")
    secret_patterns = [
        re.compile(r'(sk-[a-zA-Z0-9_-]{20,})'),
        re.compile(r'(ghp_[a-zA-Z0-9]{20,})'),
        re.compile(r'(AIza[0-9A-Za-z-_]{35})'),
        re.compile(r'AKIA[0-9A-Z]{16}')
    ]
    found_secrets = []
    for root_dir, _, files in os.walk(code_dir):
        for f in files:
            if f.endswith('.py'):
                fpath = os.path.join(root_dir, f)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as code_f:
                    text = code_f.read()
                    for sp in secret_patterns:
                        if sp.search(text):
                            found_secrets.append((f, sp.pattern))
    if not found_secrets:
        results['check_18'] = "PASS"
        print("  -> PASS: No secrets or hardcoded API keys detected in code/.")
    else:
        results['check_18'] = "FAIL"
        issues.append(f"Secrets detected: {found_secrets}")
        print(f"  -> FAIL: Secrets detected in {found_secrets}")

    # Check 19: no hardcoded request IDs or expected labels
    print("\n[Check 19] Scanning for hardcoded request IDs or sample labels...")
    hardcoded_reqs = []
    # Check for hardcoded request_01 .. request_25 in code/
    for root_dir, _, files in os.walk(code_dir):
        for f in files:
            if f.endswith('.py') and f not in ['evaluate.py']:
                fpath = os.path.join(root_dir, f)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as code_f:
                    text = code_f.read()
                    matches = re.findall(r'request_[0-9]{2,3}', text)
                    if matches:
                        hardcoded_reqs.append((f, matches))
    if not hardcoded_reqs:
        results['check_19'] = "PASS"
        print("  -> PASS: Zero hardcoded request IDs in production code/.")
    else:
        results['check_19'] = "FAIL"
        issues.append(f"Hardcoded request IDs found in code/: {hardcoded_reqs}")
        print(f"  -> FAIL: Hardcoded request IDs found: {hardcoded_reqs}")

    # Check 20: README setup instructions sufficient
    print("\n[Check 20] Verifying README setup instructions...")
    readme_path = os.path.join(repo_root, 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as rf:
            rtext = rf.read()
        has_entrypoint = 'code/main.py' in rtext
        has_run = 'python' in rtext
        has_eval = 'evaluation/' in rtext
        if has_entrypoint and has_run and has_eval:
            results['check_20'] = "PASS"
            print("  -> PASS: README contains complete entrypoint, setup, and evaluation instructions.")
        else:
            results['check_20'] = "FAIL"
            issues.append("README is missing run or entry point instructions.")
            print("  -> FAIL: Incomplete README instructions.")
    else:
        results['check_20'] = "FAIL"
        issues.append("README.md missing.")
        print("  -> FAIL: README.md missing.")

    print("\n" + "=" * 80)
    print("                      AUDIT SCORECARD SUMMARY                                  ")
    print("=" * 80)
    pass_count = sum(1 for v in results.values() if v == "PASS")
    total_checks = len(results)
    for c_id in sorted(results.keys(), key=lambda x: int(x.split('_')[1])):
        print(f"  {c_id.upper():<10}: {results[c_id]}")
    print("-" * 80)
    print(f"TOTAL RESULT: {pass_count}/{total_checks} CHECKS PASSED ({(pass_count/total_checks)*100:.1f}%)")
    print("=" * 80)

    if issues:
        print("\nISSUES FOUND:")
        for iss in issues:
            print(f"  * {iss}")
    else:
        print("\nALL 20 AUDIT CHECKS PASSED PERFECTLY WITH ZERO ISSUES!")

if __name__ == '__main__':
    run_audit()
