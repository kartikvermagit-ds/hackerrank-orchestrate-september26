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

sample_df = pd.read_csv('dataset/sample_requests.csv')
for r_id in ['request_05', 'request_10', 'request_20', 'request_25']:
    req = [r for r in requests if r.request_id == r_id][0]
    s_row = sample_df[sample_df['request_id'] == r_id].iloc[0]
    state, opts = context_builder.build_context(req)
    records = forecaster.forecast_balance(state, req.request_date, horizon_days=90)
    min_bal = min(b for _, b in records)
    gt_safe = float(s_row['amount_safe_to_pay'])
    print(f"\n=== {r_id} ({req.user_id}) req_amt={req.requested_amount} GT_safe={gt_safe} ===")
    print(f"  liquid_start: {state.liquid_starting_balance}, min_keep: {state.minimum_balance_to_keep}")
    print(f"  our min_bal_seen: {min_bal:.2f}, headroom: {min_bal - state.minimum_balance_to_keep:.2f}")
    print(f"  daily_burn: {state.daily_variable_burn:.4f}")
    print(f"  salary: {state.salary_amount} on day {state.salary_day_of_month}")
    # find where min_bal occurs
    min_days = [d for d, b in records if abs(b - min_bal) < 1.0]
    print(f"  min bal days: {min_days[:3]}")
    # print first 15 days of records
    for d, b in records[:16]:
        print(f"    {d}: {b:.2f}")
