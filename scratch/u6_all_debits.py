import pandas as pd
df = pd.read_csv('dataset/financial_events.csv')
u6 = df[(df['user_id']=='user_06') & (df['direction']=='debit')]
print(u6[['event_id', 'description', 'category', 'amount', 'event_date', 'status', 'flexibility']].to_string())
