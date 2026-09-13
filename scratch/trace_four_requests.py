import os
import sys
import pandas as pd

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
from decision_engine import DecisionEngine

loader = DataLoader(os.path.join(repo_root, 'dataset'))
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
payment_options = loader.load_payment_options()
messages = loader.load_messages()
requests_list = loader.load_requests('sample_requests.csv')
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
safe_calc = SafeAmountCalculator(forecaster)
planner = PaymentPlanner(forecaster)
decision_engine = DecisionEngine(forecast_engine=forecaster, safe_calc=safe_calc, planner=planner)

gt_df = pd.read_csv('dataset/sample_requests.csv')
gt_map = {r['request_id']: r for _, r in gt_df.iterrows()}

target_reqs = ['request_11', 'request_17', 'request_19', 'request_21']

for rid in target_reqs:
    req = requests_map[rid]
    gt = gt_map[rid]
    state, options = context_builder.build_context(req)
    
    print("=" * 80)
    print(f"TRACING {rid} (user={req.user_id}, date={req.request_date}, amount={req.requested_amount})")
    print("=" * 80)
    print(f"User Profile: currency={state.home_currency}, avail_bal={state.current_available_balance}, min_bal={state.minimum_balance_to_keep}")
    print(f"Salary Info: amount={state.salary_amount}, day={state.salary_day_of_month}, next_date={state.next_salary_date}")
    print(f"Daily var burn: {state.daily_variable_burn:.2f}")
    print(f"Allowed methods: {state.allowed_payment_methods}")
    print(f"Recurring expenses count: {len(state.recurring_expenses)}")
    for rx in state.recurring_expenses:
        print(f"  - {rx['description']} ({rx['category']}): amount={rx['amount']}, day={rx['day_of_month']}, flex={rx['flexibility']}")
    print(f"Reserved pending debits: {state.reserved_pending_debits}")
    print(f"Flexible events: {len(state.flexible_events)}")
    for fx in state.flexible_events:
        print(f"  - {fx['event_id']}: {fx['description']} ({fx['category']}), amt={fx['amount']}, flex={fx['flexibility']}, min={fx['minimum_allowed_amount']}")
    
    print("\nGROUND TRUTH:")
    print(f"  safe_amt: {gt['amount_safe_to_pay']}")
    print(f"  status:   {gt['affordability_status']}")
    print(f"  method:   {gt['recommended_payment_method']}")
    print(f"  plan:     {gt['payment_plan']}")
    print(f"  earliest: {gt['earliest_date_for_full_payment']}")
    print(f"  spending: {gt['spending_changes_needed']}")
    
    # Calculate safe amount and earliest date
    safe_amt = safe_calc.compute_safe_amount(state, req.request_date, req.requested_amount)
    ed = safe_calc.compute_earliest_date_for_full_payment(state, req.request_date, req.requested_amount, amount_safe_to_pay=safe_amt, desired_completion_date=req.desired_completion_date)
    rec = decision_engine.decide(req, state, options)
    
    print("\nCURRENT ENGINE PREDICTIONS:")
    print(f"  safe_amt: {rec.amount_safe_to_pay}")
    print(f"  status:   {rec.affordability_status}")
    print(f"  method:   {rec.recommended_payment_method}")
    print(f"  plan:     {rec.payment_plan}")
    print(f"  earliest: {rec.earliest_date_for_full_payment}")
    print(f"  spending: {rec.spending_changes_needed}")
    print()
