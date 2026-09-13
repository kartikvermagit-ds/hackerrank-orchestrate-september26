import pandas as pd

df = pd.read_csv('dataset/messages.csv')
print(f"Total messages: {len(df)}")
for idx, r in df.iterrows():
    text = r['message_text']
    if any(k in text.lower() for k in ['salary', 'gaji', 'pay', 'bonus', 'komisi', 'contract', 'income']):
        print(f"[{r['message_id']} | user={r['user_id']} | ev={r['related_event_id']} | date={r['sent_at']}]:\n  {text}\n")
