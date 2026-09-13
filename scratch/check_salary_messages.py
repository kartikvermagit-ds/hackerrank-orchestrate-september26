import pandas as pd

df = pd.read_csv('dataset/messages.csv')
for idx, r in df.iterrows():
    txt = str(r['message_text'])
    if any(w in txt.lower() for w in ['gaji', 'salary', 'pay', 'income', 'payroll', 'komisi', 'bonus', 'upah']):
        print(f"{r['message_id']} | {r['user_id']} | {r['request_id']} | {txt}")
