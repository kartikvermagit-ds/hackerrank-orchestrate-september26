import pandas as pd

profiles = pd.read_csv('dataset/financial_profiles.csv')
p21 = profiles[profiles['user_id'] == 'user_21'].iloc[0]
print("Profile 21:")
print(f"protect: {p21['expense_categories_to_protect']}")
print(f"reduce: {p21['expense_categories_user_is_willing_to_reduce']}")
print(f"stop: {p21['expense_categories_user_is_willing_to_stop']}")

events = pd.read_csv('dataset/financial_events.csv')
u21 = events[events['user_id'] == 'user_21'].sort_values('settlement_date')
print("\nEvents:")
for idx, r in u21.iterrows():
    if r['flexibility'] in ['stoppable', 'reducible', 'reducible_or_stoppable']:
        print(f"{r['event_id']} | {r['settlement_date']} | {r['category']} | {r['amount']} | {r['flexibility']} | {r['minimum_allowed_amount']} | {r['description']}")
