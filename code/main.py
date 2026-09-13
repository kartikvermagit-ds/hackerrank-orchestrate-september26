"""
HackerRank Orchestrate (September 2026) — Buy or Wait?
======================================================
Complete End-to-End Pipeline Execution

Executes the complete 13-stage deterministic financial reasoning pipeline:
 1. Load datasets (requests, profiles, events, options, exchange rates, messages, images)
 2. Normalize financial events (multi-currency, lifecycle resolution, standard classifications)
 3. Build user/request context (pair profile, options, normalized events, evidence)
 4. Resolve messages and images when necessary (untrusted data parsing)
 5. Convert foreign currencies using only dataset/exchange_rates.csv
 6. Build 90-day financial state (starting liquid balance, recurring expenses, salary projection)
 7. Calculate amount_safe_to_pay on request_date
 8. Calculate earliest_date_for_full_payment within the 90-day forecast horizon
 9. Generate candidate plans (full payment, partial payment, provider installments, wait, spending changes)
10. Rank candidates according to 6-stage tie-breaker hierarchy
11. Validate final decision with strict deterministic OutputValidator
12. Generate grounded, concise decision_explanation
13. Write root-level output.csv with exact required columns and row count
"""

import os
import sys
import argparse
from typing import Optional
import pandas as pd

from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine
from validator import OutputValidator, DecisionValidationError

REQUIRED_COLUMNS = [
    'request_id',
    'amount_safe_to_pay',
    'affordability_status',
    'recommended_payment_method',
    'payment_plan',
    'earliest_date_for_full_payment',
    'spending_changes_needed',
    'decision_explanation'
]

