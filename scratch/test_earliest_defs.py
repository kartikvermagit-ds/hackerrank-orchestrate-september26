import os, sys
import pandas as pd

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, 'code'))

from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from forecast import ForecastEngine

l = DataLoader('dataset')
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv')

cb = ContextBuilder(p, e, o, EventNormalizer(l.load_exchange_rates(), MessageProcessor(m)))
fc = ForecastEngine()

print("Testing different earliest_date horizons across all 25 sample requests:\n")

# Let's test horizons:
# H1: day of payment only (h_days = day_offset)
# H2: day of payment + 1 day
# H3: through the end of the pay cycle (until next payday)
# H4: full 90-day horizon from request_date
# H5: 90 days from candidate payment date

results_by_def = {f"H{i}": [] for i in range(1, 6)}

for idx, req in enumerate(r):
    gt = gt_df.iloc[idx]
    gt_ed = str(gt['earliest_date_for_full_payment']).strip() if pd.notna(gt['earliest_date_for_full_payment']) else ""
    state, opts = cb.build_context(req)
    
    # Let's find candidate paydays
    req_dt = pd.to_datetime(req.request_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    next_sal = state.next_salary_date
    
    # Candidate dates: request_date, plus confirmed paydays
    cand_dates = [(req.request_date, 0)]
    for d_off in range(1, 91):
        c_dt = req_dt + pd.Timedelta(days=d_off)
        c_str = c_dt.strftime('%Y-%m-%d')
        if (next_sal and c_str == next_sal) or (c_dt.day == sal_day):
            cand_dates.append((c_str, d_off))
            
    # Def 1: Safe on candidate date (min balance up to candidate date >= min_balance)
    ed_1 = ""
    for c_str, d_off in cand_dates:
        is_safe, _ = fc.passes_safety_check(state, req.request_date, {c_str: req.requested_amount}, horizon_days=d_off)
        if is_safe:
            ed_1 = c_str
            break
            
    # Def 2: Safe on candidate date through next payday
    ed_2 = ""
    for i, (c_str, d_off) in enumerate(cand_dates):
        h = cand_dates[i+1][1] if i+1 < len(cand_dates) else min(90, d_off + 15)
        is_safe, _ = fc.passes_safety_check(state, req.request_date, {c_str: req.requested_amount}, horizon_days=h)
        if is_safe:
            ed_2 = c_str
            break
            
    # Def 3: Safe across full 90 days from request_date
    ed_3 = ""
    for c_str, d_off in cand_dates:
        is_safe, _ = fc.passes_safety_check(state, req.request_date, {c_str: req.requested_amount}, horizon_days=90)
        if is_safe:
            ed_3 = c_str
            break

    print(f"{req.request_id}: GT='{gt_ed}' | Def1(on_date)='{ed_1}' | Def2(to_next_sal)='{ed_2}' | Def3(full_90d)='{ed_3}'")
