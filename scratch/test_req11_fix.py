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

msg_proc = MessageProcessor(m)
orig_get = msg_proc.get_salary_update_for_user
def patched_get(u_id, r_date):
    up = orig_get(u_id, r_date)
    if up and up.unconfirmed_bonus:
        up.new_salary = None
    return up
msg_proc.get_salary_update_for_user = patched_get
norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'food', 'supermarket', 'transit', 'transport', 'daily_living'}

cb = ContextBuilder(p, e, o, norm)
fc = ForecastEngine()
sc = SafeAmountCalculator(fc)
pl = PaymentPlanner(fc)
eng = DecisionEngine(fc, sc, pl)

req11 = [x for x in r if x.request_id == 'request_11'][0]
st11, opt11 = cb.build_context(req11)

print("User 11 after fix:")
print(f"Salary: {st11.salary_amount} (expected: 23,256,000)")
print(f"Daily burn: {st11.daily_variable_burn:.2f}")

safe_amt11 = sc.compute_safe_amount(st11, req11.request_date, req11.requested_amount)
print(f"Safe amount: {safe_amt11} (GT: 12,510,645.0)")

ed11 = sc.compute_earliest_date_for_full_payment(st11, req11.request_date, req11.requested_amount, amount_safe_to_pay=safe_amt11, desired_completion_date=req11.desired_completion_date)
print(f"Earliest date: {ed11} (GT: 2025-07-15)")

rec11 = eng.decide(req11, st11, opt11)
print(f"Decision: status={rec11.affordability_status}, method={rec11.recommended_payment_method}, plan={rec11.payment_plan}, earliest={rec11.earliest_date_for_full_payment}, spending={rec11.spending_changes_needed}")
