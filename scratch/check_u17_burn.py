import pandas as pd
df = pd.read_csv('dataset/financial_events.csv')
u17 = df[(df['user_id']=='user_17') & (df['direction']=='debit')]
print(u17[u17['category'].isin(['groceries', 'food', 'supermarket', 'transit', 'transport', 'dining', 'daily_living'])][['event_id', 'description', 'category', 'amount', 'flexibility', 'event_date']].to_string())
