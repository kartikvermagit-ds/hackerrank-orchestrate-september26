import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from currency import CurrencyConverter
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
    if req.request_id in ['request_08', 'request_18', 'request_21', 'request_22', 'request_06', 'request_14', 'request_15', 'request_07', 'request_19', 'request_24']:
        s_row = sample_df[sample_df['request_id'] == req.request_id].iloc[0]
        state, opts = context_builder.build_context(req)
        diff = state.current_available_balance - state.minimum_balance_to_keep
        target_ded = diff - float(s_row['amount_safe_to_pay'])
        print(f"\n=== {req.request_id} ({req.user_id}) req_date={req.request_date} target_ded={target_ded:.2f} ===")
        print(f"  salary_day: {state.salary_day_of_month}, salary_amt: {state.salary_amount}")
        print(f"  daily_variable_burn: {state.daily_variable_burn:.4f}")
        print(f"  reserved_pending_debits: {state.reserved_pending_debits}")
        print(f"  scheduled_debits: {state.scheduled_debits}")
        print("  recurring_expenses:")
        rec_sum = 0
        for re in state.recurring_expenses:
            print(f"    {re['category']}: amount={re['amount']}, day={re['day_of_month']}")
            rec_sum += re['amount']
        print(f"  total recurring: {rec_sum:.2f}")
