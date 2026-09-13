import os, sys
import pandas as pd

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
code_dir = os.path.join(repo_root, 'code')
sys.path.insert(0, code_dir)

from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine

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
context_builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()

req = requests_map['request_17']
state, options = context_builder.build_context(req)

print(f"User 17: avail={state.current_available_balance}, min={state.minimum_balance_to_keep}")
print(f"Salary: {state.salary_amount}, day={state.salary_day_of_month}, next={state.next_salary_date}")
print(f"Requested amount: {req.requested_amount}")

daily_proj = forecaster.forecast_balance(
    state=state,
    request_date=req.request_date,
    proposed_payments={'2026-03-15': req.requested_amount},
    spending_changes=None,
    horizon_days=90
)

min_bal = min(bal for _, bal in daily_proj)
print(f"\nSimulating payment on 2026-03-15 across 90 days (min balance seen = {min_bal:,.2f}, required = {state.minimum_balance_to_keep:,.2f}):")
for d, bal in daily_proj:
    if d in ['2026-03-01', '2026-03-02', '2026-03-14', '2026-03-15', '2026-03-16', '2026-04-01', '2026-04-02', '2026-04-14', '2026-04-15'] or bal < state.minimum_balance_to_keep:
        print(f"  {d}: balance = {bal:,.2f} {'*** BELOW MIN ***' if bal < state.minimum_balance_to_keep else ''}")

