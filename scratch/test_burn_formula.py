import os, sys, pandas as pd
sys.path.insert(0, 'code')
from loader import DataLoader
from context_builder import ContextBuilder
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

l = DataLoader('dataset')
l.load_images()
p = l.load_profiles()
e = l.load_events()
o = l.load_payment_options()
m = l.load_messages()
r = l.load_requests('sample_requests.csv')
gt_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

# Test different combinations of LIVING_EXPENSE_CATEGORIES or burn multipliers
for cats in [
    {'groceries', 'transport'},
    {'groceries', 'transport', 'dining'}
]:
    for mult in [1.0, 1.1, 1.15, 1.2]:
        msg_proc = MessageProcessor(m)
        norm = EventNormalizer(l.load_exchange_rates(), msg_proc)
        norm.LIVING_EXPENSE_CATEGORIES = set(cats)
        
        orig_burn = norm.calculate_variable_daily_burn
        def make_burn(multiplier):
            def calc(events, req_date, rec_cats=None):
                req_dt = pd.to_datetime(req_date)
                start_dt = req_dt - pd.Timedelta(days=60)
                var_debits = []
                for ev in events:
                    if (ev.status == 'settled' and ev.direction == 'debit' and 
                        ev.category in norm.LIVING_EXPENSE_CATEGORIES and 
                        start_dt <= pd.to_datetime(ev.event_date) < req_dt):
                        desc_lower = ev.description.lower()
                        if 'bulk' in desc_lower and ('purchase' in desc_lower or 'pantry' in desc_lower):
                            continue
                        var_debits.append(ev.amount)
                if not var_debits:
                    return 0.0
                return (sum(var_debits) / 60.0) * multiplier
            return calc
        norm.calculate_variable_daily_burn = make_burn(mult)
        
        cb = ContextBuilder(p, e, o, norm)
        fc = ForecastEngine()
        sc = SafeAmountCalculator(fc)
        pl = PaymentPlanner(fc)
        eng = DecisionEngine(fc, sc, pl)
        
        match_count = 0
        method_count = 0
        status_count = 0
        plan_count = 0
        date_count = 0
        chg_count = 0
        
        for req in r:
            gt = gt_df.loc[req.request_id]
            st, opts = cb.build_context(req)
            rec = eng.decide(req, st, opts)
            
            gt_m = str(gt['recommended_payment_method']).strip()
            pr_m = str(rec.recommended_payment_method).strip()
            if gt_m == pr_m: method_count += 1
            
            gt_s = str(gt['affordability_status']).strip()
            pr_s = str(rec.affordability_status).strip()
            if gt_s == pr_s: status_count += 1
            
            gt_p = str(gt['payment_plan']).strip()
            pr_p = str(rec.payment_plan).strip()
            if gt_p == pr_p: plan_count += 1
            
            gt_d = str(gt['earliest_date_for_full_payment']).strip() if pd.notna(gt['earliest_date_for_full_payment']) else ""
            pr_d = str(rec.earliest_date_for_full_payment).strip() if rec.earliest_date_for_full_payment else ""
            if gt_d == pr_d: date_count += 1
            
            gt_c = str(gt['spending_changes_needed']).strip()
            pr_c = str(rec.spending_changes_needed).strip()
            if gt_c == pr_c: chg_count += 1
            
            gt_safe = float(gt['amount_safe_to_pay'])
            pr_safe = float(rec.amount_safe_to_pay)
            if abs(gt_safe - pr_safe) <= 1.0 and gt_m == pr_m and gt_s == pr_s and gt_p == pr_p and gt_d == pr_d and gt_c == pr_c:
                match_count += 1
                
        print(f"Cats={sorted(list(cats))} Mult={mult:.2f} -> Method={method_count}/25 Status={status_count}/25 Plan={plan_count}/25 Date={date_count}/25 Chg={chg_count}/25 Exact={match_count}/25")
