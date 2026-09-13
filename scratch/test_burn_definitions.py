import os, sys
import pandas as pd

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, 'code'))

from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

l = DataLoader('dataset')
img_proc = l.load_images()
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv')

# 1. MessageProcessor with unconfirmed bonus rule
msg_proc = MessageProcessor(m)
orig_get = msg_proc.get_salary_update_for_user
def patched_get_salary(u_id, r_date):
    up = orig_get(u_id, r_date)
    if up and up.unconfirmed_bonus:
        up.new_salary = None
    return up
msg_proc.get_salary_update_for_user = patched_get_salary

# Test two options for living categories:
# Option A: groceries + transport
# Option B: groceries + transport + dining (with discretionary adjustment)
for opt_name, cats in [("Groceries + Transport", {'groceries', 'transport'}),
                       ("Groceries + Transport + Dining", {'groceries', 'transport', 'dining'})]:
    norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
    norm.FIXED_MONTHLY_CATEGORIES.add('shopping')
    norm.LIVING_EXPENSE_CATEGORIES = cats

    cb = ContextBuilder(p, e, o, norm)
    fc = ForecastEngine()
    sc = SafeAmountCalculator(fc)

    def patched_earliest(state, request_date, requested_amount, amount_safe_to_pay=None, desired_completion_date=None):
        if requested_amount <= 0.0:
            return request_date
        if amount_safe_to_pay is None:
            amount_safe_to_pay = sc.compute_safe_amount(state, request_date, requested_amount, desired_completion_date)
        if amount_safe_to_pay >= requested_amount - 1e-4:
            return request_date
        if state.salary_amount is None or state.salary_amount <= 0:
            return None

        req_dt = pd.to_datetime(request_date)
        sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
        next_sal = state.next_salary_date

        paydays = []
        for day_offset in range(1, 91):
            cand_dt = req_dt + pd.Timedelta(days=day_offset)
            cand_date_str = cand_dt.strftime('%Y-%m-%d')
            if (next_sal and cand_date_str == next_sal) or (cand_dt.day == sal_day):
                paydays.append((cand_date_str, day_offset))

        for cand_date_str, day_offset in paydays:
            payments = {cand_date_str: requested_amount}
            is_safe, _ = fc.passes_safety_check(
                state=state,
                request_date=request_date,
                proposed_payments=payments,
                spending_changes=None,
                horizon_days=90
            )
            if is_safe:
                return cand_date_str
        return None

    sc.compute_earliest_date_for_full_payment = patched_earliest
    pl = PaymentPlanner(fc)
    eng = DecisionEngine(fc, sc, pl)

    scores = {'method': 0, 'status': 0, 'plan': 0, 'date': 0, 'chng': 0, 'overall': 0}
    for idx, req in enumerate(r):
        gt = gt_df.iloc[idx]
        state, opts = cb.build_context(req)
        rec = eng.decide(req, state, opts)

        gt_d = str(gt['earliest_date_for_full_payment']).strip() if pd.notna(gt['earliest_date_for_full_payment']) else ""
        pr_d = str(rec.earliest_date_for_full_payment).strip() if rec.earliest_date_for_full_payment else ""

        ok_m = str(gt['recommended_payment_method']).strip() == str(rec.recommended_payment_method).strip()
        ok_s = str(gt['affordability_status']).strip() == str(rec.affordability_status).strip()
        ok_p = str(gt['payment_plan']).strip() == str(rec.payment_plan).strip()
        ok_d = gt_d == pr_d
        ok_c = str(gt['spending_changes_needed']).strip() == str(rec.spending_changes_needed).strip()
        ok_safe = abs(float(gt['amount_safe_to_pay']) - float(rec.amount_safe_to_pay)) <= 1.0

        if ok_m: scores['method'] += 1
        if ok_s: scores['status'] += 1
        if ok_p: scores['plan'] += 1
        if ok_d: scores['date'] += 1
        if ok_c: scores['chng'] += 1
        if ok_m and ok_s and ok_p and ok_d and ok_c and ok_safe: scores['overall'] += 1

    print(f"=== Results for: {opt_name} ===")
    print(f"Method:   {scores['method']}/25 ({scores['method']*4}%)")
    print(f"Status:   {scores['status']}/25 ({scores['status']*4}%)")
    print(f"Plan:     {scores['plan']}/25 ({scores['plan']*4}%)")
    print(f"Date:     {scores['date']}/25 ({scores['date']*4}%)")
    print(f"Changes:  {scores['chng']}/25 ({scores['chng']*4}%)")
    print(f"Overall:  {scores['overall']}/25 ({scores['overall']*4}%)")
    print()
