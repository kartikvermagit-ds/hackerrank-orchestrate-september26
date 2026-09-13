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

print(f"{'REQ':<10} | {'GT SAFE':<12} | {'REQ AMT':<12} | {'AVAIL':<12} | {'MIN BAL':<12} | {'AVAIL-MIN':<12} | {'DIFF FROM AVAIL-MIN'}")
print("-" * 90)

for idx, req in enumerate(r):
    gt = gt_df.iloc[idx]
    state, opts = cb.build_context(req)
    gt_safe = float(gt['amount_safe_to_pay'])
    avail = state.current_available_balance
    min_bal = state.minimum_balance_to_keep
    net_headroom = avail - min_bal
    diff = net_headroom - gt_safe
    print(f"{req.request_id:<10} | {gt_safe:<12.2f} | {req.requested_amount:<12.2f} | {avail:<12.2f} | {min_bal:<12.2f} | {net_headroom:<12.2f} | {diff:<12.2f}")