def run_pipeline(dataset_dir: Optional[str] = None,
                 requests_file: str = 'requests.csv',
                 output_file: Optional[str] = None) -> pd.DataFrame:
    """
    Run the complete Buy or Wait financial decision pipeline.

    Args:
        dataset_dir: Path to dataset directory containing CSV files.
        requests_file: Filename of requests CSV to evaluate (e.g. 'requests.csv' or 'sample_requests.csv').
        output_file: Target path for the generated output CSV.
    """
    # Resolve repository root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if dataset_dir is None:
        dataset_dir = os.path.join(repo_root, 'dataset')
    elif not os.path.isabs(dataset_dir):
        dataset_dir = os.path.abspath(dataset_dir)

    if output_file is None:
        output_file = os.path.join(repo_root, 'output.csv')
    elif not os.path.isabs(output_file):
        output_file = os.path.abspath(output_file)

    print(f"=== Starting Buy or Wait Financial Decision Pipeline ===", flush=True)
    print(f"Dataset directory: {dataset_dir}", flush=True)
    print(f"Requests input:    {requests_file}", flush=True)
    print(f"Target output:     {output_file}", flush=True)

    # ---------------------------------------------------------
    # Stage 1: Load datasets
    # ---------------------------------------------------------
    print("\n[Stage 1] Loading datasets from dataset/...", flush=True)
    loader = DataLoader(dataset_dir)
    currency_conv = loader.load_exchange_rates()  # Stage 5 converter
    img_proc = loader.load_images()               # Stage 4 image evidence
    profiles = loader.load_profiles()
    events_by_user = loader.load_events()
    payment_options = loader.load_payment_options()
    messages = loader.load_messages()             # Stage 4 message evidence
    requests = loader.load_requests(requests_file)
    print(f"Loaded {len(requests)} evaluation requests to process.", flush=True)

    # ---------------------------------------------------------
    # Stage 2, 4, 5: Evidence resolution, event normalizer, currency converter
    # ---------------------------------------------------------
    print("[Stage 2, 4, 5] Initializing untrusted evidence processor and multi-currency event normalizer...", flush=True)
    msg_proc = MessageProcessor(messages)
    normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)

    # ---------------------------------------------------------
    # Stage 3, 6: User context and 90-day financial state builder
    # ---------------------------------------------------------
    print("[Stage 3, 6] Initializing user context builder and 90-day financial state reconstructor...", flush=True)
    context_builder = ContextBuilder(
        profiles=profiles,
        events_by_user=events_by_user,
        payment_options_by_req=payment_options,
        event_normalizer=normalizer
    )

    # ---------------------------------------------------------
    # Stage 7, 8, 9, 10, 12: Financial engines, planners, and decision engine
    # ---------------------------------------------------------
    print("[Stage 7, 8, 9, 10, 12] Initializing forecast, safe amount, payment planner, and decision engine...", flush=True)
    forecaster = ForecastEngine()
    safe_calc = SafeAmountCalculator(forecaster)
    planner = PaymentPlanner(forecaster)
    decision_engine = DecisionEngine(
        forecast_engine=forecaster,
        safe_calc=safe_calc,
        planner=planner
    )

    # ---------------------------------------------------------
    # Process each request sequentially
    # ---------------------------------------------------------
    print(f"\nProcessing {len(requests)} requests...", flush=True)
    output_rows = []

    for idx, req in enumerate(requests):
        # Stage 3 & 6: Reconstruct user state and options
        state, options = context_builder.build_context(req)

        # Stage 7, 8, 9, 10, 12: Decide optimal financial plan and generate explanation
        rec = decision_engine.decide(req, state, options)

        # ---------------------------------------------------------
        # Stage 11: Strict deterministic validation
        # ---------------------------------------------------------
        errors = OutputValidator.validate_decision(
            rec=rec,
            request=req,
            state=state,
            options=options,
            forecaster=forecaster,
            raise_exception=False
        )
        if errors:
            err_msg = (
                f"Strict validation rejected decision for request '{req.request_id}':\n" +
                "\n".join(f"  - {e}" for e in errors)
            )
            print(f"ERROR: {err_msg}", file=sys.stderr, flush=True)
            raise DecisionValidationError(err_msg)

        # Append row with exact required columns
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
            print(f"  -> Processed and validated {idx + 1}/{len(requests)} requests...", flush=True)

    # ---------------------------------------------------------
    # Stage 13: Final Validation Checks & Output Generation
    # ---------------------------------------------------------
    print("\n[Stage 13] Running comprehensive pre-flight verification on generated predictions...", flush=True)
    out_df = pd.DataFrame(output_rows)[REQUIRED_COLUMNS]

    # 1. Confirm exactly expected number of predictions
    assert len(out_df) == len(requests), f"Expected {len(requests)} predictions, got {len(out_df)}"
    print(f"  [x] Confirmed exactly {len(out_df)} predictions generated.", flush=True)

    # 2. Confirm every request_id is present exactly once and matches input
    input_ids = [r.request_id for r in requests]
    pred_ids = out_df['request_id'].tolist()
    assert pred_ids == input_ids, "Prediction request_ids do not exactly match input requests in order!"
    assert len(set(pred_ids)) == len(requests), "Duplicate request_id detected in predictions!"
    print(f"  [x] Confirmed all {len(requests)} unique request_ids present exactly once in exact input sequence.", flush=True)

    # 3. Validate DataFrame schema and bounds via OutputValidator
    df_errors = OutputValidator.validate_dataframe(out_df, expected_rows=len(requests))
    if df_errors:
        err_msg = f"Final output DataFrame validation failed:\n" + "\n".join(f"  - {e}" for e in df_errors)
        print(f"ERROR: {err_msg}", file=sys.stderr, flush=True)
        raise DecisionValidationError(err_msg)
    print("  [x] Validated DataFrame schema, column sequence, and null-safety across all 8 required columns.", flush=True)
    print("  [x] Validated numeric bounds: 0 <= amount_safe_to_pay <= requested_amount on all rows.", flush=True)
    print("  [x] Validated payment plans: chronological order, positive amounts, totals matching, deadline compliance.", flush=True)
    print("  [x] Validated spending changes: max 3 changes, mutual exclusivity, flexible non-protected categories.", flush=True)
    print("  [x] Validated installment options: exact matching with request_payment_options.csv & tenure limits.", flush=True)
    print("  [x] Validated all calendar dates: ISO-8601 formatting, 90-day window, affordable_now consistency.", flush=True)
    print("  [x] Re-simulated deterministic safety checker: verified balance >= minimum_balance_to_keep across all plans.", flush=True)

    # Write output CSV
    out_df.to_csv(output_file, index=False)
    print(f"\nSuccessfully validated and generated root-level output file:\n  -> {output_file} ({len(out_df)} rows)", flush=True)

    return out_df

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Buy or Wait? AI Financial Decision Agent")
    parser.add_argument('--dataset-dir', default=None, help="Path to dataset directory (defaults to dataset/)")
    parser.add_argument('--requests-file', default='requests.csv', help="Filename of requests CSV to evaluate")
    parser.add_argument('--output-file', default=None, help="Path to write output.csv (defaults to root output.csv)")
    args = parser.parse_args()

    run_pipeline(
        dataset_dir=args.dataset_dir,
        requests_file=args.requests_file,
        output_file=args.output_file
    )
