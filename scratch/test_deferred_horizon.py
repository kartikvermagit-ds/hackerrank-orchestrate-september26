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
requests = loader.load_requests('sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)
context_builder = ContextBuilder(
    profiles=profiles,
    events_by_user=events_by_user,
    payment_options_by_req=payment_options,
    event_normalizer=normalizer
)
forecaster = ForecastEngine()

for r_id in ['request_18', 'request_17', 'request_13']:
    req = [r for r in requests if r.request_id == r_id][0]
    state, opts = context_builder.build_context(req)
    
    print(f"\n================ {r_id} ({req.user_id}) req_date={req.request_date} req_amt={req.requested_amount} min_keep={state.minimum_balance_to_keep} ================")
    
    # Let's test different candidate dates:
    # 1. Simulate 90 days from request_date:
    for cand in ['2026-08-15', '2026-09-15', '2026-03-01', '2026-03-15', '2024-05-15', '2024-06-15']:
        if not (req.request_date <= cand <= '2027-01-01'):
            continue
        days_from_req = (pd.to_datetime(cand) - pd.to_datetime(req.request_date)).days
        if days_from_req > 90:
            continue
            
        # Evaluation A: Horizon = 90 days from request_date
        rec_A = forecaster.forecast_balance(state, req.request_date, proposed_payments={cand: req.requested_amount}, horizon_days=90)
        min_A = min(b for _, b in rec_A)
        safe_A = (min_A >= state.minimum_balance_to_keep - 0.05)
        
        # Evaluation B: Horizon = days_from_req + 90 (i.e. 90 days AFTER the candidate payment date!)
        rec_B = forecaster.forecast_balance(state, req.request_date, proposed_payments={cand: req.requested_amount}, horizon_days=days_from_req + 90)
        min_B = min(b for _, b in rec_B)
        safe_B = (min_B >= state.minimum_balance_to_keep - 0.05)
        
        # Evaluation C: Horizon = days_from_req + 30 (i.e. until next regular cycle after payment)
        rec_C = forecaster.forecast_balance(state, req.request_date, proposed_payments={cand: req.requested_amount}, horizon_days=days_from_req + 30)
        min_C = min(b for _, b in rec_C)
        safe_C = (min_C >= state.minimum_balance_to_keep - 0.05)
        
        print(f"Cand {cand}:")
        print(f"  Eval A (90d from req_date): min_bal={min_A:.2f} safe={safe_A}")
        print(f"  Eval B (90d after payment): min_bal={min_B:.2f} safe={safe_B}")
        print(f"  Eval C (30d after payment): min_bal={min_C:.2f} safe={safe_C}")
