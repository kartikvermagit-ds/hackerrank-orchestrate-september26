import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from safe_amount import SafeAmountCalculator
from forecast import ForecastEngine

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
payment_options = loader.load_payment_options()
messages = loader.load_messages()
samples = loader.load_requests('sample_requests.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_conv, msg_proc)
builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)

# Test new earliest computation
def new_compute_earliest(state, request_date, requested_amount, amount_safe_to_pay, desired_completion_date):
    if requested_amount <= 0.0:
        return request_date
    if amount_safe_to_pay is None:
        amount_safe_to_pay = safe_calc.compute_safe_amount(state, request_date, requested_amount, desired_completion_date)
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

    due_offset = (pd.to_datetime(desired_completion_date) - req_dt).days if desired_completion_date else 90

    for cand_date_str, day_offset in paydays:
        payments = {cand_date_str: requested_amount}
        # Evaluation horizon: either up to desired_completion_date (if <= due) or day_offset + 30
        h_days = min(90, max(day_offset, due_offset)) if desired_completion_date and day_offset <= due_offset else min(90, day_offset + 30)
        is_safe, _ = forecaster.passes_safety_check(
            state=state,
            request_date=request_date,
            proposed_payments=payments,
            spending_changes=None,
            horizon_days=h_days
        )
        if is_safe:
            return cand_date_str
    return None

matches = 0
total = 0
for _, r in sample_df.iterrows():
    rid = r['request_id']
    exp = r['earliest_date_for_full_payment']
    req = [x for x in samples if x.request_id == rid][0]
    st, op = builder.build_context(req)
    safe_amt = safe_calc.compute_safe_amount(st, req.request_date, req.requested_amount, req.desired_completion_date)
    pred = new_compute_earliest(st, req.request_date, req.requested_amount, safe_amt, req.desired_completion_date)
    
    exp_str = str(exp) if pd.notna(exp) else 'None'
    pred_str = str(pred) if pred is not None else 'None'
    is_m = (exp_str == pred_str)
    if is_m:
        matches += 1
    total += 1
    print(f"{rid} | exp: {exp_str} | pred: {pred_str} | {'MATCH' if is_m else 'DIFF'}")

print(f"\nEarliest Date Accuracy: {matches} / {total} ({matches/total*100:.1f}%)")
