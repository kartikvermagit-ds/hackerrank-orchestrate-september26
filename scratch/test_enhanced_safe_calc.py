import os, sys, pandas as pd
from decimal import Decimal, ROUND_FLOOR

sys.path.insert(0, 'code')
from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

l = DataLoader('dataset')
l.load_images()
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

msg_proc = MessageProcessor(m)
norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}
cb = ContextBuilder(p, e, o, norm)
fc = ForecastEngine()
sc = SafeAmountCalculator(fc)

# Implement pre-payday headroom check in compute_safe_amount
orig_compute_safe = sc.compute_safe_amount

def enhanced_compute_safe_amount(state, request_date, requested_amount, desired_completion_date=None):
    if requested_amount <= 0.0:
        return 0.0

    h_days = 90
    if desired_completion_date and (state.salary_amount is None or state.salary_amount <= 0):
        req_days = (pd.to_datetime(desired_completion_date) - pd.to_datetime(request_date)).days
        if 0 < req_days < 90:
            h_days = req_days

    daily_records = fc.forecast_balance(
        state=state,
        request_date=request_date,
        proposed_payments=None,
        spending_changes=None,
        horizon_days=h_days
    )
    min_balance_seen = min(bal for _, bal in daily_records)
    headroom_90d = max(0.0, min_balance_seen - state.minimum_balance_to_keep)

    # Pre-payday headroom
    req_dt = pd.to_datetime(request_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    next_sal = state.next_salary_date

    next_payday_dt = None
    if next_sal:
        next_payday_dt = pd.to_datetime(next_sal)
    else:
        for d in range(1, 32):
            cand = req_dt + pd.Timedelta(days=d)
            if cand.day == sal_day:
                next_payday_dt = cand
                break

    days_to_payday = (next_payday_dt - req_dt).days if next_payday_dt else 30

    rec_outflows = 0.0
    for rx in state.recurring_expenses:
        rx_day = rx['day_of_month']
        for d in range(0, days_to_payday):
            cand = req_dt + pd.Timedelta(days=d)
            if cand.day == rx_day:
                last_dt = pd.to_datetime(rx['last_date'])
                if d == 0 and rx['last_date'] == cand.strftime('%Y-%m-%d'):
                    pass
                elif cand > last_dt:
                    rec_outflows += rx['amount']

    sched_outflows = 0.0
    for d_str, amt in state.scheduled_debits.items():
        if request_date <= d_str < next_payday_dt.strftime('%Y-%m-%d'):
            sched_outflows += amt

    living_outflows = days_to_payday * state.daily_variable_burn
    avail_cash = state.liquid_starting_balance - state.minimum_balance_to_keep
    pre_payday_headroom = max(0.0, avail_cash - (rec_outflows + sched_outflows + living_outflows))

    headroom = min(headroom_90d, pre_payday_headroom)
    if headroom <= 0.0:
        return 0.0

    headroom_dec = Decimal(str(round(headroom, 4)))
    safe_dec = min(Decimal(str(requested_amount)), headroom_dec).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)
    safe_amt = float(safe_dec)

    while safe_amt > 0.0:
        is_safe, _ = fc.passes_safety_check(
            state=state,
            request_date=request_date,
            proposed_payments={request_date: safe_amt},
            spending_changes=None,
            horizon_days=h_days
        )
        if is_safe:
            break
        safe_amt = round(safe_amt - 0.01, 2)

    return max(0.0, min(requested_amount, safe_amt))

sc.compute_safe_amount = enhanced_compute_safe_amount
pl = PaymentPlanner(fc)
eng = DecisionEngine(fc, sc, pl)

matches = {k: 0 for k in ['safe', 'status', 'method', 'plan', 'date', 'chng', 'overall']}
total = len(r)

print(f"{'REQ_ID':<11} | {'SAFE':<6} | {'STATUS':<8} | {'METHOD':<8} | {'PLAN':<8} | {'DATE':<8} | {'CHNG':<8} | OVERALL")
print("-" * 80)

for req in r:
    gt = gt_df.loc[req.request_id]
    st, opts = cb.build_context(req)
    rec = eng.decide(req, st, opts)
    
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
    print(f"{req.request_id:<11} | {mark(safe_ok):<6} | {mark(status_ok):<8} | {mark(method_ok):<8} | {mark(plan_ok):<8} | {mark(date_ok):<8} | {mark(chng_ok):<8} | {'EXACT' if overall_ok else 'MISMATCH'}")
    if not overall_ok:
        diffs = []
        if not safe_ok: diffs.append(f"safe: GT={gt_safe:.2f} vs PR={pr_safe:.2f}")
        if not status_ok: diffs.append(f"status: GT='{gt['affordability_status']}' vs PR='{rec.affordability_status}'")
        if not method_ok: diffs.append(f"method: GT='{gt['recommended_payment_method']}' vs PR='{rec.recommended_payment_method}'")
        if not plan_ok: diffs.append(f"plan: GT='{gt['payment_plan']}' vs PR='{rec.payment_plan}'")
        if not date_ok: diffs.append(f"date: GT='{gt_d}' vs PR='{pr_d}'")
        if not chng_ok: diffs.append(f"chng: GT='{gt_c}' vs PR='{pr_c}'")
        print(f"   -> {', '.join(diffs)}")

print("=" * 80)
print(f"Method:   {matches['method']}/{total} ({(matches['method']/total)*100:.1f}%)")
print(f"Status:   {matches['status']}/{total} ({(matches['status']/total)*100:.1f}%)")
print(f"Plan:     {matches['plan']}/{total} ({(matches['plan']/total)*100:.1f}%)")
print(f"Date:     {matches['date']}/{total} ({(matches['date']/total)*100:.1f}%)")
print(f"Changes:  {matches['chng']}/{total} ({(matches['chng']/total)*100:.1f}%)")
print(f"Safe Amt: {matches['safe']}/{total} ({(matches['safe']/total)*100:.1f}%)")
print(f"Overall:  {matches['overall']}/{total} ({(matches['overall']/total)*100:.1f}%)")
