import os
import sys
import argparse
import pandas as pd

from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine
from validator import OutputValidator

def run_pipeline(dataset_dir: str = 'dataset',
                 requests_file: str = 'requests.csv',
                 output_file: str = 'output.csv'):
    print(f"Starting Buy or Wait pipeline...")
    print(f"Dataset dir: {dataset_dir} | Requests: {requests_file} | Output: {output_file}")

    # 1. Initialize data loaders and processors
    loader = DataLoader(dataset_dir)
    currency_conv = loader.load_exchange_rates()
    img_proc = loader.load_images()
    profiles = loader.load_profiles()
    events_by_user = loader.load_events()
    payment_options = loader.load_payment_options()
    messages = loader.load_messages()
    requests = loader.load_requests(requests_file)

    msg_proc = MessageProcessor(messages)
    normalizer = EventNormalizer(currency_conv, msg_proc)
    context_builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)

    # 2. Initialize financial engines
    forecaster = ForecastEngine()
    safe_calc = SafeAmountCalculator(forecaster)
    planner = PaymentPlanner(forecaster)
    decision_engine = DecisionEngine(forecaster, safe_calc, planner)

    # 3. Process requests
    output_rows = []
    validation_errors = []

    for idx, req in enumerate(requests):
        state, options = context_builder.build_context(req)
        rec = decision_engine.decide(req, state, options)
        
        # Validate row
        errors = OutputValidator.validate_row(rec, req)
        if errors:
            validation_errors.extend([f"Req {req.request_id}: {e}" for e in errors])

        output_rows.append({
            'request_id': rec.request_id,
            'amount_safe_to_pay': rec.amount_safe_to_pay,
            'affordability_status': rec.affordability_status,
            'recommended_payment_method': rec.recommended_payment_method,
            'payment_plan': rec.payment_plan,
            'earliest_date_for_full_payment': rec.earliest_date_for_full_payment,
            'spending_changes_needed': rec.spending_changes_needed,
            'decision_explanation': rec.decision_explanation
        })

        if (idx + 1) % 50 == 0 or (idx + 1) == len(requests):
            print(f"Processed {idx + 1}/{len(requests)} requests...")

    if validation_errors:
        print(f"WARNING: Encountered {len(validation_errors)} validation errors:")
        for err in validation_errors[:10]:
            print("  -", err)

    # 4. Save results to DataFrame and CSV
    out_df = pd.DataFrame(output_rows)
    
    # Save to requested output file
    out_df.to_csv(output_file, index=False)
    print(f"Successfully wrote {len(out_df)} predictions to {output_file}")

    return out_df

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Buy or Wait Financial Decision Agent")
    parser.add_argument('--dataset-dir', default='dataset', help="Path to dataset directory")
    parser.add_argument('--requests-file', default='requests.csv', help="Name of requests file to evaluate")
    parser.add_argument('--output-file', default='output.csv', help="Path to output CSV file")
    args = parser.parse_args()

    run_pipeline(args.dataset_dir, args.requests_file, args.output_file)
