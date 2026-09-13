import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine

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
builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()

def evaluate_cand(state, req_date, cand_date, amount, mode):
    req_dt = pd.to_datetime(req_date)
    cand_dt = pd.to_datetime(cand_date)
    offset = (cand_dt - req_dt).days
    
    if mode == '90d_from_req':
        records = forecaster.forecast_balance(state, req_date, {cand_date: amount}, None, horizon_days=90)
        return min(b for _, b in records) >= state.minimum_balance_to_keep - 0.05
    elif mode == 'cand_day_only':
        records = forecaster.forecast_balance(state, req_date, {cand_date: amount}, None, horizon_days=offset)
        return min(b for _, b in records) >= state.minimum_balance_to_keep - 0.05
    elif mode == 'cand_cycle': # until next salary or 30 days
        records = forecaster.forecast_balance(state, req_date, {cand_date: amount}, None, horizon_days=offset + 30)
        return min(b for _, b in records) >= state.minimum_balance_to_keep - 0.05
    elif mode == 'cand_to_due': # until desired_completion_date
        # passed separately
        pass

modes = ['90d_from_req', 'cand_day_only', 'cand_plus_payday_cycle']

for _, r in sample_df.iterrows():
    req_id = r['request_id']
    expected_earliest = r['earliest_date_for_full_payment']
    if pd.isna(expected_earliest):
        continue
    
    req = [x for x in samples if x.request_id == req_id][0]
    state, opts = builder.build_context(req)
    
    # Check what paydays pass under different modes
    req_dt = pd.to_datetime(req.request_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    next_sal = state.next_salary_date
    
    cand_dates = []
    for day_offset in range(0, 91):
        cand_dt = req_dt + pd.Timedelta(days=day_offset)
        cand_str = cand_dt.strftime('%Y-%m-%d')
        if day_offset == 0 or (next_sal and cand_str == next_sal) or (cand_dt.day == sal_day):
            cand_dates.append((cand_str, day_offset))
            
    # For each mode, find first safe cand_date
    res = {}
    # Mode 1: 90d from req
    for c_date, off in cand_dates:
        records = forecaster.forecast_balance(state, req.request_date, {c_date: req.requested_amount}, None, horizon_days=90)
        if min(b for _, b in records) >= state.minimum_balance_to_keep - 0.05:
            res['90d_from_req'] = c_date
            break
    else:
        res['90d_from_req'] = 'None'

    # Mode 2: on cand_date (can user pay on that date without dipping before or on that date)
    for c_date, off in cand_dates:
        records = forecaster.forecast_balance(state, req.request_date, {c_date: req.requested_amount}, None, horizon_days=off)
        if min(b for _, b in records) >= state.minimum_balance_to_keep - 0.05:
            res['on_cand_date'] = c_date
            break
    else:
        res['on_cand_date'] = 'None'

    # Mode 3: through next payday (cand_date to next payday)
    for c_date, off in cand_dates:
        # find days until next payday
        c_dt = pd.to_datetime(c_date)
        next_p_days = 30
        for d in range(1, 35):
            if (c_dt + pd.Timedelta(days=d)).day == sal_day:
                next_p_days = d
                break
        records = forecaster.forecast_balance(state, req.request_date, {c_date: req.requested_amount}, None, horizon_days=off + next_p_days)
        if min(b for _, b in records) >= state.minimum_balance_to_keep - 0.05:
            res['through_next_payday'] = c_date
            break
    else:
        res['through_next_payday'] = 'None'

    print(f"{req_id} | expected: {expected_earliest} | 90d_from_req: {res['90d_from_req']} | on_cand_date: {res['on_cand_date']} | through_next_payday: {res['through_next_payday']}")
