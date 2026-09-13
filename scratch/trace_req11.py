import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder

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

req11 = [r for r in samples if r.request_id == 'request_11'][0]
state11, opts11 = builder.build_context(req11)

print("User 11 Financial State:")
print(f"Current Balance: {state11.current_available_balance}")
print(f"Min Balance: {state11.minimum_balance_to_keep}")
print(f"Salary Amount: {state11.salary_amount}, Day: {state11.salary_day_of_month}")
print(f"Daily var burn: {state11.daily_variable_burn}")
print(f"Daily uncommitted burn: {state11.daily_uncommitted_burn}")
print(f"Reserved debits: {state11.reserved_pending_debits}")
print(f"Recurring expenses: {state11.recurring_expenses}")

from safe_amount import SafeAmountCalculator
from forecast import ForecastEngine
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)
planner = PaymentPlanner(forecaster)
engine = DecisionEngine(forecaster, safe_calc, planner)

safe_amt = safe_calc.compute_safe_amount(state11, req11.request_date, req11.requested_amount)
earliest = forecaster.find_earliest_full_payment_date(state11, req11.request_date, req11.requested_amount)
print(f"\nCalculated safe_amount: {safe_amt} (expected 12510645.0)")
print(f"Calculated earliest_date: {earliest} (expected 2025-07-15)")

dec = engine.decide(req11, state11, opts11)
print(f"\nDecision:")
print(f"Status: {dec.affordability_status}")
print(f"Method: {dec.recommended_payment_method}")
print(f"Plan: {dec.payment_plan}")
print(f"Earliest: {dec.earliest_date_for_full_payment}")
print(f"Spending changes: {dec.spending_changes_needed}")
