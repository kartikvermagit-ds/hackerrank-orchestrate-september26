import os, sys, pandas as pd
sys.path.insert(0, 'code')
from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor

l = DataLoader('dataset')
l.load_images()
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

msg_proc = MessageProcessor(m)
norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
# Include dining in living expenses
norm.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}
cb = ContextBuilder(p, e, o, norm)

print(f"{'REQ_ID':<11} | {'REQ_AMT':<9} | {'GT_SAFE':<10} | {'PRE_PAY_HEAD':<12} | {'DIFF':<10}")
print("-" * 60)

for req in r:
    gt = gt_df.loc[req.request_id]
    gt_safe = float(gt['amount_safe_to_pay'])
    st, _ = cb.build_context(req)
    
    req_dt = pd.to_datetime(req.request_date)
    sal_day = st.salary_day_of_month if st.salary_day_of_month else 15
    next_sal = st.next_salary_date
    
    # Find next payday
    next_payday_dt = None
    if next_sal:
        next_payday_dt = pd.to_datetime(next_sal)
    else:
        for d in range(1, 32):
            cand = req_dt + pd.Timedelta(days=d)
            if cand.day == sal_day:
                next_payday_dt = cand
                break
                
    days_to_payday = (next_payday_dt - req_dt).days if next_payday_dt else 30
    
    # Recurring outflows before payday
    rec_outflows = 0.0
    for rx in st.recurring_expenses:
        rx_day = rx['day_of_month']
        for d in range(0, days_to_payday):
            cand = req_dt + pd.Timedelta(days=d)
            if cand.day == rx_day:
                last_dt = pd.to_datetime(rx['last_date'])
                if d == 0 and rx['last_date'] == cand.strftime('%Y-%m-%d'):
                    pass
                elif cand > last_dt:
                    rec_outflows += rx['amount']
                    
    sched_outflows = 0.0
    for d_str, amt in st.scheduled_debits.items():
        if req.request_date <= d_str < next_payday_dt.strftime('%Y-%m-%d'):
            sched_outflows += amt
            
    living_outflows = days_to_payday * st.daily_variable_burn
    total_pre_payday_needed = rec_outflows + sched_outflows + living_outflows
    avail_cash = st.liquid_starting_balance - st.minimum_balance_to_keep
    pre_payday_headroom = max(0.0, avail_cash - total_pre_payday_needed)
    
    diff = pre_payday_headroom - gt_safe
    print(f"{req.request_id:<11} | {req.requested_amount:<9.2f} | {gt_safe:<10.2f} | {pre_payday_headroom:<12.2f} | {diff:<10.2f}")
