import sys
import pandas as pd
sys.path.insert(0, 'code')
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

loader = DataLoader('dataset')
profiles = loader.load_profiles()
events_by_user = loader.load_events()
options_all = loader.load_payment_options()
currency_conv = loader.load_exchange_rates()
messages = loader.load_messages()
requests = loader.load_requests('sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_conv, msg_proc)

cb = ContextBuilder(profiles, events_by_user, options_all, normalizer)
fe = ForecastEngine()
safe_calc = SafeAmountCalculator(fe)
planner = PaymentPlanner(fe)
engine = DecisionEngine(fe, safe_calc, planner)

# Temporarily patch planner.generate_candidate_plans
orig_gen = planner.generate_candidate_plans
def patched_gen(request, state, options, amount_safe_to_pay, earliest_date_for_full_payment, spending_changes=None):
    if spending_changes is None:
        spending_changes = []
    plans = orig_gen(request, state, options, amount_safe_to_pay, earliest_date_for_full_payment, spending_changes)
    # Check full_payment without spending changes
    for p in plans:
        if p.method == 'full_payment' and not p.spending_changes:
            p.is_safe = (amount_safe_to_pay >= request.requested_amount - 1e-4) and (request.request_date <= request.desired_completion_date)
            if not p.is_safe:
                p.affordability_status = 'not_affordable'
    return plans

planner.generate_candidate_plans = patched_gen

targets = ['request_06', 'request_11', 'request_13', 'request_17', 'request_18', 'request_19', 'request_21']
sample_df = pd.read_csv('dataset/sample_requests.csv')

for req_id in targets:
    req = [r for r in requests if r.request_id == req_id][0]
    state, opts = cb.build_context(req)
    rec = engine.decide(req, state, opts)
    gt = sample_df[sample_df['request_id'] == req_id].iloc[0]
    print(f"\n=== {req_id} ===")
    print(f"STATUS:      pred='{rec.affordability_status}' | gt='{gt['affordability_status']}'")
    print(f"METHOD:      pred='{rec.recommended_payment_method}' | gt='{gt['recommended_payment_method']}'")
    print(f"PLAN:        pred='{rec.payment_plan}' | gt='{gt['payment_plan']}'")
    print(f"EARLIEST:    pred='{rec.earliest_date_for_full_payment}' | gt='{gt['earliest_date_for_full_payment']}'")
    print(f"CHANGES:     pred='{rec.spending_changes_needed}' | gt='{gt['spending_changes_needed']}'")
