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
requests = loader.load_requests('sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)
context_builder = ContextBuilder(
    profiles=profiles,
    events_by_user=events_by_user,
    payment_options_by_req=payment_options,
    event_normalizer=normalizer
)

sample_df = pd.read_csv('dataset/sample_requests.csv')
for req in requests:
    s_row = sample_df[sample_df['request_id'] == req.request_id].iloc[0]
    gt_safe = float(s_row['amount_safe_to_pay'])
    state, opts = context_builder.build_context(req)
    
    # Calculate days to payday
    req_dt = pd.to_datetime(req.request_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    # Next payday
    next_payday = None
    if state.next_salary_date:
        next_payday = pd.to_datetime(state.next_salary_date)
    else:
        for d in range(1, 32):
            cand = req_dt + pd.Timedelta(days=d)
            if cand.day == sal_day:
                next_payday = cand
                break
    days_to_payday = (next_payday - req_dt).days if next_payday else 30
    
    # Recurring debits before payday
    rec_debits = 0.0
    for rx in state.recurring_expenses:
        rx_day = rx['day_of_month']
        for d in range(0, days_to_payday):
            cand = req_dt + pd.Timedelta(days=d)
            if cand.day == rx_day:
                rec_debits += rx['amount']
                
    sched_debits = sum(amt for d_str, amt in state.scheduled_debits.items() if req.request_date <= d_str < next_payday.strftime('%Y-%m-%d'))
    
    avail_cash = state.current_available_balance - state.minimum_balance_to_keep - state.reserved_pending_debits
    target_ded = avail_cash - gt_safe
    living_ded = target_ded - (rec_debits + sched_debits)
    daily_living = living_ded / days_to_payday if days_to_payday > 0 else 0
    
    print(f"{req.request_id} ({req.user_id}): days={days_to_payday} | avail={avail_cash:.2f} | gt_safe={gt_safe:.2f} | rec={rec_debits:.2f} | target_ded={target_ded:.2f} | living_ded={living_ded:.2f} | daily_living={daily_living:.2f}")
