import os, sys, pandas as pd
sys.path.insert(0, 'code')
from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

l = DataLoader('dataset')
l.load_images()
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

msg_proc = MessageProcessor(m)
norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}
cb = ContextBuilder(p, e, o, norm)
fc = ForecastEngine()
sc = SafeAmountCalculator(fc)
pl = PaymentPlanner(fc)

# Patch generate_candidate_plans
orig_gen = pl.generate_candidate_plans
def patched_gen(request, state, options, amount_safe_to_pay, earliest_date_for_full_payment, spending_changes=None):
    if spending_changes is None:
        spending_changes = []
    plans = orig_gen(request, state, options, amount_safe_to_pay, earliest_date_for_full_payment, spending_changes)
    if not spending_changes:
        plans = [p for p in plans if not (p.method == 'full_payment' and amount_safe_to_pay < request.requested_amount - 1e-4)]
    return plans

pl.generate_candidate_plans = patched_gen
eng = DecisionEngine(fc, sc, pl)

for rid in ['request_06', 'request_11', 'request_13', 'request_17', 'request_18', 'request_19', 'request_21']:
    req = [x for x in r if x.request_id == rid][0]
    gt = gt_df.loc[rid]
    st, opts = cb.build_context(req)
    rec = eng.decide(req, st, opts)
    print(f"{rid}:")
    print(f"  GT: status={gt['affordability_status']} method={gt['recommended_payment_method']} plan={gt['payment_plan']} date={gt['earliest_date_for_full_payment']} chg={gt['spending_changes_needed']}")
    print(f"  PR: status={rec.affordability_status} method={rec.recommended_payment_method} plan={rec.payment_plan} date={rec.earliest_date_for_full_payment} chg={rec.spending_changes_needed}")
