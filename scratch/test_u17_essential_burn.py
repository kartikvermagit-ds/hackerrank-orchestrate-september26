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
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv')

# Let's test with ESSENTIAL_LIVING = {'groceries', 'food', 'supermarket', 'transit', 'transport', 'daily_living'}
# without dining
norm = EventNormalizer(l.load_exchange_rates(), MessageProcessor(m))
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'food', 'supermarket', 'transit', 'transport', 'daily_living'}

cb = ContextBuilder(p, e, o, norm)
fc = ForecastEngine()
sc = SafeAmountCalculator(fc)
pl = PaymentPlanner(fc)
eng = DecisionEngine(fc, sc, pl)

req17 = [x for x in r if x.request_id == 'request_17'][0]
st17, opt17 = cb.build_context(req17)
print(f"User 17 daily burn without dining: {st17.daily_variable_burn:.2f}")

ed17 = sc.compute_earliest_date_for_full_payment(st17, req17.request_date, req17.requested_amount)
print(f"User 17 earliest date: {ed17} (GT: 2026-03-15)")

is_safe_m15, min_b = fc.passes_safety_check(st17, req17.request_date, {'2026-03-15': req17.requested_amount}, horizon_days=45)
print(f"Is March 15 safe to April 15? {is_safe_m15}, min_bal={min_b:.2f}, req={st17.minimum_balance_to_keep:.2f}")
