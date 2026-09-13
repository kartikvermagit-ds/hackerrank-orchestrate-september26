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

for target_id in ['request_11', 'request_13', 'request_17', 'request_18', 'request_19', 'request_21']:
    req = [r for r in samples if r.request_id == target_id][0]
    expected_row = sample_df[sample_df['request_id'] == target_id].iloc[0]
    state, opts = builder.build_context(req)

    print(f"\n==================== {target_id} (User: {req.user_id}) ====================")
    print(f"Request Date: {req.request_date} | Due Date: {req.desired_completion_date} | Req Amount: {req.requested_amount}")
    print(f"User Balance: {state.current_available_balance} | Min to Keep: {state.minimum_balance_to_keep}")
    print(f"Salary: {state.salary_amount} on day {state.salary_day_of_month} (next: {state.next_salary_date})")
    print(f"Daily Var Burn: {state.daily_variable_burn} | Uncommitted Burn: {state.daily_uncommitted_burn}")
    print(f"Expected safe_amt: {expected_row['amount_safe_to_pay']} | status: {expected_row['affordability_status']} | method: {expected_row['recommended_payment_method']}")
    print(f"Expected earliest_date: {expected_row['earliest_date_for_full_payment']}")

    computed_safe = safe_calc.compute_safe_amount(state, req.request_date, req.requested_amount, req.desired_completion_date)
    computed_earliest = safe_calc.compute_earliest_date_for_full_payment(state, req.request_date, req.requested_amount, computed_safe, req.desired_completion_date)
    print(f"Computed safe_amt: {computed_safe} | earliest_date: {computed_earliest}")

    # Trace simulation of paying full amount on each candidate date
    req_dt = pd.to_datetime(req.request_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    for offset in [0, 5, 10, 12, 13, 14, 15, 20, 25, 30, 31, 35, 40, 45, 60, 70, 75]:
        cand_dt = req_dt + pd.Timedelta(days=offset)
        cand_str = cand_dt.strftime('%Y-%m-%d')
        # Check simulation with 90 days from request_date
        is_safe_req, min_bal_req = forecaster.passes_safety_check(
            state, req.request_date, {cand_str: req.requested_amount}, None, horizon_days=90
        )
        # Check simulation with 90 days from cand_str
        is_safe_cand, min_bal_cand = forecaster.passes_safety_check(
            state, cand_str, {cand_str: req.requested_amount}, None, horizon_days=90
        )
        if cand_dt.day == sal_day or offset == 0 or cand_str == expected_row['earliest_date_for_full_payment']:
            print(f"  Date {cand_str} (day {cand_dt.day}, offset {offset}): from_req: safe={is_safe_req} (min={min_bal_req:.1f}) | from_cand_90d: safe={is_safe_cand} (min={min_bal_cand:.1f})")
