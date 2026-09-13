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

# 2. EventNormalizer with shopping in fixed categories and living expense categories = groceries, transport
norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
norm.FIXED_MONTHLY_CATEGORIES.add('shopping')
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport'}

cb = ContextBuilder(p, e, o, norm)
fc = ForecastEngine()
sc = SafeAmountCalculator(fc)

# Patch compute_earliest_date_for_full_payment to use 90-day horizon
orig_earliest = sc.compute_earliest_date_for_full_payment
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
        # Evaluate against complete required 90-day horizon
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

print("=" * 90)
print(f"{'REQ ID':<12} | {'SAFE AMT':<8} | {'STATUS':<8} | {'METHOD':<8} | {'PLAN':<8} | {'DATE':<8} | {'CHNG':<8} | OVERALL")
print("-" * 90)

matches = {k: 0 for k in ['safe', 'status', 'method', 'plan', 'date', 'chng', 'overall']}
total = len(r)

for idx, req in enumerate(r):
    gt = gt_df.iloc[idx]
    state, opts = cb.build_context(req)
    rec = eng.decide(req, state, opts)
    
    gt_safe = float(gt['amount_safe_to_pay'])
    pr_safe = float(rec.amount_safe_to_pay)
    safe_ok = abs(gt_safe - pr_safe) <= 1.0
    if safe_ok: matches['safe'] += 1
    
    status_ok = (str(gt['affordability_status']).strip() == str(rec.affordability_status).strip())
    if status_ok: matches['status'] += 1
    
    method_ok = (str(gt['recommended_payment_method']).strip() == str(rec.recommended_payment_method).strip())
    if method_ok: matches['method'] += 1
    
    plan_ok = (str(gt['payment_plan']).strip() == str(rec.payment_plan).strip())
    if plan_ok: matches['plan'] += 1
    
    gt_d = str(gt['earliest_date_for_full_payment']).strip() if pd.notna(gt['earliest_date_for_full_payment']) else ""
    pr_d = str(rec.earliest_date_for_full_payment).strip() if rec.earliest_date_for_full_payment else ""
    date_ok = (gt_d == pr_d)
    if date_ok: matches['date'] += 1
    
    gt_c = str(gt['spending_changes_needed']).strip()
    pr_c = str(rec.spending_changes_needed).strip()
    chng_ok = (gt_c == pr_c)
    if chng_ok: matches['chng'] += 1
    
    overall_ok = (safe_ok and status_ok and method_ok and plan_ok and date_ok and chng_ok)
    if overall_ok: matches['overall'] += 1
    
    mark = lambda ok: "MATCH" if ok else "DIFF"
    print(f"{req.request_id:<12} | {mark(safe_ok):<8} | {mark(status_ok):<8} | {mark(method_ok):<8} | {mark(plan_ok):<8} | {mark(date_ok):<8} | {mark(chng_ok):<8} | {'EXACT' if overall_ok else 'MISMATCH'}")
    
    if not overall_ok:
        diffs = []
        if not safe_ok: diffs.append(f"safe: GT={gt_safe:.2f} vs PR={pr_safe:.2f}")
        if not status_ok: diffs.append(f"status: GT='{gt['affordability_status']}' vs PR='{rec.affordability_status}'")
        if not method_ok: diffs.append(f"method: GT='{gt['recommended_payment_method']}' vs PR='{rec.recommended_payment_method}'")
        if not plan_ok: diffs.append(f"plan: GT='{gt['payment_plan']}' vs PR='{rec.payment_plan}'")
        if not date_ok: diffs.append(f"date: GT='{gt_d}' vs PR='{pr_d}'")
        if not chng_ok: diffs.append(f"chng: GT='{gt_c}' vs PR='{pr_c}'")
        print(f"   -> Diff: {', '.join(diffs)}")

print("=" * 90)
print(f"Method:   {matches['method']}/{total} ({(matches['method']/total)*100:.1f}%)")
print(f"Status:   {matches['status']}/{total} ({(matches['status']/total)*100:.1f}%)")
print(f"Plan:     {matches['plan']}/{total} ({(matches['plan']/total)*100:.1f}%)")
print(f"Date:     {matches['date']}/{total} ({(matches['date']/total)*100:.1f}%)")
print(f"Changes:  {matches['chng']}/{total} ({(matches['chng']/total)*100:.1f}%)")
print(f"Safe Amt: {matches['safe']}/{total} ({(matches['safe']/total)*100:.1f}%)")
print(f"Overall:  {matches['overall']}/{total} ({(matches['overall']/total)*100:.1f}%)")
print("=" * 90)
