import os, sys, pandas as pd
repo_root = os.getcwd()
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

msg_proc = MessageProcessor(m)
orig_get = msg_proc.get_salary_update_for_user
def patched_get_salary(u_id, r_date):
    up = orig_get(u_id, r_date)
    if up and up.unconfirmed_bonus:
        up.new_salary = None
    return up
msg_proc.get_salary_update_for_user = patched_get_salary

norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
norm.FIXED_MONTHLY_CATEGORIES.add('shopping')
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}
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

for idx, req in enumerate(r):
    gt = gt_df.iloc[idx]
    state, opts = cb.build_context(req)
    rec = eng.decide(req, state, opts)
    
    diffs = []
    gt_m = str(gt['recommended_payment_method']).strip()
    pr_m = str(rec.recommended_payment_method).strip()
    if gt_m != pr_m:
        diffs.append(f'method: GT={gt_m} vs PR={pr_m}')
    gt_s = str(gt['affordability_status']).strip()
    pr_s = str(rec.affordability_status).strip()
    if gt_s != pr_s:
        diffs.append(f'status: GT={gt_s} vs PR={pr_s}')
    gt_p = str(gt['payment_plan']).strip()
    pr_p = str(rec.payment_plan).strip()
    if gt_p != pr_p:
        diffs.append(f'plan: GT={gt_p} vs PR={pr_p}')
    gt_d = str(gt['earliest_date_for_full_payment']).strip() if pd.notna(gt['earliest_date_for_full_payment']) else ''
    pr_d = str(rec.earliest_date_for_full_payment).strip() if rec.earliest_date_for_full_payment else ''
    if gt_d != pr_d:
        diffs.append(f'date: GT={gt_d} vs PR={pr_d}')
    gt_c = str(gt['spending_changes_needed']).strip()
    pr_c = str(rec.spending_changes_needed).strip()
    if gt_c != pr_c:
        diffs.append(f'chng: GT={gt_c} vs PR={pr_c}')
    if diffs:
        print(f'{req.request_id}: {", ".join(diffs)}')
