import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator

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
safe_calc = SafeAmountCalculator(forecaster)

sample_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

print(f"{'REQ_ID':12} | {'GT_EARLIEST':12} | {'OPT_A (90d)':12} | {'OPT_B (+90d)':12} | {'OPT_C (+30d)':12}")
print("-" * 75)

for req in requests:
    state, opts = context_builder.build_context(req)
    gt_earliest = str(sample_df.loc[req.request_id, 'earliest_date_for_full_payment'])
    req_amt = req.requested_amount
    req_date = req.request_date
    
    # Let's find paydays
    req_dt = pd.to_datetime(req_date)
    sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
    next_sal = state.next_salary_date
    
    paydays = []
    for day_offset in range(1, 91):
        cand_dt = req_dt + pd.Timedelta(days=day_offset)
        cand_date_str = cand_dt.strftime('%Y-%m-%d')
        if (next_sal and cand_date_str == next_sal) or (cand_dt.day == sal_day):
            paydays.append((cand_date_str, day_offset))
            
    # Compute earliest under Opt A, Opt B, Opt C
    def find_earliest(h_mode):
        # First check if safe today
        # But wait, without spending changes:
        # Check if paying req_amt today is safe for 90d
        is_safe_today, _ = forecaster.passes_safety_check(state, req_date, {req_date: req_amt}, None, 90)
        # Note: if safe amount calculation says safe today:
        safe_amt = safe_calc.compute_safe_amount(state, req_date, req_amt)
        if safe_amt >= req_amt - 1e-4:
            return req_date
            
        if state.salary_amount is None or state.salary_amount <= 0:
            return 'nan'
            
        for cand, offset in paydays:
            if h_mode == 'A':
                h = 90
            elif h_mode == 'B':
                h = offset + 90
            elif h_mode == 'C':
                h = offset + 30
            is_s, _ = forecaster.passes_safety_check(state, req_date, {cand: req_amt}, None, h)
            if is_s:
                return cand
        return 'nan'
        
    ea = find_earliest('A')
    eb = find_earliest('B')
    ec = find_earliest('C')
    print(f"{req.request_id:12} | {gt_earliest:12} | {ea:12} | {eb:12} | {ec:12}")
