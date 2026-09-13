import pandas as pd
events = pd.read_csv('dataset/financial_events.csv')
u17_events = events[events['user_id'] == 'user_17'].sort_values('settlement_date')
print(u17_events[['event_id', 'settlement_date', 'event_type', 'category', 'amount', 'currency', 'direction', 'status', 'description']].to_string())
