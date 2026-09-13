import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from context_builder import ContextBuilder
from financial_state import FinancialStateReconstructor

loader = DataLoader('dataset')
loader.load_all()
profiles = loader.load_profiles()
events = loader.load_events()
rates = loader.load_exchange_rates()
normalizer = EventNormalizer(rates)
norm_events = normalizer.normalize_events(events, profiles)
ctx_builder = ContextBuilder(profiles, norm_events, loader.load_requests(), loader.load_payment_options())
reconstructor = FinancialStateReconstructor()

sample_df = pd.read_csv('dataset/sample_requests.csv')
for r_id in ['request_08', 'request_18', 'request_21', 'request_22', 'request_06', 'request_14', 'request_15', 'request_07', 'request_19', 'request_24']:
    s_row = sample_df[sample_df['request_id'] == r_id].iloc[0]
    ctx = ctx_builder.build_context(s_row['user_id'], r_id)
    state = reconstructor.reconstruct(ctx)
    diff = ctx.profile.current_available_balance - ctx.profile.minimum_balance_to_keep
    target_deduction = diff - float(s_row['amount_safe_to_pay'])
    print(f"\n=== {r_id} ({ctx.user.user_id}) req_date={ctx.request.request_date} target_ded={target_deduction:.2f} ===")
    print(f"Detected paydays: {state.paydays}")
    print(f"Daily variable burn: {state.daily_variable_burn:.4f}")
    print("Recurring expenses:")
    for re in state.recurring_expenses:
        print(f"  {re.event_id} | day {re.day_of_month} | {re.category} | amount={re.amount} | {re.frequency}")
