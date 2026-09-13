import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
payment_options = loader.load_payment_options()
messages = loader.load_messages()
requests = loader.load_requests('sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)
# 90d essential forecast burn: groceries + transport
normalizer.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport'}
context_builder = ContextBuilder(profiles=profiles, events_by_user=events_by_user, payment_options_by_req=payment_options, event_normalizer=normalizer)
forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)
planner = PaymentPlanner(forecaster)
engine = DecisionEngine(forecaster, safe_calc, planner)

sample_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

results = []

for req in requests:
    gt = sample_df.loc[req.request_id]
    state, opts = context_builder.build_context(req)
    
    # Calculate uncommitted living burn (groceries, transport, dining)
    u_events = events_by_user.get(req.user_id, [])
    norm_events = normalizer.normalize_events_for_user(u_events, state.home_currency)
    req_dt = pd.to_datetime(req.request_date)
    start_60 = req_dt - pd.Timedelta(days=60)
    start_30 = req_dt - pd.Timedelta(days=30)
    
    liv_60 = [e.amount for e in norm_events if e.status == 'settled' and e.direction == 'debit' and e.category in {'groceries', 'transport', 'dining'} and start_60 <= pd.to_datetime(e.event_date) < req_dt]
    liv_30 = [e.amount for e in norm_events if e.status == 'settled' and e.direction == 'debit' and e.category in {'groceries', 'transport', 'dining'} and start_30 <= pd.to_datetime(e.event_date) < req_dt]
    
    burn_uncommitted = max(sum(liv_60)/60.0 if liv_60 else 0.0, sum(liv_30)/30.0 if liv_30 else 0.0)
    if burn_uncommitted == 0.0:
        burn_uncommitted = state.daily_variable_burn
        
    # Pre-payday calculation
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    next_sal = state.next_salary_date
    next_payday_dt = pd.to_datetime(next_sal) if next_sal else None
    if not next_payday_dt:
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
                    
    sched_outflows = sum(amt for d_str, amt in state.scheduled_debits.items() if req.request_date <= d_str < next_payday_dt.strftime('%Y-%m-%d'))
    living_outflows = days_to_payday * burn_uncommitted
    avail_cash = state.liquid_starting_balance - state.minimum_balance_to_keep
    pre_payday_headroom = max(0.0, avail_cash - (rec_outflows + sched_outflows + living_outflows))
    
    # 90d headroom
    daily_records = forecaster.forecast_balance(state, req.request_date, horizon_days=90)
    headroom_90d = max(0.0, min(b for _, b in daily_records) - state.minimum_balance_to_keep)
    
    headroom = min(headroom_90d, pre_payday_headroom)
    computed_safe = min(req.requested_amount, round(headroom, 2))
    
    # Custom decide using computed_safe
    # Overwrite compute_safe_amount return for this call
    safe_calc.compute_safe_amount = lambda *args, **kwargs: computed_safe
    
    dec = engine.decide(req, state, opts)
    
    def eq(a, b):
        if pd.isna(a) and (b is None or b == '' or pd.isna(b)):
            return True
        return str(a).strip() == str(b).strip()
        
    s_match = eq(dec.affordability_status, gt['affordability_status'])
    m_match = eq(dec.recommended_payment_method, gt['recommended_payment_method'])
    p_match = eq(dec.payment_plan, gt['payment_plan'])
    e_match = eq(dec.earliest_date_for_full_payment, gt['earliest_date_for_full_payment'])
    c_match = eq(dec.spending_changes_needed, gt['spending_changes_needed'])
    
    results.append({
        'req_id': req.request_id,
        'status': s_match,
        'method': m_match,
        'plan': p_match,
        'earliest': e_match,
        'changes': c_match,
        'pred_m': dec.recommended_payment_method,
        'pred_s': dec.affordability_status,
        'pred_e': dec.earliest_date_for_full_payment,
        'gt_e': gt['earliest_date_for_full_payment'],
        'pred_p': dec.payment_plan,
        'gt_p': gt['payment_plan'],
        'pred_c': dec.spending_changes_needed,
        'gt_c': gt['spending_changes_needed']
    })

print(f"{'REQ_ID':12} | {'STATUS':6} | {'METHOD':6} | {'PLAN':6} | {'EARLIEST':8} | {'CHANGES':7}")
print("-" * 55)
for r in results:
    s_s = 'OK' if r['status'] else 'DIFF'
    s_m = 'OK' if r['method'] else 'DIFF'
    s_p = 'OK' if r['plan'] else 'DIFF'
    s_e = 'OK' if r['earliest'] else 'DIFF'
    s_c = 'OK' if r['changes'] else 'DIFF'
    print(f"{r['req_id']:12} | {s_s:6} | {s_m:6} | {s_p:6} | {s_e:8} | {s_c:7}")

print("\nAccuracy:")
print("  Status:  ", sum(1 for r in results if r['status']), "/ 25")
print("  Method:  ", sum(1 for r in results if r['method']), "/ 25")
print("  Plan:    ", sum(1 for r in results if r['plan']), "/ 25")
print("  Earliest:", sum(1 for r in results if r['earliest']), "/ 25")
print("  Changes: ", sum(1 for r in results if r['changes']), "/ 25")
