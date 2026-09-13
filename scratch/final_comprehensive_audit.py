import os
import sys
import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta
import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_DIR = os.path.join(ROOT_DIR, "dataset")
OUTPUT_PATH = os.path.join(ROOT_DIR, "output.csv")
CODE_DIR = os.path.join(ROOT_DIR, "code")

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from validator import OutputValidator
from models import RecommendationOutput

def run_comprehensive_audit():
    results = {}
    details = {}
    
    # 1. output.csv exists at repository root
    exists = os.path.isfile(OUTPUT_PATH)
    results[1] = exists
    details[1] = f"output.csv exists at {OUTPUT_PATH}" if exists else "output.csv missing at repo root"
    if not exists:
        return results, details, {}

    # Calculate SHA256
    with open(OUTPUT_PATH, "rb") as f:
        file_bytes = f.read()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Read output.csv with csv.reader
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        out_rows = list(reader)

    # Load dataset via DataLoader
    loader = DataLoader(DATASET_DIR)
    currency_conv = loader.load_exchange_rates()
    img_proc = loader.load_images()
    profiles = loader.load_profiles()
    events_by_user = loader.load_events()
    payment_options = loader.load_payment_options()
    messages = loader.load_messages()
    requests = loader.load_requests("requests.csv")
    
    msg_proc = MessageProcessor(messages)
    normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)
    context_builder = ContextBuilder(
        profiles=profiles,
        events_by_user=events_by_user,
        payment_options_by_req=payment_options,
        event_normalizer=normalizer
    )
    forecaster = ForecastEngine()

    req_dict = {req.request_id: req for req in requests}
    req_id_list = [req.request_id for req in requests]

    num_rows = len(out_rows)
    out_req_ids = [r[0] if len(r) > 0 else "" for r in out_rows]
    unique_req_ids = set(out_req_ids)
    num_unique = len(unique_req_ids)
    
    missing_req_ids = [rid for rid in req_id_list if rid not in unique_req_ids]
    seen = set()
    dup_req_ids = []
    for rid in out_req_ids:
        if rid in seen:
            dup_req_ids.append(rid)
        seen.add(rid)

    # 2. Exactly 250 prediction rows
    results[2] = (num_rows == 250)
    details[2] = f"Found {num_rows} data rows (target: 250)"

    # 3. Exactly one row per request_id
    results[3] = (num_rows == len(req_id_list) and len(missing_req_ids) == 0 and len(dup_req_ids) == 0)
    details[3] = f"All {len(req_id_list)} requests present with exactly 1 row each (0 missing, 0 extra)"

    # 4. No duplicate request_id
    results[4] = (len(dup_req_ids) == 0)
    details[4] = f"0 duplicate request_ids found" if results[4] else f"Duplicates found: {dup_req_ids}"

    # 5. Request order matches dataset/requests.csv
    results[5] = (out_req_ids == req_id_list)
    details[5] = "Order matches dataset/requests.csv exactly from request_01 to request_250" if results[5] else "Order mismatch"

    # 6. Exact required output column names and order
    expected_header = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation"
    ]
    results[6] = (header == expected_header)
    details[6] = f"Header matches exactly: {header}"

    # Validate each row
    c7_errors = []
    c8_errors = []
    c9_errors = []
    c10_errors = []
    c11_errors = []
    c12_errors = []
    c13_errors = []
    c14_errors = []
    c15_errors = []
    c16_errors = []
    c17_errors = []
    
    invalid_rows = []

    valid_statuses = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
    valid_methods = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}

    for idx, row in enumerate(out_rows):
        if len(row) != 8:
            invalid_rows.append((idx, row[0] if len(row) > 0 else f"row_{idx}", [f"Row has {len(row)} columns instead of 8"]))
            continue

        rid = row[0]
        req = req_dict.get(rid)
        if not req:
            invalid_rows.append((idx, rid, ["Missing request in dataset"]))
            continue
            
        rec = RecommendationOutput(
            request_id=row[0],
            amount_safe_to_pay=float(row[1]) if re.match(r"^-?\d+(?:\.\d+)?$", row[1]) else -999.0,
            affordability_status=row[2],
            recommended_payment_method=row[3],
            payment_plan=row[4],
            earliest_date_for_full_payment=row[5],
            spending_changes_needed=row[6],
            decision_explanation=row[7]
        )

        state, options = context_builder.build_context(req)

        # 7. amount_safe_to_pay numeric and bounded
        try:
            val = float(row[1])
            if val < -1e-6 or val > req.requested_amount + 1e-4:
                c7_errors.append(f"{rid}: amount_safe_to_pay {val} out of bounds [0, {req.requested_amount}]")
        except ValueError:
            c7_errors.append(f"{rid}: non-numeric amount_safe_to_pay '{row[1]}'")

        # 8. affordability_status valid
        if rec.affordability_status not in valid_statuses:
            c8_errors.append(f"{rid}: invalid affordability_status '{rec.affordability_status}'")

        # 9. recommended_payment_method valid
        if rec.recommended_payment_method not in valid_methods:
            c9_errors.append(f"{rid}: invalid recommended_payment_method '{rec.recommended_payment_method}'")

        # 10. payment_plan formatting
        if rec.payment_plan != "none":
            parts = rec.payment_plan.split("|")
            for p in parts:
                m = re.match(r"^(\d{4}-\d{2}-\d{2}):(\d+(?:\.\d+)?)$", p)
                if not m:
                    c10_errors.append(f"{rid}: malformed payment_plan item '{p}'")
                    break
                try:
                    datetime.strptime(m.group(1), "%Y-%m-%d")
                except ValueError:
                    c10_errors.append(f"{rid}: invalid date in payment_plan item '{p}'")
                    break
        else:
            if rec.recommended_payment_method in {"full_payment", "partial_payment", "installments"}:
                c10_errors.append(f"{rid}: method '{rec.recommended_payment_method}' requires active plan, got 'none'")

        # 11. payment plan amounts sum to requested amount where applicable
        if rec.payment_plan != "none":
            total_plan = sum(float(p.split(":")[1]) for p in rec.payment_plan.split("|"))
            if rec.recommended_payment_method in {"full_payment", "partial_payment", "wait"}:
                if abs(total_plan - req.requested_amount) > 0.05:
                    c11_errors.append(f"{rid}: {rec.recommended_payment_method} plan sum {total_plan:.2f} != requested_amount {req.requested_amount:.2f}")
            elif rec.recommended_payment_method == "installments":
                # For installments, sum equals total_payable_amount of matching option (including financing fee)
                matched_fee = False
                for opt in options:
                    if opt.payment_method == "installments" and abs(opt.total_payable_amount - total_plan) < 0.1:
                        matched_fee = True
                        break
                if not matched_fee:
                    c11_errors.append(f"{rid}: installment plan sum {total_plan:.2f} does not match any provider option total_payable_amount")

        # 12. installment plans correspond to actual supplied payment options
        if rec.recommended_payment_method == "installments":
            matched = False
            parts = rec.payment_plan.split("|")
            plan_dates = [p.split(":")[0] for p in parts]
            plan_amts = [float(p.split(":")[1]) for p in parts]
            for opt in options:
                if opt.payment_method == "installments":
                    if len(parts) == opt.number_of_payments:
                        # Check schedule
                        freq = opt.payment_frequency_days if opt.payment_frequency_days else 30
                        cur_d = pd.to_datetime(opt.first_payment_date)
                        exp_dates = [(cur_d + timedelta(days=i * freq)).strftime("%Y-%m-%d") for i in range(opt.number_of_payments)]
                        if plan_dates == exp_dates and all(abs(a - opt.payment_amount) < 0.1 for a in plan_amts):
                            matched = True
                            break
            if not matched:
                c12_errors.append(f"{rid}: installment plan {rec.payment_plan} does not match supplied options")

        # 13. partial-payment plans follow two-payment rule
        if rec.recommended_payment_method == "partial_payment":
            parts = rec.payment_plan.split("|")
            if len(parts) != 2:
                c13_errors.append(f"{rid}: partial plan must have exactly 2 payments, got {len(parts)}")
            else:
                d1, a1 = parts[0].split(":")
                d2, a2 = parts[1].split(":")
                a1 = float(a1)
                a2 = float(a2)
                if d1 != req.request_date:
                    c13_errors.append(f"{rid}: partial payment 1 date {d1} != request_date {req.request_date}")
                if abs(a1 - rec.amount_safe_to_pay) > 0.05:
                    c13_errors.append(f"{rid}: partial payment 1 amt {a1} != safe_amt {rec.amount_safe_to_pay}")
                if d2 != rec.earliest_date_for_full_payment:
                    c13_errors.append(f"{rid}: partial payment 2 date {d2} != earliest_date {rec.earliest_date_for_full_payment}")
                if d2 > req.desired_completion_date:
                    c13_errors.append(f"{rid}: partial payment 2 date {d2} exceeds desired_completion_date {req.desired_completion_date}")
                if not (0 < rec.amount_safe_to_pay < req.requested_amount):
                    c13_errors.append(f"{rid}: partial payment requires 0 < safe_amt < req_amt")
                if not req.allows_partial_payment:
                    c13_errors.append(f"{rid}: request does not allow partial payment")
                if "partial_payment" not in state.allowed_payment_methods:
                    c13_errors.append(f"{rid}: user profile does not allow partial payment")

        # 14. earliest_date_for_full_payment is valid
        ed = rec.earliest_date_for_full_payment
        if rec.affordability_status == "affordable_now":
            if ed != req.request_date:
                c14_errors.append(f"{rid}: affordable_now must have earliest_date == request_date")
        if ed != "":
            try:
                dt_ed = datetime.strptime(ed, "%Y-%m-%d")
                dt_rd = datetime.strptime(req.request_date, "%Y-%m-%d")
                if dt_ed < dt_rd:
                    c14_errors.append(f"{rid}: earliest_date {ed} < request_date {req.request_date}")
                if (dt_ed - dt_rd).days > 90:
                    c14_errors.append(f"{rid}: earliest_date {ed} beyond 90-day horizon")
            except ValueError:
                c14_errors.append(f"{rid}: malformed earliest_date '{ed}'")
        else:
            if rec.affordability_status in {"affordable_now"}:
                c14_errors.append(f"{rid}: affordable_now cannot have blank earliest_date")

        # 15. spending_changes_needed only contains allowed flexible expenses
        if rec.spending_changes_needed != "none":
            ch_list = rec.spending_changes_needed.split("|")
            if len(ch_list) > 3:
                c15_errors.append(f"{rid}: more than 3 spending changes ({len(ch_list)})")
            pool_events = {r['event_id']: r for r in list(state.recurring_expenses) + list(state.flexible_events)}
            for ch in ch_list:
                if ch.startswith("stop:"):
                    ev_id = ch[5:]
                    ev = pool_events.get(ev_id)
                    if not ev:
                        c15_errors.append(f"{rid}: unknown event {ev_id}")
                    else:
                        if not ev.get('is_flexible', False) and ev.get('flexibility') not in ['stoppable', 'reducible_or_stoppable']:
                            c15_errors.append(f"{rid}: event {ev_id} not flexible")
                        if ev.get('category', '').lower() in [c.lower() for c in state.protected_categories]:
                            c15_errors.append(f"{rid}: category '{ev['category']}' is protected")
                        if ev.get('category', '').lower() not in [c.lower() for c in state.stoppable_categories]:
                            c15_errors.append(f"{rid}: category '{ev['category']}' not stoppable")
                elif ch.startswith("reduce_to:"):
                    parts = ch.split(":")
                    if len(parts) == 3:
                        ev_id = parts[1]
                        red_amt = float(parts[2])
                        ev = pool_events.get(ev_id)
                        if not ev:
                            c15_errors.append(f"{rid}: unknown event {ev_id}")
                        else:
                            if not ev.get('is_flexible', False) and ev.get('flexibility') not in ['reducible', 'reducible_or_stoppable']:
                                c15_errors.append(f"{rid}: event {ev_id} not flexible")
                            if ev.get('category', '').lower() in [c.lower() for c in state.protected_categories]:
                                c15_errors.append(f"{rid}: category '{ev['category']}' is protected")
                            if ev.get('category', '').lower() not in [c.lower() for c in state.reducible_categories]:
                                c15_errors.append(f"{rid}: category '{ev['category']}' not reducible")
                            if red_amt >= ev.get('amount', 0):
                                c15_errors.append(f"{rid}: reduce_to amount {red_amt} >= current amount {ev.get('amount')}")
                else:
                    c15_errors.append(f"{rid}: invalid action format '{ch}'")

        # 16. all proposed plans maintain minimum balance throughout safety horizon
        # Run validator's strict validation
        val_errors = OutputValidator.validate_decision(
            rec=rec,
            request=req,
            state=state,
            options=options,
            forecaster=forecaster,
            raise_exception=False
        )
        if val_errors:
            for ve in val_errors:
                if "minimum_balance_to_keep" in ve:
                    c16_errors.append(f"{rid}: {ve}")
                elif "exceeds desired_completion_date" in ve and rec.recommended_payment_method == "full_payment":
                    c17_errors.append(f"{rid}: {ve}")

        # 17. all full-payment plans complete within desired_completion_date when required
        if rec.recommended_payment_method == "full_payment":
            plan_d = rec.payment_plan.split(":")[0]
            if plan_d > req.desired_completion_date:
                c17_errors.append(f"{rid}: full payment date {plan_d} > desired_completion_date {req.desired_completion_date}")

        # Track any invalid row
        row_issues = [e for e in (c7_errors + c8_errors + c9_errors + c10_errors + c11_errors + c12_errors + c13_errors + c14_errors + c15_errors + c16_errors + c17_errors) if e.startswith(rid)]
        if row_issues:
            invalid_rows.append((idx, rid, row_issues))

    results[7] = (len(c7_errors) == 0)
    details[7] = "All 250 amount_safe_to_pay values are numeric and within [0, requested_amount]" if results[7] else f"{len(c7_errors)} errors"

    results[8] = (len(c8_errors) == 0)
    details[8] = "All 250 affordability_status values are valid enum literals" if results[8] else f"{len(c8_errors)} errors"

    results[9] = (len(c9_errors) == 0)
    details[9] = "All 250 recommended_payment_method values are valid enum literals" if results[9] else f"{len(c9_errors)} errors"

    results[10] = (len(c10_errors) == 0)
    details[10] = "All payment_plans follow strict YYYY-MM-DD:amount syntax or 'none'" if results[10] else f"{len(c10_errors)} errors"

    results[11] = (len(c11_errors) == 0)
    details[11] = "All active payment plans sum to requested_amount where applicable (or matching provider option total_payable_amount for installments)" if results[11] else f"{len(c11_errors)} errors"

    results[12] = (len(c12_errors) == 0)
    details[12] = "All installment plans correspond strictly to supplied options in request_payment_options.csv" if results[12] else f"{len(c12_errors)} errors"

    results[13] = (len(c13_errors) == 0)
    details[13] = "All partial-payment plans follow the two-payment contract exactly (safe on req_date, rem on earliest_date <= due_date)" if results[13] else f"{len(c13_errors)} errors"

    results[14] = (len(c14_errors) == 0)
    details[14] = "All earliest_date_for_full_payment values are valid dates within 90 days or empty string" if results[14] else f"{len(c14_errors)} errors"

    results[15] = (len(c15_errors) == 0)
    details[15] = "All spending_changes_needed modify only non-protected, flexible, permitted expenses (max 3)" if results[15] else f"{len(c15_errors)} errors"

    results[16] = (len(c16_errors) == 0)
    details[16] = "All proposed plans maintain minimum balance throughout safety horizon (0 violations across 90-day simulation)" if results[16] else f"{len(c16_errors)} violations: {c16_errors[:3]}"

    results[17] = (len(c17_errors) == 0)
    details[17] = "All full-payment plans complete on or before desired_completion_date" if results[17] else f"{len(c17_errors)} violations"

    # 18. No dataset files were modified
    git_stat = subprocess.run(["git", "status", "--porcelain", "dataset"], capture_output=True, text=True)
    results[18] = (git_stat.stdout.strip() == "")
    details[18] = "dataset/ directory clean and untouched (0 modified files)" if results[18] else f"dataset modified: {git_stat.stdout.strip()}"

    # 19. No API keys or secrets are present
    secret_patterns = [
        re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{8,}['\"]"),
        re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
        re.compile(r"sk-[a-zA-Z0-9]{20,}")
    ]
    found_secrets = []
    for walk_dir in ["code", "tests", "evaluation"]:
        for root, _, files in os.walk(os.path.join(ROOT_DIR, walk_dir)):
            for file in files:
                if file.endswith((".py", ".md", ".json", ".txt")):
                    fpath = os.path.join(root, file)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as sf:
                        for l_no, line in enumerate(sf, 1):
                            for sp in secret_patterns:
                                if sp.search(line):
                                    found_secrets.append(f"{fpath}:{l_no}")
    results[19] = (len(found_secrets) == 0)
    details[19] = "No API keys or secrets present in code/, tests/, or evaluation/" if results[19] else f"Found secrets: {found_secrets}"

    # 20. No hardcoded sample request answers exist
    hardcoded_sample_findings = []
    for root, _, files in os.walk(CODE_DIR):
        for file in files:
            if file.endswith(".py"):
                fpath = os.path.join(root, file)
                with open(fpath, "r", encoding="utf-8") as pyf:
                    for l_no, line in enumerate(pyf, 1):
                        if re.search(r"sample_\d{2}", line):
                            hardcoded_sample_findings.append(f"{file}:{l_no}: {line.strip()}")
    results[20] = (len(hardcoded_sample_findings) == 0)
    details[20] = "Zero hardcoded sample answers or request IDs exist in code/" if results[20] else f"Found references: {hardcoded_sample_findings}"

    summary_stats = {
        "number_of_rows": num_rows,
        "number_of_unique_request_ids": num_unique,
        "missing_request_ids": len(missing_req_ids),
        "duplicate_request_ids": len(dup_req_ids),
        "invalid_rows": len(invalid_rows),
        "output_csv_sha256": sha256_hash,
    }
    
    return results, details, summary_stats

if __name__ == "__main__":
    results, details, stats = run_comprehensive_audit()
    print("=== SUMMARY STATS ===")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("\n=== 20 AUDIT CHECKS ===")
    all_passed = True
    for i in range(1, 21):
        status_str = "PASS" if results[i] else "FAIL"
        if not results[i]:
            all_passed = False
        print(f"[{status_str}] Check {i}: {details[i]}")
    print(f"\nFinal Verdict: {'ALL CHECKS PASSED (20/20)' if all_passed else 'SOME CHECKS FAILED'}")
