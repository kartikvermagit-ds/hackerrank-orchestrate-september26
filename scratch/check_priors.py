import pandas as pd
profs = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
for u, name in [
    ('user_04', '0.22'), ('user_14', '0.22'), ('user_19', '0.22'), ('user_24', '0.22'),
    ('user_18', '0.20'), ('user_23', '0.20'),
    ('user_05', '0.05'), ('user_15', '0.05'), ('user_20', '0.05'), ('user_25', '0.05')
]:
    p = profs.loc[u]
    print(f"{u} ({name}): priorities={p['financial_priorities']} | protect={p['expense_categories_to_protect']}")
