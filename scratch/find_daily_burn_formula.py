import pandas as pd

events = pd.read_csv('dataset/financial_events.csv')
for u, daily in [('user_06', 11.9383), ('user_11', 309144.41), ('user_21', 17.2116), ('user_22', 5.866)]:
    uev = events[(events['user_id'] == u) & (events['status'] == 'settled') & (events['direction'] == 'debit')].copy()
    uev['amount'] = uev['amount'].astype(float)
    print(f"\n=== {u} (target daily: {daily:.4f}) ===")
    print(f"Target 30d: {daily * 30:.2f}, Target 60d: {daily * 60:.2f}, Target 90d: {daily * 90:.2f}")
    # group by category
    by_cat = uev.groupby('category')['amount'].sum()
    print("All debits by category sum:")
    for cat, val in by_cat.items():
        print(f"  {cat}: {val:.2f} (val/30={val/30:.2f}, val/60={val/60:.2f}, val/90={val/90:.2f}, val/180={val/180:.2f})")
