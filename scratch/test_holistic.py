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
# Essential 90-day continuous burn: groceries + transport
normalizer.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport'}
context_builder = ContextBuilder(profiles=profiles, events_by_user=events_by_user, payment_options_by_req=payment_options, event_normalizer=normalizer)
forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)
planner = PaymentPlanner(forecaster)
engine = DecisionEngine(forecaster, safe_calc, planner)

sample_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

matches = {'status': 0, 'method': 0, 'plan': 0, 'earliest': 0, 'changes': 0}
total = len(requests)

for req in requests:
    gt = sample_df.loc[req.request_id]
    state, opts = context_builder.build_context(req)
    
    # Calculate pre-payday daily burn including dining/uncommitted variable living
    u_events = events_by_user.get(req.user_id, [])
    norm_events = normalizer.normalize_events_for_user(u_events, state.home_currency)
    req_dt = pd.to_datetime(req.request_date)
    start_30 = req_dt - pd.Timedelta(days=30)
    start_60 = req_dt - pd.Timedelta(days=60)
    all_living_debits = [e.amount for e in norm_events if e.status == 'settled' and e.direction == 'debit' and e.category in {'groceries', 'transport', 'dining'} and start_60 <= pd.to_datetime(e.event_date) < req_dt]
    burn_uncommitted = sum(all_living_debits) / 60.0 if all_living_debits else state.daily_variable_burn
    
    # Run safe_calc with pre_payday_headroom protecting uncommitted living expenses until payday
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
    
    # Decide
    dec = engine.decide(req, state, opts)
    
    s_match = dec.affordability_status == gt['affordability_status']
    m_match = dec.recommended_payment_method == gt['recommended_payment_method']
    p_match = dec.payment_plan == gt['payment_plan']
    e_match = str(dec.earliest_date_for_full_payment) == str(gt['earliest_date_for_full_payment'])
    c_match = dec.spending_changes_needed == gt['spending_changes_needed']
    
    if s_match: matches['status'] += 1
    if m_match: matches['method'] += 1
    if p_match: matches['plan'] += 1
    if e_match: matches['earliest'] += 1
    if c_match: matches['changes'] += 1
    
    print(f"{req.request_id:12} | S:{'OK' if s_match else 'FAIL':4} | M:{'OK' if m_match else 'FAIL':4} | P:{'OK' if p_match else 'FAIL':4} | E:{'OK' if e_match else 'FAIL':4} | C:{'OK' if c_match else 'FAIL':4} | pred_m={dec.recommended_payment_method:15} | pred_s={dec.affordability_status}")

print("\nSummary:")
for k, v in matches.items():
    print(f"  {k}: {v}/{total} ({v/total*100:.1f}%)")
