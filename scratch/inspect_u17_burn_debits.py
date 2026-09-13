import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
events_by_user = loader.load_events()
messages = loader.load_messages()
msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_conv, msg_proc)

u17_events = normalizer.normalize_events_for_user(events_by_user['user_17'], 'INR', '2026-03-01')
req_dt = pd.to_datetime('2026-03-01')
start_60 = req_dt - pd.Timedelta(days=60)
start_30 = req_dt - pd.Timedelta(days=30)

print("User 17 debits in last 60 days (groceries & transport):")
tot_60 = 0
tot_30 = 0
for e in u17_events:
    if e.status == 'settled' and e.direction == 'debit' and e.category in {'groceries', 'transport'}:
        dt = pd.to_datetime(e.event_date)
        desc = e.description.lower()
        if 'bulk' in desc and 'purchase' in desc:
            print(f"SKIPPED BULK: {e.event_id} | {e.event_date} | {e.amount} | {e.description}")
            continue
        if start_60 <= dt < req_dt:
            print(f"60d: {e.event_id} | {e.event_date} | {e.amount} | {e.category} | {e.description}")
            tot_60 += e.amount
        if start_30 <= dt < req_dt:
            tot_30 += e.amount

print(f"tot_60: {tot_60}, per day: {tot_60 / 60.0}")
print(f"tot_30: {tot_30}, per day: {tot_30 / 30.0}")
