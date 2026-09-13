import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
messages = loader.load_messages()
requests = loader.load_requests('sample_requests.csv')
msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)

# Test with living categories including dining
normalizer.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}

for r_id in ['request_06', 'request_11', 'request_18', 'request_21']:
    req = [r for r in requests if r.request_id == r_id][0]
    u_events = events_by_user.get(req.user_id, [])
    norm_events = normalizer.normalize_events_for_user(u_events, profiles[req.user_id].home_currency)
    
    # 60-day burn
    burn_60 = normalizer.calculate_variable_daily_burn(norm_events, req.request_date)
    
    # Let's also check 30-day burn
    req_dt = pd.to_datetime(req.request_date)
    start_30 = req_dt - pd.Timedelta(days=30)
    debits_30 = [e.amount for e in norm_events if e.status == 'settled' and e.direction == 'debit' and e.category in normalizer.LIVING_EXPENSE_CATEGORIES and start_30 <= pd.to_datetime(e.event_date) < req_dt]
    burn_30 = sum(debits_30) / 30.0 if debits_30 else 0.0
    
    print(f"{r_id} ({req.user_id}): burn_60={burn_60:.4f}, burn_30={burn_30:.4f}, max={max(burn_60, burn_30):.4f}")
