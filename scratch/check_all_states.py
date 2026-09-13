import sys
sys.path.insert(0, 'code')
from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor

l = DataLoader('dataset')
m = l.load_messages()
norm = EventNormalizer(l.load_exchange_rates(), MessageProcessor(m))
cb = ContextBuilder(l.load_profiles(), l.load_events(), l.load_payment_options(), norm)
reqs = l.load_requests('sample_requests.csv')

for r in reqs:
    st, _ = cb.build_context(r)
    print(f"{r.request_id} ({r.user_id}, {r.request_date}): sal={st.salary_amount}, day={st.salary_day_of_month}, next={st.next_salary_date}, burn={st.daily_variable_burn:.2f}, avail={st.current_available_balance}, min={st.minimum_balance_to_keep}")
