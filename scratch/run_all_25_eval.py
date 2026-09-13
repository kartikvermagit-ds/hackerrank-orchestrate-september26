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

# Set living expense categories
EventNormalizer.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}

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

# Apply 60d smoothed burn if available
orig_burn = normalizer.calculate_variable_daily_burn
def calc_var_60(self, events, request_date, recurring_categories=None):
    req_dt = pd.to_datetime(request_date)
    start_60 = req_dt - pd.Timedelta(days=60)
    start_30 = req_dt - pd.Timedelta(days=30)
    debits_60 = []
    debits_30 = []
    for e in events:
        if (e.status == 'settled' and e.direction == 'debit' and e.category in self.LIVING_EXPENSE_CATEGORIES):
            dt = pd.to_datetime(e.event_date)
            desc_lower = e.description.lower()
            if 'bulk' in desc_lower and 'purchase' in desc_lower:
                continue
            if start_60 <= dt < req_dt:
                debits_60.append(e.amount)
            if start_30 <= dt < req_dt:
                debits_30.append(e.amount)
    burn_60 = sum(debits_60) / 60.0 if debits_60 else 0.0
    burn_30 = sum(debits_30) / 30.0 if debits_30 else 0.0
    return burn_60 if burn_60 > 0 else burn_30

normalizer.calculate_variable_daily_burn = calc_var_60.__get__(normalizer, EventNormalizer)

builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)
planner = PaymentPlanner(forecaster)
engine = DecisionEngine(forecaster, safe_calc, planner)

# In decision_engine, apply spending changes filtering by desired_completion_date & stop priority
def find_best_with_deadline(request, state, options, amount_safe_to_pay, earliest_date_for_full_payment):
    import itertools
    def fmt_amount(val: float) -> str:
        if float(val).is_integer():
            return f"{int(val)}"
        return f"{float(val):.2f}"

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

    # Priority: stop over reduce, then recency, then saving
    candidate_changes.sort(key=lambda x: (x[0].startswith('stop:'), x[3], x[1], x[2]), reverse=True)
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

# In safe_calc, compute_earliest_date_for_full_payment with deadline evaluation
def compute_earliest_with_deadline(state, request_date, requested_amount, amount_safe_to_pay=None, desired_completion_date=None):
    if requested_amount <= 0.0:
        return request_date
    if amount_safe_to_pay is None:
        amount_safe_to_pay = safe_calc.compute_safe_amount(state, request_date, requested_amount, desired_completion_date)
    if amount_safe_to_pay >= requested_amount - 1e-4:
        return request_date
    if state.salary_amount is None or state.salary_amount <= 0:
        return None

    req_dt = pd.to_datetime(request_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    next_sal = state.next_salary_date

    paydays = []
    for day_offset in range(1, 91):
        cand_dt = req_dt + pd.Timedelta(days=day_offset)
        cand_date_str = cand_dt.strftime('%Y-%m-%d')
        if (next_sal and cand_date_str == next_sal) or (cand_dt.day == sal_day):
            paydays.append((cand_date_str, day_offset))

    due_offset = (pd.to_datetime(desired_completion_date) - req_dt).days if desired_completion_date else 90

    for cand_date_str, day_offset in paydays:
        payments = {cand_date_str: requested_amount}
        h_days = min(90, max(day_offset, due_offset)) if desired_completion_date and day_offset <= due_offset else min(90, day_offset + 30)
        is_safe, _ = forecaster.passes_safety_check(
            state=state,
            request_date=request_date,
            proposed_payments=payments,
            spending_changes=None,
            horizon_days=h_days
        )
        if is_safe:
            return cand_date_str
    return None

safe_calc.compute_earliest_date_for_full_payment = compute_earliest_with_deadline

# Evaluate all 25 sample requests!
field_matches = {
    'status': 0,
    'method': 0,
    'plan': 0,
    'earliest': 0,
    'changes': 0,
    'all_5': 0
}

print("==================== FULL 25-SAMPLE EVALUATION ====================")
for _, r in sample_df.iterrows():
    rid = r['request_id']
    req = [x for x in samples if x.request_id == rid][0]
    st, op = builder.build_context(req)
    dec = engine.decide(req, st, op)

    exp_status = r['affordability_status']
    exp_method = r['recommended_payment_method']
    exp_plan = r['payment_plan']
    exp_earliest = str(r['earliest_date_for_full_payment']) if pd.notna(r['earliest_date_for_full_payment']) else 'None'
    exp_changes = r['spending_changes_needed']

    pred_status = dec.affordability_status
    pred_method = dec.recommended_payment_method
    pred_plan = dec.payment_plan
    pred_earliest = str(dec.earliest_date_for_full_payment) if dec.earliest_date_for_full_payment else 'None'
    pred_changes = dec.spending_changes_needed

    m_status = (exp_status == pred_status)
    m_method = (exp_method == pred_method)
    m_plan = (exp_plan == pred_plan)
    m_earliest = (exp_earliest == pred_earliest)
    m_changes = (exp_changes == pred_changes)
    m_all = m_status and m_method and m_plan and m_earliest and m_changes

    if m_status: field_matches['status'] += 1
    if m_method: field_matches['method'] += 1
    if m_plan: field_matches['plan'] += 1
    if m_earliest: field_matches['earliest'] += 1
    if m_changes: field_matches['changes'] += 1
    if m_all: field_matches['all_5'] += 1

    status_icon = "PASS" if m_all else "FAIL"
    print(f"\n[{status_icon}] {rid}:")
    if not m_all:
        if not m_status: print(f"  status:   exp={exp_status} vs pred={pred_status}")
        if not m_method: print(f"  method:   exp={exp_method} vs pred={pred_method}")
        if not m_plan:   print(f"  plan:     exp={exp_plan} vs pred={pred_plan}")
        if not m_earliest: print(f"  earliest: exp={exp_earliest} vs pred={pred_earliest}")
        if not m_changes: print(f"  changes:  exp={exp_changes} vs pred={pred_changes}")
    else:
        print(f"  status={pred_status} | method={pred_method} | earliest={pred_earliest} | changes={pred_changes}")

print("\n==================== EVALUATION SUMMARY ====================")
for k, v in field_matches.items():
    print(f"{k}: {v}/25 ({v/25*100:.1f}%)")
