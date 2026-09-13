import pandas as pd

events = pd.read_csv('dataset/financial_events.csv')
uev = events[events['user_id'] == 'user_22'].copy()
print(uev[['event_id', 'event_date', 'category', 'direction', 'amount', 'status', 'description']].to_string())
