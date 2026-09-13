import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from safe_amount import SafeAmountCalculator
from forecast import ForecastEngine
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
payment_options = loader.load_payment_options()
messages = loader.load_messages()
samples = loader.load_requests('sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_conv, msg_proc)
builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)
planner = PaymentPlanner(forecaster)
engine = DecisionEngine(forecaster, safe_calc, planner)

req21 = [r for r in samples if r.request_id == 'request_21'][0]
state21, opts21 = builder.build_context(req21)

# Check candidate spending changes with next_occurrence <= due_date filter
print("Req 21 due date:", req21.desired_completion_date)
candidates = []
for r in state21.recurring_expenses + state21.flexible_events:
    ev_id = r['event_id']
    dt_str = str(r.get('last_date') or r.get('event_date') or '')
    dt = pd.to_datetime(dt_str)
    day = r.get('day_of_month') or dt.day
    # compute next occurrence from request_date
    req_dt = pd.to_datetime(req21.request_date)
    # next occurrence of 'day' on or after req_dt
    next_dt = req_dt.replace(day=min(day, 28)) # rough
    if next_dt < req_dt:
        next_dt = (req_dt + pd.DateOffset(months=1)).replace(day=min(day, 28))
    next_str = next_dt.strftime('%Y-%m-%d')
    print(f"  {ev_id} ({r['category']}) - day {day} -> next {next_str} <= {req21.desired_completion_date}? {next_str <= req21.desired_completion_date}")
