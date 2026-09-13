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

# Monkey-patch find_best_spending_changes with deadline check
orig_find = engine.find_best_spending_changes

def find_best_with_deadline(request, state, options, amount_safe_to_pay, earliest_date_for_full_payment):
    import itertools
    def fmt_amount(val: float) -> str:
        s = f"{val:.2f}"
        if s.endswith('.00'):
            return s[:-3]
        if s.endswith('0') and '.' in s:
            return s[:-1]
        return s

    pool = []
    for r in state.recurring_expenses:
        pool.append(r)
    for f in state.flexible_events:
        if not any(p['event_id'] == f['event_id'] for p in pool):
            pool.append(f)

    seen_ids = set()
    candidate_changes = []

    req_dt = pd.to_datetime(request.request_date)
    due_dt_str = request.desired_completion_date

    for rec in pool:
        ev_id = rec['event_id']
        if ev_id in seen_ids:
            continue
        seen_ids.add(ev_id)

        cat = rec['category']
        flex = rec['flexibility']
        amt = rec['amount']
        min_amt = rec.get('minimum_allowed_amount')

        dt_str = str(rec.get('last_date') or rec.get('event_date') or '')
        dt = pd.to_datetime(dt_str)
        day = rec.get('day_of_month') or dt.day

        # Check next occurrence date
        try:
            next_occ = req_dt.replace(day=day)
        except ValueError:
            next_occ = req_dt.replace(day=28)
        if next_occ < req_dt:
            month = req_dt.month + 1 if req_dt.month < 12 else 1
            year = req_dt.year if req_dt.month < 12 else req_dt.year + 1
            try:
                next_occ = pd.Timestamp(year=year, month=month, day=day)
            except ValueError:
                next_occ = pd.Timestamp(year=year, month=month, day=28)
        next_occ_str = next_occ.strftime('%Y-%m-%d')
        if due_dt_str and next_occ_str > due_dt_str:
            continue

        if cat in state.protected_categories or flex == 'fixed':
            continue

        if cat in state.stoppable_categories and flex in ['stoppable', 'reducible_or_stoppable']:
            candidate_changes.append((f"stop:{ev_id}", amt, ev_id, dt_str))

        if cat in state.reducible_categories and flex in ['reducible', 'reducible_or_stoppable']:
            if min_amt is not None and amt > min_amt:
                saving = amt - min_amt
                candidate_changes.append((f"reduce_to:{ev_id}:{fmt_amount(min_amt)}", saving, ev_id, dt_str))

    candidate_changes.sort(key=lambda x: (x[3], x[1], x[2]), reverse=True)
    pruned_candidates = [(c[0], c[1], c[2]) for c in candidate_changes[:8]]
    successful_plans = []

    for k in range(1, min(4, len(pruned_candidates) + 1)):
        for combo_items in itertools.combinations(pruned_candidates, k):
            event_ids = [item[2] for item in combo_items]
            if len(event_ids) != len(set(event_ids)):
                continue
            combo_strings = [item[0] for item in combo_items]
            plans = planner.generate_candidate_plans(
                request=request,
                state=state,
                options=options,
                amount_safe_to_pay=amount_safe_to_pay,
                earliest_date_for_full_payment=earliest_date_for_full_payment,
                spending_changes=combo_strings
            )
            safe_plans = [p for p in plans if p.is_safe]
            if safe_plans:
                successful_plans.extend(safe_plans)
        if successful_plans:
            break
    return successful_plans

engine.find_best_spending_changes = find_best_with_deadline

for rid in ['request_06', 'request_11', 'request_21']:
    req = [r for r in samples if r.request_id == rid][0]
    st, op = builder.build_context(req)
    dec = engine.decide(req, st, op)
    print(f"\n{rid}:")
    print(f"  status: {dec.affordability_status}")
    print(f"  method: {dec.recommended_payment_method}")
    print(f"  plan: {dec.payment_plan}")
    print(f"  earliest: {dec.earliest_date_for_full_payment}")
    print(f"  changes: {dec.spending_changes_needed}")
